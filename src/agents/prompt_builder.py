# src/agents/prompt_builder.py

class PromptBuilder:
    """Zentrale Hierarchie für alle System-Prompts und LLM-Constraints."""

    # Der globale Anti-Halluzinations-Block
    BASE_RULES = (
        "WICHTIG: Gib direkt das befüllte JSON-Datenobjekt zurück. "
        "Generiere unter keinen Umständen ein JSON-Schema (mit Wörtern wie 'properties' oder 'type'). "
        "Halte dich exakt an die JSON-Validierung."
    )

    @staticmethod
    def _build_identity(agent_name: str, persona) -> str:
        return (
            f"Du bist '{agent_name}'.\n"
            f"Deine Philosophie: {persona.core_philosophy}\n"
            f"Dein Stil: {persona.tone_of_voice}\n"
            f"Strikte Verhaltensregeln:\n{persona.constraints}\n"
        )

    @classmethod
    def organic_statement(cls, agent_name: str, persona, rag_context: str) -> str:
        return (
            f"{cls._build_identity(agent_name, persona)}\n"
            f"Verfügbares Wissen (RAG):\n{rag_context}\n\n"
            "Formuliere dein erstes Statement zur aktuellen Thematik.\n"
            f"{cls.BASE_RULES}"
        )

    @classmethod
    def organic_replik(cls, agent_name: str, persona, forum_context: str) -> str:
        return (
            f"{cls._build_identity(agent_name, persona)}\n"
            f"Bisheriger Diskurs:\n{forum_context}\n\n"
            "Reagiere auf die Aussagen deiner Vorredner aus deiner fachlichen Perspektive.\n"
            "WICHTIG: Wenn du dem Diskurs nichts Neues hinzufügen kannst, setze das Feld 'abstain' "
            "zwingend auf True und lass den 'spoken_text' leer.\n"
            f"{cls.BASE_RULES}"
        )

    @classmethod
    def agenda_statement(cls, agent_name: str, persona, rag_context: str) -> str:
        return (
            f"{cls._build_identity(agent_name, persona)}\n"
            f"Verfügbares Wissen (RAG):\n{rag_context}\n\n"
            "Formuliere dein Statement. Wenn du eine konkrete Ja/Nein-Entscheidung vom Rat erzwingen willst, "
            "füge sie als Frage unter 'proposed_agenda_items' hinzu (z.B. 'Sollen wir Taktik X anwenden?').\n"
            "WICHTIG: Wenn du nichts beizutragen hast, setze 'abstain' auf True.\n"
            f"{cls.BASE_RULES}"
        )

    @classmethod
    def agenda_voting(cls, agent_name: str, persona, agenda_text: str) -> str:
        return (
            f"{cls._build_identity(agent_name, persona)}\n"
            f"Die offizielle Agenda lautet:\n{agenda_text}\n\n"
            "Stimme über JEDEN Punkt auf der Agenda strikt ab und begründe es kurz.\n"
            f"{cls.BASE_RULES}"
        )

    @classmethod
    def document_review(cls, agent_name: str, persona, rag_context: str) -> str:
        return (
            f"{cls._build_identity(agent_name, persona)}\n"
            f"Fachwissen:\n{rag_context}\n\n"
            "Analysiere den vorliegenden Entwurf/Text des Nutzers. Erstelle detailliertes Feedback "
            "unterteilt in konkrete Aspekte und formuliere Verbesserungsvorschläge.\n"
            f"{cls.BASE_RULES}"
        )