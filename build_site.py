"""Monta o diretório estático que será publicado pelo GitHub Pages."""

import json
import shutil
from pathlib import Path

from config import PRODUTOS


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
SITE_DIR = ROOT / "site"
ARQUIVOS_WEB = (
    "index.html",
    "detalhes.html",
    "configuracao.html",
    "styles.css",
    "detalhes.css",
    "configuracao.css",
    "app.js",
    "detalhes.js",
    "configuracao.js",
)
ARQUIVOS_DADOS = (
    "consolidado.json",
    "historico.json",
)


def main() -> None:
    ausentes = [name for name in ARQUIVOS_WEB if not (WEB_DIR / name).exists()]
    ausentes.extend(name for name in ARQUIVOS_DADOS if not (ROOT / name).exists())
    if ausentes:
        ausentes_texto = ", ".join(ausentes)
        raise FileNotFoundError(f"Arquivos necessários ausentes: {ausentes_texto}")

    SITE_DIR.mkdir(exist_ok=True)
    for nome in ARQUIVOS_WEB:
        shutil.copy2(WEB_DIR / nome, SITE_DIR / nome)
    for nome in ARQUIVOS_DADOS:
        shutil.copy2(ROOT / nome, SITE_DIR / nome)
    links_configurados = [
        {
            "id": produto.id,
            "nome": produto.nome,
            "prioridade": produto.prioridade,
            "comentario": produto.comentario,
            "links": [
                {
                    "plataforma": link.plataforma.value,
                    "url": link.url,
                    "pesquisa": link.pesquisa,
                    "top_n": link.top_n,
                    "comentario": link.comentario,
                }
                for link in produto.links
            ],
        }
        for produto in PRODUTOS
    ]
    (SITE_DIR / "links-configurados.json").write_text(
        json.dumps(links_configurados, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Site estático preparado em {SITE_DIR}")


if __name__ == "__main__":
    main()
