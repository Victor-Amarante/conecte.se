"""Agent wiring and tool contracts.

No network here: the model is never invoked. What these check is that the graph
compiles, the tools are exposed with the schema the model will see, and the
turn-context plumbing that keeps the user's identity out of the model's reach
actually works.
"""

import pytest

from app.agent.context import TurnContext, current_context, use_turn_context
from app.agent.graph import ConecteseAgent, _location_note
from app.agent.tools import BASE_TOOLS
from app.core.config import settings


class TestTurnContext:
    def test_context_is_visible_inside_the_block(self):
        with use_turn_context(TurnContext("5581999999999", -8.05, -34.95)):
            context = current_context()
            assert context.whatsapp_number == "5581999999999"
            assert context.has_location

    def test_context_is_cleared_afterwards(self):
        with use_turn_context(TurnContext("5581999999999")):
            pass
        with pytest.raises(RuntimeError, match="turn context"):
            current_context()

    def test_missing_coordinates_mean_no_location(self):
        assert not TurnContext("5581999999999").has_location
        assert not TurnContext("5581999999999", latitude=-8.05).has_location

    def test_nested_contexts_restore_the_outer_one(self):
        with use_turn_context(TurnContext("aaa")):
            with use_turn_context(TurnContext("bbb")):
                assert current_context().whatsapp_number == "bbb"
            assert current_context().whatsapp_number == "aaa"


class TestLocationNote:
    def test_says_unknown_without_coordinates(self):
        note = _location_note({"messages": []})
        assert "DESCONHECIDA" in note

    def test_reports_known_coordinates_and_selection(self):
        note = _location_note(
            {"user_lat": -8.05, "user_lon": -34.95, "selected_line": "011"}
        )
        assert "-8.05" in note
        assert "011" in note

    def test_flags_a_stale_location(self):
        note = _location_note(
            {"user_lat": -8.05, "user_lon": -34.95, "location_age_seconds": 1800}
        )
        assert "30 minutos" in note

    def test_says_when_no_line_is_selected(self):
        note = _location_note({"user_lat": -8.05, "user_lon": -34.95})
        assert "Nenhuma linha escolhida" in note


class TestTools:
    def test_every_tool_has_a_portuguese_description(self):
        for tool in BASE_TOOLS:
            assert tool.description, f"{tool.name} has no description"
            assert len(tool.description) > 40

    def test_the_flow_critical_tools_are_present(self):
        names = {tool.name for tool in BASE_TOOLS}
        assert {
            "find_probable_lines",
            "select_line",
            "get_bus_eta",
            "search_lines",
        } <= names

    async def test_location_tools_refuse_without_a_location(self):
        from app.agent.tools import find_probable_lines

        with use_turn_context(TurnContext("5581999999999")):
            result = await find_probable_lines.ainvoke({"radius_m": 0})

        assert result["erro"] == "sem_localizacao"

    async def test_eta_refuses_without_a_location(self):
        from app.agent.tools import get_bus_eta

        with use_turn_context(TurnContext("5581999999999")):
            result = await get_bus_eta.ainvoke({"codigo_linha": "011"})

        assert result["erro"] == "sem_localizacao"


