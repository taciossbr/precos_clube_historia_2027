"""Associa coletas aos produtos e calcula suas métricas atuais."""

from dataclasses import dataclass
from statistics import mean, median
from typing import List, Optional

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
        )

    vencedor = min(validos, key=lambda resultado: resultado.preco)
    return ProdutoProcessado(
        produto=produto,
        resultados=resultados,
        menor_preco=vencedor.preco,
        plataforma_vencedora=vencedor.plataforma,
        media=mean(precos),
        mediana=median(precos),
    )
