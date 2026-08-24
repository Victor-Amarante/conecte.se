from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class WebhookPayloadError(AppException):
    """Raised when the webhook payload is invalid or missing required fields."""

    def __init__(self, reason: str) -> None:
        super().__init__(message=reason, status_code=400)
        self.reason = reason


class WebhookIgnoredError(AppException):
    """Raised when the webhook message should be ignored (group, bot, LID, etc.)."""

    def __init__(self, reason: str) -> None:
        super().__init__(message=reason, status_code=200)
        self.reason = reason


class ExternalServiceError(AppException):
    """Raised when an external API call fails (Evolution, OpenRouteService, etc.)."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(
            message=f"{service} error: {detail}",
            status_code=502,
        )
        self.service = service
        self.detail = detail


class MessageSendError(ExternalServiceError):
    """Raised when sending a message through Evolution API fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(service="EvolutionAPI", detail=detail)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    logger.error(f"{exc.__class__.__name__}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "detail": exc.message},
    )


async def webhook_ignored_handler(_request: Request, exc: WebhookIgnoredError) -> JSONResponse:
    # Descartar em silêncio esconde mensagens que o passageiro mandou e nunca
    # foram respondidas — foi assim que o caso do LID sem `senderPn` passou
    # despercebido, visível só porque o usuário reclamou de ter que reenviar.
    # Grupos e eco do próprio bot são ruído esperado; o resto merece atenção.
    reason = exc.reason
    if "group" in reason or "bot" in reason:
        logger.debug(f"Webhook ignorado: {reason}")
    else:
        logger.warning(f"Mensagem do usuário DESCARTADA: {reason}")

    return JSONResponse(
        status_code=200,
        content={"status": "ignored", "reason": reason},
    )
