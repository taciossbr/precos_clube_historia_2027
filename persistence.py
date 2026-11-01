"""Gera os snapshots atuais e atualiza os históricos em JSON."""

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from config import LinkConfig
from processing import ProdutoProcessado
from scrapers.protocol import ResultadoColeta


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_CONSOLIDADO = BASE_DIR / "consolidado.json"
ARQUIVO_HISTORICO = BASE_DIR / "historico.json"
VARIACAO_MINIMA = Decimal("0.70")


def persistir_resultados(processados: List[ProdutoProcessado]) -> None:
    """Grava consolidado e histórico a partir da execução atual."""
    timestamp = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(
        timespec="seconds"
    )
    consolidado_anterior = _ler_json(ARQUIVO_CONSOLIDADO, default={})
    historico = _ler_json(ARQUIVO_HISTORICO, default={})
    contadores_produto = _contadores_anteriores(consolidado_anterior)

    produtos_json = []
    produtos_com_preco = 0
    produtos_com_falha = 0
    ids_produtos = [item.produto.id for item in processados]
    if len(ids_produtos) != len(set(ids_produtos)):
        raise ValueError("Cada produto precisa ter um id único")

    for item in processados:
        produto = item.produto
        if len(produto.links) != len(item.resultados):
            raise ValueError(f"Resultados incompletos para o produto {produto.id}")
        pares_validos = _pares_validos(item)
        plataformas_esperadas = {link.plataforma.value for link in produto.links}
        plataformas_com_preco = {resultado.plataforma for _, resultado in pares_validos}
        tem_falha = not plataformas_esperadas.issubset(plataformas_com_preco)
        contador_falhas = (
            contadores_produto.get(produto.id, 0) + 1 if tem_falha else 0
        )

        if pares_validos:
            produtos_com_preco += 1
        if tem_falha:
            produtos_com_falha += 1

        capa_url = next(
            (
                resultado.capa_url
                for resultado in item.resultados
                if resultado.capa_url
            ),
            None,
        )
        links_json = [
            _serializar_link(link, resultado)
            for link, resultado in zip(produto.links, item.resultados)
        ]

        produtos_json.append(
            {
                "id": produto.id,
                "nome": produto.nome,
                "prioridade": produto.prioridade,
                "porcentagem_alvo": produto.porcentagem_alvo,
                "capa_url": capa_url,
                "comentario": produto.comentario,
                "contador_falhas": contador_falhas,
                "metricas_atuais": {
                    "menor_preco_geral": _preco_json(item.menor_preco),
                    "plataforma_vencedora": item.plataforma_vencedora,
                    "media": _preco_json(item.media),
                    "mediana": _preco_json(item.mediana),
                },
                "links": links_json,
            }
        )
        _atualizar_historico(historico, item, pares_validos, timestamp)

    consolidado = {
        "ultima_atualizacao": timestamp,
        "estatisticas_gerais": {
            "total_produtos": len(processados),
            "produtos_com_preco": produtos_com_preco,
            "produtos_com_falha": produtos_com_falha,
        },
        "produtos": produtos_json,
    }

    _salvar_json(ARQUIVO_CONSOLIDADO, consolidado)
    _salvar_json(ARQUIVO_HISTORICO, historico)


def _serializar_link(
    link: LinkConfig,
    resultado: ResultadoColeta,
) -> Dict[str, Any]:
    link_json: Dict[str, Any] = {
        "plataforma": link.plataforma.value,
        "url": link.url,
        "pesquisa": link.pesquisa,
        "comentario": link.comentario,
        "preco_atual": _preco_json(resultado.preco)
        if resultado.status == "sucesso"
        else None,
        "titulo": resultado.titulo,
        "capa_url": resultado.capa_url,
        "status": resultado.status,
        "erros_consecutivos": resultado.erros_consecutivos,
        "erro": resultado.erro,
    }
    if resultado.extras is not None:
        link_json["extras"] = resultado.extras
    if link.pesquisa:
        link_json["top_n"] = link.top_n
        link_json["top_n_resultados"] = resultado.top_n_resultados or []
    return link_json


