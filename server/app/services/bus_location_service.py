import time
from typing import Optional

from loguru import logger

from app.schemas.location import BusLocation

# Key used when a tracker reports without saying which line it is running.
UNKNOWN_LINE = "__unknown__"


class BusLocationService:
    """Latest GPS fix per line, held in memory.

    Keyed by line code so several trackers can report at once; a tracker that
    does not identify its line lands under ``UNKNOWN_LINE`` and is used as the
    fallback for any query, which keeps the current single-bus setup working.
    """

    LOCATION_MAX_AGE_SECONDS = 300

    def __init__(self) -> None:
        self._locations: dict[str, BusLocation] = {}

    def update_location(
        self, location: BusLocation, codigo_linha: str | None = None
    ) -> None:
        if not location.timestamp:
            location.timestamp = int(time.time())

        key = codigo_linha or UNKNOWN_LINE
        self._locations[key] = location
        logger.info(
            f"Bus location updated [line={key}]: lat={location.latitude}, "
            f"lon={location.longitude}, timestamp={location.timestamp}"
        )

    def _fresh(self, key: str) -> Optional[BusLocation]:
        location = self._locations.get(key)
        if location is None:
            return None

        age = int(time.time()) - (location.timestamp or 0)
        if age > self.LOCATION_MAX_AGE_SECONDS:
            logger.warning(
                f"Bus location for {key} is too old: {age}s "
                f"(max: {self.LOCATION_MAX_AGE_SECONDS}s)"
            )
            return None
        return location

    def get_current_location(
        self, codigo_linha: str | None = None
    ) -> Optional[BusLocation]:
        """The freshest fix for a line, falling back to the unlabelled tracker."""
        if codigo_linha:
            location = self._fresh(codigo_linha)
            if location is not None:
                return location

        location = self._fresh(UNKNOWN_LINE)
        if location is None and not self._locations:
            logger.warning("No bus location available")
        return location

    def has_location(self, codigo_linha: str | None = None) -> bool:
        return self.get_current_location(codigo_linha) is not None

    def tracked_lines(self) -> list[str]:
        return [
            key
            for key in self._locations
            if key != UNKNOWN_LINE and self._fresh(key) is not None
        ]
