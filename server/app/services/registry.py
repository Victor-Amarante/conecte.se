"""Instâncias únicas dos serviços de aplicação.

Fica num módulo próprio, sem importar nada de ``app.agent``, para que tanto as
ferramentas do agente quanto as dependências do FastAPI possam importá-lo sem
ciclo — e, principalmente, sem depender da *ordem* em que os módulos foram
importados.

A versão anterior injetava esses serviços nas ferramentas por efeito colateral
de importar ``app.dependencies``. Quem usasse o agente sem passar por lá (um
script, um teste) recebia ferramentas mudas, falhando em silêncio.
"""

from app.core.config import settings
from app.services.bus_location_service import BusLocationService
from app.services.departure_service import DepartureService
from app.services.eta_service import ETAService
from app.services.evolution_service import EvolutionApiService
from app.services.geocoding_service import GeocodingService
from app.services.journey_service import JourneyService

evolution_service = EvolutionApiService()
bus_location_service = BusLocationService()
eta_service = ETAService(api_key=settings.google_maps_api_key)
departure_service = DepartureService(api_key=settings.google_maps_api_key)
geocoding_service = GeocodingService(api_key=settings.google_maps_api_key)
journey_service = JourneyService(api_key=settings.google_maps_api_key)


async def close_all() -> None:
    await evolution_service.close()
    await eta_service.close()
    await departure_service.close()
    await geocoding_service.close()
    await journey_service.close()
