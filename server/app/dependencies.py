from app.core.config import settings
from app.services.ai_service import AIService
from app.services.bus_location_service import BusLocationService
from app.services.eta_service import ETAService
from app.services.evolution_service import EvolutionApiService
from app.services.webhook_service import WebhookService

evolution_service = EvolutionApiService()
ai_service = AIService()
bus_location_service = BusLocationService()
eta_service = ETAService(api_key=settings.openrouteservice_api_key)
webhook_service = WebhookService(
    evolution_service=evolution_service,
    ai_service=ai_service,
    bus_location_service=bus_location_service,
    eta_service=eta_service,
)


def get_evolution_service() -> EvolutionApiService:
    return evolution_service


def get_ai_service() -> AIService:
    return ai_service


def get_bus_location_service() -> BusLocationService:
    return bus_location_service


def get_eta_service() -> ETAService:
    return eta_service


def get_webhook_service() -> WebhookService:
    return webhook_service
