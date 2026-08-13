"""The Conectese conversational agent.

A standard tool-calling loop: the model either answers or asks for tools, the
tool node runs them, and control returns to the model. Conversation history is
checkpointed in Postgres keyed by WhatsApp number, which is what lets a rider
send their location in one message and pick a line in the next.
"""

import asyncio

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from loguru import logger

from app.agent.context import TurnContext, use_turn_context
from app.agent.mcp import load_mcp_tools
from app.agent.state import AgentState
from app.agent.tools import BASE_TOOLS
from app.core.config import settings
from app.prompts.whatsapp_system_prompt import SYSTEM_PROMPT

FALLBACK_REPLY = (
    "Tive um problema para consultar as informações agora 😕. "
    "Tenta de novo em instantes?"
)

# Guards against a pathological tool loop burning tokens on a paid API.
RECURSION_LIMIT = 12


def _location_note(state: AgentState) -> str:
    """A short system note telling the model what it already knows."""
    lat, lon = state.get("user_lat"), state.get("user_lon")
    if lat is None or lon is None:
        return (
            "[CONTEXTO] Localização do usuário: DESCONHECIDA. "
            "Peça a localização antes de usar ferramentas que dependem dela."
        )

    parts = [f"[CONTEXTO] Localização do usuário conhecida ({lat:.5f}, {lon:.5f})."]
    age = state.get("location_age_seconds")
    if age is not None and age > 600:
        parts.append(
            f"Foi enviada há {age // 60} minutos; se a resposta parecer "
            "inconsistente, considere pedir a localização novamente."
        )
    selected = state.get("selected_line")
    if selected:
        parts.append(f"Linha escolhida no momento: {selected}.")
    else:
        parts.append("Nenhuma linha escolhida ainda.")
    return " ".join(parts)


class ConecteseAgent:
    def __init__(self, tools: list, checkpointer) -> None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set — the agent cannot start. "
                "Add it to server/.env."
            )

        self.tools = tools
        self.model = ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        ).bind_tools(tools)
        self.graph = self._build(checkpointer)

    def _build(self, checkpointer):
        async def call_model(state: AgentState) -> dict:
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                SystemMessage(content=_location_note(state)),
                *state["messages"],
            ]
            response = await self.model.ainvoke(messages)
            return {"messages": [response]}

        builder = StateGraph(AgentState)
        builder.add_node("agent", call_model)
        builder.add_node("tools", ToolNode(self.tools))
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent", tools_condition, {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "agent")
        return builder.compile(checkpointer=checkpointer)

    async def respond(
        self,
        *,
        whatsapp_number: str,
        user_message: str,
        latitude: float | None = None,
        longitude: float | None = None,
        location_age_seconds: int | None = None,
        selected_line: str | None = None,
    ) -> tuple[str, list[str]]:
        """Run one conversational turn.

        Returns the reply text and the names of the tools that were called,
        which the webhook persists for auditing.
        """
        context = TurnContext(
            whatsapp_number=whatsapp_number, latitude=latitude, longitude=longitude
        )
        config = {
            "configurable": {"thread_id": whatsapp_number},
            "recursion_limit": RECURSION_LIMIT,
        }
        state: AgentState = {
            "messages": [HumanMessage(content=user_message)],
            "whatsapp_number": whatsapp_number,
            "user_lat": latitude,
            "user_lon": longitude,
            "location_age_seconds": location_age_seconds,
            "selected_line": selected_line,
        }

        try:
            with use_turn_context(context):
                result = await self.graph.ainvoke(state, config=config)
        except Exception:
            logger.exception(f"Agent failed for {whatsapp_number}")
            return FALLBACK_REPLY, []

        messages = result.get("messages", [])

        # With a checkpointer, ainvoke returns the whole thread, not just this
        # turn. Everything after the last HumanMessage is what this turn
        # produced — counting the full history would make tools_used (and the
        # eta_available flag derived from it) cumulative and wrong.
        turn_start = 0
        for index in range(len(messages) - 1, -1, -1):
            if isinstance(messages[index], HumanMessage):
                turn_start = index
                break
        turn_messages = messages[turn_start:]

        tools_used = [
            call["name"]
            for message in turn_messages
            if isinstance(message, AIMessage)
            for call in (message.tool_calls or [])
        ]

        reply = ""
        for message in reversed(turn_messages):
            if isinstance(message, AIMessage) and message.content:
                reply = (
                    message.content
                    if isinstance(message.content, str)
                    else str(message.content)
                )
                break

        if not reply.strip():
            logger.warning(f"Agent produced an empty reply for {whatsapp_number}")
            return FALLBACK_REPLY, tools_used

        return reply.strip(), tools_used


# --------------------------------------------------------------------------
# Lazily built singleton
# --------------------------------------------------------------------------

_agent: ConecteseAgent | None = None
_agent_lock = asyncio.Lock()
_checkpointer_cm = None


async def _build_checkpointer():
    """Postgres-backed conversation memory, with an in-memory fallback.

    Losing history is far better than refusing to answer, so a checkpointer
    that fails to connect degrades instead of raising.
    """
    global _checkpointer_cm
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(
            settings.sync_database_url
        )
        checkpointer = await _checkpointer_cm.__aenter__()
        await checkpointer.setup()
        logger.info("Agent checkpointer: Postgres")
        return checkpointer
    except Exception as exc:
        logger.error(
            f"Postgres checkpointer unavailable ({exc}); "
            "falling back to in-memory conversation history"
        )
        _checkpointer_cm = None
        return InMemorySaver()


async def get_agent() -> ConecteseAgent:
    global _agent
    if _agent is not None:
        return _agent

    async with _agent_lock:
        if _agent is None:
            checkpointer = await _build_checkpointer()
            tools = [*BASE_TOOLS, *await load_mcp_tools()]
            _agent = ConecteseAgent(tools=tools, checkpointer=checkpointer)
            logger.info(f"Agent ready with {len(tools)} tool(s)")
    return _agent


async def shutdown_agent() -> None:
    global _agent, _checkpointer_cm
    _agent = None
    if _checkpointer_cm is not None:
        try:
            await _checkpointer_cm.__aexit__(None, None, None)
        except Exception as exc:
            logger.warning(f"Error closing checkpointer: {exc}")
        _checkpointer_cm = None
