import time
from typing import Optional

from loguru import logger

from app.schemas.location import BusLocation


class BusLocationService:
    LOCATION_MAX_AGE_SECONDS = 300

    def __init__(self) -> None:
        self._current_location: Optional[BusLocation] = None

    def update_location(self, location: BusLocation) -> None:
        if not location.timestamp:
            location.timestamp = int(time.time())

        self._current_location = location
        logger.info(
            f"Bus location updated: lat={location.latitude}, "
            f"lon={location.longitude}, timestamp={location.timestamp}"
        )

    def get_current_location(self) -> Optional[BusLocation]:
        if not self._current_location:
            logger.warning("No bus location available")
            return None

        current_time = int(time.time())
        location_age = current_time - (self._current_location.timestamp or 0)

        if location_age > self.LOCATION_MAX_AGE_SECONDS:
            logger.warning(
                f"Bus location is too old: {location_age}s "
                f"(max: {self.LOCATION_MAX_AGE_SECONDS}s)"
            )
            return None

        logger.debug(
            f"Bus location is valid: age={location_age}s, "
            f"lat={self._current_location.latitude}, "
            f"lon={self._current_location.longitude}"
        )
        return self._current_location

    def has_location(self) -> bool:
        return self.get_current_location() is not None
