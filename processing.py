"""Associa coletas aos produtos e calcula suas métricas atuais."""

from dataclasses import dataclass
from statistics import mean, median
from typing import Dict, List, Optional

from config import Produto
from scrapers.protocol import ResultadoColeta


@dataclass(frozen=True)
class ProdutoProcessado:
    produto: Produto
    resultados: List[ResultadoColeta]
    menor_preco: Optional[float]
    plataforma_vencedora: Optional[str]
    media: Optional[float]
    mediana: Optional[float]
    mediana_por_plataforma: Dict[str, float]


def processar_produto(
    produto: Produto, resultados: List[ResultadoColeta]
) -> ProdutoProcessado:
    """Calcula métricas somente com preços coletados com sucesso."""
    validos = [
        resultado
        for resultado in resultados
        if resultado.status == "sucesso" and resultado.preco is not None
    ]
    precos = [resultado.preco for resultado in validos]

    if not validos:
        return ProdutoProcessado(
            produto=produto,
            resultados=resultados,
            menor_preco=None,
            plataforma_vencedora=None,
            media=None,
            mediana=None,
            mediana_por_plataforma={},
        )

    vencedor = min(validos, key=lambda resultado: resultado.preco)
    precos_por_plataforma: Dict[str, List[float]] = {}
    for resultado in validos:
        precos_por_plataforma.setdefault(resultado.plataforma, []).append(resultado.preco)
    return ProdutoProcessado(
        produto=produto,
        resultados=resultados,
        menor_preco=vencedor.preco,
        plataforma_vencedora=vencedor.plataforma,
        media=mean(precos),
        mediana=median(precos),
        mediana_por_plataforma={
            plataforma: median(valores)
            for plataforma, valores in precos_por_plataforma.items()
        },
    )
