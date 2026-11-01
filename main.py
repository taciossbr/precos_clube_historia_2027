"""Executa a coleta configurada e apresenta os resultados no console."""

import random
import time
from dataclasses import replace
from typing import List

from config import PRODUTOS, Produto
from error_counter import registrar_resultado
from persistence import persistir_resultados
from processing import ProdutoProcessado, processar_produto
from scrapers.amazon import ColetorAmazon
from telegram_alerts import enviar_alertas


def executar(
    produtos: List[Produto] = PRODUTOS,
    intervalo_entre_produtos: float = 12,
) -> List[ProdutoProcessado]:
    if intervalo_entre_produtos < 0:
        raise ValueError("intervalo_entre_produtos não pode ser negativo")

    coletor = ColetorAmazon()
    processados: List[ProdutoProcessado] = []

    for indice, produto in enumerate(produtos):
        if indice > 0 and intervalo_entre_produtos:
            intervalo = random.uniform(
                intervalo_entre_produtos * 0.8,
                intervalo_entre_produtos * 1.2,
            )
            print(f"\nAguardando {intervalo:.1f}s antes do próximo produto...")
            time.sleep(intervalo)

        resultados = []
        for link in produto.links:
            resultado = coletor.coletar(link)
            erros = registrar_resultado(
                link.url, sucesso=resultado.status == "sucesso"
            )
            resultados.append(replace(resultado, erros_consecutivos=erros))

        processado = processar_produto(produto, resultados)
        processados.append(processado)
        apresentar(processado)

    persistir_resultados(processados)
    quantidade_alertas = enviar_alertas(processados)
    if quantidade_alertas:
        print(f"Alertas enviados pelo Telegram: {quantidade_alertas}")
    print("\nArquivos atualizados: consolidado.json e historico.json")
    return processados


def apresentar(processado: ProdutoProcessado) -> None:
    produto = processado.produto
    print(f"\n{produto.nome} (prioridade {produto.prioridade})")

    for resultado in processado.resultados:
        titulo = f" — {resultado.titulo}" if resultado.titulo else ""
        if resultado.status == "sucesso" and resultado.preco is not None:
            print(
                f"  {resultado.plataforma}: {_formatar_preco(resultado.preco)}"
                f"{titulo}"
            )
        else:
            titulo_pagina = (
                f" — título encontrado: {resultado.titulo}"
                if resultado.titulo
                else ""
            )
            print(
                f"  {resultado.plataforma}: erro na coleta"
                f" ({resultado.erro or 'preço indisponível'}){titulo_pagina}"
            )
        print(f"    Erros consecutivos neste link: {resultado.erros_consecutivos}")

    if processado.menor_preco is None:
        print("  Métricas indisponíveis: nenhum preço foi coletado.")
        return

    print(f"  Menor preço: {_formatar_preco(processado.menor_preco)}")
    print(f"  Plataforma vencedora: {processado.plataforma_vencedora}")
    print(f"  Média: {_formatar_preco(processado.media)}")
    print(f"  Mediana: {_formatar_preco(processado.mediana)}")


def _formatar_preco(preco: float) -> str:
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


if __name__ == "__main__":
    executar()
