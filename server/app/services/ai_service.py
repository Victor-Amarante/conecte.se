from langchain_groq import ChatGroq
from app.core.config import settings
from app.prompts.whatsapp_system_prompt import SYSTEM_PROMPT



class AIService:
  def __init__(self):
    self.model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.0, api_key=settings.groq_api_key)
    
  async def generate_response(self, user_message: str):
    messages = [
      ("system", SYSTEM_PROMPT),
      ("human", user_message),
    ]
    response = await self.model.ainvoke(messages)
    
    return response.content