def _atualizar_historico(
    historico: Dict[str, Any],
    item: ProdutoProcessado,
    pares_validos: List[Tuple[LinkConfig, ResultadoColeta]],
    timestamp: str,
) -> None:
    produto_id = item.produto.id
    registro = historico.setdefault(
        produto_id,
        {"vencedor_geral": [], "por_plataforma": {}, "por_link": {}},
    )
    if not isinstance(registro, dict):
        raise ValueError(f"Histórico inválido para o produto {produto_id}")
    vencedor_geral = registro.setdefault("vencedor_geral", [])
    por_plataforma = registro.setdefault("por_plataforma", {})
    por_link = registro.setdefault("por_link", {})
    if not isinstance(vencedor_geral, list) or not isinstance(por_plataforma, dict):
        raise ValueError(f"Histórico inválido para o produto {produto_id}")
    if not isinstance(por_link, dict):
        raise ValueError(f"Histórico por link inválido para o produto {produto_id}")

    for link, resultado in pares_validos:
        eventos = por_link.setdefault(link.url, [])
        if not isinstance(eventos, list):
            raise ValueError(f"Histórico inválido para o link {link.url}")
        preco = _decimal_preco(resultado.preco)
        if _deve_registrar(eventos, preco):
            eventos.append(
                {
                    "timestamp": timestamp,
                    "preco": float(preco),
                    "plataforma": resultado.plataforma,
                }
            )

    por_plataforma_validos: Dict[
        str, List[Tuple[LinkConfig, ResultadoColeta]]
    ] = {}
    for par in pares_validos:
        por_plataforma_validos.setdefault(par[1].plataforma, []).append(par)

    for plataforma, pares in por_plataforma_validos.items():
        link, resultado = min(pares, key=lambda par: _decimal_preco(par[1].preco))
        eventos = por_plataforma.setdefault(plataforma, [])
        if not isinstance(eventos, list):
            raise ValueError(f"Histórico inválido para a plataforma {plataforma}")
        preco = _decimal_preco(resultado.preco)
        if _deve_registrar(eventos, preco):
            eventos.append(
                {"timestamp": timestamp, "preco": float(preco), "url": link.url}
            )

    if pares_validos:
        link, resultado = min(
            pares_validos, key=lambda par: _decimal_preco(par[1].preco)
        )
        preco = _decimal_preco(resultado.preco)
        if _deve_registrar(vencedor_geral, preco):
            vencedor_geral.append(
                {
                    "timestamp": timestamp,
                    "preco": float(preco),
                    "plataforma": resultado.plataforma,
                    "url": link.url,
                }
            )


def _deve_registrar(eventos: List[Dict[str, Any]], preco: Decimal) -> bool:
    if not eventos:
        return True
    ultimo_preco = _decimal_preco(eventos[-1].get("preco"))
    return abs(preco - ultimo_preco) > VARIACAO_MINIMA


def _pares_validos(
    item: ProdutoProcessado,
) -> List[Tuple[LinkConfig, ResultadoColeta]]:
    return [
        (link, resultado)
        for link, resultado in zip(item.produto.links, item.resultados)
        if resultado.status == "sucesso" and resultado.preco is not None
    ]


def _contadores_anteriores(consolidado: Dict[str, Any]) -> Dict[str, int]:
    contadores: Dict[str, int] = {}
    produtos = consolidado.get("produtos", [])
    if not isinstance(produtos, list):
        raise ValueError("Campo produtos inválido em consolidado.json")
    for produto in produtos:
        if not isinstance(produto, dict) or not isinstance(produto.get("id"), str):
            continue
        contador = produto.get("contador_falhas", 0)
        if type(contador) is not int or contador < 0:
            raise ValueError(f"contador_falhas inválido para {produto['id']}")
        contadores[produto["id"]] = contador
    return contadores


def _ler_json(caminho: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not caminho.exists():
        return default
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"JSON inválido em {caminho}; arquivo preservado") from exc
    if not isinstance(dados, dict):
        raise ValueError(f"O conteúdo de {caminho} deve ser um objeto JSON")
    return dados


def _salvar_json(caminho: Path, dados: Dict[str, Any]) -> None:
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    conteudo = json.dumps(
        dados, ensure_ascii=False, indent=2, allow_nan=False
    ) + "\n"
    temporario.write_text(conteudo, encoding="utf-8")
    temporario.replace(caminho)


def _decimal_preco(preco: Any) -> Decimal:
    if preco is None:
        raise ValueError("Preço ausente em um resultado considerado válido")
    try:
        return Decimal(str(preco)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"Preço inválido: {preco!r}") from exc


def _preco_json(preco: Optional[float]) -> Optional[float]:
    if preco is None:
        return None
    return float(_decimal_preco(preco))
