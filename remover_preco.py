"""Remove uma oferta incorreta do consolidado/histórico e inclui seu título na blacklist."""

import json
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

from config import ARQUIVO_BLACKLIST


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_CONSOLIDADO = BASE_DIR / "consolidado.json"
ARQUIVO_HISTORICO = BASE_DIR / "historico.json"


def ler_json(caminho: Path) -> Dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_json(caminho: Path, dados: Dict[str, Any]) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporario.replace(caminho)


def escolher(itens: List[Any], rotulo) -> int:
    for indice, item in enumerate(itens, 1):
        print(f"{indice}. {rotulo(item)}")
    while True:
        entrada = input("Selecione o número (ou 0 para cancelar): ").strip()
        if entrada == "0":
            return -1
        if entrada.isdigit() and 1 <= int(entrada) <= len(itens):
            return int(entrada) - 1
        print("Opção inválida.")


def remover_eventos(historico: Dict[str, Any], produto_id: str, url: str,
                    plataforma: str, preco: float | None) -> int:
    registro = historico.get(produto_id, {})
    removidos = 0

    def filtrar(eventos, corresponde):
        nonlocal removidos
        mantidos = [evento for evento in eventos if not corresponde(evento)]
        removidos += len(eventos) - len(mantidos)
        return mantidos

    por_link = registro.get("por_link", {})
    if url in por_link:
        por_link[url] = filtrar(
            por_link[url], lambda e: preco is None or float(e.get("preco", -1)) == preco
        )
    por_plataforma = registro.get("por_plataforma", {})
    if plataforma in por_plataforma:
        por_plataforma[plataforma] = filtrar(
            por_plataforma[plataforma],
            lambda e: e.get("url") == url and (preco is None or float(e.get("preco", -1)) == preco),
        )
    if isinstance(registro.get("vencedor_geral"), list):
        registro["vencedor_geral"] = filtrar(
            registro["vencedor_geral"],
            lambda e: e.get("url") == url and e.get("plataforma") == plataforma
            and (preco is None or float(e.get("preco", -1)) == preco),
        )
    return removidos


def adicionar_blacklist(titulo: str) -> None:
    linhas = ARQUIVO_BLACKLIST.read_text(encoding="utf-8").splitlines()
    existentes = {linha.strip().casefold() for linha in linhas if linha.strip() and not linha.lstrip().startswith("#")}
    if titulo.casefold() not in existentes:
        linhas.append(titulo)
        ARQUIVO_BLACKLIST.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")


def atualizar_metricas(produto: Dict[str, Any]) -> None:
    links = [l for l in produto.get("links", [])
             if l.get("status") == "sucesso" and l.get("preco_atual") is not None]
    precos = [float(l["preco_atual"]) for l in links]
    por_plataforma: Dict[str, List[float]] = {}
    for link in links:
        por_plataforma.setdefault(link["plataforma"], []).append(float(link["preco_atual"]))
    metricas = produto.setdefault("metricas_atuais", {})
    metricas["menor_preco_geral"] = min(precos) if precos else None
    metricas["plataforma_vencedora"] = (
        min(links, key=lambda l: float(l["preco_atual"]))["plataforma"] if links else None
    )
    metricas["media"] = round(sum(precos) / len(precos), 2) if precos else None
    metricas["mediana"] = round(median(precos), 2) if precos else None
    metricas["mediana_por_plataforma"] = {
        plataforma: round(median(valores), 2)
        for plataforma, valores in por_plataforma.items()
    }


