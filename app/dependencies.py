from app.services.evolution_service import EvolutionApiService

evolution_service = EvolutionApiService()

def get_evolution_service():
  return evolution_service