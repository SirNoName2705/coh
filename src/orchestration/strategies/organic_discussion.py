# src/orchestration/strategies/organic_discussion.py
import json
import asyncio
from fastapi import Request

from src.core.logger import get_logger
from src.agents.schemas import AgentResponse, TurnContext
from src.agents.persona import PersonaManager
from src.rag.chroma_manager import rag_manager
from src.orchestration.strategies.base import TurnStrategy

logger = get_logger(__name__)


class OrganicDiscussionStrategy(TurnStrategy):
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents:
            return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]

        rag_tasks = [rag_manager.query_context(slug, context.current_topic, k=3) for slug in author_slugs]
        persona_tasks = [PersonaManager.get_persona(slug) for slug in author_slugs]

        rag_results = await asyncio.gather(*rag_tasks)
        persona_results = await asyncio.gather(*persona_tasks)

        history = []

        # --- PHASE 1: Statements ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 1: Initiale Statements'})}\n\n"
        for agent_name, rag_context, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Philosophie: {persona.core_philosophy}\n"
                f"Wissen: {rag_context}\n"
                "Formuliere dein erstes Statement."
            )

            final_text = ""
            try:
                stream_generator = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=AgentResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": context.current_topic}],
                    stream=True,
                    api_base=llm_client.config.llm_base_url
                )

                async for partial_obj in stream_generator:
                    if await request.is_disconnected(): return
                    yield f"data: {partial_obj.model_dump_json()}\n\n"
                    if partial_obj.spoken_text:
                        final_text = partial_obj.spoken_text

            except Exception as e:
                logger.error(f"Inferenz-Fehler bei Phase 1 für {agent_name}: {e}")
                error_msg = "[Der Experte konnte seine Gedanken nicht abschließen]"
                final_text = final_text if final_text else error_msg
                yield f"data: {json.dumps({'status': 'error', 'message': f'{agent_name} hatte einen Inferenz-Abbruch.'})}\n\n"

            history.append(f"{agent_name}: {final_text}")
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"

        # --- PHASE 2: Replik (Eine Runde) ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 2: Offene Diskussion'})}\n\n"
        forum_context = "\n".join(history)

        for agent_name, persona in zip(context.target_agents, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent_name} (Replik)', 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Reagiere auf die Aussagen:\n{forum_context}\n\n"
                f"Philosophie: {persona.core_philosophy}\n"
                "WICHTIG: Wenn du den bisherigen Aussagen fachlich nichts Substanzielles "
                "mehr hinzuzufügen hast, setze das Feld 'abstain' zwingend auf True und "
                "lass den 'spoken_text' leer."
            )

            try:
                stream_generator = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=AgentResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": "Deine Replik:"}],
                    stream=True,
                    api_base=llm_client.config.llm_base_url
                )

                async for partial_obj in stream_generator:
                    if await request.is_disconnected(): return
                    yield f"data: {partial_obj.model_dump_json()}\n\n"

            except Exception as e:
                logger.error(f"Inferenz-Fehler bei Phase 2 für {agent_name}: {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'{agent_name} hatte einen Inferenz-Abbruch.'})}\n\n"

            yield f"data: {json.dumps({'agent': f'{agent_name} (Replik)', 'status': 'agent_done'})}\n\n"

        yield f"data: {json.dumps({'status': 'info', 'message': 'Diskussion beendet.'})}\n\n"