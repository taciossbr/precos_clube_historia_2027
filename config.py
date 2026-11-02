"""Configuração dos produtos acompanhados pelo rastreador."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


# Títulos/trechos que devem ser ignorados nos resultados de busca.
BLACKLIST_BOOKS: List[str] = [
    "Em busca de Jesus",
    "O Novo Testamento Ilustrado",
    "Portugal a Terra e o Homem",
    "A farsa sobre Jesus",
    "Siga-Me",
    "O Diabólico Cérebro Eletrônico",
    "O Mundo Jesus Cristo",
    "A Escolha dos Discípulos",
    "A Juventude de Jesus",
    "Kit A Visão dos Vencidos",
    "Combo A Visão dos Vencidos",
]


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
    alvo_real: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.nome.strip():
            raise ValueError("O nome do produto não pode ficar vazio")
        if not self.id.strip():
            raise ValueError("O id do produto não pode ficar vazio")
        if self.prioridade < 1:
            raise ValueError("A prioridade deve ser maior que zero")
        if not 0 <= self.porcentagem_alvo <= 1:
            raise ValueError("porcentagem_alvo deve estar entre 0 e 1")
        if self.alvo_real is not None and self.alvo_real <= 0:
            raise ValueError("alvo_real deve ser maior que zero")
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
        porcentagem_alvo=0.10,
        alvo_real=55,
        # categoria="1ª Fase (Roma)",
        comentario="É o primeiro, prioridade máxima antes da viagem",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8531613930"),
            MercadoLink("https://lista.mercadolivre.com.br/roma%3A-a-hist%C3%B3ria-de-um-imp%C3%A9rio-%E2%80%94-greg-woolf", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=Roma%3A%20A%20Hist%C3%B3ria%20de%20um%20Imp%C3%A9rio&searchField=titulo-autor&sort=lowest-first", pesquisa=True, top_n=5),
        ]
    ),
    Produto(
        id="alexandre-e-cesar-plutarco",
        nome="Alexandre e César — Plutarco",
        prioridade=3,
        porcentagem_alvo=0.15,
        alvo_real=29,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/6556405825"),
            MercadoLink("https://lista.mercadolivre.com.br/alexandre-e-c%C3%A9sar-%E2%80%94-plutarco", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/alexandre-e-cesar-0B0-5297-000-BK"),
        ]
    ),
    Produto(
        id="o-jesus-historico-david-flusser",
        nome="O Jesus Histórico — David Flusser",
        prioridade=2,
        porcentagem_alvo=0.15,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8527302829"),
            MercadoLink("https://lista.mercadolivre.com.br/o-jesus-hist%C3%B3rico-%E2%80%94-david-flusser", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=O%20Jesus%20Hist%C3%B3rico%20%E2%80%94%20David%20Flusser&searchField=titulo-autor&sort=relevance", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/jesus-04G-7460-000-BK"),
        ]
    ),
    Produto(
        id="pompeia-mary-beard",
        nome="Pompeia: A Vida de uma Cidade Romana — Mary Beard",
        prioridade=5,
        porcentagem_alvo=0.20,
        alvo_real=90,
        # categoria="1ª Fase (Roma)",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8501092215"),
            MercadoLink("https://lista.mercadolivre.com.br/pompeia%3A-a-vida-de-uma-cidade-romana-%E2%80%94-mary-beard", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/pompeia-a-vida-de-uma-cidade-romana-06V-7741-000-BK"),
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
            MercadoLink("https://lista.mercadolivre.com.br/teogonia-%E2%80%94-hes%C3%ADodo-hedra", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/teogonia-0GH-2736-000-BK"),
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
            MercadoLink("https://lista.mercadolivre.com.br/os-trabalhos-e-os-dias-%E2%80%94-hes%C3%ADodo-hedra", pesquisa=True, top_n=5),
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
            MercadoLink("https://lista.mercadolivre.com.br/o-que-%C3%A9-a-filosofia-antiga%3F-%E2%80%94-pierre-hadot", pesquisa=True, top_n=7),
            # EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=O%20Que%20%C3%A9%20a%20Filosofia%20Antiga%3F%20%E2%80%94%20Pierre%20Hadot&searchField=titulo-autor&sort=lowest-first", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/o-que-e-a-filosofia-antiga-08V-7398-000-BK"),
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
            MercadoLink("https://lista.mercadolivre.com.br/o-anticristo%3A-uma-biografia-%E2%80%94-philip-c.-almond", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=O%20Anticristo%3A%20Uma%20Biografia%20%E2%80%94%20Philip%20C.%20Almond&searchField=titulo-autor&sort=lowest-first", pesquisa=True, top_n=5),
        ]
    ),

    # ==========================================
    # AMÉRICAS
    # ==========================================
    Produto(
        id="piratas-no-brasil-carvalho",
        nome="Piratas no Brasil — Jean Marcel Carvalho",
        prioridade=2,
        porcentagem_alvo=0.15,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8525058270"),
            MercadoLink("https://lista.mercadolivre.com.br/piratas-no-brasil-%E2%80%94-jean-marcel-carvalho", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=Piratas%20no%20Brasil%20%E2%80%94%20Jean%20Marcel%20Carvalho&searchField=titulo-autor&sort=lowest-first", pesquisa=True, top_n=5),
        ]
    ),
    Produto(
        id="os-mitos-maias-vozes",
        nome="Os Mitos Maias — Coleção Editora Vozes",
        prioridade=9,
        porcentagem_alvo=0.20,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/B0GH289VSL"),
            MercadoLink("https://lista.mercadolivre.com.br/os-mitos-maias-%E2%80%94-cole%C3%A7%C3%A3o-editora-vozes", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/livro/os-mitos-maias-NVV-7604-000-BK"),
        ]
    ),
    Produto(
        id="o-quinto-sol-camilla-townsend",
        nome="O Quinto Sol: Uma Nova História dos Astecas — Camilla Townsend",
        prioridade=2,
        porcentagem_alvo=0.15,
        # categoria="Américas",
        links=[
            AmazonLink("https://www.amazon.com.br/dp/8532674275"),
            MercadoLink("https://lista.mercadolivre.com.br/o-quinto-sol%3A-uma-nova-hist%C3%B3ria-dos-astecas-%E2%80%94-camilla-townsend", pesquisa=True, top_n=5),
            EstanteLink("https://www.estantevirtual.com.br/busca?nsCat=Natural&q=O%20Quinto%20Sol%3A%20Uma%20Nova%20Hist%C3%B3ria%20dos%20Astecas%20%E2%80%94%20Camilla%20Townsend&searchField=titulo-autor", pesquisa=True, top_n=5),
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
            MercadoLink("https://lista.mercadolivre.com.br/o-cora%C3%A7%C3%A3o-do-mundo-%E2%80%94-peter-frankopan", pesquisa=True, top_n=3),
            EstanteLink("https://www.estantevirtual.com.br/livro/o-coracao-do-mundo-07Y-5190-000-BK"),
        ]
    ),
]


BLACKLIST_BOOKS = [
    'em busca de jesus',
    'o novo testamento ilustrado: a história de jesus e os primeiros discí',
    'Novo Argumentação Estoica 5 Livros | Literatura Reflexiva',
    'Chamados Pelo Coração Do Mundo',
    'Brasil, Coração Do Mundo, Pátria Do Evangelho (novo Projeto)',
    'Combo Como Ter O Coração De Maria No Mundo De Marta',
    'Livro Como Ter O Coração De Maria No Mundo De Marta | Cpad',
    'Kit Com 5 Livros Luciano Subirá | Rumo 120 Anos+ Cuidado Do Corpo+ Cultura Jejum+ Até Que Nada Nos Importe+ Todo Coração',
]
