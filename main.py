"""Executa a coleta configurada e apresenta os resultados no console."""

import argparse
import json
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import PRODUTOS, Produto, Plataforma
from error_counter import registrar_resultado
from persistence import persistir_resultados
from processing import ProdutoProcessado, processar_produto
from scrapers.amazon import ColetorAmazon
from scrapers.estante_virtual import ColetorEstanteVirtual
from scrapers.mercado_livre import ColetorMercadoLivre
from scrapers.protocol import ResultadoColeta
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
    processados: List[ProdutoProcessado] = []
    coletas_realizadas = 0

    for produto in produtos:
        resultados = []
        for link in produto.links:
            if plataforma is not None and link.plataforma is not plataforma:
                resultados.append(
                    _resultado_anterior(
                        produto.id, link.url, link.plataforma, resultados_anteriores
                    )
                )
                continue

            coletor = coletores.get(link.plataforma)
            if coletor is None:
                resultados.append(ResultadoColeta(
                    plataforma=link.plataforma.value,
                    url=link.url,
                    status="erro",
                    erro=f"Não há coletor implementado para {link.plataforma.value}",
                    coletado_nesta_execucao=False,
                ))
                continue

            if coletas_realizadas and intervalo_entre_produtos:
                intervalo = random.uniform(
                    intervalo_entre_produtos * 0.8,
                    intervalo_entre_produtos * 1.2,
                )
                print(f"\nAguardando {intervalo:.1f}s antes da próxima chamada...")
                time.sleep(intervalo)

            resultado = coletor.coletar(link)
            coletas_realizadas += 1
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
    print(f"\n{produto.nome} (prioridade {produto.prioridade})")

    for resultado in processado.resultados:
        titulo = f" — {resultado.titulo}" if resultado.titulo else ""
        if resultado.status == "sucesso" and resultado.preco is not None:
            print(
                f"  {resultado.plataforma}: {_formatar_preco(resultado.preco)}"
                f"{titulo}{'' if resultado.coletado_nesta_execucao else ' (dado reutilizado)'}"
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
                f"{'' if resultado.coletado_nesta_execucao else ' (dado reutilizado/sem nova coleta)'}"
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