def main() -> None:
    consolidado = ler_json(ARQUIVO_CONSOLIDADO)
    historico = ler_json(ARQUIVO_HISTORICO)
    produtos = consolidado.get("produtos", [])
    if not produtos:
        print("O consolidado não contém livros.")
        return
    ip = escolher(produtos, lambda p: f"{p.get('nome', '?')} [{p.get('id', '?')}]" )
    if ip < 0:
        return
    produto = produtos[ip]
    alvos = []
    for indice_link, link in enumerate(produto.get("links", [])):
        ofertas = link.get("top_n_resultados") or []
        if ofertas:
            for indice_oferta, oferta in enumerate(ofertas):
                preco = oferta.get("preco_total", oferta.get("preco"))
                alvos.append(("oferta", indice_link, indice_oferta,
                              f"{link.get('plataforma')} | R$ {preco} | {oferta.get('titulo', '?')} | {oferta.get('url', '')}"))
        else:
            alvos.append(("link", indice_link, None,
                          f"{link.get('plataforma')} | R$ {link.get('preco_atual')} | {link.get('titulo') or '(sem título)'} | {link.get('url', '')}"))
    if not alvos:
        print("Este livro não tem preços ou links no consolidado.")
        return
    print("\nPreços e ofertas encontrados:")
    indice_alvo = escolher(alvos, lambda alvo: alvo[3])
    if indice_alvo < 0:
        return
    tipo, indice_link, indice_oferta, _ = alvos[indice_alvo]
    link = produto["links"][indice_link]
    if tipo == "oferta":
        ofertas = link["top_n_resultados"]
        oferta = ofertas[indice_oferta]
        titulo = str(oferta.get("titulo", "")).strip()
        preco = float(oferta.get("preco_total", oferta.get("preco")))
        url_historico = link["url"]
        url_anuncio = oferta.get("url", "")
        pergunta = f"Remover a oferta '{titulo}' (R$ {preco:.2f}) e adicioná-la à blacklist? [s/N] "
    else:
        titulo = str(link.get("titulo") or "").strip()
        preco = link.get("preco_atual")
        url_historico = link["url"]
        url_anuncio = link["url"]
        pergunta = f"Remover o link '{titulo}' (R$ {preco}) e adicioná-lo à blacklist? [s/N] "
    confirmado = input(pergunta).strip().lower()
    if confirmado not in {"s", "sim"}:
        print("Cancelado.")
        return

    if tipo == "oferta":
        era_escolhida = bool(oferta.get("escolhido"))
        ofertas.pop(indice_oferta)
        if era_escolhida:
            for item in ofertas:
                item["escolhido"] = False
            print("\nEscolha manualmente uma oferta restante para usar como preço atual.")
            print("Use 0 se nenhuma das ofertas restantes parecer correta.")
            indice_substituta = escolher(
                ofertas,
                lambda o: f"R$ {o.get('preco_total', o.get('preco', '?'))} | {o.get('titulo', '?')} | {o.get('autor', '')} | {o.get('url', '')}",
            ) if ofertas else -1
            proxima = ofertas[indice_substituta] if indice_substituta >= 0 else None
            if proxima:
                proxima["escolhido"] = True
                link["preco_atual"] = proxima.get("preco_total", proxima.get("preco"))
                link["titulo"] = proxima.get("titulo")
                link["status"] = "sucesso"
                link["erro"] = None
                link["extras"] = {k: proxima[k] for k in ("valor_sem_frete", "frete_aplicado", "frete_presumido") if k in proxima}
            else:
                link["preco_atual"] = None
                link["status"] = "erro"
                link["erro"] = "Nenhuma oferta válida restante após remoção manual"
                link.pop("extras", None)
            atualizar_metricas(produto)
    else:
        produto["links"].pop(indice_link)
        atualizar_metricas(produto)
    estatisticas = consolidado.setdefault("estatisticas_gerais", {})
    estatisticas["produtos_com_preco"] = sum(
        1 for item in produtos
        if item.get("metricas_atuais", {}).get("menor_preco_geral") is not None
    )

    eventos = remover_eventos(historico, produto["id"], url_historico,
                              link["plataforma"], preco if tipo == "oferta" else None)
    adicionar_blacklist(titulo)
    salvar_json(ARQUIVO_CONSOLIDADO, consolidado)
    salvar_json(ARQUIVO_HISTORICO, historico)
    print(f"Oferta removida. {eventos} evento(s) de histórico removido(s).")
    if url_anuncio != url_historico:
        print(f"Anúncio removido: {url_anuncio}")
    print(f"Título incluído na blacklist: {titulo}")
    if era_escolhida and ofertas:
        print("A oferta escolhida no consolidado foi atualizada para o menor resultado restante.")


if __name__ == "__main__":
    main()
