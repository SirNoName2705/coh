"""Strategy-Pattern-Implementierung für Rundenabläufe im 'Council of Heroes'."""
import abc
import asyncio
import json
import os
import time
from typing import List, Sequence

from fastapi import Request
from src.core.logger import get_logger
from src.agents.executor import AgentCommand, ConsultationCommand, SpeechCommand, VoteCommand
from src.agents.schemas import AgentResponse, ConsultationResponse, TurnContext, VoteResponse
from src.agents.persona import PersonaManager
from src.rag.chroma_manager import rag_manager

logger = get_logger(__name__)

class TurnStrategy(abc.ABC):
    _semaphore = asyncio.Semaphore(int(os.getenv("OLLAMA_NUM_PARALLEL", "4")))

    @abc.abstractmethod
    async def execute_turn(self, context: TurnContext) -> Sequence[object]:
        raise NotImplementedError

    @abc.abstractmethod
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        raise NotImplementedError

    async def _execute_safely(self, commands: List[AgentCommand]) -> list:
        async def throttled_execution(cmd: AgentCommand):
            async with self._semaphore:
                return await cmd.execute()

        raw_results = await asyncio.gather(
            *(throttled_execution(cmd) for cmd in commands),
            return_exceptions=True,
        )

        valid_results = []
        for res in raw_results:
            if isinstance(res, Exception):
                logger.error(f"Agentenaufruf in Runde fehlgeschlagen: {res}", exc_info=True)
            else:
                valid_results.append(res)
        return valid_results

class ConsultationTurnStrategy(TurnStrategy):
    async def execute_turn(self, context: TurnContext) -> list[ConsultationResponse]:
        # Nur für Non-Streaming Fallback
        pass

    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents:
            return

        logger.info(f"Starte paralleles RAG & Persona-Load für: {context.target_agents}")

        # 1. RAG-Lookups & Personas PARALLEL laden (CPU/Disk I/O)
        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]

        rag_tasks = [rag_manager.query_context(slug, context.current_topic, k=3) for slug in author_slugs]
        persona_tasks = [PersonaManager.get_persona(slug) for slug in author_slugs]

        rag_results = await asyncio.gather(*rag_tasks)
        persona_results = await asyncio.gather(*persona_tasks)

        # 2. Inferenz & SSE-Streaming (Sequenziell für sauberes Partial-JSON)
        for agent_name, rag_context, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected():
                break

            yield f"data: {json.dumps({'agent': agent_name, 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist der Fachberater '{agent_name}' im Konzil. "
                "Erstelle eine analytische Handlungsempfehlung auf Basis des vorliegenden Wissens.\n\n"
                f"Kernphilosophie:\n{persona.core_philosophy}\n\n"
                f"Tonfall & Stil:\n{persona.tone_of_voice}\n\n"
                f"Verhaltensregeln:\n{persona.constraints}\n\n"
                f"Strategischer Kontext (RAG):\n{rag_context}\n\n"
                "Nutze den 'inner_monologue' für deine Analyse, bevor du antwortest."
            )

            stream_generator = llm_client.client.create_partial(
                model=llm_client.config.llm_model_name,
                response_model=ConsultationResponse,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context.moderator_instruction}
                ],
                stream=True,
                api_base=llm_client.config.llm_base_url
            )

            async for partial_obj in stream_generator:
                if await request.is_disconnected():
                    break
                yield f"data: {partial_obj.model_dump_json()}\n\n"

            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"