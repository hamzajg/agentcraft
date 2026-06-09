"""
Hermes API Routes — Full agent platform with memory, tools, artifacts, skills.
"""

import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from core.hermes.database import get_hermes_session, init_hermes_db
from core.hermes.models import (
    Agent, AgentCreate, AgentUpdate, AgentStatus,
    Conversation, ConversationCreate,
    Message, MessageCreate, MessageType,
    Artifact, ArtifactCreate, ArtifactType,
    Memory, MemoryCreate, MemoryType,
    Skill, SkillCreate,
    AgentRun, RunCreate, RunStatus, ExecutionMode,
    ToolExecution, AgentMessage, AgentMessageCreate,
    EventType,
)
from core.hermes.runner import get_runner
from core.hermes.event_bus import get_event_bus, HermesEvent
from core.hermes.tools import tool_registry
from core.hermes.skills import skill_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hermes", tags=["hermes"])


def init():
    """Initialize Hermes database tables."""
    init_hermes_db()


# ─── Health ──────────────────────────────────────────────────────────────────

@router.get("/health")
async def hermes_health():
    return {"status": "healthy", "service": "hermes", "version": "0.2.0"}


# ─── Agents ──────────────────────────────────────────────────────────────────

@router.post("/agents", response_model=Agent)
async def create_agent(agent: AgentCreate, session: Session = Depends(get_hermes_session)):
    agent_id = str(uuid.uuid4())
    db_agent = Agent(id=agent_id, **agent.model_dump())
    session.add(db_agent)
    session.commit()
    session.refresh(db_agent)
    return db_agent


@router.get("/agents", response_model=List[Agent])
async def list_agents(skip: int = 0, limit: int = 100, session: Session = Depends(get_hermes_session)):
    return session.exec(select(Agent).offset(skip).limit(limit)).all()


