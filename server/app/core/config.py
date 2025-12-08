from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra="ignore" 
    )
    
    authentication_api_key: str
    evo_base_url: str
    evo_instance_name: str
    groq_api_key: str  
    user_latitude: float = -8.055455094388444
    user_longitude: float = -34.95131252286159
    openrouteservice_api_key: str
    
settings = Settings()
