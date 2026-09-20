#src/core/llm_client
"""
Core LLM Client für das "Council of Heroes" Multi-Agenten-System.
Diese Komponente orchestriert die asynchrone Kommunikation mit dem lokalen
Ollama-LLM über LiteLLM und erzwingt strikte Pydantic-Strukturen via Instructor.
"""

import asyncio
from typing import Type, TypeVar, Any

import instructor
import litellm
from litellm import acompletion
from pydantic import BaseModel

# Lokale Importe gemäß Architekturvorgaben
from src.config import get_settings
from src.core.logger import get_logger

# Definition eines generischen Typs, der strikt an Pydantic's BaseModel gebunden ist.
# Dies ermöglicht statischen Type-Checkern (Mypy, Pyright) und IDEs die
# exakte Typ-Inferenz des Rückgabewerts basierend auf dem übergebenen response_model.
T = TypeVar("T", bound=BaseModel)


class AsyncInstructorClient:
    """
    Ein asynchroner LLM-Client, der rohe Textgenerierungen in strukturierte
    Pydantic-Objekte transformiert. Entwickelt für die nahtlose und nebenläufige
    Kommunikation in lokalen Multi-Agenten-Umgebungen (z.B. RTX 4090 Host).
    """

    def __init__(self) -> None:
        """
        Initialisiert den Client, lädt die Systemkonfiguration und patcht LiteLLM
        mit den Metaprogrammierungs-Funktionalitäten von Instructor.
        """
        # Laden der globalen Konfiguration
        self.config = get_settings()

        # Initialisierung des klassenspezifischen Loggers für Observability
        self.logger = get_logger(__name__)

        # Initialisierung des asynchronen Instructor-Clients für LiteLLM.
        # Mode.JSON wird explizit verwendet, da Ollama als lokaler Host
        # bei der nativen OpenAI Tool-Calling-Spezifikation (Mode.TOOLS)
        # zu unzuverlässigen Ergebnissen führen kann. Mode.JSON modifiziert
        # stattdessen den System-Prompt und erzwingt valides JSON auf Syntax-Ebene.
        self.client = instructor.from_litellm(
            acompletion,
            mode=instructor.Mode.JSON
        )

    async def generate_structured_response(
            self,
            system_prompt: str,
            user_prompt: str,
            response_model: Type[T]
    ) -> T:
        """
        Sendet eine asynchrone Anfrage an das lokale LLM und garantiert die
        Rückgabe einer validierten Instanz des spezifizierten Pydantic-Modells.

        Diese Methode handhabt vollautomatisch Netzwerkabbrüche, Timeouts sowie
        JSON-Schema-Validierungsfehler durch ein in Instructor integriertes
        Retry-System (Re-Prompting mit Fehlermeldung).

        Argumente:
            system_prompt (str): Der System-Kontext, der das Verhalten des Agenten definiert.
            user_prompt (str): Der spezifische Input oder die Aufgabenstellung.
            response_model (Type[T]): Die Pydantic-Klasse, die die Struktur definiert.

        Rückgabe:
            T: Eine strikt typisierte Instanz des übergebenen Pydantic-Modells.

        Exceptions:
            Reicht litellm- oder instructor-Ausnahmen an den Aufrufer weiter,
            nachdem sie ordnungsgemäß geloggt wurden.
        """

        self.logger.info(
            f"Starte asynchronen LLM-Aufruf. Modell: '{self.config.llm_model_name}', "
            f"Ziel-Schema: '{response_model.__name__}'."
        )

        try:
            response: T = await self.client.chat.completions.create(
                model=self.config.llm_model_name,
                api_base=self.config.llm_base_url,
                response_model=response_model,
                max_retries=self.config.max_retries,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            self.logger.info(
                f"LLM-Aufruf erfolgreich abgeschlossen. Schema '{response_model.__name__}' "
                f"wurde strikt konform instanziiert."
            )
            return response

        except litellm.exceptions.Timeout as e:
            self.logger.error(
                f"Timeout beim Zugriff auf Ollama ({self.config.llm_base_url}). "
                f"Das Modell hat in der vorgegebenen Zeit nicht geantwortet. "
                f"Möglicher KV-Cache Überlauf oder GPU-Überlastung. Details: {str(e)}"
            )
            raise

        except litellm.exceptions.APIConnectionError as e:
            self.logger.error(
                f"Kritischer Verbindungsfehler zur Ollama-API unter {self.config.llm_base_url}. "
                f"Der Host ist nicht erreichbar oder die TCP-Verbindung wurde abgewiesen. "
                f"Details: {str(e)}"
            )
            raise

        except instructor.exceptions.InstructorRetryException as e:
            self.logger.error(
                f"Fehlschlag der strukturierten Generierung. Das LLM konnte das "
                f"Pydantic-Schema '{response_model.__name__}' auch nach {e.n_attempts} "
                f"Korrekturversuchen nicht korrekt ausfüllen. "
                f"Letzter Fehler: {str(e)}"
            )
            raise

        except Exception as e:
            self.logger.error(
                f"Unerwarteter, systemkritischer Fehler im AsyncInstructorClient "
                f"während der Modell-Evaluation: {str(e)}"
            )
            raise