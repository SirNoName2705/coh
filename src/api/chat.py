# src/api/chat.py
import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.core.llm_client import AsyncInstructorClient
from src.agents.schemas import ModeratorDecision, TurnContext
from src.orchestration.factory import StrategyFactory

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat Streaming"])

class ChatRequest(BaseModel):
    query: str
    stream: bool = True
    strategy: str = Field(default="organic_discussion")
    discussion_rounds: int = Field(default=1, ge=0, le=3)
    auto_select_agents: bool = Field(default=True)
    manual_agents: list[str] = Field(default_factory=list)

async def verify_chat_context(request: Request) -> bool:
    return True

@router.post("/message")
async def chat_message(payload: ChatRequest, request: Request, is_valid: bool = Depends(verify_chat_context)):
    llm_client = AsyncInstructorClient()
    target_agents = payload.manual_agents
    turn_instruction = "Folgt eurer Philosophie und analysiert die Anfrage."

    # Moderator nur triggern, wenn auto_select_agents aktiv ist
    if payload.auto_select_agents:
        moderator_prompt = (
            "Du bist der Moderator des 'Council of Heroes'. "
            "Wähle basierend auf dem Problem zwischen 2 und 4 Experten. "
            "Verfügbar: Dale Carnegie, Daniel Kahneman, Jack Nasher, Robert B Cialdini, Roman Braun, Thorsten Havener."
        )
        try:
            decision: ModeratorDecision = await llm_client.generate_structured_response(
                system_prompt=moderator_prompt,
                user_prompt=f"Nutzeranfrage: {payload.query}",
                response_model=ModeratorDecision
            )
            target_agents = decision.target_agents
            turn_instruction = decision.turn_instruction
        except Exception as e:
            logger.error(f"Moderator Error: {e}")
            return JSONResponse(status_code=500, content={"error": "Moderator defekt."})

    if not target_agents:
        return JSONResponse(status_code=400, content={"error": "Keine Agenten ausgewählt."})

    context = TurnContext(
        current_topic=payload.query,
        chat_history=[],
        moderator_instruction=turn_instruction,
        target_agents=target_agents
    )

    # Factory holt die richtige Strategie!
    strategy = StrategyFactory.get_strategy(payload.strategy)

    async def sse_event_generator():
        try:
            yield f"data: {json.dumps({'status': 'info', 'message': f'Gewählte Agenten: {target_agents}'})}\n\n"
            async for chunk in strategy.execute_turn_stream(context, llm_client, request):
                yield chunk
            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")