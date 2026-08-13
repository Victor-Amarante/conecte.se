from app.agent.graph import get_agent
from app.services.bus_location_service import BusLocationService
from app.services.departure_service import DepartureService
from app.services.eta_service import ETAService
from app.services.evolution_service import EvolutionApiService
from app.services.registry import (
    bus_location_service,
    departure_service,
    eta_service,
    evolution_service,
)
from app.services.transit_service import TransitService, transit_service
from app.services.webhook_service import WebhookService

webhook_service = WebhookService(
    evolution_service=evolution_service,
    agent_factory=get_agent,
)


def get_evolution_service() -> EvolutionApiService:
    return evolution_service


def get_bus_location_service() -> BusLocationService:
    return bus_location_service


def get_eta_service() -> ETAService:
    return eta_service


def get_departure_service() -> DepartureService:
    return departure_service


def get_transit_service() -> TransitService:
    return transit_service


def get_webhook_service() -> WebhookService:
    return webhook_service
