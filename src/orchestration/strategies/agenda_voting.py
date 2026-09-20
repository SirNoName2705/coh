# src/orchestration/strategies/agenda_voting.py
import json
import asyncio
from fastapi import Request

from src.core.logger import get_logger
from src.agents.schemas import AgentResponse, VoteResponse, TurnContext
from src.agents.persona import PersonaManager
from src.rag.chroma_manager import rag_manager
from src.orchestration.strategies.base import TurnStrategy

logger = get_logger(__name__)


class AgendaVotingStrategy(TurnStrategy):
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents:
            return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]

        rag_tasks = [rag_manager.query_context(slug, context.current_topic, k=3) for slug in author_slugs]
        persona_tasks = [PersonaManager.get_persona(slug) for slug in author_slugs]

        rag_results = await asyncio.gather(*rag_tasks)
        persona_results = await asyncio.gather(*persona_tasks)

        master_agenda = set()
        history = []

        # --- PHASE 1: Statements & Agenda-Findung ---
        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 1: Diskussion & Agenda-Findung'})}\n\n"

        for agent_name, rag_context, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Philosophie: {persona.core_philosophy}\n"
                f"Wissen: {rag_context}\n"
                "Formuliere dein Statement. Wenn du eine konkrete Ja/Nein-Entscheidung vom Rat erzwingen willst, "
                "füge sie als Frage unter 'proposed_agenda_items' hinzu (z.B. 'Sollen wir Taktik X anwenden?').\n"
                "WICHTIG: Wenn du dem Thema nichts hinzufügen kannst, setze 'abstain' auf True."
                "WICHTIG: Gib direkt das befüllte JSON-Datenobjekt zurück. "
                "Generiere unter keinen Umständen ein JSON-Schema (mit Wörtern wie 'properties' oder 'type')."
            )

            final_obj = None
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
                    final_obj = partial_obj

                if final_obj and final_obj.proposed_agenda_items:
                    for item in final_obj.proposed_agenda_items:
                        master_agenda.add(item)

                if final_obj and final_obj.spoken_text:
                    history.append(f"{agent_name}: {final_obj.spoken_text}")

            except Exception as e:
                logger.error(f"Inferenz-Fehler bei Phase 1 (Agenda) für {agent_name}: {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'{agent_name} hatte einen Aussetzer beim Erstellen der Agenda.'})}\n\n"

            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"

        if not master_agenda:
            yield f"data: {json.dumps({'status': 'info', 'message': 'Keine Agenda-Punkte vorgeschlagen. Voting entfällt.'})}\n\n"
            return

        agenda_list = list(master_agenda)
        agenda_text = "\n".join([f"- {item}" for item in agenda_list])

        # --- PHASE 2: Voting auf die gesammelte Agenda ---
        yield f"data: {json.dumps({'status': 'info', 'message': f'Phase 2: Formales Voting\\n{agenda_text}'})}\n\n"

        for agent_name, persona in zip(context.target_agents, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent_name} (Vote)', 'status': 'starting_agent'})}\n\n"

            system_prompt = (
                f"Du bist '{agent_name}'. Philosophie: {persona.core_philosophy}\n"
                f"Die offizielle Agenda lautet:\n{agenda_text}\n\n"
                "Stimme über JEDEN Punkt auf der Agenda strikt mit True (JA) oder False (NEIN) ab und begründe es kurz."
                "WICHTIG: Gib direkt das befüllte JSON-Datenobjekt zurück. "
                "Generiere unter keinen Umständen ein JSON-Schema (mit Wörtern wie 'properties' oder 'type')."
            )

            try:
                stream_generator = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=VoteResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": "Deine formale Abstimmung:"}],
                    stream=True,
                    api_base=llm_client.config.llm_base_url
                )

                async for partial_obj in stream_generator:
                    if await request.is_disconnected(): return
                    yield f"data: {partial_obj.model_dump_json()}\n\n"
            except Exception as e:
                logger.error(f"Inferenz-Fehler beim Voting für {agent_name}: {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'{agent_name} hat einen formalen Fehler beim Voting begangen.'})}\n\n"

            yield f"data: {json.dumps({'agent': f'{agent_name} (Vote)', 'status': 'agent_done'})}\n\n"