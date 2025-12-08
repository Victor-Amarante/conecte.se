from langchain_groq import ChatGroq
from app.core.config import settings
from app.prompts.whatsapp_system_prompt import SYSTEM_PROMPT
from typing import Optional

class AIService:
  def __init__(self):
    self.model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0, api_key=settings.groq_api_key)
    
  async def generate_response(self, user_message: str, eta_data: Optional[dict] = None):
    context_message = user_message
    
    if eta_data:
      eta_context = (
          f"\n\n[DADOS DO SISTEMA - Use estes dados na resposta]\n"
          f"Distância: {eta_data['distance_km']} km\n"
          f"Tempo estimado: {eta_data['duration_minutes']} minutos\n"
          f"Tempo em segundos: {eta_data['duration_seconds']} segundos"
      )
      
      if eta_data.get("note"):
        eta_context += f"\nNota: {eta_data['note']}"
      context_message = user_message + eta_context
        
    messages = [
      ("system", SYSTEM_PROMPT),
      ("human", context_message),
    ]
    
    response = await self.model.ainvoke(messages)
    
    return response.content
