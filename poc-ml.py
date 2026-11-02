"""POC independente de scraping para uma busca do Mercado Livre."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

URL = (
    "https://lista.mercadolivre.com.br/"
    "roma%3A-a-hist%C3%B3ria-de-um-imp%C3%A9rio-%E2%80%94-greg-woolf"
)
TIMEOUT_MS = 20_000
ESPERA_APOS_CARREGAR_MS = 7_000


def extrair_preco(elemento):
    fracao = elemento.select_one(".andes-money-amount__fraction")
    if fracao:
        valor = fracao.get_text(strip=True)
        centavos = elemento.select_one(".andes-money-amount__cents")
        if centavos:
            valor += "," + centavos.get_text(strip=True)
    else:
        valor = elemento.get("aria-label") or elemento.get_text(" ", strip=True)

    numeros = re.sub(r"[^\d,.]", "", valor or "")
    if "," in numeros:
        numeros = numeros.replace(".", "").replace(",", ".")
    else:
        numeros = numeros.replace(".", "")
    try:
        preco = float(numeros)
    except ValueError:
        return None
    return preco if preco > 0 else None


def extrair_anuncios(html):
    sopa = BeautifulSoup(html, "html.parser")
    cards = sopa.select(".poly-card, .ui-search-result")
    if not cards:
        cards = sopa.select("li.ui-search-layout__item")

    anuncios = []
    for card in cards:
        titulo_elemento = card.select_one(
            "h2, .poly-component__title, .ui-search-item__title"
        )
        if not titulo_elemento:
            continue
        titulo = titulo_elemento.get_text(" ", strip=True)
        preco_elemento = card.select_one(
            ".poly-component__price .andes-money-amount, "
            ".ui-search-price__part"
        )
        if not preco_elemento:
            continue
        preco = extrair_preco(preco_elemento)
        if preco is None:
            continue

        link_elemento = card.select_one(
            "a.poly-component__title, a.ui-search-link, a[href]"
        )
        href = link_elemento.get("href") if link_elemento else None
        anuncios.append(
            {
                "titulo": titulo,
                "preco": preco,
                "url": urljoin(URL, href) if href else URL,
            }
        )
    return anuncios


def exibir_resultado(page) -> None:
    anuncios = extrair_anuncios(page.content())
    if not anuncios:
        print("Nenhum anúncio com título e preço foi encontrado no HTML")
        return

    escolhido = min(anuncios, key=lambda item: item["preco"])
    print(f"Anúncios encontrados: {len(anuncios)}")
    print(f"Menor preço: R$ {escolhido['preco']:.2f}")
    for item in anuncios:
        marcador = " (menor preço)" if item is escolhido else ""
        print(f"- R$ {item['preco']:.2f}: {item['titulo']}{marcador}")
        print(f"  {item['url']}")


def main() -> None:
    print(f"URL: {URL}")
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=True)
        contexto = browser.new_context(
            locale="pt-BR",
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
        )
        page = contexto.new_page()
        page.set_default_navigation_timeout(TIMEOUT_MS)

        try:
            resposta = page.goto(URL, wait_until="domcontentloaded")
            if resposta and resposta.status >= 400:
                raise RuntimeError(f"Mercado Livre respondeu HTTP {resposta.status}")
            page.wait_for_timeout(ESPERA_APOS_CARREGAR_MS)
            print(f"User-Agent: {page.evaluate('navigator.userAgent')}")
            exibir_resultado(page)
        except (PlaywrightError, RuntimeError) as exc:
            print(f"Falha: {type(exc).__name__}: {exc}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
