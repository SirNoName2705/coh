# src/api/routes.py
import json
import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.core.logger import get_logger
from src.core.llm_client import AsyncInstructorClient
from src.agents.schemas import ModeratorDecision, TurnContext
from src.orchestration.strategies import OrganicCouncilStrategy

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat Streaming"])

class ChatRequest(BaseModel):
    query: str
    stream: bool = True

async def verify_chat_context(request: Request) -> bool:
    return True

@router.post("/message")
async def chat_message(payload: ChatRequest, request: Request, is_valid: bool = Depends(verify_chat_context)):
    llm_client = AsyncInstructorClient()

    moderator_prompt = (
        "Du bist der Moderator des 'Council of Heroes'. "
        "Analysiere das Problem und wähle exakt 2 Experten, die sich am stärksten ergänzen oder widersprechen. "
        "Verfügbar: Dale Carnegie, Daniel Kahneman, Jack Nasher, Robert B Cialdini, Roman Braun, Thorsten Havener. "
        "Setze next_turn_type strikt auf 'organic_discussion'."
    )

    try:
        decision: ModeratorDecision = await llm_client.generate_structured_response(
            system_prompt=moderator_prompt,
            user_prompt=f"Nutzeranfrage: {payload.query}",
            response_model=ModeratorDecision
        )
    except Exception as e:
        logger.error(f"Moderator Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Moderator defekt."})

    context = TurnContext(
        current_topic=payload.query,
        chat_history=[],
        moderator_instruction=decision.turn_instruction,
        target_agents=decision.target_agents
    )

    strategy = OrganicCouncilStrategy()

    async def sse_event_generator():
        try:
            yield f"data: {json.dumps({'status': 'info', 'message': f'Moderator wählt: {decision.target_agents}'})}\n\n"
            async for chunk in strategy.execute_turn_stream(context, llm_client, request):
                yield chunk
            yield f"data: {json.dumps({'status': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream"
    )