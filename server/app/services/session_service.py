"""Durable per-user state: last known location and chosen line."""

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSession

# A rider's location goes stale quickly — they walk, or ask again from a
# different street the next day. Beyond this we ask for it again.
LOCATION_MAX_AGE_SECONDS = 30 * 60


class SessionService:
    async def get(
        self, session: AsyncSession, whatsapp_number: str
    ) -> UserSession | None:
        result = await session.execute(
            select(UserSession).where(UserSession.whatsapp_number == whatsapp_number)
        )
        return result.scalar_one_or_none()

    async def save_location(
        self,
        session: AsyncSession,
        whatsapp_number: str,
        latitude: float,
        longitude: float,
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(UserSession).values(
            whatsapp_number=whatsapp_number,
            last_latitude=latitude,
            last_longitude=longitude,
            location_updated_at=now,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[UserSession.whatsapp_number],
                set_={
                    "last_latitude": stmt.excluded.last_latitude,
                    "last_longitude": stmt.excluded.last_longitude,
                    "location_updated_at": stmt.excluded.location_updated_at,
                    "updated_at": now,
                    # A new location invalidates the previous choice: the rider
                    # has moved, so the line they picked may not serve them here.
                    "selected_codigo_linha": None,
                },
            )
        )
        await session.commit()
        logger.info(f"Saved location for {whatsapp_number}: ({latitude}, {longitude})")

    async def save_selected_line(
        self, session: AsyncSession, whatsapp_number: str, codigo_linha: str
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = insert(UserSession).values(
            whatsapp_number=whatsapp_number,
            selected_codigo_linha=codigo_linha,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[UserSession.whatsapp_number],
                set_={
                    "selected_codigo_linha": stmt.excluded.selected_codigo_linha,
                    "updated_at": now,
                },
            )
        )
        await session.commit()
        logger.info(f"{whatsapp_number} selected line {codigo_linha}")

    @staticmethod
    def location_age_seconds(user_session: UserSession | None) -> int | None:
        if user_session is None or user_session.location_updated_at is None:
            return None
        updated_at = user_session.location_updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - updated_at).total_seconds())

    @classmethod
    def has_fresh_location(cls, user_session: UserSession | None) -> bool:
        age = cls.location_age_seconds(user_session)
        return age is not None and age <= LOCATION_MAX_AGE_SECONDS


session_service = SessionService()
