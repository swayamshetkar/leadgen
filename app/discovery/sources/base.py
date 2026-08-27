from abc import ABC, abstractmethod
from typing import List
from app.schemas.discovery_request import DiscoveryRequest
from app.models.candidate import CandidateBusiness
from app.core.logging import get_logger


class BaseDiscoverySource(ABC):
    """
    Abstract base class for all pluggable discovery sources.
    Every source must isolate its errors and return normalized candidate businesses.
    """
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"source.{name}")

    @abstractmethod
    async def discover(self, request: DiscoveryRequest) -> List[CandidateBusiness]:
        """
        Execute discovery for the given request and return candidate business records.
        """
        pass
