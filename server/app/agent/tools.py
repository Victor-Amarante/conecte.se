"""Tools the agent uses to answer questions about the Recife bus network.

Each tool opens its own short-lived database session: LangGraph may run several
in parallel from one model turn, and sharing a session across them is not safe.

Tool descriptions are written in Portuguese because that is the language of the
conversation and of the data they return.
"""

from langchain_core.tools import tool
from loguru import logger

from app.agent.context import current_context
from app.db.session import SessionLocal
from app.schemas.location import UserLocation
from app.services.registry import (
    bus_location_service,
    departure_service,
    eta_service,
)
from app.services.session_service import session_service
from app.services.transit_service import transit_service


@tool
async def find_probable_lines(radius_m: int = 0) -> dict:
    """Lista as linhas de ônibus que provavelmente atendem a localização atual do usuário.

    Use esta ferramenta quando o usuário perguntar quais ônibus passam por onde
    ele está, ou quando ele precisar escolher uma linha. O resultado já vem
    ordenado da opção mais provável para a menos provável.

    Args:
        radius_m: Raio de busca em metros. Use 0 para busca automática, que
            amplia o raio até encontrar linhas.
    """
    context = current_context()
    if not context.has_location:
        return {
            "erro": "sem_localizacao",
            "mensagem": "A localização do usuário ainda não é conhecida. Peça que ele "
            "envie a localização pelo anexo do WhatsApp.",
        }

    async with SessionLocal() as session:
        if radius_m and radius_m > 0:
            lines = await transit_service.find_probable_lines(
                session, context.latitude, context.longitude, radius_m=radius_m
            )
            used_radius = radius_m
        else:
            lines, used_radius = await transit_service.find_probable_lines_expanding(
                session, context.latitude, context.longitude
            )

    if not lines:
        return {
            "erro": "nenhuma_linha",
            "raio_m": used_radius,
            "mensagem": "Nenhuma linha encontrada perto dessa localização.",
        }

    return {
        "raio_m": used_radius,
        "total": len(lines),
        "linhas": [
            {
                "codigo_linha": line.codigo_linha,
                "nome": line.nome,
                "parada": line.stop_nome or line.stop_codigo,
                # Ordinary stops are named by a numeric code, so this is the
                # part a rider can actually recognise on the street.
                "referencia_da_parada": line.stop_referencia,
                "distancia_m": round(line.distance_m),
                "terminal": line.serves_terminal,
            }
            for line in lines
        ],
    }


@tool
async def find_nearby_stops(radius_m: int = 500) -> dict:
    """Lista as paradas de ônibus mais próximas da localização atual do usuário.

    Use quando o usuário perguntar onde fica a parada mais próxima.

    Args:
        radius_m: Raio de busca em metros (padrão 500).
    """
    context = current_context()
    if not context.has_location:
        return {
            "erro": "sem_localizacao",
            "mensagem": "Peça a localização do usuário antes de usar esta ferramenta.",
        }

    async with SessionLocal() as session:
        stops = await transit_service.find_nearby_stops(
            session, context.latitude, context.longitude, radius_m=radius_m
        )

    return {
        "total": len(stops),
        "paradas": [
            {
                "stop_id": stop.stop_id,
                "nome": stop.nome or stop.codigo,
                "referencia": stop.referencia,
                "distancia_m": round(stop.distance_m),
                "terminal": stop.is_terminal,
            }
            for stop in stops
        ],
    }


@tool
async def list_lines_at_stop(stop_id: int) -> dict:
    """Lista todas as linhas que atendem uma parada específica.

    Args:
        stop_id: Identificador da parada, obtido de find_nearby_stops.
    """
    async with SessionLocal() as session:
        lines = await transit_service.list_lines_at_stop(session, stop_id)
    return {"stop_id": stop_id, "total": len(lines), "linhas": lines}


@tool
async def search_lines(termo: str) -> dict:
    """Busca linhas de ônibus por código ou por nome/destino.

    Use quando o usuário citar uma linha pelo número ("o 011") ou pelo destino
    ("o ônibus que vai pro Derby").

    Args:
        termo: Código da linha ou parte do nome/destino.
    """
    async with SessionLocal() as session:
        lines = await transit_service.search_lines(session, termo)
    return {"termo": termo, "total": len(lines), "linhas": lines}


@tool
async def get_line_itinerary(codigo_linha: str) -> dict:
    """Retorna o itinerário (sequência de paradas) de uma linha.

    A lista pode ser longa; resuma os pontos principais em vez de repetir tudo.

    Args:
        codigo_linha: Código da linha, por exemplo "011".
    """
    async with SessionLocal() as session:
        itinerary = await transit_service.get_line_itinerary(session, codigo_linha)

    if itinerary is None:
        return {"erro": "linha_nao_encontrada", "codigo_linha": codigo_linha}

    stops = itinerary["stops"]
    return {
        "codigo_linha": itinerary["codigo_linha"],
        "variacao": itinerary["subline_descricao"],
        "total_paradas": itinerary["stop_count"],
        "origem": stops[0]["nome"] if stops else None,
        "destino": stops[-1]["nome"] if stops else None,
        "paradas": [stop["nome"] for stop in stops],
    }


