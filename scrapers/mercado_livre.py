"""Coleta preços de anúncios do Mercado Livre com Firefox headless."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from config import BLACKLIST_BOOKS, LinkConfig, Plataforma
from scrapers.protocol import ResultadoColeta


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

        try:
            with sync_playwright() as playwright:
                browser = playwright.firefox.launch(headless=True)
                try:
                    contexto = browser.new_context(
                        locale="pt-BR",
                        extra_http_headers={
                            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
                        },
                    )
                    page = contexto.new_page()
                    page.set_default_navigation_timeout(self.timeout * 1000)
                    page.on("dialog", lambda dialog: dialog.dismiss())
                    response = page.goto(link.url, wait_until="domcontentloaded")
                    if response and response.status >= 400:
                        return self._erro(
                            link,
                            f"Falha HTTP no Mercado Livre: HTTP {response.status}",
                        )
                    page.wait_for_timeout(self.espera_apos_carregar * 1000)
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
        except PlaywrightError as exc:
            return self._erro(link, f"Falha no Playwright para Mercado Livre: {exc}")
        except Exception as exc:
            return self._erro(link, f"{type(exc).__name__}: {exc}")

    def _coletar_busca(self, link: LinkConfig, soup: BeautifulSoup) -> ResultadoColeta:
        candidatos: List[Dict[str, Any]] = []
        cards = soup.select(".poly-card, .ui-search-result")
        if not cards:
            cards = soup.select("li.ui-search-layout__item")
        for card in cards:
            titulo_elemento = card.select_one(
                "h2, .poly-component__title, .ui-search-item__title"
            )
            titulo = self._texto(titulo_elemento)
            if not titulo or self._esta_na_blacklist(titulo):
                continue
            preco = self._preco_card(card)
            if preco is None:
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
        return self._resultado(link, soup, candidatos)

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
        return any(
            marcador in html
            for marcador in (
                "micro-landing-container",
                "browser-assessment",
                "bot-interceptor-muralla",
            )
        )

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
