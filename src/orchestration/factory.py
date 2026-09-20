# src/orchestration/factory.py
from orchestration.strategies.agenda_voting import AgendaVotingStrategy
from src.core.logger import get_logger
from src.orchestration.strategies.base import TurnStrategy
from src.orchestration.strategies.organic_discussion import OrganicDiscussionStrategy

# from src.orchestration.strategies.agenda_voting import AgendaVotingStrategy # Kommt im nächsten Schritt

logger = get_logger(__name__)


class StrategyFactory:
    @staticmethod
    def get_strategy(strategy_name: str) -> TurnStrategy:
        logger.info(f"Lade Strategie: {strategy_name}")

        if strategy_name == "agenda_voting":
            return AgendaVotingStrategy()
        elif strategy_name == "organic_discussion":
            return OrganicDiscussionStrategy()

        logger.warning(f"Strategie '{strategy_name}' unbekannt. Fallback auf organic_discussion.")
        return OrganicDiscussionStrategy()