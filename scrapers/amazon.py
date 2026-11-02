"""Coleta preço e metadados de uma página de produto da Amazon Brasil."""

import json
import random
import re
import time
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests

from config import LinkConfig, Plataforma
from scrapers.protocol import ResultadoColeta


class ColetorAmazon:
    """Coletor compatível com o contrato comum das plataformas."""

    _PERFIS_NAVEGADOR = ("chrome", "firefox", "safari")

    _PRECO_SELETORES = (
        "#corePrice_feature_div .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#apex_desktop .a-offscreen",
        "#buybox .a-offscreen",
        ".reinventPricePriceToPayMargin .a-offscreen",
        "#price_inside_buybox",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
    )
    _PRECO_CONTAINERS = (
        "#corePrice_feature_div",
        "#corePriceDisplay_desktop_feature_div",
        "#apex_desktop",
        "#buybox",
    )

    def __init__(
        self,
        timeout: float = 20,
        max_retries: int = 3,
        retry_delay_base: float = 5,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries não pode ser negativo")
        if retry_delay_base < 0:
            raise ValueError("retry_delay_base não pode ser negativo")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self._ultimo_perfil: Optional[str] = None

    def coletar(self, link: LinkConfig) -> ResultadoColeta:
        if link.plataforma is not Plataforma.AMAZON:
            return ResultadoColeta(
                plataforma=link.plataforma.value,
                url=link.url,
                status="erro",
                erro="ColetorAmazon aceita somente links da Amazon",
            )

        for tentativa in range(self.max_retries + 1):
            perfil = self._proximo_perfil()
            print(f"  Perfil de navegador desta requisição: {perfil}")
            resultado, pode_repetir = self._coletar_uma_vez(link, perfil)
            if resultado.status == "sucesso" or not pode_repetir:
                return resultado
            if tentativa == self.max_retries:
                return resultado

            atraso_base = self.retry_delay_base * (tentativa + 1)
            atraso = random.uniform(atraso_base * 0.8, atraso_base * 1.2)
            print(
                f"  Falha na Amazon ({resultado.erro}); nova tentativa "
                f"{tentativa + 1}/{self.max_retries} em {atraso:.1f}s."
            )
            time.sleep(atraso)

        raise RuntimeError("Fluxo de retry terminou sem resultado")

    def _coletar_uma_vez(
        self, link: LinkConfig, perfil: str
    ) -> tuple[ResultadoColeta, bool]:
        try:
            response = requests.get(
                link.url,
                impersonate=perfil,
                timeout=self.timeout,
                headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            if self._pagina_de_verificacao(soup):
                return (
                    ResultadoColeta(
                        plataforma=Plataforma.AMAZON.value,
                        url=link.url,
                        status="erro",
                        erro="Amazon retornou uma página de verificação anti-bot (CAPTCHA/Robot Check)",
                    ),
                    True,
                )

            titulo = self._texto(soup.select_one("#productTitle"))
            capa = self._capa(soup)
            preco = self._preco(soup)

            if preco is None:
                return (
                    ResultadoColeta(
                        plataforma=Plataforma.AMAZON.value,
                        url=link.url,
                        status="erro",
                        titulo=titulo,
                        capa_url=capa,
                        erro=self._erro_sem_preco(titulo),
                    ),
                    True,
                )

            return (
                ResultadoColeta(
                    plataforma=Plataforma.AMAZON.value,
                    url=link.url,
                    status="sucesso",
                    preco=preco,
                    titulo=titulo,
                    capa_url=capa,
                ),
                False,
            )
        except requests.exceptions.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            resposta = getattr(exc, "response", None)
            captcha_http_403 = (
                status_code == 403
                and resposta is not None
                and self._pagina_de_verificacao(
                    BeautifulSoup(resposta.text, "html.parser")
                )
            )
            temporario = (
                status_code is None
                or status_code in (408, 429)
                or status_code >= 500
                or captcha_http_403
            )
            return (
                ResultadoColeta(
                    plataforma=Plataforma.AMAZON.value,
                    url=link.url,
                    status="erro",
                    erro=f"{type(exc).__name__}: {exc}",
                ),
                temporario,
            )
        except Exception as exc:
            return (
                ResultadoColeta(
                    plataforma=Plataforma.AMAZON.value,
                    url=link.url,
                    status="erro",
                    erro=f"{type(exc).__name__}: {exc}",
                ),
                False,
            )

    def _proximo_perfil(self) -> str:
        disponiveis = [
            perfil
            for perfil in self._PERFIS_NAVEGADOR
            if perfil != self._ultimo_perfil
        ]
        self._ultimo_perfil = random.choice(disponiveis)
        return self._ultimo_perfil

    @classmethod
    def _preco(cls, soup: BeautifulSoup) -> Optional[float]:
        for seletor in cls._PRECO_SELETORES:
            elemento = soup.select_one(seletor)
            valor = cls._valor_preco(cls._texto(elemento))
            if valor is not None:
                return valor

        for seletor in cls._PRECO_CONTAINERS:
            container = soup.select_one(seletor)
            if container is None:
                continue
            preco_atual = container.select_one(".a-price:not(.a-text-price)")
            if preco_atual is None:
                continue
            valor = cls._valor_preco(preco_atual.get("data-a-price"))
            if valor is not None:
                return valor

            inteiro = cls._texto(preco_atual.select_one(".a-price-whole"))
            centavos = cls._texto(preco_atual.select_one(".a-price-fraction"))
            if inteiro:
                inteiro = re.sub(r"\D", "", inteiro)
                texto_preco = f"{inteiro},{centavos}" if centavos else inteiro
                valor = cls._valor_preco(texto_preco)
                if valor is not None:
                    return valor

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                dados = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            for item in cls._percorrer_json(dados):
                tipos = item.get("@type", [])
                if isinstance(tipos, str):
                    tipos = [tipos]
                if "Offer" in tipos or "AggregateOffer" in tipos:
                    valor = cls._valor_preco(
                        item.get("price") or item.get("lowPrice")
                    )
                    if valor is not None:
                        return valor
                    especificacao = item.get("priceSpecification")
                    if isinstance(especificacao, dict):
                        valor = cls._valor_preco(especificacao.get("price"))
                        if valor is not None:
                            return valor
        return None

    @staticmethod
    def _pagina_de_verificacao(soup: BeautifulSoup) -> bool:
        acao_captcha = soup.find(
            "form", action=re.compile(r"validateCaptcha|captcha", re.IGNORECASE)
        )
        if acao_captcha or soup.select_one("#captchacharacters"):
            return True

        conteudo = soup.get_text(" ", strip=True).lower()
        marcadores = (
            "robot check",
            "enter the characters you see below",
            "digite os caracteres que você vê",
            "validatecaptcha",
        )
        return any(marcador in conteudo for marcador in marcadores)

    @staticmethod
    def _erro_sem_preco(titulo: Optional[str]) -> str:
        if titulo is None:
            return (
                "Página sem título do produto nem preço; a Amazon pode ter retornado "
                "um intersticial ou HTML alternativo"
            )
        return "Preço não encontrado na página do produto"

    @staticmethod
    def _valor_preco(valor: Any) -> Optional[float]:
        if valor is None:
            return None
        texto = str(valor).strip()
        numeros = re.sub(r"[^\d,.]", "", texto)
        if not numeros:
            return None
        # Na formatação brasileira, o ponto separa milhares e a vírgula os centavos.
        if "," in numeros:
            numeros = numeros.replace(".", "").replace(",", ".")
        try:
            preco = float(numeros)
        except ValueError:
            return None
        return preco if preco > 0 else None

    @staticmethod
    def _texto(elemento: Any) -> Optional[str]:
        if elemento is None:
            return None
        texto = elemento.get_text(" ", strip=True)
        return texto or None

    @staticmethod
    def _capa(soup: BeautifulSoup) -> Optional[str]:
        imagem = soup.select_one("#landingImage, #imgBlkFront, #main-image")
        if imagem is None:
            return None
        return imagem.get("data-old-hires") or imagem.get("src")

    @classmethod
    def _percorrer_json(cls, dados: Any) -> Iterable[dict[str, Any]]:
        if isinstance(dados, dict):
            yield dados
            for chave in ("@graph", "offers"):
                if chave in dados:
                    yield from cls._percorrer_json(dados[chave])
        elif isinstance(dados, list):
            for item in dados:
                yield from cls._percorrer_json(item)
