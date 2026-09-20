import yaml
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.config import get_settings

logger = get_logger(__name__)


class PersonaConfig(BaseModel):
    """Definiert die strukturierte Charakter-Basis eines Ratsmitglieds."""
    core_philosophy: str = Field(..., description="Die grundlegende Weltanschauung der Persona.")
    tone_of_voice: str = Field(..., description="Spezifische rhetorische Stilmittel und Tonalität.")
    constraints: str = Field(..., description="Strikte Verhaltensregeln, die nicht gebrochen werden dürfen.")


class PersonaManager:
    """Verwaltet das Laden und Cachen der Persona-Definitionen."""
    _cache: dict[str, PersonaConfig] = {}

    @classmethod
    async def get_persona(cls, author_slug: str) -> PersonaConfig:
        if author_slug in cls._cache:
            return cls._cache[author_slug]

        settings = get_settings()
        yaml_path = Path(settings.data_dir) / "authors" / author_slug / "persona.yaml"

        if not yaml_path.exists():
            logger.warning(f"Keine persona.yaml für '{author_slug}' gefunden. Nutze neutralen Fallback.")
            return PersonaConfig(
                core_philosophy="Du bist ein analytisches, weises Mitglied des Rates.",
                tone_of_voice="Du sprichst formell, präzise und respektvoll.",
                constraints="Bleibe sachlich. Verweise ausschließlich auf den bereitgestellten Kontext."
            )

        def _read_yaml():
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        try:
            # async-wrapper für blockierendes File-I/O
            data = await asyncio.to_thread(_read_yaml)
            persona = PersonaConfig(**data)
            cls._cache[author_slug] = persona
            logger.info(f"Persona für '{author_slug}' erfolgreich geladen und gecached.")
            return persona

        except Exception as e:
            logger.error(f"Fehler beim Laden/Parsen der persona.yaml für '{author_slug}': {e}", exc_info=True)
            raise