"""Saída de log com contexto por thread e escrita de linhas sem intercalação."""

from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Iterator, Optional


_CONTEXTO_LOG: ContextVar[Optional[str]] = ContextVar("contexto_log", default=None)
_LOCK_LOG = Lock()


@contextmanager
def contexto_log(prefixo: str) -> Iterator[None]:
    token = _CONTEXTO_LOG.set(prefixo)
    try:
        yield
    finally:
        _CONTEXTO_LOG.reset(token)


def registrar_log(mensagem: object, prefixo: Optional[str] = None) -> None:
    contexto = prefixo or _CONTEXTO_LOG.get() or "sistema/geral"
    linhas = str(mensagem).splitlines() or [""]
    with _LOCK_LOG:
        for linha in linhas:
            print(f"[{contexto}] {linha}", flush=True)
