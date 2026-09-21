# src/orchestration/strategies/document_review.py
import json
import asyncio
from fastapi import Request

from src.core.logger import get_logger
from src.agents.schemas import ConsultationResponse, TurnContext
from src.agents.persona import PersonaManager
from src.agents.prompt_builder import PromptBuilder
from src.rag.chroma_manager import rag_manager
from src.orchestration.strategies.base import TurnStrategy

logger = get_logger(__name__)


class DocumentReviewStrategy(TurnStrategy):
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents: return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]
        rag_results = await asyncio.gather(*[rag_manager.query_context(s, context.current_topic) for s in author_slugs])
        persona_results = await asyncio.gather(*[PersonaManager.get_persona(s) for s in author_slugs])

        yield f"data: {json.dumps({'status': 'info', 'message': 'Starte tiefgehende Dokumenten-Analyse'})}\n\n"

        for agent, rag, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent, 'status': 'starting_agent'})}\n\n"

            system_prompt = PromptBuilder.document_review(agent, persona, rag)

            try:
                stream = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=ConsultationResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": context.current_topic}],
                    stream=True, api_base=llm_client.config.llm_base_url
                )
                async for chunk in stream:
                    if await request.is_disconnected(): return

                    # Mapping für das UI, damit es wie 'spoken_text' aussieht
                    dump = chunk.model_dump()
                    feedbacks = dump.get("feedbacks", [])
                    if feedbacks:
                        formatted = ""
                        for fb in feedbacks:
                            if fb.get("aspect"): formatted += f"**[{fb['aspect']}]**\n"
                            if fb.get("critique"): formatted += f"Kritik: {fb['critique']}\n"
                            if fb.get(
                                "improvement_suggestion"): formatted += f"💡 Vorschlag: {fb['improvement_suggestion']}\n\n"
                        if dump.get("overall_verdict"):
                            formatted += f"**Fazit:** {dump['overall_verdict']}"

                        dump["spoken_text"] = formatted

                    yield f"data: {json.dumps(dump)}\n\n"

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error {agent}: {e}")

            yield f"data: {json.dumps({'agent': agent, 'status': 'agent_done'})}\n\n"