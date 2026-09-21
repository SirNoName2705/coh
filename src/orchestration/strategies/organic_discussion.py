# src/orchestration/strategies/organic_discussion.py
import json
import asyncio
from fastapi import Request

from src.core.logger import get_logger
from src.agents.schemas import AgentResponse, TurnContext
from src.agents.persona import PersonaManager
from src.agents.prompt_builder import PromptBuilder
from src.rag.chroma_manager import rag_manager
from src.orchestration.strategies.base import TurnStrategy

logger = get_logger(__name__)


class OrganicDiscussionStrategy(TurnStrategy):
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents: return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]
        rag_results = await asyncio.gather(*[rag_manager.query_context(s, context.current_topic) for s in author_slugs])
        persona_results = await asyncio.gather(*[PersonaManager.get_persona(s) for s in author_slugs])

        history = []

        # --- PHASE 1 ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 1: Initiale Statements'})}\n\n"
        for agent, rag, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent, 'status': 'starting_agent'})}\n\n"

            system_prompt = PromptBuilder.organic_statement(agent, persona, rag)
            final_text = ""
            try:
                stream = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=AgentResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": context.current_topic}],
                    stream=True, api_base=llm_client.config.llm_base_url
                )
                async for chunk in stream:
                    if await request.is_disconnected(): return
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    if chunk.spoken_text: final_text = chunk.spoken_text
            except asyncio.CancelledError:
                logger.warning(f"Client Disconnect während Inferenz von {agent}. Gebe Ressourcen frei.")
                raise  # Zwingend erforderlich laut Sektion 3.1
            except Exception as e:
                logger.error(f"Error {agent}: {e}")
                final_text = "[Konnte Gedanken nicht abschließen]"

            history.append(f"{agent}: {final_text}")
            yield f"data: {json.dumps({'agent': agent, 'status': 'agent_done'})}\n\n"

        # --- PHASE 2 ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 2: Offene Diskussion'})}\n\n"
        forum_context = "\n".join(history)

        for agent, persona in zip(context.target_agents, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent} (Replik)', 'status': 'starting_agent'})}\n\n"

            system_prompt = PromptBuilder.organic_replik(agent, persona, forum_context)
            try:
                stream = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=AgentResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": "Deine Replik:"}],
                    stream=True, api_base=llm_client.config.llm_base_url
                )
                async for chunk in stream:
                    if await request.is_disconnected(): return
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error {agent}: {e}")

            yield f"data: {json.dumps({'agent': f'{agent} (Replik)', 'status': 'agent_done'})}\n\n"