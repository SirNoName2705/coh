# src/orchestration/strategies/agenda_voting.py
import json
import asyncio
from enum import Enum
from typing import List
from fastapi import Request
from pydantic import BaseModel, Field, create_model, field_validator

from src.core.logger import get_logger
from src.agents.schemas import AgentResponse, TurnContext
from src.agents.persona import PersonaManager
from src.agents.prompt_builder import PromptBuilder
from src.rag.chroma_manager import rag_manager
from src.orchestration.strategies.base import TurnStrategy

logger = get_logger(__name__)


class AgendaVotingStrategy(TurnStrategy):
    async def execute_turn_stream(self, context: TurnContext, llm_client, request: Request):
        if not context.target_agents: return

        author_slugs = [a.lower().replace(" ", "_") for a in context.target_agents]
        rag_results = await asyncio.gather(*[rag_manager.query_context(s, context.current_topic) for s in author_slugs])
        persona_results = await asyncio.gather(*[PersonaManager.get_persona(s) for s in author_slugs])

        master_agenda = set()

        yield f"data: {json.dumps({'status': 'info', 'message': 'Phase 1: Diskussion & Agenda-Findung'})}\n\n"
        for agent_name, rag_context, persona in zip(context.target_agents, rag_results, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': agent_name, 'status': 'starting_agent'})}\n\n"

            system_prompt = PromptBuilder.agenda_statement(agent_name, persona, rag_context)
            final_obj = None
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
                    final_obj = chunk

                if final_obj and final_obj.proposed_agenda_items:
                    for item in final_obj.proposed_agenda_items: master_agenda.add(item)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error {agent_name}: {e}")

            yield f"data: {json.dumps({'agent': agent_name, 'status': 'agent_done'})}\n\n"

        if not master_agenda:
            yield f"data: {json.dumps({'status': 'info', 'message': 'Keine Agenda-Punkte. Voting entfällt.'})}\n\n"
            return

        agenda_list = list(master_agenda)
        agenda_text = "\n".join([f"- {item}" for item in agenda_list])

        # Dynamisches Pydantic Model (Sektion 2.2)
        agenda_mapping = {f"ITEM_{i}": item for i, item in enumerate(agenda_list)}
        AgendaEnum = Enum("AgendaEnum", agenda_mapping)

        class DynamicAgendaVote(BaseModel):
            agenda_item: AgendaEnum = Field(...)
            vote: bool = Field(...)
            reason: str = Field(...)

            @field_validator('vote', mode='before')
            @classmethod
            def parse_bool(cls, v):
                if isinstance(v, str): return v.lower() in ('true', '1', 'ja', 'yes', 't')
                return bool(v)

        DynamicVoteResponse = create_model('DynamicVoteResponse', inner_monologue=(str, ...),
                                           votes=(List[DynamicAgendaVote], ...))

        yield f"data: {json.dumps({'status': 'info', 'message': f'Phase 2: Formales Voting\\n{agenda_text}'})}\n\n"
        for agent_name, persona in zip(context.target_agents, persona_results):
            if await request.is_disconnected(): return
            yield f"data: {json.dumps({'agent': f'{agent_name} (Vote)', 'status': 'starting_agent'})}\n\n"

            system_prompt = PromptBuilder.agenda_voting(agent_name, persona, agenda_text)
            try:
                stream = llm_client.client.create_partial(
                    model=llm_client.config.llm_model_name,
                    response_model=DynamicVoteResponse,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": "Deine Abstimmung:"}],
                    stream=True, api_base=llm_client.config.llm_base_url
                )
                async for chunk in stream:
                    if await request.is_disconnected(): return
                    yield f"data: {chunk.model_dump_json()}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Vote Error {agent_name}: {e}")

            yield f"data: {json.dumps({'agent': f'{agent_name} (Vote)', 'status': 'agent_done'})}\n\n"