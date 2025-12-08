from app.services.evolution_service import EvolutionApiService
from app.services.ai_service import AIService
from app.services.bus_location_service import BusLocationService
from app.services.eta_service import ETAService


evolution_service = EvolutionApiService()
ai_service = AIService()
bus_location_service = BusLocationService()
eta_service = ETAService()


def get_evolution_service():
    return evolution_service

def get_ai_service():
    return ai_service

def get_bus_location_service():
    return bus_location_service

def get_eta_service():
    return eta_service