@router.get("/agents/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, update: AgentUpdate, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.utcnow()
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    session.delete(agent)
    session.commit()
    return {"message": "Agent deleted"}


# ─── Conversations ───────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/conversations", response_model=Conversation)
async def create_conversation(agent_id: str, body: ConversationCreate, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    conv = Conversation(id=str(uuid.uuid4()), agent_id=agent_id, title=body.title)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@router.get("/agents/{agent_id}/conversations", response_model=List[Conversation])
async def list_conversations(agent_id: str, session: Session = Depends(get_hermes_session)):
    return session.exec(
        select(Conversation).where(Conversation.agent_id == agent_id).order_by(Conversation.updated_at.desc())
    ).all()


@router.get("/conversations/{conv_id}", response_model=Conversation)
async def get_conversation(conv_id: str, session: Session = Depends(get_hermes_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, session: Session = Depends(get_hermes_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session.delete(conv)
    session.commit()
    return {"message": "Conversation deleted"}


# ─── Messages ────────────────────────────────────────────────────────────────

@router.get("/conversations/{conv_id}/messages", response_model=List[Message])
async def list_messages(conv_id: str, limit: int = 100, session: Session = Depends(get_hermes_session)):
    return session.exec(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at).limit(limit)
    ).all()


@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, body: MessageCreate, session: Session = Depends(get_hermes_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        message_type=MessageType.USER,
        content=body.content,
    )
    session.add(user_msg)
    conv.message_count += 1
    conv.updated_at = datetime.utcnow()
    session.add(conv)
    session.commit()

    # Create and execute agent run
    agent = session.get(Agent, conv.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    run_id = str(uuid.uuid4())
    run = AgentRun(
        id=run_id,
        agent_id=conv.agent_id,
        conversation_id=conv_id,
        mode=ExecutionMode.ASYNC,
        input_data={"message": body.content},
        status=RunStatus.PENDING,
    )
    session.add(run)
    session.commit()

    # Execute in background
    runner = get_runner()
    asyncio.create_task(runner.run(
        run_id=run_id,
        agent=agent,
        conversation_id=conv_id,
        input_data={"message": body.content},
        mode=ExecutionMode.ASYNC,
    ))

    return {"run_id": run_id, "status": "started"}


@router.post("/conversations/{conv_id}/messages/stream")
async def send_message_stream(conv_id: str, body: MessageCreate, session: Session = Depends(get_hermes_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    agent = session.get(Agent, conv.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        message_type=MessageType.USER,
        content=body.content,
    )
    session.add(user_msg)
    conv.message_count += 1
    conv.updated_at = datetime.utcnow()
    session.add(conv)
    session.commit()

    run_id = str(uuid.uuid4())
    run = AgentRun(
        id=run_id,
        agent_id=conv.agent_id,
        conversation_id=conv_id,
        mode=ExecutionMode.STREAMING,
        input_data={"message": body.content},
        status=RunStatus.PENDING,
    )
    session.add(run)
    session.commit()

    event_bus = get_event_bus()
    queue = await event_bus.subscribe_to_run(run_id)

    runner = get_runner()

    async def generate():
        try:
            # Start the run in background
            asyncio.create_task(runner.run_stream(
                run_id=run_id,
                agent=agent,
                conversation_id=conv_id,
                input_data={"message": body.content},
            ))

            while True:
                try:
                    event: HermesEvent = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event.to_dict())}\n\n"
                    if event.event_type.value in ("run_completed", "run_failed"):
                        break
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            await event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ─── Artifacts ───────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/artifacts", response_model=Artifact)
async def create_artifact(agent_id: str, body: ArtifactCreate, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    artifact = Artifact(id=str(uuid.uuid4()), agent_id=agent_id, **body.model_dump())
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.get("/agents/{agent_id}/artifacts", response_model=List[Artifact])
async def list_artifacts(agent_id: str, session: Session = Depends(get_hermes_session)):
    return session.exec(
        select(Artifact).where(Artifact.agent_id == agent_id).order_by(Artifact.updated_at.desc())
    ).all()


@router.get("/artifacts/{artifact_id}", response_model=Artifact)
async def get_artifact(artifact_id: str, session: Session = Depends(get_hermes_session)):
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.put("/artifacts/{artifact_id}", response_model=Artifact)
async def update_artifact(artifact_id: str, body: ArtifactCreate, session: Session = Depends(get_hermes_session)):
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    for field, value in body.model_dump().items():
        setattr(artifact, field, value)
    artifact.version += 1
    artifact.updated_at = datetime.utcnow()
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str, session: Session = Depends(get_hermes_session)):
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    session.delete(artifact)
    session.commit()
    return {"message": "Artifact deleted"}


# ─── Memory ──────────────────────────────────────────────────────────────────

@router.post("/agents/{agent_id}/memories", response_model=Memory)
async def create_memory(agent_id: str, body: MemoryCreate, session: Session = Depends(get_hermes_session)):
    agent = session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    memory = Memory(id=str(uuid.uuid4()), agent_id=agent_id, **body.model_dump())
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


@router.get("/agents/{agent_id}/memories", response_model=List[Memory])
async def list_memories(
    agent_id: str,
    memory_type: str = None,
    session: Session = Depends(get_hermes_session)
):
    query = select(Memory).where(Memory.agent_id == agent_id)
    if memory_type:
        query = query.where(Memory.memory_type == memory_type)
    return session.exec(query.order_by(Memory.importance.desc())).all()


@router.put("/memories/{memory_id}", response_model=Memory)
async def update_memory(memory_id: str, body: MemoryCreate, session: Session = Depends(get_hermes_session)):
    memory = session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    for field, value in body.model_dump().items():
        setattr(memory, field, value)
    memory.updated_at = datetime.utcnow()
    memory.access_count += 1
    memory.last_accessed_at = datetime.utcnow()
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, session: Session = Depends(get_hermes_session)):
    memory = session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    session.delete(memory)
    session.commit()
    return {"message": "Memory deleted"}


# ─── Skills ──────────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills():
    skills = skill_registry.list_skills()
    return [
        {"id": s.id, "name": s.name, "description": s.description,
         "category": s.category, "tools": s.tools, "enabled": s.enabled,
         "prompt_sections": s.prompt_sections}
        for s in skills
    ]


@router.get("/skills/categories")
async def list_skill_categories():
    return skill_registry.get_categories()


@router.put("/skills/{skill_id}")
async def update_skill(skill_id: str, body: dict):
    skill = skill_registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if "enabled" in body:
        skill.enabled = body["enabled"]
    if "description" in body:
        skill.description = body["description"]
    if "tools" in body:
        skill.tools = body["tools"]
    if "prompt_sections" in body:
        skill.prompt_sections = body["prompt_sections"]
    return {"id": skill.id, "name": skill.name, "description": skill.description,
            "category": skill.category, "tools": skill.tools, "enabled": skill.enabled,
            "prompt_sections": skill.prompt_sections}


# ─── Tools ───────────────────────────────────────────────────────────────────

@router.get("/tools")
async def list_tools():
    return tool_registry.list_tools()


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, args: dict):
    result = await tool_registry.execute(tool_name, args)
    return result


# ─── Runs ────────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=List[AgentRun])
async def list_runs(skip: int = 0, limit: int = 50, session: Session = Depends(get_hermes_session)):
    return session.exec(select(AgentRun).order_by(AgentRun.created_at.desc()).offset(skip).limit(limit)).all()


@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_run(run_id: str, session: Session = Depends(get_hermes_session)):
    run = session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str, session: Session = Depends(get_hermes_session)):
    return session.exec(
        select(ToolExecution).where(ToolExecution.run_id == run_id)
    ).all()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, session: Session = Depends(get_hermes_session)):
    run = session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    event_bus = get_event_bus()
    queue = await event_bus.subscribe_to_run(run_id)

    async def generate():
        try:
            while True:
                try:
                    event: HermesEvent = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event.to_dict())}\n\n"
                    if event.event_type.value in ("run_completed", "run_failed"):
                        break
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            await event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ─── Agent Messages (Agent-to-Agent) ────────────────────────────────────────

