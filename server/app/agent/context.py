"""Per-turn context for agent tools.

Tools are plain callables invoked by LangGraph, so they cannot take the current
user as an argument without exposing it to the model. A context variable keeps
the WhatsApp number and last known location out of the model's reach while
still available to every tool, and stays correct under concurrent turns.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TurnContext:
    whatsapp_number: str
    latitude: float | None = None
    longitude: float | None = None

    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


_turn_context: ContextVar[TurnContext | None] = ContextVar(
    "conectese_turn_context", default=None
)


@contextmanager
def use_turn_context(context: TurnContext) -> Iterator[TurnContext]:
    token = _turn_context.set(context)
    try:
        yield context
    finally:
        _turn_context.reset(token)


def current_context() -> TurnContext:
    context = _turn_context.get()
    if context is None:
        raise RuntimeError(
            "No turn context set — tools must run inside use_turn_context()"
        )
    return context
