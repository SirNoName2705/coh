# src/agents/schemas/consultation.py
from pydantic import BaseModel, Field, ConfigDict

class ConsultationFeedback(BaseModel):
    model_config = ConfigDict(strict=True)
    aspect: str = Field(..., description="Aspekt des Textes (z.B. Tonalität, Persuasion).")
    critique: str = Field(..., description="Deine Analyse.")
    improvement_suggestion: str = Field(..., description="Konkreter Formulierungsvorschlag.")

class ConsultationResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    inner_monologue: str = Field(...)
    feedbacks: list[ConsultationFeedback] = Field(...)
    overall_verdict: str = Field(..., description="z.B. 'Genehmigt', 'Überarbeitung nötig'")