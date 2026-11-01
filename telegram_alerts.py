"""Regras e envio de alertas de preço pelo Telegram."""

import json
import os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from processing import ProdutoProcessado


BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALERTAS = BASE_DIR / "alertas_enviados.json"
MINIMO_PRECOS = 3
VARIACAO_MINIMA = Decimal("0.70")
DESTINATARIO_TELEGRAM = "taciossbr"


def validar_token(token: Optional[str] = None) -> Dict[str, Any]:
    """Consulta getMe e retorna os dados do bot sem imprimir o token."""
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não está definido no ambiente atual")
    token = token.strip()
    if ":" not in token or len(token) < 30:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN não parece estar no formato de token do BotFather (ID:segredo)"
        )
    resposta = requests.get(
        f"https://api.telegram.org/bot{token}/getMe", timeout=15
    )
    dados = resposta.json()
    if not resposta.ok or not dados.get("ok"):
        raise ValueError("Telegram recusou o token; confira TELEGRAM_BOT_TOKEN")
    return dados["result"]


def consultar_chat_id(token: Optional[str] = None) -> str:
    """Lê /start via getUpdates e retorna o ID se a mensagem for do usuário permitido."""
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não está definido no ambiente atual")
    token = token.strip()
    if ":" not in token or len(token) < 30:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN não parece estar no formato de token do BotFather (ID:segredo)"
        )
    resposta = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates", timeout=15
    )
    try:
        dados = resposta.json()
    except ValueError as exc:
        raise ValueError(
            f"Telegram retornou uma resposta inválida (HTTP {resposta.status_code})"
        ) from exc
    if not resposta.ok or not dados.get("ok"):
        descricao = dados.get("description", "sem descrição")
        codigo = dados.get("error_code", resposta.status_code)
        if "webhook" in descricao.casefold():
            detalhe = "O bot tem webhook ativo; getUpdates não funciona enquanto ele estiver ativo."
        elif codigo == 401:
            detalhe = "O token foi recusado; confira TELEGRAM_BOT_TOKEN."
        else:
            detalhe = f"Telegram: {descricao} (código {codigo})."
        raise ValueError(f"Não foi possível consultar atualizações. {detalhe}")
    for update in reversed(dados.get("result", [])):
        mensagem = update.get("message", {})
        usuario = mensagem.get("from", {}).get("username", "")
        if mensagem.get("text", "").split()[0:1] == ["/start"] and usuario.casefold() == DESTINATARIO_TELEGRAM.casefold():
            chat_id = str(mensagem.get("chat", {}).get("id", ""))
            if chat_id:
                _enviar(token, chat_id, "Olá! Este chat está configurado para receber seus alertas de preços de livros.")
                return chat_id
    raise ValueError(
        f"Nenhum /start recente de @{DESTINATARIO_TELEGRAM} foi recebido. Envie /start ao bot e tente novamente."
    )


def enviar_mensagem_teste() -> None:
    """Envia uma mensagem manual de teste somente ao usuário permitido."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise ValueError("Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no ambiente")
    _validar_destinatario(token, chat_id)
    _enviar(token, chat_id, "✅ Teste do bot de alertas: envio funcionando para @taciossbr.")
    print("Mensagem de teste enviada para @taciossbr.")


def enviar_alertas(processados: List[ProdutoProcessado]) -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Alertas Telegram ignorados: configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return 0

    _validar_destinatario(token, chat_id)

    estado = _ler_estado()
    enviados = 0
    for item in processados:
        if item.menor_preco is None:
            continue
        eventos = _coletas_validas(estado, item)
        preco = _decimal(item.menor_preco)
        alertas = estado.setdefault(item.produto.id, {})
        if not isinstance(alertas, dict):
            raise ValueError(f"Estado de alertas inválido para {item.produto.id}")

        candidatos = []
        mediana = item.mediana
        limite = (
            _decimal(mediana) * (Decimal("1") - _decimal(item.produto.porcentagem_alvo))
            if mediana is not None
            else None
        )
        if len(eventos) >= MINIMO_PRECOS and limite is not None and preco <= limite:
            candidatos.append(("abaixo_mediana", f"{item.produto.porcentagem_alvo:.0%} abaixo da mediana"))

        menor_anterior = min((_decimal(e["preco"]) for e in eventos[:-1]), default=None)
        if menor_anterior is not None and preco < menor_anterior:
            candidatos.append(("novo_menor", "menor preço registrado até agora"))

        for tipo, motivo in candidatos:
            chave = f"{tipo}:{preco:.2f}"
            if alertas.get(tipo) == chave:
                continue
            mensagem = _formatar_mensagem(item, motivo)
            _enviar(token, chat_id, mensagem)
            alertas[tipo] = chave
            enviados += 1

    _salvar_estado(estado)
    return enviados


def _validar_destinatario(token: str, chat_id: str) -> None:
    """Falha fechado se o chat configurado não for o usuário permitido."""
    resposta = requests.get(
        f"https://api.telegram.org/bot{token}/getChat",
        params={"chat_id": chat_id},
        timeout=15,
    )
    dados = resposta.json()
    usuario = dados.get("result", {}).get("username", "") if dados.get("ok") else ""
    if not resposta.ok or not dados.get("ok") or usuario.casefold() != DESTINATARIO_TELEGRAM.casefold():
        raise ValueError(
            f"Envio bloqueado: TELEGRAM_CHAT_ID precisa pertencer a @{DESTINATARIO_TELEGRAM}"
        )


def _coletas_validas(estado: Dict[str, Any], item: ProdutoProcessado) -> List[Dict[str, Any]]:
    produto_id = item.produto.id
    registros = estado.setdefault(produto_id, {}).setdefault("coletas_validas", [])
    if not isinstance(registros, list):
        raise ValueError(f"Coletas válidas inválidas para {produto_id}")
    validos = [
        _decimal(resultado.preco)
        for resultado in item.resultados
        if resultado.status == "sucesso" and resultado.preco is not None
    ]
    for preco in validos:
        registros.append({"preco": float(preco)})
        del registros[:-100]
    return registros


def _formatar_mensagem(item: ProdutoProcessado, motivo: str) -> str:
    indice = next(
        (i for i, resultado in enumerate(item.resultados)
         if resultado.status == "sucesso" and resultado.preco == item.menor_preco),
        0,
    )
    link = item.produto.links[indice].url
    return (
        f"📚 Alerta de preço\n{item.produto.nome}\n"
        f"Preço: {_formatar_preco(item.menor_preco)} ({item.plataforma_vencedora})\n"
        f"Motivo: {motivo}\n{link}"
    )


def _enviar(token: str, chat_id: str, mensagem: str) -> None:
    resposta = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": mensagem, "disable_web_page_preview": True},
        timeout=15,
    )
    dados = resposta.json()
    if not resposta.ok or not dados.get("ok"):
        raise RuntimeError("Falha ao enviar alerta pelo Telegram")


def _ler_estado() -> Dict[str, Any]:
    if not ARQUIVO_ALERTAS.exists():
        return {}
    dados = json.loads(ARQUIVO_ALERTAS.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("Formato inválido em alertas_enviados.json")
    return dados


def _salvar_estado(estado: Dict[str, Any]) -> None:
    temporario = ARQUIVO_ALERTAS.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(ARQUIVO_ALERTAS)


def _decimal(valor: Any) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