@tool
async def select_line(codigo_linha: str) -> dict:
    """Registra qual linha o usuário escolheu acompanhar.

    Chame assim que o usuário indicar a linha, inclusive quando ele responder
    apenas com o número da opção de uma lista que você ofereceu.

    Args:
        codigo_linha: Código da linha escolhida, por exemplo "011".
    """
    context = current_context()

    async with SessionLocal() as session:
        line = await transit_service.get_line(session, codigo_linha)
        if line is None:
            return {"erro": "linha_nao_encontrada", "codigo_linha": codigo_linha}
        await session_service.save_selected_line(
            session, context.whatsapp_number, codigo_linha
        )

    return {"ok": True, "codigo_linha": codigo_linha, "nome": line["nome"]}


@tool
async def get_bus_eta(codigo_linha: str) -> dict:
    """Diz quanto tempo falta para o ônibus dessa linha passar na parada do usuário.

    Consulta os horários reais do Google Maps para a parada mais próxima do
    usuário nessa linha. Quando existe um veículo transmitindo GPS ao vivo, usa
    a posição dele, que é mais precisa.

    Chame esta ferramenta **toda vez** que perguntarem sobre tempo de chegada —
    nunca reaproveite uma resposta anterior, porque o ônibus se move.

    Args:
        codigo_linha: Código da linha, por exemplo "2462".
    """
    context = current_context()
    if not context.has_location:
        return {
            "erro": "sem_localizacao",
            "mensagem": "Peça a localização do usuário antes de calcular o tempo.",
        }

    async with SessionLocal() as session:
        stop = await transit_service.nearest_stop_of_line(
            session, codigo_linha, context.latitude, context.longitude
        )
        if stop is None:
            return {
                "erro": "parada_nao_encontrada",
                "codigo_linha": codigo_linha,
                "mensagem": "Essa linha não tem paradas registradas perto do usuário.",
            }
        downstream = await transit_service.downstream_stop_of_line(
            session, codigo_linha, stop.stop_id
        )

    parada = stop.nome or stop.codigo

    # Caminho preferencial quando há rastreador ao vivo: a posição real do
    # veículo bate qualquer horário programado.
    bus_location = bus_location_service.get_current_location(codigo_linha)
    if bus_location is not None:
        eta = await eta_service.calculate_eta(
            origin=bus_location,
            destination=UserLocation(latitude=stop.latitude, longitude=stop.longitude),
        )
        if eta:
            return {
                "fonte": "gps_ao_vivo",
                "codigo_linha": codigo_linha,
                "parada": parada,
                "referencia_da_parada": stop.referencia,
                "distancia_ate_a_parada_m": round(stop.distance_m),
                "distancia_do_onibus_km": eta["distance_km"],
                "faltam_minutos": eta["duration_minutes"],
                "estimativa_aproximada": bool(eta.get("note")),
            }

    if downstream is None:
        return {
            "erro": "itinerario_incompleto",
            "codigo_linha": codigo_linha,
            "mensagem": "Não há paradas adiante dessa no itinerário da linha.",
        }

    # Sem filtro de linha, de propósito. A Routes API devolve a viagem mais
    # rápida entre dois pontos e não aceita "quero esta linha": num corredor
    # movimentado ela responde com as linhas concorrentes e a escolhida nunca
    # aparece. Pedimos tudo o que sai desta parada no sentido do usuário e
    # destacamos a linha dele se estiver entre os resultados.
    departures = await departure_service.next_departures(
        origin_lat=stop.latitude,
        origin_lon=stop.longitude,
        destination_lat=downstream.latitude,
        destination_lon=downstream.longitude,
        codigo_linha=None,
        max_results=6,
    )

    if not departures:
        return {
            "erro": "sem_horarios",
            "codigo_linha": codigo_linha,
            "parada": parada,
            "mensagem": (
                "O Google não retornou nenhuma passagem nessa parada agora. "
                "Pode ser fora do horário de operação."
            ),
        }

    escolhida = next(
        (d for d in departures if d.codigo_linha.strip() == codigo_linha.strip()), None
    )

    resultado = {
        "fonte": "horarios_google",
        "codigo_linha": codigo_linha,
        "parada": parada,
        "referencia_da_parada": stop.referencia,
        "distancia_ate_a_parada_m": round(stop.distance_m),
        "proximos_na_parada": [d.as_dict() for d in departures],
    }

    if escolhida is not None:
        resultado["linha_escolhida_confirmada"] = True
        resultado["sentido"] = escolhida.headsign
        resultado["faltam_minutos"] = escolhida.minutes_from_now
        resultado["horario"] = escolhida.local_time
    else:
        resultado["linha_escolhida_confirmada"] = False
        resultado["observacao"] = (
            f"Não foi possível confirmar o horário da linha {codigo_linha} nesta "
            "parada. Os horários acima são de outras linhas que passam no mesmo "
            "ponto, no mesmo sentido."
        )

    return resultado


BASE_TOOLS = [
    find_probable_lines,
    find_nearby_stops,
    list_lines_at_stop,
    search_lines,
    get_line_itinerary,
    select_line,
    get_bus_eta,
]