@router.post("/messages", response_model=AgentMessage)
async def send_agent_message(body: AgentMessageCreate, session: Session = Depends(get_hermes_session)):
    msg = AgentMessage(id=str(uuid.uuid4()), from_agent_id="system", **body.model_dump())
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg


@router.get("/messages")
async def list_agent_messages(agent_id: str = None, session: Session = Depends(get_hermes_session)):
    query = select(AgentMessage)
    if agent_id:
        query = query.where(
            (AgentMessage.from_agent_id == agent_id) | (AgentMessage.to_agent_id == agent_id)
        )
    return session.exec(query.order_by(AgentMessage.created_at.desc()).limit(50)).all()


# ─── SSE Event Stream ───────────────────────────────────────────────────────

@router.get("/events/stream")
async def global_event_stream():
    event_bus = get_event_bus()
    queue = await event_bus.subscribe_global()

    async def generate():
        try:
            while True:
                try:
                    event: HermesEvent = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event.to_dict())}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
        finally:
            await event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ─── System ─────────────────────────────────────────────────────────────────

@router.get("/system/stats")
async def system_stats(session: Session = Depends(get_hermes_session)):
    agent_count = len(session.exec(select(Agent)).all())
    running = len(session.exec(select(Agent).where(Agent.status == AgentStatus.RUNNING)).all())
    conversation_count = len(session.exec(select(Conversation)).all())
    artifact_count = len(session.exec(select(Artifact)).all())
    memory_count = len(session.exec(select(Memory)).all())

    return {
        "agents": agent_count,
        "agents_running": running,
        "conversations": conversation_count,
        "artifacts": artifact_count,
        "memories": memory_count,
        "tools": len(tool_registry.list_names()),
        "skills": len(skill_registry.list_skills()),
    }


# ─── Agent Factory — YAML + DB agents ───────────────────────────────────────

import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LEGACY_AGENTS_DIR = PROJECT_ROOT / "agents"
HERMES_AGENTS_DIR = PROJECT_ROOT / "core" / "hermes" / "agents" / "examples"


def _scan_legacy_agents() -> list:
    """Scan agents/*/config.yaml for legacy agent definitions."""
    results = []
    if not LEGACY_AGENTS_DIR.exists():
        return results
    for agent_dir in sorted(LEGACY_AGENTS_DIR.iterdir()):
        config_file = agent_dir / "config.yaml"
        if not config_file.is_file():
            continue
        try:
            with open(config_file) as f:
                cfg = yaml.safe_load(f) or {}
            # Read prompt file if referenced
            prompt_text = ""
            prompt_ref = cfg.get("prompt", "")
            if prompt_ref and isinstance(prompt_ref, str) and not prompt_ref.startswith("You "):
                prompt_path = agent_dir / prompt_ref
                if prompt_path.is_file():
                    prompt_text = prompt_path.read_text(errors="replace")[:2000]
            elif isinstance(prompt_ref, str):
                prompt_text = prompt_ref

            results.append({
                "id": cfg.get("id", agent_dir.name),
                "name": cfg.get("label", cfg.get("id", agent_dir.name)),
                "description": f"Legacy agent from AgentCraft",
                "source": "legacy",
                "source_path": str(config_file.relative_to(PROJECT_ROOT)),
                "skills": cfg.get("skills", []),
                "system_prompt": prompt_text,
                "framework": "raw",
                "tags": list(cfg.get("framework_skills", {}).keys()) if cfg.get("framework_skills") else [],
            })
        except Exception:
            continue
    return results


