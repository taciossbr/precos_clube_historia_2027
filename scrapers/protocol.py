"""Contrato comum para coletores de plataformas."""

from dataclasses import dataclass
from typing import Optional, Protocol

from config import LinkConfig


@dataclass(frozen=True)
class ResultadoColeta:
    plataforma: str
    url: str
    status: str
    preco: Optional[float] = None
    titulo: Optional[str] = None
    capa_url: Optional[str] = None
    erro: Optional[str] = None
    erros_consecutivos: int = 0


class Coletor(Protocol):
    def coletar(self, link: LinkConfig) -> ResultadoColeta:
        """Consulta um link e retorna o resultado sem propagar falhas de coleta."""
