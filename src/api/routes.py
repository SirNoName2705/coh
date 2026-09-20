"""
src/api/routes.py
Zentrales Modul für Chat-Interaktionen mit Moderator-Orchestrierung.
"""
import json
import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.core.logger import get_logger
from src.core.llm_client import AsyncInstructorClient
from src.agents.schemas import ModeratorDecision, TurnContext
from src.orchestration.strategies import ConsultationTurnStrategy

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat Streaming"])

class ChatRequest(BaseModel):
    query: str
    session_context: dict = {}
    stream: bool = True

async def verify_chat_context(request: Request) -> bool:
    return True

@router.post("/message")
async def chat_message(payload: ChatRequest, request: Request, is_valid: bool = Depends(verify_chat_context)):
    logger.info(f"Neuer Konzil-Turn angefragt. Stream: {payload.stream}")
    llm_client = AsyncInstructorClient()

    # 1. MODERATOR-TURN (Synchron, Blockierend, Kein Stream)
    moderator_prompt = (
        "Du bist der Moderator des 'Council of Heroes'. "
        "Verfügbare Experten: Dale Carnegie, Daniel Kahneman, Jack Nasher, Robert B Cialdini, Roman Braun, Thorsten Havener. "
        "Analysiere die Nutzeranfrage und wähle exakt 2 passende Experten aus, die sich ergänzen. "
        "Setze next_turn_type strikt auf 'consultation'."
    )

    try:
        decision: ModeratorDecision = await llm_client.generate_structured_response(
            system_prompt=moderator_prompt,
            user_prompt=f"Nutzeranfrage: {payload.query}",
            response_model=ModeratorDecision
        )
        logger.info(f"Moderator wählt Agenten: {decision.target_agents}")
    except Exception as e:
        logger.error(f"Moderator-Entscheidung fehlgeschlagen: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Moderator ausgefallen."})

    # 2. TURN CONTEXT
    context = TurnContext(
        current_topic=payload.query,
        chat_history=[],
        moderator_instruction=decision.turn_instruction,
        target_agents=decision.target_agents
    )

    strategy = ConsultationTurnStrategy()

    # 3. SSE STREAMING GENERATOR
    async def sse_event_generator():
        try:
            yield f"data: {json.dumps({'status': 'moderator_done', 'agents': decision.target_agents})}\n\n"

            async for chunk in strategy.execute_turn_stream(context, llm_client, request):
                yield chunk

            yield f"data: {json.dumps({'status': 'done'})}\n\n"

        except asyncio.CancelledError:
            logger.warning("Client hat die SSE-Verbindung abgebrochen.")
            raise
        except Exception as e:
            logger.error(f"SSE Fehler im Council-Turn: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )