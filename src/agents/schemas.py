#https://gemini.google.com/app/4af5ef208a00a4bd
# src/agents/schemas.py
from pydantic import BaseModel, Field, ConfigDict

class AgentResponse(BaseModel):
    """Schema for a standard conversational turn by an agent."""
    model_config = ConfigDict(strict=True)

    inner_monologue: str = Field(
        ...,
        description="Your hidden chain of thought. Use this space to process the context, plan your response, and reflect on your character's persona before speaking. This is strictly private."
    )
    spoken_text: str = Field(
        ...,
        description="The actual dialogue you contribute to the council. It must be written strictly from your character's perspective and directly address the current topic."
    )
    referenced_concepts: list[str] = Field(
        default_factory=list,
        description="A list of key concepts, entities, or domain-specific terms you explicitly mentioned in your spoken_text."
    )


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


class VoteResponse(BaseModel):
    """Schema for an agent casting a vote among discrete options."""
    model_config = ConfigDict(strict=True)

    inner_monologue: str = Field(
        ...,
        description="Your internal deliberation weighing the pros and cons of the available options before committing to a decision."
    )
    chosen_option_id: str = Field(
        ...,
        description="The exact, unique identifier of the option you are voting for."
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="A float representing your confidence in this vote, from 0.0 (completely uncertain/guessing) to 1.0 (absolutely certain)."
    )


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