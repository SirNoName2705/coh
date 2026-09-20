# src/agents/executor.py
import abc
import logging
import time
from typing import Generic, TypeVar

from pydantic import BaseModel

# Korrigierte Import-Pfade
from src.core.llm_client import AsyncInstructorClient
from src.agents.schemas import AgentResponse, ConsultationResponse, VoteResponse

logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse", bound=BaseModel)

# Globale Instanz des LLM-Clients
llm_client = AsyncInstructorClient()

class AgentCommand(abc.ABC, Generic[TResponse]):
    """Abstrakte Basisklasse für alle Agentenkommandos."""

    def __init__(
        self,
        agent_name: str,
        context: str,
        user_prompt: str,
    ) -> None:
        self.agent_name = agent_name
        self.context = context
        self.user_prompt = user_prompt

    @abc.abstractmethod
    def get_response_model(self) -> type[TResponse]:
        """Gibt das Ziel-Pydantic-Modell für die Strukturierung zurück."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_system_prompt(self) -> str:
        """Konstruiert den System-Prompt inklusive RAG-Wissensbasis."""
        raise NotImplementedError

    async def execute(self) -> TResponse:
        """Führt den asynchronen Inferenzaufruf aus und validiert das Ergebnis."""
        response_model = self.get_response_model()
        system_prompt = self.get_system_prompt()
        start_time = time.perf_counter()

        logger.info(
            "Starte %s für Agent '%s'",
            self.__class__.__name__,
            self.agent_name,
        )

        try:
            # Hier nutzen wir nun die saubere Methode aus llm_client.py!
            response = await llm_client.generate_structured_response(
                system_prompt=system_prompt,
                user_prompt=f"Identität: {self.agent_name}\nBenutzervorgabe: {self.user_prompt}",
                response_model=response_model
            )

            execution_time = time.perf_counter() - start_time
            logger.info(
                "Kommando %s für Agent '%s' erfolgreich beendet in %.3f s",
                self.__class__.__name__,
                self.agent_name,
                execution_time,
            )
            return response

        except Exception as exc:
            execution_time = time.perf_counter() - start_time
            logger.error(
                "Ausführungsfehler in %s für Agent '%s' nach %.3f s: %s",
                self.__class__.__name__,
                self.agent_name,
                execution_time,
                str(exc),
                exc_info=True,
            )
            raise


class SpeechCommand(AgentCommand[AgentResponse]):
    """Kommando zur Generierung rhetorischer Debattenbeiträge."""

    def get_response_model(self) -> type[AgentResponse]:
        return AgentResponse

    def get_system_prompt(self) -> str:
        return (
            f"Du agierst als Ratsmitglied '{self.agent_name}'. "
            "Formuliere einen rhetorisch prägnanten Redebeitrag für das Konzil.\n\n"
            f"Abgerufener Wissenskontext (RAG):\n{self.context}\n\n"
            "Lege deine Absicht und deine Argumentation präzise dar. "
            "Nutze den 'inner_monologue' für deine Gedanken."
            "WICHTIG: Gib direkt das befüllte JSON-Datenobjekt zurück. "
            "Generiere unter keinen Umständen ein JSON-Schema (mit Wörtern wie 'properties' oder 'type')."
        )


class ConsultationCommand(AgentCommand[ConsultationResponse]):
    """Kommando für analytische Expertise und Risikoeinschätzungen."""

    def get_response_model(self) -> type[ConsultationResponse]:
        return ConsultationResponse

    def get_system_prompt(self) -> str:
        return (
            f"Du bist der Fachberater '{self.agent_name}' im Konzil. "
            "Erstelle eine analytische Handlungsempfehlung auf Basis des vorliegenden Wissens.\n\n"
            f"Strategischer Kontext (RAG):\n{self.context}\n\n"
            "Nutze den 'inner_monologue' für deine Analyse, bevor du antwortest."
        )


class VoteCommand(AgentCommand[VoteResponse]):
    """Kommando zur Abgabe eines formalen Votums."""

    def get_response_model(self) -> type[VoteResponse]:
        return VoteResponse

    def get_system_prompt(self) -> str:
        return (
            f"Du nimmst als Ratsmitglied '{self.agent_name}' an einer formalen Abstimmung teil.\n\n"
            f"Entscheidungsgrundlage (RAG):\n{self.context}\n\n"
            "Begründe dein Stimmverhalten im 'inner_monologue' präzise, bevor du die 'chosen_option_id' wählst."
        )