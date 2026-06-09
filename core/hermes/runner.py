"""
Hermes Agent Runner — Executes agents with tools, memory, and streaming.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, Any, Optional, AsyncIterator, List
from datetime import datetime

from core.hermes.models import (
    Agent, AgentRun, RunStatus, ExecutionMode, EventType,
    Message, MessageType, Conversation, Artifact, ArtifactType,
    Memory, MemoryType, ToolExecution,
)
from core.hermes.event_bus import (
    EventBus, HermesEvent, get_event_bus,
    emit_run_started, emit_run_completed, emit_run_failed,
)
from core.hermes.tools import tool_registry
from core.hermes.skills import skill_registry
from core.hermes.database import engine
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


class AgentRunner:
    """Agent execution engine with tools, memory, and streaming."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()

    async def run(
        self,
        run_id: str,
        agent: Agent,
        conversation_id: Optional[str],
        input_data: Dict[str, Any],
        mode: ExecutionMode = ExecutionMode.ASYNC,
    ) -> Dict[str, Any]:
        """Execute an agent run with full context."""
        start_time = datetime.utcnow()

        self._update_run_status(run_id, RunStatus.RUNNING, started_at=start_time)
        await emit_run_started(run_id, agent.id)

        try:
            # Build context from memory
            memory_context = self._load_agent_memory(agent.id)

            # Get skill prompt additions
            skill_prompt = skill_registry.get_prompt_additions(agent.skills or [])

            # Build the full system prompt
            system_prompt = agent.system_prompt
            if agent.goal:
                system_prompt += f"\n\n## Goal\n{agent.goal}"
            if skill_prompt:
                system_prompt += f"\n\n{skill_prompt}"
            if memory_context:
                system_prompt += f"\n\n## Memory Context\n{memory_context}"

            # Get available tools for this agent
            available_tools = self._get_agent_tools(agent)

            # Create LLM provider
            llm_config = {
                "provider": agent.llm_provider,
                "model": agent.llm_model,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
            }
            llm_config.update(agent.config.get("llm_config", {}))
            from core.hermes.llm.factory import ProviderFactory
            llm_provider = ProviderFactory.create_provider_from_config(llm_config)

            # Build messages
            user_message = input_data.get("message", input_data.get("content", ""))
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            # Execute with tool loop
            max_iterations = 10
            full_response = []

            for iteration in range(max_iterations):
                from core.hermes.llm import Message as LLMMessage
                llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

                # Check if we should use tools
                if available_tools and iteration < max_iterations - 1:
                    # Add tool instructions
                    tool_desc = "\n".join([
                        f"- {t['name']}: {t['description']}"
                        for t in available_tools
                    ])
                    tool_msg = f"\n\nYou have access to these tools: {tool_desc}\nTo use a tool, respond with a JSON block:\n```tool\n{{\"tool\": \"tool_name\", \"args\": {{...}}}}\n```"
                    messages_with_tools = list(messages)
                    messages_with_tools[0] = {"role": "system", "content": system_prompt + tool_msg}

                    llm_messages_with_tools = [
                        LLMMessage(role=m["role"], content=m["content"])
                        for m in messages_with_tools
                    ]

                    response = await llm_provider.generate(messages=llm_messages_with_tools)
                else:
                    response = await llm_provider.generate(messages=llm_messages)

                content = response.content
                full_response.append(content)

                # Check for tool call
                tool_call = self._extract_tool_call(content)

                if tool_call and iteration < max_iterations - 1:
                    # Emit thinking event
                    await self.event_bus.publish(HermesEvent(
                        run_id=run_id,
                        event_type=EventType.THINKING,
                        agent_id=agent.id,
                        data={"thinking": content[:500]},
                    ))

                    # Execute tool
                    tool_name = tool_call["tool"]
                    tool_args = tool_call.get("args", {})

                    await self.event_bus.publish(HermesEvent(
                        run_id=run_id,
                        event_type=EventType.TOOL_CALLED,
                        agent_id=agent.id,
                        data={"tool": tool_name, "args": tool_args},
                    ))

                    tool_result = await tool_registry.execute(tool_name, tool_args)

                    await self.event_bus.publish(HermesEvent(
                        run_id=run_id,
                        event_type=EventType.TOOL_RESULT,
                        agent_id=agent.id,
                        data={"tool": tool_name, "result": tool_result},
                    ))

                    # Record tool execution
                    self._record_tool_execution(run_id, agent.id, tool_name, tool_args, tool_result)

                    # Add tool result to conversation
                    messages.append({"role": "assistant", "content": content})
                    messages.append({
                        "role": "user",
                        "content": f"Tool result for {tool_name}:\n{json.dumps(tool_result, indent=2)[:2000]}"
                    })

                    # Save to conversation if exists
                    if conversation_id:
                        self._save_message(conversation_id, MessageType.ASSISTANT, content)
                        self._save_message(conversation_id, MessageType.TOOL_RESULT,
                                          json.dumps(tool_result, indent=2)[:5000])
                else:
                    # Final response — no more tool calls
                    messages.append({"role": "assistant", "content": content})

                    if conversation_id:
                        self._save_message(conversation_id, MessageType.ASSISTANT, content)

                    break

            # Build final result
            result_content = "\n".join(full_response)
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            token_usage = response.token_usage if response else None

            self._update_run_status(
                run_id, RunStatus.COMPLETED,
                completed_at=end_time, duration_ms=duration_ms,
                output_data={"response": result_content},
                token_usage=token_usage,
            )

            await emit_run_completed(run_id, agent.id, {"response": result_content}, token_usage)

            # Update agent state
            self._update_agent_status(agent.id, "idle")

            return {
                "success": True,
                "response": result_content,
                "token_usage": token_usage,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            error_msg = str(e)
            error_type = type(e).__name__

            logger.exception(f"Run {run_id} failed")

            self._update_run_status(
                run_id, RunStatus.FAILED,
                completed_at=end_time, duration_ms=duration_ms,
                error_message=error_msg, error_type=error_type,
            )

            await emit_run_failed(run_id, agent.id, error_msg, error_type)
            self._update_agent_status(agent.id, "error")

            return {"success": False, "error": error_msg, "error_type": error_type}

    async def run_stream(
        self,
        run_id: str,
        agent: Agent,
        conversation_id: Optional[str],
        input_data: Dict[str, Any],
    ) -> AsyncIterator[HermesEvent]:
        """Execute an agent and stream events."""
        start_time = datetime.utcnow()
        self._update_run_status(run_id, RunStatus.RUNNING, started_at=start_time)
        self._update_agent_status(agent.id, "running")

        queue = await self.event_bus.subscribe_to_run(run_id)

        try:
            # Build context
            memory_context = self._load_agent_memory(agent.id)
            skill_prompt = skill_registry.get_prompt_additions(agent.skills or [])

            system_prompt = agent.system_prompt
            if agent.goal:
                system_prompt += f"\n\n## Goal\n{agent.goal}"
            if skill_prompt:
                system_prompt += f"\n\n{skill_prompt}"
            if memory_context:
                system_prompt += f"\n\n## Memory Context\n{memory_context}"

            # Create LLM
            llm_config = {
                "provider": agent.llm_provider,
                "model": agent.llm_model,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
            }
            llm_config.update(agent.config.get("llm_config", {}))
            from core.hermes.llm.factory import ProviderFactory
            llm_provider = ProviderFactory.create_provider_from_config(llm_config)

            await emit_run_started(run_id, agent.id)

            user_message = input_data.get("message", input_data.get("content", ""))
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            # Stream response
            from core.hermes.llm import Message as LLMMessage
            llm_messages = [LLMMessage(role=m["role"], content=m["content"]) for m in messages]

            full_response = []
            async for chunk in llm_provider.generate_stream(messages=llm_messages):
                full_response.append(chunk)
                event = HermesEvent(
                    run_id=run_id,
                    event_type=EventType.TOKEN,
                    agent_id=agent.id,
                    data={"token": chunk},
                )
                await self.event_bus.publish(event)
                yield event

            result_content = "".join(full_response)
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            if conversation_id:
                self._save_message(conversation_id, MessageType.USER, user_message)
                self._save_message(conversation_id, MessageType.ASSISTANT, result_content)

            self._update_run_status(
                run_id, RunStatus.COMPLETED,
                completed_at=end_time, duration_ms=duration_ms,
                output_data={"response": result_content},
            )

            await emit_run_completed(run_id, agent.id, {"response": result_content})
            self._update_agent_status(agent.id, "idle")

        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            logger.exception(f"Stream run {run_id} failed")

            self._update_run_status(
                run_id, RunStatus.FAILED,
                completed_at=end_time, duration_ms=duration_ms,
                error_message=str(e), error_type=type(e).__name__,
            )

            await emit_run_failed(run_id, agent.id, str(e))
            self._update_agent_status(agent.id, "error")

        finally:
            await self.event_bus.unsubscribe(queue)

    def _extract_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract tool call from LLM response."""
        import re
        pattern = r'```tool\s*\n({.*?})\s*\n```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _get_agent_tools(self, agent: Agent) -> List[Dict[str, Any]]:
        """Get available tools for an agent based on its skills."""
        tool_names = skill_registry.get_tools_for_skills(agent.skills or [])
        # Also add explicitly enabled tools
        if agent.tools_enabled:
            tool_names.extend(agent.tools_enabled)
        tool_names = list(set(tool_names))

        tools = []
        for name in tool_names:
            tool = tool_registry.get(name)
            if tool:
                tools.append(tool.to_schema())
        return tools

    def _load_agent_memory(self, agent_id: str) -> str:
        """Load agent memory as context string."""
        try:
            with Session(engine) as session:
                memories = session.exec(
                    select(Memory)
                    .where(Memory.agent_id == agent_id)
                    .order_by(Memory.importance.desc())
                    .limit(20)
                ).all()

                if not memories:
                    return ""

                lines = []
                for m in memories:
                    lines.append(f"- [{m.memory_type.value}] {m.key}: {m.content[:200]}")
                return "\n".join(lines)
        except Exception:
            return ""

    def _save_message(self, conversation_id: str, message_type: MessageType, content: str):
        """Save a message to the conversation."""
        try:
            with Session(engine) as session:
                msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    message_type=message_type,
                    content=content[:10000],
                )
                session.add(msg)

                # Update conversation
                conv = session.get(Conversation, conversation_id)
                if conv:
                    conv.message_count += 1
                    conv.updated_at = datetime.utcnow()
                    session.add(conv)

                session.commit()
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    def _record_tool_execution(self, run_id: str, agent_id: str, tool_name: str,
                                tool_args: Dict, tool_result: Dict):
        """Record a tool execution."""
        try:
            with Session(engine) as session:
                execution = ToolExecution(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=json.dumps(tool_result)[:5000],
                    status="completed" if tool_result.get("success") else "failed",
                    completed_at=datetime.utcnow(),
                )
                session.add(execution)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to record tool execution: {e}")

    def _update_run_status(self, run_id: str, status: RunStatus, **kwargs):
        """Update run status in database."""
        try:
            with Session(engine) as session:
                run = session.get(AgentRun, run_id)
                if run:
                    run.status = status
                    for key, value in kwargs.items():
                        if hasattr(run, key):
                            setattr(run, key, value)
                    session.add(run)
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update run status: {e}")

    def _update_agent_status(self, agent_id: str, status: str):
        """Update agent status."""
        try:
            with Session(engine) as session:
                agent = session.get(Agent, agent_id)
                if agent:
                    agent.status = status
                    agent.last_active_at = datetime.utcnow()
                    session.add(agent)
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update agent status: {e}")


# Global runner
_runner: Optional[AgentRunner] = None


def get_runner() -> AgentRunner:
    global _runner
    if _runner is None:
        _runner = AgentRunner()
    return _runner
