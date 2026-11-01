"""Configuração dos produtos acompanhados pelo rastreador."""

from dataclasses import dataclass
from enum import Enum
from typing import List


class Plataforma(Enum):
    AMAZON = "amazon"
    MERCADO_LIVRE = "mercado_livre"
    ESTANTE_VIRTUAL = "estante_virtual"


@dataclass(frozen=True)
class LinkConfig:
    url: str
    plataforma: Plataforma
    pesquisa: bool = False
    top_n: int = 1
    comentario: str = ""

    def __post_init__(self) -> None:
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("A URL do link deve começar com http:// ou https://")
        if self.top_n < 1:
            raise ValueError("top_n deve ser maior que zero")


@dataclass(frozen=True)
class Produto:
    nome: str
    prioridade: int
    links: List[LinkConfig]
    id: str
    comentario: str = ""
    porcentagem_alvo: float = 0.20

    def __post_init__(self) -> None:
        if not self.nome.strip():
            raise ValueError("O nome do produto não pode ficar vazio")
        if not self.id.strip():
            raise ValueError("O id do produto não pode ficar vazio")
        if self.prioridade < 1:
            raise ValueError("A prioridade deve ser maior que zero")
        if not 0 <= self.porcentagem_alvo <= 1:
            raise ValueError("porcentagem_alvo deve estar entre 0 e 1")
        if not self.links:
            raise ValueError("O produto deve ter ao menos um link")


def AmazonLink(url: str, comentario: str = "") -> LinkConfig:
    return LinkConfig(url=url, plataforma=Plataforma.AMAZON, comentario=comentario)


def MercadoLink(
    url: str, pesquisa: bool = False, top_n: int = 3, comentario: str = ""
) -> LinkConfig:
    return LinkConfig(
        url=url,
        plataforma=Plataforma.MERCADO_LIVRE,
        pesquisa=pesquisa,
        top_n=top_n if pesquisa else 1,
        comentario=comentario,
    )


def EstanteLink(
    url: str, pesquisa: bool = False, top_n: int = 5, comentario: str = ""
) -> LinkConfig:
    return LinkConfig(
        url=url,
        plataforma=Plataforma.ESTANTE_VIRTUAL,
        pesquisa=pesquisa,
        top_n=top_n if pesquisa else 1,
        comentario=comentario,
    )


# PRODUTOS: List[Produto] = [
#     Produto(
#         nome="Roma: A História de um Império — Greg Woolf",
#         prioridade=1,
#         id="roma-greg-woolf",
#         comentario="É o primeiro compre logo",
#         links=[AmazonLink("https://www.amazon.com.br/dp/8531613930")],
#     ),
#     Produto(
#         nome="Alexandre e César — Plutarco",
#         prioridade=2,
#         id="alexandre-cesar-plutarco",
#         links=[AmazonLink("https://www.amazon.com.br/dp/6556405825")],
#     ),
#     Produto(
#         nome="O Jesus Histórico — David Flusser",
#         prioridade=3,
#         id="jesus-historico-david-flusser",
#         links=[AmazonLink("https://www.amazon.com.br/dp/8527302829")],
#     ),
#     Produto(
#         nome="Pompeia: A Vida de uma Cidade Romana — Mary Beard",
#         prioridade=4,
#         id="pompeia-mary-beard",
#         links=[AmazonLink("https://www.amazon.com.br/dp/8501092215")],
#     ),
# ]