class TestArrivalReporting:
    """A Routes API devolve a viagem mais rápida entre dois pontos e não aceita
    "quero esta linha". Num corredor movimentado ela responde com as linhas
    concorrentes, então a linha escolhida pode simplesmente não aparecer — e
    afirmar um horário nesse caso seria inventar."""

    @pytest.fixture
    def patched(self, monkeypatch):
        from datetime import datetime, timedelta, timezone

        from app.agent import tools as tools_module
        from app.services.departure_service import Departure
        from app.services.transit_service import NearbyStop

        stop = NearbyStop(
            stop_id=1, codigo="010014", nome="010014", referencia="PARADA 15",
            is_terminal=False, latitude=-8.127, longitude=-34.901, distance_m=166.0,
        )

        async def fake_nearest(*_a, **_k):
            return stop

        async def fake_downstream(*_a, **_k):
            return stop

        monkeypatch.setattr(
            tools_module.transit_service, "nearest_stop_of_line", fake_nearest
        )
        monkeypatch.setattr(
            tools_module.transit_service, "downstream_stop_of_line", fake_downstream
        )
        monkeypatch.setattr(
            tools_module.bus_location_service, "get_current_location", lambda *_a: None
        )

        def make(*codigos):
            base = datetime.now(timezone.utc) + timedelta(minutes=10)
            return [
                Departure(
                    codigo_linha=c, nome_linha=f"Linha {c}", headsign="Centro",
                    stop_name="010014",
                    departure_time=base + timedelta(minutes=i * 5), stop_count=10,
                )
                for i, c in enumerate(codigos)
            ]

        def set_departures(*codigos):
            async def fake(*_a, **_k):
                return make(*codigos)

            monkeypatch.setattr(
                tools_module.departure_service, "next_departures", fake
            )

        return set_departures

    async def test_confirms_when_the_chosen_line_is_returned(self, patched):
        from app.agent.tools import get_bus_eta

        patched("011", "910")

        with use_turn_context(TurnContext("5581", -8.126, -34.902)):
            result = await get_bus_eta.ainvoke({"codigo_linha": "011"})

        assert result["linha_escolhida_confirmada"] is True
        assert result["faltam_minutos"] >= 0
        assert result["sentido"] == "Centro"

    async def test_does_not_claim_a_time_for_an_absent_line(self, patched):
        from app.agent.tools import get_bus_eta

        patched("910", "064", "030")  # a 011 não veio

        with use_turn_context(TurnContext("5581", -8.126, -34.902)):
            result = await get_bus_eta.ainvoke({"codigo_linha": "011"})

        assert result["linha_escolhida_confirmada"] is False
        assert "faltam_minutos" not in result
        assert "horario" not in result
        assert "observacao" in result
        # As alternativas reais continuam disponíveis: é o que resolve o
        # problema do passageiro quando a linha dele não pôde ser confirmada.
        assert [d["codigo_linha"] for d in result["proximos_na_parada"]] == [
            "910", "064", "030"
        ]

    async def test_reports_when_nothing_runs_at_all(self, patched):
        from app.agent.tools import get_bus_eta

        patched()

        with use_turn_context(TurnContext("5581", -8.126, -34.902)):
            result = await get_bus_eta.ainvoke({"codigo_linha": "011"})

        assert result["erro"] == "sem_horarios"


class TestGraph:
    @pytest.fixture
    def agent(self, monkeypatch):
        from langgraph.checkpoint.memory import InMemorySaver

        monkeypatch.setattr(settings, "openai_api_key", "sk-test-not-used")
        return ConecteseAgent(tools=BASE_TOOLS, checkpointer=InMemorySaver())

    def test_graph_compiles_with_the_tool_loop(self, agent):
        nodes = agent.graph.get_graph().nodes
        assert "agent" in nodes
        assert "tools" in nodes

    def test_all_tools_are_bound(self, agent):
        assert len(agent.tools) == len(BASE_TOOLS)

    async def test_tools_used_covers_only_the_current_turn(self, agent, monkeypatch):
        """With a checkpointer the graph returns the whole thread.

        Counting tool calls across the full history would keep reporting a tool
        the user triggered several messages ago, corrupting message_logs and
        pinning eta_available to True forever.
        """
        from langchain_core.messages import AIMessage, HumanMessage

        history = [
            HumanMessage(content="quais ônibus passam aqui?"),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "find_probable_lines", "args": {}, "id": "call_1"}
                ],
            ),
            AIMessage(content="1️⃣ 2431 ..."),
            # This turn: answered from memory, no tools.
            HumanMessage(content="quanto tempo falta?"),
            AIMessage(content="Faltam cerca de 13 minutos."),
        ]

        async def fake_ainvoke(_state, config=None):
            return {"messages": history}

        monkeypatch.setattr(agent.graph, "ainvoke", fake_ainvoke)

        reply, tools_used = await agent.respond(
            whatsapp_number="5581999000111", user_message="quanto tempo falta?"
        )

        assert tools_used == []
        assert reply == "Faltam cerca de 13 minutos."

    def test_refuses_to_start_without_an_api_key(self, monkeypatch):
        from langgraph.checkpoint.memory import InMemorySaver

        monkeypatch.setattr(settings, "openai_api_key", "")
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            ConecteseAgent(tools=BASE_TOOLS, checkpointer=InMemorySaver())


class TestMCP:
    async def test_missing_config_yields_no_tools(self, tmp_path):
        from app.agent.mcp import load_mcp_tools

        assert await load_mcp_tools(tmp_path / "absent.json") == []

    async def test_malformed_config_is_not_fatal(self, tmp_path):
        from app.agent.mcp import load_mcp_tools

        path = tmp_path / "mcp_servers.json"
        path.write_text("{ not json", encoding="utf-8")

        assert await load_mcp_tools(path) == []

    async def test_empty_server_list_yields_no_tools(self, tmp_path):
        from app.agent.mcp import load_mcp_tools

        path = tmp_path / "mcp_servers.json"
        path.write_text('{"servers": {}}', encoding="utf-8")

        assert await load_mcp_tools(path) == []
