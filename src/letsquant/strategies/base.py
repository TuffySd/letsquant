from abc import ABC, abstractmethod
from typing import List, Optional

from letsquant.models import Bar, Position, Signal


class Strategy(ABC):
    @abstractmethod
    def generate(
        self,
        symbol: str,
        history: List[Bar],
        position: Optional[Position],
    ) -> Signal:
        raise NotImplementedError
