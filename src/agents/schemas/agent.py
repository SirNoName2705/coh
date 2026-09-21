# src/agents/schemas/agent.py
from pydantic import BaseModel, Field, ConfigDict, field_validator

class AgentResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    inner_monologue: str = Field(..., description="Deine internen Gedanken.")
    abstain: bool = Field(default=False, description="Setze dies auf True, wenn du dich der Stimme enthalten willst.")
    spoken_text: str = Field(..., description="Was du dem Rat laut sagst. Bleibt leer, wenn abstain=True.")
    proposed_agenda_items: list[str] = Field(default_factory=list)

class AgendaVote(BaseModel):
    agenda_item: str = Field(...)
    vote: bool = Field(...)
    reason: str = Field(...)

    @field_validator('vote', mode='before')
    @classmethod
    def parse_boolean(cls, v):
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'ja', 'yes', 't')
        return bool(v)

class VoteResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    inner_monologue: str = Field(...)
    votes: list[AgendaVote] = Field(...)