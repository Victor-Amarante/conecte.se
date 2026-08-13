from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """Conversation state, checkpointed per WhatsApp number.

    ``user_lat``/``user_lon`` and ``selected_line`` are mirrored into the state
    from ``user_sessions`` on every turn so the model can see them without a
    tool call, while the table remains the durable source of truth.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    whatsapp_number: str
    user_lat: float | None
    user_lon: float | None
    location_age_seconds: int | None
    selected_line: str | None
