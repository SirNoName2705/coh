# src/agents/schemas/orchestration.py
from pydantic import BaseModel, Field, ConfigDict

class ModeratorDecision(BaseModel):
    model_config = ConfigDict(strict=True)
    reasoning: str = Field(...)
    next_turn_type: str = Field(...)
    target_agents: list[str] = Field(...)
    turn_instruction: str = Field(...)

class TurnContext(BaseModel):
    model_config = ConfigDict(strict=True)
    current_topic: str = Field(...)
    chat_history: list[str] = Field(default_factory=list)
    moderator_instruction: str = Field(...)
    target_agents: list[str] = Field(...)
    draft_document: str | None = Field(default=None)