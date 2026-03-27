from typing import Optional

from langchain_groq import ChatGroq
from loguru import logger

from app.core.config import settings
from app.prompts.whatsapp_system_prompt import SYSTEM_PROMPT


class AIService:
    def __init__(self) -> None:
        self.model = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.0,
            api_key=settings.groq_api_key,
        )

    async def generate_response(
        self, user_message: str, eta_data: Optional[dict] = None
    ) -> str:
        if eta_data:
            if not isinstance(eta_data, dict) or not eta_data.get("distance_km") or not eta_data.get("duration_minutes"):
                logger.warning(f"Invalid ETA data: {eta_data}, treating as unavailable")
                eta_data = None

        if eta_data:
            data_context = (
                f"\n\n[DADOS DO SISTEMA ATUAL]\n"
                f"Distância: {eta_data['distance_km']} km\n"
                f"Tempo estimado: {eta_data['duration_minutes']} minutos\n"
                f"Tempo em segundos: {eta_data['duration_seconds']} segundos"
            )
            if eta_data.get("note"):
                data_context += f"\nNota: {eta_data['note']}"

            logger.debug(
                f"Providing ETA data to AI: distance={eta_data['distance_km']}km, "
                f"duration={eta_data['duration_minutes']}min"
            )
        else:
            data_context = (
                f"\n\n[DADOS DO SISTEMA ATUAL]\n"
                f"Status: INDISPONÍVEL / SEM SINAL GPS 🔴\n"
                f"Ação recomendada: Informe ao usuário que está sincronizando.\n"
            )
            logger.debug("No ETA data available, informing AI to say synchronizing")

        full_user_message = f"{user_message}{data_context}"

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", full_user_message),
        ]

        try:
            response = await self.model.ainvoke(messages)
            logger.debug(f"AI response generated: {response.content[:100]}...")
            return response.content
        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            if eta_data:
                return (
                    f"O ônibus está a {eta_data['distance_km']} km e deve chegar "
                    f"em cerca de {eta_data['duration_minutes']} minutos 🚌"
                )
            return "Estou sincronizando a localização agora 🛰️. Tente novamente em instantes!"
