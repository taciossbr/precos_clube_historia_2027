"""Executa a coleta configurada e apresenta os resultados no console."""

import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import PRODUTOS, LinkConfig, Produto, Plataforma
from error_counter import registrar_resultado
from logging_utils import contexto_log, registrar_log
from persistence import persistir_resultados
from processing import ProdutoProcessado, processar_produto
from scrapers.amazon import ColetorAmazon
from scrapers.estante_virtual import ColetorEstanteVirtual
from scrapers.mercado_livre import ColetorMercadoLivre
from scrapers.protocol import Coletor, ResultadoColeta
from telegram_alerts import enviar_alertas


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_CONSOLIDADO = BASE_DIR / "consolidado.json"


def executar(
    produtos: List[Produto] = PRODUTOS,
    intervalo_entre_produtos: float = 12,
    plataforma: Optional[Plataforma] = None,
) -> List[ProdutoProcessado]:
    if intervalo_entre_produtos < 0:
        raise ValueError("intervalo_entre_produtos não pode ser negativo")

    coletores = {
        Plataforma.AMAZON: ColetorAmazon(),
        Plataforma.MERCADO_LIVRE: ColetorMercadoLivre(),
        Plataforma.ESTANTE_VIRTUAL: ColetorEstanteVirtual(),
    }
    if plataforma is not None and plataforma not in coletores:
        raise ValueError(f"Não há coletor implementado para {plataforma.value}")
    resultados_anteriores = _carregar_resultados_anteriores() if plataforma else {}
    trabalhos_por_plataforma: Dict[
        Plataforma, List[Tuple[int, int, str, LinkConfig]]
    ] = {}
    resultados_por_posicao: Dict[Tuple[int, int], ResultadoColeta] = {}

    for indice_produto, produto in enumerate(produtos):
        for indice_link, link in enumerate(produto.links):
            if plataforma is not None and link.plataforma is not plataforma:
                resultados_por_posicao[(indice_produto, indice_link)] = (
                    _resultado_anterior(
                        produto.id, link.url, link.plataforma, resultados_anteriores
                    )
                )
                continue

            if link.plataforma not in coletores:
                resultados_por_posicao[(indice_produto, indice_link)] = ResultadoColeta(
                    plataforma=link.plataforma.value,
                    url=link.url,
                    status="erro",
                    erro=f"Não há coletor implementado para {link.plataforma.value}",
                    coletado_nesta_execucao=False,
                )
                continue
            trabalhos_por_plataforma.setdefault(link.plataforma, []).append(
                (indice_produto, indice_link, produto.id, link)
            )

    if trabalhos_por_plataforma:
        with ThreadPoolExecutor(max_workers=len(trabalhos_por_plataforma)) as executor:
            futuros = {
                executor.submit(
                    _coletar_fila_plataforma,
                    coletores[plataforma_fila],
                    trabalhos,
                    intervalo_entre_produtos,
                ): plataforma_fila
                for plataforma_fila, trabalhos in trabalhos_por_plataforma.items()
            }
            for futuro in as_completed(futuros):
                for indice_produto, indice_link, _, resultado in futuro.result():
                    resultados_por_posicao[(indice_produto, indice_link)] = resultado

    processados: List[ProdutoProcessado] = []
    for indice_produto, produto in enumerate(produtos):
        resultados = []
        for indice_link, link in enumerate(produto.links):
            resultado = resultados_por_posicao[(indice_produto, indice_link)]
            if resultado.coletado_nesta_execucao:
                erros = registrar_resultado(
                    link.url, sucesso=resultado.status == "sucesso"
                )
                resultado = replace(resultado, erros_consecutivos=erros)
            resultados.append(resultado)
        processado = processar_produto(produto, resultados)
        processados.append(processado)
        apresentar(processado)

    persistir_resultados(processados)
    quantidade_alertas = enviar_alertas(processados)
    if quantidade_alertas:
        registrar_log(f"Alertas enviados pelo Telegram: {quantidade_alertas}")
    registrar_log("Arquivos atualizados: consolidado.json e historico.json")
    return processados


def _coletar_fila_plataforma(
    coletor: Coletor,
    trabalhos: List[Tuple[int, int, str, LinkConfig]],
    intervalo_entre_produtos: float,
) -> List[Tuple[int, int, str, ResultadoColeta]]:
    """Coleta sequencialmente uma plataforma e retorna resultados sem persistir."""
    resultados = []
    for indice, (indice_produto, indice_link, produto_id, link) in enumerate(trabalhos):
        prefixo = f"{link.plataforma.value}/{produto_id}"
        with contexto_log(prefixo):
            if indice and intervalo_entre_produtos:
                intervalo = random.uniform(
                    intervalo_entre_produtos * 0.8,
                    intervalo_entre_produtos * 1.2,
                )
                registrar_log(
                    f"Aguardando {intervalo:.1f}s antes da próxima chamada."
                )
                time.sleep(intervalo)
            try:
                resultado = coletor.coletar(link)
            except Exception as exc:
                resultado = ResultadoColeta(
                    plataforma=link.plataforma.value,
                    url=link.url,
                    status="erro",
                    erro=f"Falha inesperada no coletor: {type(exc).__name__}: {exc}",
                )
                registrar_log(resultado.erro or "Falha inesperada no coletor.")
        resultados.append((indice_produto, indice_link, produto_id, resultado))
    return resultados


