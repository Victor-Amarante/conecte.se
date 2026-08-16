import httpx
from loguru import logger

from app.core.config import settings
from app.core.exceptions import MessageSendError
from app.utils.whatsapp_format import to_whatsapp


class EvolutionApiService:
    def __init__(self) -> None:
        self.api_key = settings.authentication_api_key
        self.base_url = settings.evo_base_url
        self.instance_name = settings.evo_instance_name
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=self.headers, timeout=15.0)
        return self._client

    async def send_text_message(self, user_cellphone: str, message: str) -> dict:
        payload = {
            "number": user_cellphone,
            # O modelo escreve Markdown; o WhatsApp tem sintaxe própria.
            "text": to_whatsapp(message),
        }

        url = f"{self.base_url}/message/sendText/{self.instance_name}"
        client = await self._get_client()

        try:
            response = await client.post(url, json=payload)
        except httpx.RequestError as e:
            raise MessageSendError(f"Connection error: {e}") from e

        # Evolution answers 201 on send, but accept any 2xx: a 200 is a
        # delivered message too, and treating it as a failure would retry a
        # message the user already got.
        if not 200 <= response.status_code < 300:
            raise MessageSendError(f"HTTP {response.status_code}: {response.text}")

        logger.info(f"Message sent to {user_cellphone}")
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
