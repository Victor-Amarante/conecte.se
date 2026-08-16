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
from app.services.geocoding_service import Place
from app.services.registry import (
    bus_location_service,
    departure_service,
    eta_service,
    geocoding_service,
    journey_service,
)
from app.services.session_service import session_service
from app.services.transit_service import transit_service


@tool
async def plan_trip(destino: str = "") -> dict:
    """Descobre qual ônibus o usuário precisa pegar para chegar a um destino.

    **Esta é a ferramenta principal e a única fonte de horários.** Use sempre
    que o usuário disser para onde quer ir ("quero ir pro Shopping Recife",
    "como chego no TI Barro") e também quando ele perguntar de novo sobre o
    tempo ("e agora?", "quanto tempo falta?") — nesse caso deixe `destino`
    vazio e ela replaneja a mesma viagem com horários atualizados.

    Args:
        destino: Para onde o usuário quer ir, como ele escreveu. Pode ser um
            ponto conhecido ("Shopping Recife"), um terminal ("TI Barro") ou um
            endereço ("Rua da Aurora, 200"). Deixe vazio para reusar o destino
            que o usuário já informou nesta conversa.
    """
    context = current_context()
    if not context.has_location:
        return {
            "erro": "sem_localizacao",
            "mensagem": "Peça a localização do usuário antes de planejar a viagem.",
        }

    place: Place | None = None

    if destino and destino.strip():
        place = await geocoding_service.geocode(destino)
        if place is None:
            return {
                "erro": "destino_nao_encontrado",
                "destino": destino,
                "mensagem": (
                    "Não consegui localizar esse destino na Região Metropolitana "
                    "do Recife. Peça uma referência melhor: bairro, rua com "
                    "número ou um ponto conhecido."
                ),
            }
        async with SessionLocal() as session:
            await session_service.save_destination(
                session,
                context.whatsapp_number,
                place.endereco,
                place.latitude,
                place.longitude,
            )
    else:
        # Replanejamento: mesma viagem, horários novos. É isto que mantém as
        # respostas coerentes entre si — recalcular pela parada mais próxima
        # daria outro embarque e outro horário para o mesmo trajeto.
        async with SessionLocal() as session:
            user_session = await session_service.get(session, context.whatsapp_number)
        if not session_service.has_fresh_destination(user_session):
            return {
                "erro": "sem_destino",
                "mensagem": "Pergunte ao usuário para onde ele quer ir.",
            }
        place = Place(
            latitude=user_session.destino_latitude,
            longitude=user_session.destino_longitude,
            endereco=user_session.destino_texto or "seu destino",
        )

    resultado = await journey_service.plan(
        origin_lat=context.latitude,
        origin_lon=context.longitude,
        destination_lat=place.latitude,
        destination_lon=place.longitude,
    )

    if resultado.a_pe_metros is not None:
        # O Google não sugere ônibus para trajeto curto, mas o passageiro pode
        # querer ir de ônibus de todo jeito — bagagem, mobilidade, chuva, sol.
        # Buscamos a linha direta nos nossos próprios itinerários.
        async with SessionLocal() as session:
            diretas = await transit_service.find_direct_lines(
                session,
                origin_lat=context.latitude,
                origin_lon=context.longitude,
                destination_lat=place.latitude,
                destination_lon=place.longitude,
            )
        return {
            "destino": place.endereco,
            "a_pe": True,
            "distancia_m": resultado.a_pe_metros,
            "minutos_a_pe": resultado.a_pe_minutos,
            "linhas_de_onibus": diretas,
            "mensagem": (
                "O destino é perto e dá para ir a pé, mas as linhas acima também "
                "levam até lá. Ofereça as duas possibilidades."
            ),
        }

    if resultado.vazio:
        # Mesma rede de segurança: o Google pode não achar rota por horário ou
        # por cobertura, e ainda assim existir linha direta no itinerário.
        async with SessionLocal() as session:
            diretas = await transit_service.find_direct_lines(
                session,
                origin_lat=context.latitude,
                origin_lon=context.longitude,
                destination_lat=place.latitude,
                destination_lon=place.longitude,
            )
        if diretas:
            return {
                "destino": place.endereco,
                "sem_horario_google": True,
                "linhas_de_onibus": diretas,
                "mensagem": (
                    "Não consegui os horários agora, mas estas linhas fazem o "
                    "trajeto. Ofereça-as sem afirmar horário."
                ),
            }
        return {
            "erro": "sem_rota",
            "destino": place.endereco,
            "mensagem": "Não encontrei linha de ônibus para esse trajeto agora.",
        }

    async with SessionLocal() as session:
        await journey_service.enrich_stops(session, resultado.journeys)

    opcoes = [j.as_dict() for j in resultado.journeys]

    # Se houver rastreador transmitindo a posição da linha recomendada, ela vale
    # mais que o horário programado — é onde o veículo está de fato agora.
    primeiro = resultado.journeys[0].legs[0]
    ao_vivo = bus_location_service.get_current_location(primeiro.codigo_linha)
    if ao_vivo is not None and primeiro.embarque_lat is not None:
        eta = await eta_service.calculate_eta(
            origin=ao_vivo,
            destination=UserLocation(
                latitude=primeiro.embarque_lat, longitude=primeiro.embarque_lon
            ),
        )
        if eta:
            opcoes[0]["gps_ao_vivo"] = {
                "codigo_linha": primeiro.codigo_linha,
                "distancia_do_onibus_km": eta["distance_km"],
                "faltam_minutos": eta["duration_minutes"],
                "estimativa_aproximada": bool(eta.get("note")),
            }

    return {
        "destino": place.endereco,
        "total_opcoes": len(opcoes),
        "opcoes": opcoes,
    }


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
async def get_stop_departures() -> dict:
    """Próximas passagens de ônibus na parada mais próxima do usuário.

    Use quando ele quiser saber o movimento do ponto onde está, sem ter dito
    para onde vai. Devolve o que realmente sai daquela parada, **de todas as
    linhas** — não é possível consultar uma linha isolada.

    Se ele quiser saber sobre uma linha específica, verifique se ela aparece em
    `proximos`. Se não aparecer, diga com franqueza que não confirmou e sugira
    informar o destino, que dá uma resposta melhor.
    """
    context = current_context()
    if not context.has_location:
        return {
            "erro": "sem_localizacao",
            "mensagem": "Peça a localização do usuário antes de consultar horários.",
        }

    async with SessionLocal() as session:
        stops = await transit_service.find_nearby_stops(
            session, context.latitude, context.longitude, radius_m=600, limit=1
        )
        if not stops:
            return {
                "erro": "sem_parada",
                "mensagem": "Nenhuma parada encontrada perto do usuário.",
            }
        stop = stops[0]
        # Um ponto adiante serve de destino para o roteador: sem ele o Google
        # não tem viagem para calcular e não devolve partida nenhuma.
        lines = await transit_service.list_lines_at_stop(session, stop.stop_id)
        downstream = None
        for line in lines:
            downstream = await transit_service.downstream_stop_of_line(
                session, line["codigo_linha"], stop.stop_id
            )
            if downstream is not None:
                break

    if downstream is None:
        return {
            "erro": "itinerario_incompleto",
            "parada": stop.nome or stop.codigo,
            "mensagem": "Não há paradas adiante desta no itinerário.",
        }

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
            "parada": stop.nome or stop.codigo,
            "mensagem": (
                "Nenhuma passagem prevista nessa parada agora. Pode ser fora do "
                "horário de operação."
            ),
        }

    return {
        "parada": stop.nome or stop.codigo,
        "referencia_da_parada": stop.referencia,
        "distancia_m": round(stop.distance_m),
        "proximos": [d.as_dict() for d in departures],
    }


BASE_TOOLS = [
    plan_trip,
    find_probable_lines,
    find_nearby_stops,
    list_lines_at_stop,
    search_lines,
    get_line_itinerary,
    select_line,
    get_stop_departures,
]