def _scan_hermes_yaml_agents() -> list:
    """Scan core/hermes/agents/examples/*.yaml for Hermes YAML agents."""
    results = []
    if not HERMES_AGENTS_DIR.exists():
        return results
    for yaml_file in sorted(HERMES_AGENTS_DIR.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                cfg = yaml.safe_load(f) or {}
            llm = cfg.get("llm", {})
            prompt = cfg.get("prompt", {})
            results.append({
                "id": cfg.get("id", yaml_file.stem),
                "name": cfg.get("name", yaml_file.stem),
                "description": cfg.get("description", ""),
                "source": "hermes_yaml",
                "source_path": str(yaml_file.relative_to(PROJECT_ROOT)),
                "skills": cfg.get("skills", []),
                "system_prompt": prompt.get("system", ""),
                "llm_provider": llm.get("provider", "ollama"),
                "llm_model": llm.get("model", "llama3.2"),
                "temperature": llm.get("temperature", 0.7),
                "framework": cfg.get("framework", "raw"),
                "tags": cfg.get("tags", []),
                "version": cfg.get("version", "1.0.0"),
                "author": cfg.get("author"),
            })
        except Exception:
            continue
    return results


@router.get("/factory/agents")
async def list_factory_agents():
    """List all available agents from YAML definitions + DB."""
    legacy = _scan_legacy_agents()
    hermes_yaml = _scan_hermes_yaml_agents()
    return {"legacy": legacy, "hermes_yaml": hermes_yaml}


@router.post("/factory/import/{source}/{agent_id}")
async def import_agent_from_yaml(source: str, agent_id: str, session: Session = Depends(get_hermes_session)):
    """Import a YAML agent definition into the database."""
    if source == "legacy":
        agent_dir = LEGACY_AGENTS_DIR / agent_id
        config_file = agent_dir / "config.yaml"
        if not config_file.exists():
            raise HTTPException(status_code=404, detail=f"Legacy agent not found: {agent_id}")
        with open(config_file) as f:
            cfg = yaml.safe_load(f) or {}
        prompt_text = ""
        prompt_ref = cfg.get("prompt", "")
        if prompt_ref and isinstance(prompt_ref, str) and not prompt_ref.startswith("You "):
            prompt_path = agent_dir / prompt_ref
            if prompt_path.is_file():
                prompt_text = prompt_path.read_text(errors="replace")[:4000]
        elif isinstance(prompt_ref, str):
            prompt_text = prompt_ref

        new_id = str(uuid.uuid4())
        db_agent = Agent(
            id=new_id,
            name=cfg.get("label", cfg.get("id", agent_id)),
            description=f"Imported from legacy agent: {agent_id}",
            system_prompt=prompt_text or "You are a helpful assistant.",
            llm_provider="ollama",
            llm_model="llama3.2",
            framework="raw",
            skills=cfg.get("skills", []),
            config={"source": "legacy", "original_id": agent_id},
        )
    elif source == "hermes_yaml":
        # Try by agent_id.yaml first, then scan for matching ID inside files
        yaml_file = HERMES_AGENTS_DIR / f"{agent_id}.yaml"
        if not yaml_file.exists():
            # Scan files for matching internal id
            for f in HERMES_AGENTS_DIR.glob("*.yaml"):
                try:
                    with open(f) as fh:
                        cfg_check = yaml.safe_load(fh) or {}
                    if cfg_check.get("id") == agent_id:
                        yaml_file = f
                        break
                except Exception:
                    continue
        if not yaml_file.exists():
            raise HTTPException(status_code=404, detail=f"Hermes YAML agent not found: {agent_id}")
        with open(yaml_file) as f:
            cfg = yaml.safe_load(f) or {}
        llm = cfg.get("llm", {})
        prompt = cfg.get("prompt", {})
        new_id = str(uuid.uuid4())
        db_agent = Agent(
            id=new_id,
            name=cfg.get("name", agent_id),
            description=cfg.get("description", ""),
            system_prompt=prompt.get("system", "You are a helpful assistant."),
            llm_provider=llm.get("provider", "ollama"),
            llm_model=llm.get("model", "llama3.2"),
            temperature=llm.get("temperature", 0.7),
            framework=cfg.get("framework", "raw"),
            skills=cfg.get("skills", []),
            config={"source": "hermes_yaml", "original_id": agent_id, "mcp_servers": cfg.get("mcp_servers", [])},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    session.add(db_agent)
    session.commit()
    session.refresh(db_agent)
    return db_agent


@router.post("/factory/create")
async def create_agent_from_factory(body: dict, session: Session = Depends(get_hermes_session)):
    """Create a new agent from the factory with full configuration."""
    new_id = str(uuid.uuid4())
    db_agent = Agent(
        id=new_id,
        name=body.get("name", "New Agent"),
        description=body.get("description", ""),
        system_prompt=body.get("system_prompt", "You are a helpful assistant."),
        goal=body.get("goal"),
        persona=body.get("persona"),
        llm_provider=body.get("llm_provider", "ollama"),
        llm_model=body.get("llm_model", "llama3.2"),
        temperature=body.get("temperature", 0.7),
        max_tokens=body.get("max_tokens"),
        framework=body.get("framework", "raw"),
        skills=body.get("skills", []),
        tools_enabled=body.get("tools_enabled", []),
        config=body.get("config", {}),
    )
    session.add(db_agent)
    session.commit()
    session.refresh(db_agent)
    return db_agent
