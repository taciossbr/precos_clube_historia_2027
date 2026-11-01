"""Persistência do contador de falhas consecutivas por URL."""

import json
from pathlib import Path
from typing import Dict


ARQUIVO_CONTADORES = Path(__file__).resolve().parent / "erros_consecutivos.json"


def registrar_resultado(url: str, sucesso: bool) -> int:
    """Zera a contagem em sucesso ou soma uma falha final para a URL."""
    if ARQUIVO_CONTADORES.exists():
        dados = json.loads(ARQUIVO_CONTADORES.read_text(encoding="utf-8"))
        if not isinstance(dados, dict) or any(
            not isinstance(valor, int) or valor < 0 for valor in dados.values()
        ):
            raise ValueError(f"Formato inválido em {ARQUIVO_CONTADORES}")
    else:
        dados: Dict[str, int] = {}

    dados[url] = 0 if sucesso else dados.get(url, 0) + 1
    temporario = ARQUIVO_CONTADORES.with_suffix(".json.tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporario.replace(ARQUIVO_CONTADORES)
    return dados[url]
