#https://gemini.google.com/app/4af5ef208a00a4bd
# src/agents/schemas.py
from pydantic import BaseModel, Field, ConfigDict, field_validator


class AgentResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    inner_monologue: str = Field(..., description="Deine internen Gedanken.")
    abstain: bool = Field(default=False, description="Setze dies auf True, wenn du dich der Stimme enthalten willst, weil du dem Diskurs nichts Neues hinzufügen kannst.")
    spoken_text: str = Field(..., description="Was du dem Rat laut sagst. Bleibt leer, wenn abstain=True.")
    proposed_agenda_items: list[str] = Field(default_factory=list)


class ConsultationFeedback(BaseModel):
    """Schema for a single piece of constructive feedback on a document or proposal."""
    model_config = ConfigDict(strict=True)

    aspect: str = Field(
        ...,
        description="The specific aspect, section, or metric of the draft being reviewed (e.g., 'Tone', 'Technical Feasibility', 'Ethical Implications')."
    )
    critique: str = Field(
        ...,
        description="Your detailed, critical analysis and evaluation of this specific aspect."
    )
    improvement_suggestion: str = Field(
        ...,
        description="Clear, actionable advice on how to resolve the issues identified in your critique."
    )


class ConsultationResponse(BaseModel):
    """Schema for an agent providing a structured review of a draft or proposal."""
    model_config = ConfigDict(strict=True)

    inner_monologue: str = Field(
        ...,
        description="Your internal reasoning process. Evaluate the draft thoroughly based on your domain expertise before writing the formal feedback."
    )
    feedbacks: list[ConsultationFeedback] = Field(
        ...,
        description="A list of detailed feedback items addressing different aspects of the draft."
    )
    overall_verdict: str = Field(
        ...,
        description="Your final conclusion regarding the draft (e.g., 'Approved', 'Needs Revision', 'Rejected')."
    )


class AgendaVote(BaseModel):
    agenda_item: str = Field(..., description="Die genaue Ja/Nein-Frage von der Agenda.")
    vote: bool = Field(..., description="True für Ja/Zustimmen, False für Nein/Ablehnen.")
    reason: str = Field(..., description="Ein extrem kurzer Begründungssatz (max 10 Wörter).")

    @field_validator('vote', mode='before')
    @classmethod
    def parse_boolean(cls, v):
        # Fängt dumme LLM-Strings ab und macht echte Booleans draus
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'ja', 'yes', 't')
        return bool(v)


class VoteResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    inner_monologue: str = Field(..., description="Kurzes Abwägen der Agenda-Punkte.")
    votes: list[AgendaVote] = Field(..., description="Deine Stimme für JEDEN Punkt auf der aktuellen Agenda.")


class ModeratorDecision(BaseModel):
    """Schema for the moderator agent controlling the flow of the council."""
    model_config = ConfigDict(strict=True)

    reasoning: str = Field(
        ...,
        description="The moderator's internal logic for deciding the next steps, based on analyzing the recent chat history and overall progress."
    )
    next_turn_type: str = Field(
        ...,
        description="The type of the upcoming turn (e.g., 'discussion', 'vote', 'consultation', 'conclusion')."
    )
    target_agents: list[str] = Field(
        ...,
        description="A list of the exact agent names that are required to participate or speak in this upcoming turn."
    )
    turn_instruction: str = Field(
        ...,
        description="Explicit instructions or constraints provided to the target_agents for what they need to accomplish in the next turn."
    )


class TurnContext(BaseModel):
    """Schema representing the state and context passed to an agent for their turn.
    (Often used internally by the system to build prompts, but defined here for consistency.)"""
    model_config = ConfigDict(strict=True)

    current_topic: str = Field(
        ...,
        description="The overarching subject or problem currently being addressed by the council."
    )
    chat_history: list[str] = Field(
        default_factory=list,
        description="A chronological list of recent dialogue and events to provide context."
    )
    moderator_instruction: str = Field(
        ...,
        description="The specific directive or question posed by the moderator for this exact moment."
    )
    target_agents: list[str] = Field(
        ...,
        description="The agents whose input is currently expected."
    )
    draft_document: str | None = Field(
        default=None,
        description="The current text of the draft or proposal under review, if the current turn requires it. Null otherwise."
    )



# src/agents/schemas.py (Auszug - füge das zu den bestehenden hinzu bzw. ersetze Agent/VoteResponse)

