"""Converse com o agente pelo terminal, sem WhatsApp nem Evolution API.

    uv run python scripts/chat.py

O script monta payloads no mesmo formato que a Evolution envia e os entrega ao
WebhookService real, trocando apenas o envio da resposta. Assim o caminho
exercitado é o de produção — parsing, sessão, agente e ferramentas — e não uma
simulação paralela que poderia divergir do que roda de verdade.

Comandos:
    /loc <lat> <lon>   envia uma localização (padrão: Boa Viagem)
    /reset             começa uma conversa nova
    /sair
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

from app.agent.graph import get_agent, shutdown_agent  # noqa: E402
from app.core.exceptions import AppException  # noqa: E402
from app.db.session import dispose_engine  # noqa: E402
from app.services.webhook_service import WebhookService  # noqa: E402

# Cidade Universitária (UFPE), Recife — bem servida, ótima para testes.
DEFAULT_LOCATION = (-8.04887728646683, -34.95138771773008)


class ConsoleEvolution:
    """Stand-in para a Evolution API: imprime em vez de enviar ao WhatsApp."""

    async def send_text_message(self, number: str, message: str) -> dict:
        print(f"\n\033[92m🤖 Conectese\033[0m\n{message}\n")
        return {"status": "printed"}

    async def close(self) -> None:
        return None


def text_payload(number: str, text: str) -> dict:
    return {
        "data": {
            "key": {"remoteJid": f"{number}@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": text},
        }
    }


def location_payload(number: str, lat: float, lon: float) -> dict:
    return {
        "data": {
            "key": {"remoteJid": f"{number}@s.whatsapp.net", "fromMe": False},
            "message": {
                "locationMessage": {"degreesLatitude": lat, "degreesLongitude": lon}
            },
        }
    }


async def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    number = f"5581{uuid.uuid4().int % 100000000:08d}"
    service = WebhookService(
        evolution_service=ConsoleEvolution(), agent_factory=get_agent
    )

    print("\033[1mConectese — chat local\033[0m")
    print(f"número simulado: {number}")
    print("comandos: /loc [lat lon]  ·  /reset  ·  /sair\n")

    loop = asyncio.get_running_loop()
    try:
        while True:
            try:
                line = (await loop.run_in_executor(None, input, "\033[94mvocê ›\033[0m ")).strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue

            if line in ("/sair", "/quit", "/exit"):
                break

            if line == "/reset":
                number = f"5581{uuid.uuid4().int % 100000000:08d}"
                print(f"nova conversa — número {number}\n")
                continue

            if line.startswith("/loc"):
                parts = line.split()
                try:
                    lat, lon = (
                        (float(parts[1]), float(parts[2]))
                        if len(parts) >= 3
                        else DEFAULT_LOCATION
                    )
                except ValueError:
                    print("uso: /loc <lat> <lon>\n")
                    continue
                print(f"\033[90m📍 enviando localização ({lat}, {lon})\033[0m")
                payload = location_payload(number, lat, lon)
            else:
                payload = text_payload(number, line)

            try:
                result = await service.handle(payload)
            except AppException as exc:
                print(f"\033[91mignorado/erro:\033[0m {exc}\n")
                continue

            if result.tools_used:
                print(f"\033[90m   ferramentas: {', '.join(result.tools_used)}\033[0m")
    finally:
        await shutdown_agent()
        await dispose_engine()
        print("\naté mais 👋")


if __name__ == "__main__":
    asyncio.run(main())
