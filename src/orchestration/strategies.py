# src/orchestration/strategies.py
import json
import asyncio
from fastapi import Request
from src.core.logger import get_logger
from src.agents.schemas import AgentResponse, VoteResponse, TurnContext
from src.agents.persona import PersonaManager
from src.rag.chroma_manager import rag_manager

logger = get_logger(__name__)

class OrganicCouncilStrategy:
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents:
            return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]

        # Lade RAG und Personas parallel
        rag_tasks = [rag_manager.query_context(slug, context.current_topic, k=3) for slug in author_slugs]
        persona_tasks = [PersonaManager.get_persona(slug) for slug in author_slugs]

        rag_results = await asyncio.gather(*rag_tasks)
        persona_results = await asyncio.gather(*persona_tasks)

        history_for_round_2 = []

        # --- PHASE 1: INITALE STATEMENTS ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 1: Initiale Statements'})}\n\n"
        for agent_name, rag_context, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Du sitzt in einem Experten-Rat.\n"
                f"Deine Philosophie: {persona.core_philosophy}\n"
                f"Stil: {persona.tone_of_voice}\n"
                f"Regeln: {persona.constraints}\n\n"
                f"Wissen (RAG): {rag_context}\n\n"
                "Formuliere dein erstes klares Statement zum Problem des Nutzers."
            )

            stream_generator = llm_client.client.create_partial(
                model=llm_client.config.llm_model_name,
                response_model=AgentResponse,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": context.current_topic}],
                stream=True,
                api_base=llm_client.config.llm_base_url
            )

            final_text = ""
            async for partial_obj in stream_generator:
                if await request.is_disconnected(): return
                yield f"data: {partial_obj.model_dump_json()}\n\n"
                if partial_obj.spoken_text:
                    final_text = partial_obj.spoken_text

            history_for_round_2.append(f"{agent_name} sagte: {final_text}")
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"

        # --- PHASE 2: DISKUSSION (CROSS-TALK) ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 2: Offene Diskussion'})}\n\n"
        forum_context = "\n".join(history_for_round_2)

        for agent_name, persona in zip(context.target_agents, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent_name} (Replik)', 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Reagiere auf die Aussagen deiner Kollegen.\n"
                f"Bisherige Aussagen:\n{forum_context}\n\n"
                f"Bleibe strikt in deiner Philosophie: {persona.core_philosophy}\n"
                "Widersprich, ergänze oder kritisiere die anderen aus deiner fachlichen Sicht."
            )

            stream_generator = llm_client.client.create_partial(
                model=llm_client.config.llm_model_name,
                response_model=AgentResponse,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Deine Replik:"}],
                stream=True,
                api_base=llm_client.config.llm_base_url
            )

            async for partial_obj in stream_generator:
                yield f"data: {partial_obj.model_dump_json()}\n\n"
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"

        # --- PHASE 3: VOTING ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 3: Finaler Vote'})}\n\n"
        for agent_name in context.target_agents:
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent_name} (Vote)', 'status': 'starting_agent'})}\n\n"

            system_prompt = f"Du bist '{agent_name}'. Triff basierend auf der Diskussion eine finale, harte Entscheidung. Begründe sie kurz im Monolog."

            stream_generator = llm_client.client.create_partial(
                model=llm_client.config.llm_model_name,
                response_model=VoteResponse,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": "Dein finales Votum:"}],
                stream=True,
                api_base=llm_client.config.llm_base_url
            )

            async for partial_obj in stream_generator:
                yield f"data: {partial_obj.model_dump_json()}\n\n"
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"