def _carregar_resultados_anteriores() -> Dict[Tuple[str, str, str], dict]:
    if not ARQUIVO_CONSOLIDADO.exists():
        return {}
    try:
        dados = json.loads(ARQUIVO_CONSOLIDADO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Não foi possível reutilizar consolidado.json inválido") from exc
    if not isinstance(dados, dict) or not isinstance(dados.get("produtos", []), list):
        raise ValueError("Formato inválido em consolidado.json")

    resultados: Dict[Tuple[str, str, str], dict] = {}
    for produto in dados.get("produtos", []):
        if not isinstance(produto, dict) or not isinstance(produto.get("id"), str):
            continue
        for link in produto.get("links", []):
            if not isinstance(link, dict):
                continue
            chave = (produto["id"], str(link.get("url", "")), str(link.get("plataforma", "")))
            resultados[chave] = link
    return resultados


def _resultado_anterior(
    produto_id: str,
    url: str,
    plataforma: Plataforma,
    anteriores: Dict[Tuple[str, str, str], dict],
) -> ResultadoColeta:
    anterior = anteriores.get((produto_id, url, plataforma.value))
    if anterior is None:
        return ResultadoColeta(
            plataforma=plataforma.value,
            url=url,
            status="erro",
            erro="Link não coletado neste modo e sem resultado anterior para reutilizar",
            coletado_nesta_execucao=False,
        )
    return ResultadoColeta(
        plataforma=plataforma.value,
        url=url,
        status=anterior.get("status", "erro"),
        preco=anterior.get("preco_atual"),
        titulo=anterior.get("titulo"),
        capa_url=anterior.get("capa_url"),
        erro=anterior.get("erro"),
        erros_consecutivos=anterior.get("erros_consecutivos", 0),
        extras=anterior.get("extras"),
        top_n_resultados=anterior.get("top_n_resultados"),
        coletado_nesta_execucao=False,
    )


def apresentar(processado: ProdutoProcessado) -> None:
    produto = processado.produto

    for resultado in processado.resultados:
        prefixo = f"{resultado.plataforma}/{produto.id}"
        titulo = f" — {resultado.titulo}" if resultado.titulo else ""
        if resultado.status == "sucesso" and resultado.preco is not None:
            registrar_log(
                f"  {resultado.plataforma}: {_formatar_preco(resultado.preco)}"
                f"{titulo}{'' if resultado.coletado_nesta_execucao else ' (dado reutilizado)'}",
                prefixo,
            )
        else:
            titulo_pagina = (
                f" — título encontrado: {resultado.titulo}"
                if resultado.titulo
                else ""
            )
            registrar_log(
                f"  {resultado.plataforma}: erro na coleta"
                f" ({resultado.erro or 'preço indisponível'}){titulo_pagina}"
                f"{'' if resultado.coletado_nesta_execucao else ' (dado reutilizado/sem nova coleta)'}",
                prefixo,
            )
        registrar_log(
            f"Erros consecutivos neste link: {resultado.erros_consecutivos}", prefixo
        )

    if processado.menor_preco is None:
        prefixo = f"{processado.resultados[0].plataforma}/{produto.id}"
        registrar_log("Métricas indisponíveis: nenhum preço foi coletado.", prefixo)
        return

    prefixo = f"{processado.plataforma_vencedora}/{produto.id}"
    registrar_log(f"Menor preço: {_formatar_preco(processado.menor_preco)}", prefixo)
    registrar_log(f"Plataforma vencedora: {processado.plataforma_vencedora}", prefixo)
    registrar_log(f"Média: {_formatar_preco(processado.media)}", prefixo)
    registrar_log(f"Mediana: {_formatar_preco(processado.mediana)}", prefixo)


def _formatar_preco(preco: float) -> str:
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta e atualiza preços dos livros.")
    parser.add_argument(
        "--plataforma",
        choices=[
            Plataforma.AMAZON.value,
            Plataforma.MERCADO_LIVRE.value,
            Plataforma.ESTANTE_VIRTUAL.value,
        ],
        help="Coleta somente esta plataforma e reutiliza os demais dados do consolidado.",
    )
    argumentos = parser.parse_args()
    executar(plataforma=Plataforma(argumentos.plataforma) if argumentos.plataforma else None)
