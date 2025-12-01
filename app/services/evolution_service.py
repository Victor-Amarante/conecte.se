import requests
from app.core.config import settings


class EvolutionApiService:
  def __init__(self):
    self.api_key = settings.authentication_api_key
    self.headers = {
      "apikey": self.api_key,
      "Content-Type": "application/json"
    }
  
  def send_text_message(self, user_cellphone: str, message: str):
    payload = {
      "number": user_cellphone,
      "text": message,
    }
    
    try:
      response = requests.post(
        url=f"{settings.evo_base_url}/message/sendText/{settings.evo_instance_name}",
        headers=self.headers,
        json=payload
      )
      
      if response.status_code != 201:
        raise Exception(f"Error sending text message: {response.text}")
      
      return response.json()
    except Exception as e:
      raise Exception(f"Error sending text message: {e}")
