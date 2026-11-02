"""Coleta preços do Mercado Livre em desktop e, se necessário, em modo móvel."""

import os
import re
from dataclasses import replace
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import BLACKLIST_BOOKS, LinkConfig, Plataforma
from logging_utils import registrar_log
from scrapers.protocol import ResultadoColeta


DEBUG_MERCADO_LIVRE = False


class ColetorMercadoLivre:
    """Lê anúncios em páginas de busca ou páginas diretas de produto."""

    def __init__(
        self,
        timeout: float = 20,
        espera_apos_carregar: float = 7,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout deve ser maior que zero")
        if espera_apos_carregar < 0:
            raise ValueError("espera_apos_carregar não pode ser negativo")
        self.timeout = timeout
        self.espera_apos_carregar = espera_apos_carregar

    def coletar(self, link: LinkConfig) -> ResultadoColeta:
        if link.plataforma is not Plataforma.MERCADO_LIVRE:
            return self._erro(
                link, "ColetorMercadoLivre aceita somente links do Mercado Livre"
            )

        registrar_log("Iniciando tentativa desktop com Firefox.")
        resultado_desktop = self._coletar_tentativa(link, mobile=False)
        if resultado_desktop.status == "sucesso":
            return resultado_desktop

        registrar_log(
            f"Tentativa desktop falhou ({resultado_desktop.erro}); "
            "tentando uma vez no modo móvel com Chromium."
        )
        resultado_movel = self._coletar_tentativa(link, mobile=True)
        if resultado_movel.status == "sucesso":
            registrar_log("Coleta concluída no modo móvel.")
            return resultado_movel

        return replace(
            resultado_movel,
            erro=(
                f"Tentativa desktop: {resultado_desktop.erro or 'falha sem detalhes'}. "
                f"Tentativa móvel: {resultado_movel.erro or 'falha sem detalhes'}."
            ),
        )

    def _coletar_tentativa(
        self, link: LinkConfig, mobile: bool
    ) -> ResultadoColeta:
        nome_navegador = "Chromium móvel" if mobile else "Firefox desktop"
        fase = "iniciar o Firefox"
        if mobile:
            fase = "iniciar o Chromium móvel"
        try:
            with sync_playwright() as playwright:
                tipo_navegador = playwright.chromium if mobile else playwright.firefox
                debug_visivel = (
                    DEBUG_MERCADO_LIVRE
                    and os.getenv("GITHUB_ACTIONS", "").casefold() != "true"
                )
                browser = tipo_navegador.launch(headless=not debug_visivel)
                try:
                    opcoes_contexto = {}
                    if mobile:
                        opcoes_contexto.update(playwright.devices["Pixel 7"])
                    opcoes_contexto.update(
                        locale="pt-BR",
                        extra_http_headers={
                            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
                        },
                    )
                    contexto = browser.new_context(**opcoes_contexto)
                    page = contexto.new_page()
                    page.set_default_navigation_timeout(self.timeout * 1000)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    fase = "carregar a página"
                    response = page.goto(link.url, wait_until="domcontentloaded")
                    if response and response.status >= 400:
                        if response.status == 403:
                            mensagem_http = "Acesso bloqueado pelo Mercado Livre (HTTP 403)."
                        elif response.status == 429:
                            mensagem_http = "Mercado Livre limitou temporariamente o acesso (HTTP 429)."
                        else:
                            mensagem_http = f"Mercado Livre respondeu com HTTP {response.status}."
                        return self._erro(
                            link,
                            mensagem_http,
                        )
                    if link.pesquisa:
                        fase = "aguardar os resultados da busca"
                        soup = self._aguardar_busca(page)
                    else:
                        fase = "aguardar o resultado do produto"
                        page.wait_for_timeout(self.espera_apos_carregar * 1000)
                        fase = "ler o conteúdo da página"
                        soup = BeautifulSoup(page.content(), "html.parser")
                finally:
                    browser.close()

            if self._eh_desafio(soup):
                return self._erro(
                    link,
                    "Mercado Livre retornou uma tela de verificação JavaScript; "
                    "a página de resultados não foi carregada",
                )
            if link.pesquisa:
                return self._coletar_busca(link, soup)
            return self._coletar_pagina_direta(link, soup)
        except PlaywrightTimeoutError:
            return self._erro(
                link,
                f"Tempo esgotado ao {fase} no {nome_navegador} "
                f"(limite de {self.timeout:g}s).",
            )
        except PlaywrightError as exc:
            return self._erro(
                link,
                f"{nome_navegador}: {self._mensagem_playwright(exc, fase)}",
            )
        except Exception as exc:
            return self._erro(
                link,
                f"Erro inesperado no {nome_navegador} ao {fase}: "
                f"{type(exc).__name__}: {str(exc).splitlines()[0]}",
            )

    def _coletar_busca(self, link: LinkConfig, soup: BeautifulSoup) -> ResultadoColeta:
        candidatos: List[Dict[str, Any]] = []
        cards = self._cards_busca(soup)
        if not cards:
            return self._erro(
                link,
                "A busca carregou, mas nenhum card de anúncio foi encontrado. "
                "Os resultados podem estar vazios, bloqueados ou com o layout alterado.",
                titulo=self._texto(soup.select_one("h1")),
            )

        descartados_blacklist = 0
        sem_titulo = 0
        sem_preco = 0
        for card in cards:
            titulo_elemento = card.select_one(
                "h2, .poly-component__title, .ui-search-item__title"
            )
            titulo = self._texto(titulo_elemento)
            if not titulo:
                sem_titulo += 1
                continue
            if self._esta_na_blacklist(titulo):
                descartados_blacklist += 1
                continue
            preco = self._preco_card(card)
            if preco is None:
                sem_preco += 1
                continue
            anuncio = card.select_one("a.poly-component__title, a.ui-search-link, a[href]")
            url_anuncio = (
                urljoin(link.url, str(anuncio.get("href")))
                if anuncio and anuncio.get("href")
                else link.url
            )
            candidatos.append(self._candidato(titulo, preco, url_anuncio))
            if len(candidatos) >= link.top_n:
                break
        if not candidatos:
            if descartados_blacklist == len(cards):
                erro = (
                    f"Os {len(cards)} anúncios encontrados foram descartados pela blacklist."
                )
            elif sem_preco and not descartados_blacklist:
                erro = (
                    f"Encontrei {len(cards)} cards, mas não consegui ler o preço de nenhum. "
                    "O layout ou os seletores de preço podem ter mudado."
                )
            else:
                erro = (
                    "Nenhum anúncio com título e preço válidos. "
                    f"Cards: {len(cards)}; sem título: {sem_titulo}; "
                    f"sem preço: {sem_preco}; na blacklist: {descartados_blacklist}."
                )
            return self._erro(link, erro, titulo=self._texto(soup.select_one("h1")))
        return self._resultado(link, soup, candidatos)

    def _aguardar_busca(self, page) -> BeautifulSoup:
        soup = BeautifulSoup(page.content(), "html.parser")
        for verificacao in range(2):
            page.wait_for_timeout(5_000)
            soup = BeautifulSoup(page.content(), "html.parser")
            if self._eh_desafio(soup) or self._busca_pronta(soup):
                return soup
            if verificacao == 0:
                registrar_log(
                    "Busca ainda sem anúncios com título e preço após 5s; "
                    "aguardando mais 5s."
                )
        return soup

    @classmethod
    def _busca_pronta(cls, soup: BeautifulSoup) -> bool:
        return any(
            cls._texto(card.select_one("h2, .poly-component__title, .ui-search-item__title"))
            and cls._preco_card(card) is not None
            for card in cls._cards_busca(soup)
        )

    @staticmethod
    def _cards_busca(soup: BeautifulSoup) -> List[Tag]:
        cards = soup.select(".poly-card, .ui-search-result")
        return cards or soup.select("li.ui-search-layout__item")

    def _coletar_pagina_direta(
        self, link: LinkConfig, soup: BeautifulSoup
    ) -> ResultadoColeta:
        titulo = self._texto(soup.select_one("h1.ui-pdp-title, h1"))
        if not titulo:
            return self._erro(link, "Título do produto não encontrado na página")
        preco = self._preco_elemento(
            soup.select_one(".ui-pdp-price__second-line .andes-money-amount, .ui-pdp-price")
        )
        if preco is None:
            return self._erro(link, "Preço não encontrado na página", titulo=titulo)
        return self._resultado(
            link, soup, [self._candidato(titulo, preco, link.url)], titulo
        )

    def _resultado(
        self,
        link: LinkConfig,
        soup: BeautifulSoup,
        candidatos: List[Dict[str, Any]],
        titulo: Optional[str] = None,
    ) -> ResultadoColeta:
        if not candidatos:
            return self._erro(
                link,
                "Nenhum anúncio válido encontrado após aplicar BLACKLIST_BOOKS",
                titulo=titulo or self._texto(soup.select_one("h1")),
            )
        escolhido = min(candidatos, key=lambda item: item["preco_total"])
        for candidato in candidatos:
            candidato["escolhido"] = candidato is escolhido
        return ResultadoColeta(
            plataforma=Plataforma.MERCADO_LIVRE.value,
            url=link.url,
            status="sucesso",
            preco=escolhido["preco_total"],
            titulo=titulo or escolhido["titulo"],
            capa_url=self._capa(soup),
            extras={
                "valor_sem_frete": escolhido["valor_sem_frete"],
                "frete_aplicado": 0.0,
                "frete_presumido": True,
            },
            top_n_resultados=candidatos if link.pesquisa else None,
        )

    @staticmethod
    def _candidato(titulo: str, preco: float, url: str) -> Dict[str, Any]:
        return {
            "titulo": titulo,
            "valor_sem_frete": preco,
            "preco_total": preco,
            "frete_aplicado": 0.0,
            "frete_presumido": True,
            "escolhido": False,
            "url": url,
        }

    @classmethod
    def _preco_card(cls, card: Tag) -> Optional[float]:
        return cls._preco_elemento(
            card.select_one(".poly-component__price .andes-money-amount, .ui-search-price__part")
        )

    @staticmethod
    def _preco_elemento(elemento: Optional[Tag]) -> Optional[float]:
        if elemento is None:
            return None
        fracao = elemento.select_one(".andes-money-amount__fraction")
        if fracao is not None:
            valor = fracao.get_text("", strip=True)
            centavos = elemento.select_one(".andes-money-amount__cents")
            if centavos is not None:
                valor += "," + centavos.get_text("", strip=True)
            return ColetorMercadoLivre._preco(valor)
        acessivel = elemento.get("aria-label")
        if acessivel:
            preco = ColetorMercadoLivre._preco(str(acessivel))
            if preco is not None:
                return preco
        return ColetorMercadoLivre._preco(elemento.get_text(" ", strip=True))

    @staticmethod
    def _preco(valor: Optional[str]) -> Optional[float]:
        if not valor:
            return None
        numeros = re.sub(r"[^\d,.]", "", valor)
        if "," in numeros:
            numeros = numeros.replace(".", "").replace(",", ".")
        else:
            numeros = numeros.replace(".", "")
        try:
            preco = float(numeros)
        except ValueError:
            return None
        return preco if preco > 0 else None

    @staticmethod
    def _esta_na_blacklist(titulo: str) -> bool:
        titulo = titulo.lower()
        return any(item and item.lower() in titulo for item in BLACKLIST_BOOKS)

    @staticmethod
    def _eh_desafio(soup: BeautifulSoup) -> bool:
        html = str(soup).lower()
        texto = soup.get_text(" ", strip=True).lower()
        marcadores_html = (
            "micro-landing-container",
            "browser-assessment",
            "bot-interceptor-muralla",
        )
        marcadores_texto = (
            "verifique que você não é um robô",
            "verifique que voce nao e um robo",
            "confirme que você não é um robô",
            "captcha",
        )
        return any(marcador in html for marcador in marcadores_html) or any(
            marcador in texto for marcador in marcadores_texto
        )

    @staticmethod
    def _mensagem_playwright(erro: PlaywrightError, fase: str) -> str:
        detalhe = str(erro).splitlines()[0]
        texto = str(erro).casefold()
        if "executable doesn't exist" in texto or "executable does not exist" in texto:
            return (
                "O navegador solicitado do Playwright não está instalado. "
                "Instale com `python -m playwright install firefox chromium`."
            )
        if (
            "shared libraries" in texto
            or "error while loading shared library" in texto
            or "cannot open shared object file" in texto
        ):
            return (
                "O navegador não iniciou porque faltam bibliotecas do sistema. "
                "Instale com `python -m playwright install-deps firefox chromium`."
            )
        if "net::err_name_not_resolved" in texto:
            return "Falha de DNS ao acessar o Mercado Livre."
        if "net::err_connection_refused" in texto:
            return "Conexão recusada ao acessar o Mercado Livre."
        if "net::err_connection_reset" in texto:
            return "A conexão com o Mercado Livre foi interrompida."
        if "net::err_internet_disconnected" in texto:
            return "O runner está sem conexão com a internet."
        if "target page, context or browser has been closed" in texto:
            return "O Firefox fechou antes de concluir a coleta."
        return f"Falha do Playwright ao {fase}: {detalhe}"

    @staticmethod
    def _texto(elemento: Optional[Tag]) -> Optional[str]:
        if elemento is None:
            return None
        texto = elemento.get_text(" ", strip=True)
        return texto or None

    @staticmethod
    def _capa(soup: BeautifulSoup) -> Optional[str]:
        imagem = soup.select_one(
            "meta[property='og:image'], .ui-pdp-gallery img, .poly-card img"
        )
        if imagem is None:
            return None
        return imagem.get("content") or imagem.get("src") or imagem.get("data-src")

    @staticmethod
    def _erro(
        link: LinkConfig, erro: str, titulo: Optional[str] = None
    ) -> ResultadoColeta:
        return ResultadoColeta(
            plataforma=Plataforma.MERCADO_LIVRE.value,
            url=link.url,
            status="erro",
            titulo=titulo,
            erro=erro,
        )
