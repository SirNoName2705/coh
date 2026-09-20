# src/orchestration/strategies/base.py
import abc
from fastapi import Request
from src.agents.schemas import TurnContext
from src.core.llm_client import AsyncInstructorClient


class TurnStrategy(abc.ABC):
    """Abstrakte Basisklasse für alle Runden-Abläufe im Rat."""

    @abc.abstractmethod
    async def execute_turn_stream(self, context: TurnContext, llm_client: AsyncInstructorClient, request: Request):
        """Muss von jeder spezifischen Strategie implementiert werden."""
        raise NotImplementedError