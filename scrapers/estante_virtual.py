"""Coleta preços da Estante Virtual em páginas de busca e de livros."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests

from config import BLACKLIST_BOOKS, LinkConfig, Plataforma
from scrapers.protocol import ResultadoColeta


class ColetorEstanteVirtual:
    """Lê os cards de busca ou as ofertas de uma página direta de livro."""

    def __init__(self, timeout: float = 20) -> None:
        self.timeout = timeout

    def coletar(self, link: LinkConfig) -> ResultadoColeta:
        if link.plataforma is not Plataforma.ESTANTE_VIRTUAL:
            return ResultadoColeta(
                plataforma=link.plataforma.value,
                url=link.url,
                status="erro",
                erro="ColetorEstanteVirtual aceita somente links da Estante Virtual",
            )

        try:
            response = requests.get(
                link.url,
                impersonate="chrome",
                timeout=self.timeout,
                headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            if link.pesquisa:
                return self._coletar_busca(link, soup)
            return self._coletar_pagina_direta(link, soup)
        except requests.exceptions.RequestException as exc:
            return self._erro(link, f"Falha HTTP na Estante Virtual: {exc}")
        except Exception as exc:
            return self._erro(link, f"{type(exc).__name__}: {exc}")

    def _coletar_busca(self, link: LinkConfig, soup: BeautifulSoup) -> ResultadoColeta:
        candidatos: List[Dict[str, Any]] = []

        for card in soup.select("div.product-item.product-list__item"):
            titulo = self._texto(card.select_one(".product-item__title"))
            if not titulo or self._esta_na_blacklist(titulo):
                continue

            preco_sem_frete = self._preco(
                self._texto(card.select_one(".product-item__sale-price"))
            )
            if preco_sem_frete is None:
                continue

            anuncio = card.select_one("a.product-item__link")
            if anuncio is None:
                anuncio = card.select_one("a[href]")
            url_anuncio = (
                urljoin(link.url, anuncio.get("href"))
                if anuncio and anuncio.get("href")
                else link.url
            )
            candidato = self._candidato(
                titulo=titulo,
                autor=self._texto(card.select_one(".product-item__author")),
                preco_sem_frete=preco_sem_frete,
                texto_frete=card.get_text(" ", strip=True),
                url=url_anuncio,
            )
            candidatos.append(candidato)
            if len(candidatos) >= link.top_n:
                break

        return self._resultado(link, soup, candidatos)

    def _coletar_pagina_direta(
        self, link: LinkConfig, soup: BeautifulSoup
    ) -> ResultadoColeta:
        titulo = self._texto(soup.select_one(".product-details__header--title"))
        if not titulo:
            return self._erro(link, "Título do livro não encontrado na página")
        autor = self._texto(soup.select_one(".product-details__header--author"))
        candidatos: List[Dict[str, Any]] = []

        elementos_preco = soup.select(".book-copy__price__sale-price")
        for elemento_preco in elementos_preco:
            contexto_oferta = " ".join(
                pai.get_text(" ", strip=True)
                for pai in list(elemento_preco.parents)[:4]
                if isinstance(pai, Tag)
            )
            preco_sem_frete = self._preco(self._texto(elemento_preco))
            if preco_sem_frete is None:
                continue
            candidatos.append(
                self._candidato(
                    titulo=titulo,
                    autor=autor,
                    preco_sem_frete=preco_sem_frete,
                    texto_frete=contexto_oferta,
                    url=link.url,
                )
            )

        if not candidatos:
            return self._erro(link, "Nenhuma oferta com preço encontrada na página")
        return self._resultado(
            link,
            soup,
            candidatos,
            titulo=titulo,
        )

    def _resultado(
        self,
        link: LinkConfig,
        soup: BeautifulSoup,
        candidatos: List[Dict[str, Any]],
        titulo: Optional[str] = None,
    ) -> ResultadoColeta:
        if not candidatos:
            titulo_busca = titulo or self._texto(soup.select_one("h1"))
            return self._erro(
                link,
                "Nenhuma oferta válida encontrada após aplicar BLACKLIST_BOOKS",
                titulo=titulo_busca,
            )

        escolhido = min(candidatos, key=lambda item: item["preco_total"])
        for candidato in candidatos:
            candidato["escolhido"] = candidato is escolhido

        capa = self._capa(soup)
        return ResultadoColeta(
            plataforma=Plataforma.ESTANTE_VIRTUAL.value,
            url=link.url,
            status="sucesso",
            preco=escolhido["preco_total"],
            titulo=titulo or escolhido["titulo"],
            capa_url=capa,
            extras={
                "valor_sem_frete": escolhido["valor_sem_frete"],
                "frete_aplicado": escolhido["frete_aplicado"],
                "frete_presumido": escolhido["frete_presumido"],
            },
            top_n_resultados=candidatos if link.pesquisa else None,
        )

    @staticmethod
    def _candidato(
        titulo: str,
        autor: Optional[str],
        preco_sem_frete: float,
        texto_frete: str,
        url: str,
    ) -> Dict[str, Any]:
        frete_gratis = ColetorEstanteVirtual._frete_gratis(texto_frete)
        frete = 0.0 if frete_gratis else 16.0
        return {
            "titulo": titulo,
            "autor": autor,
            "valor_sem_frete": preco_sem_frete,
            "preco_total": round(preco_sem_frete + frete, 2),
            "frete_aplicado": frete,
            "frete_presumido": not frete_gratis,
            "escolhido": False,
            "url": url,
        }

    @staticmethod
    def _frete_gratis(texto: str) -> bool:
        texto = texto.lower()
        return "frete grátis" in texto or "frete gratis" in texto

    @staticmethod
    def _esta_na_blacklist(titulo: str) -> bool:
        titulo = titulo.lower()
        return any(
            item and item.lower() in titulo
            for item in BLACKLIST_BOOKS
        )

    @staticmethod
    def _capa(soup: BeautifulSoup) -> Optional[str]:
        imagem = soup.select_one(".book-cover img, meta[property='og:image']")
        if imagem is None:
            return None
        return imagem.get("content") or imagem.get("src") or imagem.get("data-src")

    @staticmethod
    def _texto(elemento: Optional[Tag]) -> Optional[str]:
        if elemento is None:
            return None
        texto = elemento.get_text(" ", strip=True)
        return texto or None

    @staticmethod
    def _preco(valor: Optional[str]) -> Optional[float]:
        if not valor:
            return None
        numeros = re.sub(r"[^\d,.]", "", valor)
        if "," in numeros:
            numeros = numeros.replace(".", "").replace(",", ".")
        try:
            preco = float(numeros)
        except ValueError:
            return None
        return preco if preco > 0 else None

    @staticmethod
    def _erro(
        link: LinkConfig, erro: str, titulo: Optional[str] = None
    ) -> ResultadoColeta:
        return ResultadoColeta(
            plataforma=Plataforma.ESTANTE_VIRTUAL.value,
            url=link.url,
            status="erro",
            titulo=titulo,
            erro=erro,
        )