PRODUTOS: List[Produto] = [
    # ==========================================
    # 1ª FASE (ANTES DA VIAGEM A ROMA)
    # ==========================================
    Produto(
        id="roma-greg-woolf",
        nome="Roma: A História de um Império — Greg Woolf",
        prioridade=1,
        porcentagem_alvo=0.15,
        # categoria="1ª Fase (Roma)",
        comentario="É o primeiro, prioridade máxima antes da viagem",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8531613930"),
            # MercadoLink("https://lista.mercadolivre.com.br/roma-a-historia-de-um-imperio-greg-woolf", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=roma-a-historia-de-um-imperio-greg-woolf", top_n=5),
        ]
    ),
    Produto(
        id="alexandre-e-cesar-plutarco",
        nome="Alexandre e César — Plutarco",
        prioridade=1,
        porcentagem_alvo=0.20,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/6556405825"),
            # MercadoLink("https://lista.mercadolivre.com.br/alexandre-e-cesar-plutarco", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=alexandre-e-cesar-plutarco", top_n=5),
        ]
    ),
    Produto(
        id="o-jesus-historico-david-flusser",
        nome="O Jesus Histórico — David Flusser",
        prioridade=1,
        porcentagem_alvo=0.20,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8527302829"),
            # MercadoLink("https://lista.mercadolivre.com.br/o-jesus-historico-david-flusser", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=o-jesus-historico-david-flusser", top_n=5),
        ]
    ),
    Produto(
        id="pompeia-mary-beard",
        nome="Pompeia: A Vida de uma Cidade Romana — Mary Beard",
        prioridade=5,
        porcentagem_alvo=0.20,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8501092215"),
            # MercadoLink("https://lista.mercadolivre.com.br/pompeia-a-vida-de-uma-cidade-romana-mary-beard", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=pompeia-mary-beard", top_n=5),
        ]
    ),

    # ==========================================
    # GRÉCIA ANTIGA
    # ==========================================
    Produto(
        id="teogonia-hesiodo",
        nome="Teogonia — Hesíodo",
        prioridade=5,
        porcentagem_alvo=0.20,
        # categoria="Grécia Antiga",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/6589705585"),
            # MercadoLink("https://lista.mercadolivre.com.br/teogonia-hesiodo", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=teogonia-hesiodo", top_n=5),
        ]
    ),
    Produto(
        id="os-trabalhos-e-os-dias-hesiodo",
        nome="Os Trabalhos e os Dias — Hesíodo",
        prioridade=5,
        porcentagem_alvo=0.20,
        # categoria="Grécia Antiga",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/6589705577"),
            # MercadoLink("https://lista.mercadolivre.com.br/os-trabalhos-e-os-dias-hesiodo", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=os-trabalhos-e-os-dias-hesiodo", top_n=5),
        ]
    ),
    Produto(
        id="o-que-e-a-filosofia-antiga-hadot",
        nome="O Que é a Filosofia Antiga? — Pierre Hadot",
        prioridade=4,
        porcentagem_alvo=0.20,
        # categoria="Grécia Antiga",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8515017857"),
            # MercadoLink("https://lista.mercadolivre.com.br/o-que-e-a-filosofia-antiga-pierre-hadot", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=o-que-e-a-filosofia-antiga-pierre-hadot", top_n=5),
        ]
    ),

    # ==========================================
    # GERAL / RELIGIÃO
    # ==========================================
    Produto(
        id="o-anticristo-biografia-almond",
        nome="O Anticristo: Uma Biografia (Movimentos Apocalípticos) — Philip C. Almond",
        prioridade=2,
        porcentagem_alvo=0.20,
        # categoria="Geral / Religião",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/B0D4WQ179K"),
            # MercadoLink("https://lista.mercadolivre.com.br/o-anticristo-uma-biografia-philip-c-almond", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=o-anticristo-uma-biografia-philip-c-almond", top_n=5),
        ]
    ),

    # ==========================================
    # AMÉRICAS
    # ==========================================
    Produto(
        id="piratas-no-brasil-carvalho",
        nome="Piratas no Brasil — Jean Marcel Carvalho",
        prioridade=2,
        porcentagem_alvo=0.20,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8525058270"),
            # MercadoLink("https://lista.mercadolivre.com.br/piratas-no-brasil-jean-marcel-carvalho", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=piratas-no-brasil-jean-marcel-carvalho", top_n=5),
        ]
    ),
    Produto(
        id="os-mitos-maias-vozes",
        nome="Os Mitos Maias — Coleção Editora Vozes",
        prioridade=10,
        porcentagem_alvo=0.20,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/B0GH289VSL"),
            # MercadoLink("https://lista.mercadolivre.com.br/os-mitos-maias-editora-vozes", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=os-mitos-maias-editora-vozes", top_n=5),
        ]
    ),
    Produto(
        id="o-quinto-sol-camilla-townsend",
        nome="O Quinto Sol: Uma Nova História dos Astecas — Camilla Townsend",
        prioridade=3,
        porcentagem_alvo=0.20,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8532674275"),
            # MercadoLink("https://lista.mercadolivre.com.br/o-quinto-sol-camilla-townsend", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=o-quinto-sol-camilla-townsend", top_n=5),
        ]
    ),

    # ==========================================
    # HISTÓRIA GLOBAL
    # ==========================================
    Produto(
        id="o-coracao-do-mundo-peter-frankopan",
        nome="O Coração do Mundo — Peter Frankopan",
        prioridade=3,
        porcentagem_alvo=0.20,
        # categoria="História Global",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8542217497"),
            # MercadoLink("https://lista.mercadolivre.com.br/o-coracao-do-mundo-peter-frankopan", top_n=3),
            # EstanteLink("https://www.estantevirtual.com.br/busca?q=o-coracao-do-mundo-peter-frankopan", top_n=5),
        ]
    ),
]