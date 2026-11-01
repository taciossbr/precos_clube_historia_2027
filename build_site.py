"""Monta o diretório estático que será publicado pelo GitHub Pages."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
SITE_DIR = ROOT / "site"
ARQUIVOS_WEB = (
    "index.html",
    "detalhes.html",
    "styles.css",
    "detalhes.css",
    "app.js",
    "detalhes.js",
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
    print(f"Site estático preparado em {SITE_DIR}")


if __name__ == "__main__":
    main()
