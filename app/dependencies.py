from app.services.evolution_service import EvolutionApiService
from app.services.ai_service import AIService

evolution_service = EvolutionApiService()
ai_service = AIService()

def get_evolution_service():
    return evolution_service

def get_ai_service():
    return ai_service
