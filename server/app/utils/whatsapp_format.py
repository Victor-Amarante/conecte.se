"""Converte a formatação do modelo para a do WhatsApp.

O modelo escreve Markdown por hábito — `**negrito**`. O WhatsApp usa **um**
asterisco, então `**360**` chega ao passageiro com os asteriscos visíveis.

A conversão é feita aqui, no envio, e não só via prompt: instrução de formato é
justamente o tipo de coisa que o modelo esquece quando a resposta fica longa, e
o custo do esquecimento é uma mensagem feia para o usuário final.
"""

import re

# **negrito** ou __negrito__ -> *negrito*. O `.+?` não atravessa linhas, o que
# evita que um asterisco solto no meio do texto coma o parágrafo inteiro.
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BOLD_ALT = re.compile(r"__(.+?)__")

# Cabeçalhos Markdown não existem no WhatsApp; viram negrito.
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

# Markdown quebra linha com dois espaços no fim; no WhatsApp isso é só sujeira.
_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)


def to_whatsapp(text: str) -> str:
    """Normaliza um texto para o formato aceito pelo WhatsApp."""
    if not text:
        return text

    text = _HEADING.sub(r"*\1*", text)
    text = _BOLD.sub(r"*\1*", text)
    text = _BOLD_ALT.sub(r"*\1*", text)
    text = _TRAILING_SPACES.sub("", text)
    return text.strip()
