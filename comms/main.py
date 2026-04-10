"""
main.py — Agent Comms Server.

Endpoints:
  GET  /                       → chat UI (static/index.html)
  GET  /api/channels           → list agent channels with unread counts
  GET  /api/messages/{agent}   → message history for one agent
  GET  /api/pending            → all currently blocked agents
  POST /api/clarify            → agent posts a blocker (internal)
  POST /api/reply              → human posts a reply
  POST /api/status             → agent updates its status (internal)
  WS   /ws                     → real-time push to UI

Run:
  uvicorn main:app --port 7000 --reload
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import store
from . import pending as pending_store
from .models import (
    ClarificationRequest, ClarificationMessage,
    ReplyRequest, ReplyMessage,
    WsEvent, AgentStatus, MessageStatus, LogMessage,
    agent_label,
)
from .notifier import notify_clarification
from .llm_suggest import generate_suggestions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
ASSETS_DIR = STATIC_DIR / "assets"

# Ensure assets directory exists
if not ASSETS_DIR.exists():
    logger.warning(f"Assets directory not found: {ASSETS_DIR}")
else:
    logger.info(f"Serving assets from: {ASSETS_DIR}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    pending_store.set_loop(asyncio.get_running_loop())
    logger.info("[comms] server ready on :7000")
    yield


app = FastAPI(title="Agent Comms", version="1.0.0", lifespan=lifespan)

# Mount static files
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
    logger.info(f"Mounted assets at /assets -> {ASSETS_DIR}")
else:
    logger.error(f"Cannot mount assets: directory {ASSETS_DIR} does not exist")

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        logger.info("[ws] client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)
        logger.info("[ws] client disconnected (%d total)", len(self._connections))

    async def broadcast(self, event: WsEvent):
        payload = event.model_dump_json()
        if event.event == 'log':
            logger.debug("[ws] broadcasting %s to %d clients", event.event, len(self._connections))
        else:
            logger.info("[ws] broadcasting %s to %d clients", event.event, len(self._connections))
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)

    async def send_to(self, ws: WebSocket, event: WsEvent):
        await ws.send_text(event.model_dump_json())


manager = ConnectionManager()

# ── Static UI ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(STATIC_DIR / "index.html")


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/api/channels")
async def get_channels():
    """List all agent channels with message counts and unread indicators."""
    return store.list_agents_with_history()


@app.get("/api/messages/{agent_id}")
async def get_messages(agent_id: str, limit: int = 50):
    """Full message history for one agent (default: newest 50)."""
    return store.list_by_agent(agent_id, limit)


@app.get("/api/messages/{agent_id}/older")
async def get_older_messages(agent_id: str, before: str = None, limit: int = 20):
    """Load older messages before a cursor (created_at timestamp)."""
    return store.list_by_agent_cursor(agent_id, before, limit)


@app.get("/api/pending")
async def get_pending():
    """All currently blocked agents (status=pending)."""
    msgs = store.list_pending()
    return {
        "count": len(msgs),
        "agents": [m.agent_id for m in msgs],
        "messages": [m.model_dump() for m in msgs],
    }


@app.post("/api/clarify")
async def clarify(req: ClarificationRequest):
    """
    Agent POSTs here when it hits a blocker.
    Creates a pending Future — agent's thread will block on it.
    Broadcasts to all connected UI clients.
    """
    label = agent_label(req.agent_id)

    msg = ClarificationMessage(
        agent_id=req.agent_id,
        agent_label=label,
        task_id=req.task_id,
        iteration_id=req.iteration_id,
        file=req.file,
        question=req.question,
        partial_output=req.partial_output,
        suggestions=req.suggestions,
        status=req.status,
        created_at=datetime.utcnow(),
    )
    # Generate LLM suggestions if agent didn't provide any and status is PENDING
    if msg.status == MessageStatus.PENDING and not msg.suggestions:
        try:
            generated = await generate_suggestions(
                req.agent_id, label, req.question, req.file, req.partial_output
            )
            if generated:
                msg.suggestions = generated
        except Exception:
            pass

    store.save(msg)

    # Create the Future the agent will block on only if status is PENDING
    if msg.status == MessageStatus.PENDING:
        pending_store.create_future(msg.id)

    # Push to all open UI tabs immediately
    await manager.broadcast(WsEvent(
        event="clarification",
        payload=msg.model_dump(mode="json"),
    ))

    # Also broadcast updated channels list
    channels = store.list_agents_with_history()
    await manager.broadcast(WsEvent(
        event="channels_updated",
        payload={"channels": channels},
    ))

    # Fire external notifications (Slack/Teams if configured) for PENDING
    if msg.status == MessageStatus.PENDING:
        await notify_clarification(
            agent_label=label,
            question=req.question,
            file=req.file,
            message_id=msg.id,
        )

    logger.info("[comms] %s from %s: %s", msg.status, req.agent_id, req.question[:80])
    return {"message_id": msg.id, "status": msg.status.value}


@app.post("/api/reply")
async def reply(req: ReplyRequest):
    """
    Human POSTs their reply from the UI.
    Unblock the waiting agent thread and update UI.
    Supports @mentions to create collaboration requests for other agents.
    """
    msg = store.get(req.message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.status != MessageStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Message already {msg.status.value}")

    # Persist reply
    updated = store.mark_replied(req.message_id, req.reply)

    # Unblock the waiting agent thread (if using Future-based blocking)
    resolved = pending_store.resolve(req.message_id, req.reply)
    if not resolved:
        logger.debug("[comms] no pending future for %s (using polling mechanism)", req.message_id)

    # Extract @mentions from reply text and create collaboration requests
    import re
    mentions_match = re.findall(r'@(\w+)', req.reply)
    if mentions_match:
        valid_agents = ['spec', 'architect', 'planner', 'backend_dev', 'test_dev', 
                       'config_agent', 'docs_agent', 'reviewer', 'integration_test', 'cicd']
        for agent_mention in mentions_match:
            if agent_mention in valid_agents:
                # Create a collaboration request for the mentioned agent
                collab_msg = ClarificationMessage(
                    agent_id=agent_mention,
                    agent_label=agent_label(agent_mention),
                    task_id=f"{msg.task_id}_collab",
                    iteration_id=msg.iteration_id,
                    question=f"[From {msg.agent_id}] {req.reply}",
                    status=MessageStatus.PENDING,
                    created_at=datetime.utcnow(),
                )
                store.save(collab_msg)
                pending_store.create_future(collab_msg.id)
                
                # Broadcast collaboration request
                await manager.broadcast(WsEvent(
                    event="clarification",
                    payload=collab_msg.model_dump(mode="json"),
                ))
                logger.info("[comms] collaboration request to %s from %s", agent_mention, msg.agent_id)

    # Broadcast the complete updated message to UI
    if updated:
        reply_event = WsEvent(
            event="reply_confirmed",
            payload=updated.model_dump(mode="json"),
        )
        await manager.broadcast(reply_event)
        logger.info("[comms] reply sent to %s: %s", msg.agent_id, req.reply[:60])
        return {"status": "replied", "agent_id": msg.agent_id, "message": updated.model_dump(mode="json")}
    else:
        raise HTTPException(status_code=500, detail="Failed to update message")


@app.post("/api/status")
async def update_status(status: AgentStatus):
    """Agent reports its current execution state — shown in sidebar."""
    await manager.broadcast(WsEvent(
        event="agent_status",
        payload=status.model_dump(),
    ))
    return {"ok": True}


@app.post("/api/log")
async def log_message(log: LogMessage):
    """Agent sends a log message — broadcast to console view."""
    await manager.broadcast(WsEvent(
        event="log",
        payload=log.model_dump(),
    ))
    return {"ok": True}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)

    # Send current state on connect
    channels = store.list_agents_with_history()
    pending  = store.list_pending()
    await manager.send_to(ws, WsEvent(
        event="init",
        payload={
            "channels": channels,
            "pending":  [m.model_dump(mode="json") for m in pending],
        },
    ))

    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.get("/api/stats")
async def get_stats():
    """Summary counts for the header badge."""
    pending = store.list_pending()
    channels = store.list_agents_with_history()
    return {
        "pending_count": len(pending),
        "agent_count":   len(channels),
        "pending_agents": [m.agent_id for m in pending],
    }


@app.delete("/api/messages/{message_id}")
async def dismiss_message(message_id: str):
    """Dismiss a replied or expired message (UI cleanup only)."""
    msg = store.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.status == MessageStatus.PENDING:
        raise HTTPException(status_code=409, detail="Cannot dismiss a pending message")
    return {"dismissed": message_id}


@app.get("/api/metrics")
async def metrics_stream():
    """
    Server-Sent Events stream of system metrics.
    React monitor page subscribes to this for live gauges.
    Polls every 2 seconds.
    """
    import sys, asyncio, json as _json
    from pathlib import Path
    from fastapi.responses import StreamingResponse

    ai_team = Path(__file__).parent.parent
    

    async def generate():
        while True:
            try:
                from monitor.collector import collect
                m = collect()
                yield f"data: {_json.dumps(m.to_dict())}\n\n"
            except Exception as e:
                yield f"data: {_json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/hardware")
async def hardware_profile():
    """Return the hardware profile from model-profile.yaml if it exists."""
    import sys
    from pathlib import Path
    ai_team = Path(__file__).parent.parent
    profile = Path(__file__).parent.parent / "model-profile.yaml"
    if not profile.exists():
        return {"profile": None, "message": "Run: agentcraft diagnose"}
    try:
        import yaml
        return yaml.safe_load(profile.read_text())
    except Exception as e:
        return {"error": str(e)}


# ── RAG repository endpoints ──────────────────────────────────────────────────

def _rag_store_path():
    import yaml
    from pathlib import Path
    repo_root = Path(__file__).parent.parent
    ws_file   = repo_root / "workspace.yaml"
    if ws_file.exists():
        ws  = yaml.safe_load(ws_file.read_text()) or {}
        base = ws.get("paths", {}).get("output", "output")
        sub  = ws.get("rag", {}).get("store_path", ".rag")
        return repo_root / base / sub
    return repo_root / "output" / ".rag"


# ═══════════════════════════════════════════════════════════════════════
# RAG observatory endpoints
# ═══════════════════════════════════════════════════════════════════════

def _rag_store_path() -> "Path":
    """Resolve the LanceDB store path from workspace.yaml."""
    import sys
    from pathlib import Path as P
    ai_team   = P(__file__).parent.parent
    
    repo_root = P(__file__).parent.parent
    try:
        import yaml
        ws = yaml.safe_load((repo_root / "workspace.yaml").read_text())
    except Exception:
        ws = {}
    output = repo_root / ws.get("paths", {}).get("output", ".")
    return output / ".rag"


def _make_rag_stats():
    from rag.rag_stats import RagStats
    return RagStats(_rag_store_path())


@app.get("/api/rag/stats")
async def api_rag_stats():
    """Full RAG index snapshot: chunk counts, file counts,
    line counts, collection/language breakdown, query health."""
    try:
        return _make_rag_stats().snapshot()
    except Exception as e:
        return {"error": str(e), "index": {"status": "unavailable",
                "total_chunks": 0, "total_files": 0,
                "total_lines": 0, "total_chars": 0,
                "collections": {}, "languages": {}}}


@app.get("/api/rag/files")
async def api_rag_files(limit: int = 200):
    """Per-file breakdown: path, collection, language,
    chunk count, line count, character count, existence flag."""
    try:
        return _make_rag_stats().files(limit=limit)
    except Exception:
        return []


@app.get("/api/rag/queries")
async def api_rag_queries(limit: int = 50):
    """Query activity log: recent queries, top retrieved sources,
    queries per agent, aggregate summary."""
    try:
        return _make_rag_stats().queries(limit=limit)
    except Exception:
        return {"recent": [], "top_sources": [], "by_agent": [], "summary": {}}


@app.post("/api/rag/search")
async def api_rag_search(body: dict):
    """
    Test semantic search against the live store.
    Body: { "query": str, "top_k": int (default 5), "collection": str (optional) }
    Returns: { "query", "count", "duration_ms", "results": [{source, preview}] }
    """
    import sys, time
    from pathlib import Path as P
    ai_team = P(__file__).parent.parent
    

    query      = body.get("query", "").strip()
    top_k      = int(body.get("top_k", 5))
    collection = body.get("collection") or None

    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    from rag.rag_client import RagClient
    client = RagClient(store_path=_rag_store_path())
    if not client.setup():
        return {"error": "RAG store unavailable", "results": []}

    try:
        t0    = time.time()
        paths = client.retrieve(query, top_k=top_k, collection=collection)
        ms    = round((time.time() - t0) * 1000, 1)

        results = []
        for p in paths:
            raw    = p.read_text(errors="replace")
            source = ""
            for line in raw.splitlines():
                if "RAG context from:" in line:
                    source = line.replace("<!-- RAG context from:", "").replace("-->", "").strip()
                    break
            body_text = raw
            if source:
                body_text = raw.replace(f"<!-- RAG context from: {source} -->\n\n", "")
            results.append({
                "source":  source,
                "preview": body_text[:400].strip(),
            })

        return {"query": query, "count": len(results),
                "duration_ms": ms, "results": results}
    finally:
        client.close()


@app.post("/api/rag/reindex")
async def api_rag_reindex(body: dict = {}):
    """
    Trigger background re-indexing of docs/ and repo root.
    Body: { "force": bool }  — force=true bypasses hash cache.
    Returns immediately; indexing runs in background.
    """
    import asyncio, sys
    from pathlib import Path as P
    ai_team   = P(__file__).parent.parent
    
    repo_root = P(__file__).parent.parent
    try:
        import yaml
        ws = yaml.safe_load((repo_root / "workspace.yaml").read_text())
    except Exception:
        ws = {}
    docs_dir = repo_root / ws.get("paths", {}).get("docs", "docs")
    output   = repo_root / ws.get("paths", {}).get("output", ".")
    force    = bool(body.get("force", False))
    store    = _rag_store_path()

    async def _run():
        from rag.rag_client import RagClient
        client = RagClient(store_path=store)
        if client.setup():
            client.ingest_directory(docs_dir, "docs",     force=force)
            if output.exists():
                client.ingest_directory(output, "codebase", force=force)
            client.close()

    asyncio.create_task(_run())
    return {"status": "started", "force": force}


@app.delete("/api/rag/collection/{collection_name}")
async def api_rag_clear_collection(collection_name: str):
    """Delete all chunks for one collection (docs / codebase / legacy)."""
    allowed = {"docs", "codebase", "legacy"}
    if collection_name not in allowed:
        raise HTTPException(status_code=422,
                            detail=f"collection must be one of {allowed}")
    try:
        import lancedb
        db    = lancedb.connect(str(_rag_store_path()))
        if "chunks" not in db.table_names():
            return {"deleted": 0}
        table = db.open_table("chunks")
        before = table.count_rows()
        table.delete(f"collection = '{collection_name}'")
        after  = table.count_rows()
        return {"collection": collection_name, "deleted": before - after}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# AgentBus endpoints — agent-to-agent communication visibility
# ═══════════════════════════════════════════════════════════════════════

def _get_bus():
    """Get the AgentBus instance, or None if no build is running."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.bus import AgentBus
        return AgentBus.instance()
    except Exception:
        return None


def _wire_bus_to_ws():
    """Inject the WebSocket broadcast function into AgentBus."""
    bus = _get_bus()
    if bus:
        async def _push(event: str, payload: dict):
            await manager.broadcast({"event": event, "payload": payload})
        # Wrap sync-safe: bus calls from threads, WS is async
        import asyncio
        def _sync_push(event: str, payload: dict):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(_push(event, payload), loop)
            except Exception:
                pass
        bus.set_ws_push(_sync_push)


@app.on_event("startup")
async def _startup_bus():
    _wire_bus_to_ws()


@app.get("/api/bus/messages")
async def api_bus_messages(limit: int = 100):
    """
    Recent agent-to-agent messages on the AgentBus.
    Returns: list of {id, type, from_agent, to_agent, content, ts, task_id}
    """
    bus = _get_bus()
    if not bus:
        return []
    return bus.messages(limit=limit)


@app.get("/api/bus/context")
async def api_bus_context():
    """
    Shared context store snapshot.
    Keys use convention: '<role>.<topic>' e.g. 'architect.iteration_plan'
    """
    bus = _get_bus()
    if not bus:
        return {}
    return bus.context_snapshot()


@app.get("/api/bus/messages/{agent_a}/{agent_b}")
async def api_bus_thread(agent_a: str, agent_b: str):
    """Messages between two specific agents."""
    bus = _get_bus()
    if not bus:
        return []
    return bus.messages_between(agent_a, agent_b)


@app.post("/api/bus/message")
async def api_bus_receive_message(message: dict):
    """
    Receive an AgentBus message from the orchestrator process.
    This allows the comms server to display agent-to-agent communication
    even when running in a separate process.
    """
    from core.bus import BusMessage, MsgType
    from datetime import datetime
    
    bus = _get_bus()
    if not bus:
        return {"status": "error", "message": "AgentBus not initialized"}
    
    try:
        # Reconstruct the BusMessage
        msg = BusMessage(
            id=message["id"],
            type=MsgType(message["type"]),
            from_agent=message["from_agent"],
            to_agent=message.get("to_agent"),
            content=message["content"],
            ref_id=message.get("ref_id"),
            ts=message.get("ts", datetime.utcnow().timestamp()),
            task_id=message.get("task_id"),
            iteration_id=message.get("iteration_id"),
        )
        
        # Mark as from comms to prevent re-forwarding loop
        msg._from_comms = True
        
        # Record it in the local bus
        bus._record(msg)
        
        # Also push to WebSocket clients
        event_map = {
            MsgType.QUERY: "agent_query",
            MsgType.REPLY: "agent_reply",
            MsgType.CONTEXT: "agent_context",
            MsgType.DELEGATE: "agent_delegate",
            MsgType.BROADCAST: "agent_broadcast",
        }
        
        ws_event = event_map.get(msg.type, "agent_bus_message")
        
        # Broadcast via WebSocket
        import asyncio
        async def _push():
            await manager.broadcast({"event": ws_event, "payload": msg.to_dict()})
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_push(), loop)
        except Exception:
            pass
        
        return {"status": "ok"}
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to process bus message: {e}")
        return {"status": "error", "message": str(e)}

# ═══════════════════════════════════════════════════════════════════════
# EventStream → WebSocket bridge
# ═══════════════════════════════════════════════════════════════════════

async def _es_subscriber(event: dict):
    """Forward every EventStream event to all WS clients."""
    await manager.broadcast(WsEvent(event=event["type"], payload=event))


@app.on_event("startup")
async def _startup_event_bridge():
    import asyncio
    loop = asyncio.get_running_loop()
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.event_stream import ES
        ES.set_loop(loop)
        ES.subscribe(_es_subscriber)
        logger.info("[comms] EventStream bridge wired")
    except Exception as e:
        logger.warning("[comms] EventStream not available: %s", e)


# ═══════════════════════════════════════════════════════════════════════
# Live observability endpoints
# ═══════════════════════════════════════════════════════════════════════

def _get_es():
    try:
        from core.event_stream import ES
        return ES
    except Exception:
        return None


def _get_cc():
    try:
        from core.control import CC
        return CC
    except Exception:
        return None


@app.get("/api/live/events")
async def live_events(limit: int = 200, since: float = 0):
    """
    Recent events from the ring buffer.
    Pass ?since=<ts> to get only events newer than that timestamp.
    """
    es = _get_es()
    if not es:
        return []
    if since > 0:
        return es.since(since)
    return es.recent(limit)


@app.get("/api/build/state")
async def build_state():
    """
    Reconstruct current build state from the persistent event store.
    Returns: {build_status, current_phase, current_iter, completed_iterations, ...}
    """
    import sys, json
    from pathlib import Path as P
    ai_dir = P(__file__).parent.parent
    events_file = ai_dir / ".ai" / "events.jsonl"

    if not events_file.exists():
        return {"build_status": "idle", "resume_from_iteration": 1}

    try:
        state = {
            "completed_iterations": [],
            "build_status": "idle",
            "current_phase": None,
            "current_iter": None,
            "phases_completed": [],
            "delivered_files": [],
            "approved_count": 0,
            "rejected_count": 0,
            "resume_from_iteration": 1,
            "last_event_ts": 0,
        }

        with open(events_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue

                etype = ev.get("type", "")
                data = ev.get("data", {})
                ts = ev.get("ts", 0)
                state["last_event_ts"] = max(state["last_event_ts"], ts)

                if etype == "build_started":
                    state["build_status"] = "running"
                    state["completed_iterations"] = []
                    state["phases_completed"] = []
                    state["delivered_files"] = []
                    state["approved_count"] = 0
                    state["rejected_count"] = 0
                elif etype == "build_done":
                    state["build_status"] = "done"
                    state["current_iter"] = None
                elif etype == "stopped":
                    state["build_status"] = "stopped"
                elif etype == "error":
                    state["build_status"] = "error"
                elif etype == "paused":
                    state["build_status"] = "paused"
                elif etype == "resumed":
                    state["build_status"] = "running"
                elif etype == "phase_started":
                    state["current_phase"] = data.get("phase")
                elif etype == "phase_done":
                    p = data.get("phase")
                    if p and p not in state["phases_completed"]:
                        state["phases_completed"].append(p)
                elif etype == "iter_started":
                    state["current_iter"] = data.get("id")
                elif etype == "iter_done":
                    iid = data.get("id")
                    ok = data.get("approved", False)
                    if iid is not None:
                        if ok and iid not in state["completed_iterations"]:
                            state["completed_iterations"].append(iid)
                            state["approved_count"] += 1
                        elif not ok:
                            state["rejected_count"] += 1
                        if state["current_iter"] == iid:
                            state["current_iter"] = None
                elif etype == "file_written":
                    fp = data.get("path")
                    if fp and fp not in state["delivered_files"]:
                        state["delivered_files"].append(fp)

        # Compute resume point
        if state["build_status"] == "done":
            state["resume_from_iteration"] = 1
        elif state["completed_iterations"]:
            state["resume_from_iteration"] = max(state["completed_iterations"]) + 1
        else:
            state["resume_from_iteration"] = 1

        return state
    except Exception as e:
        return {"error": str(e), "build_status": "unknown"}


@app.post("/api/log")
async def post_log(req: LogMessage):
    """Agent posts a log message to the console."""
    await manager.broadcast(WsEvent(event="log", payload=req.model_dump()))
    return {"ok": True}


@app.post("/api/live/emit")
async def live_emit(event: dict):
    """Receive an event from an external process (e.g. orchestrator) and broadcast it."""
    from core.event_stream import ES
    # We use inject to preserve the original ID and TS
    ES.inject(event)
    return {"ok": True}


@app.post("/api/live/reset")
async def live_reset():
    from core.event_stream import ES
    ES.clear()
    return {"ok": True}


@app.post("/api/control/reset")
async def control_reset():
    cc = _get_cc()
    if cc:
        cc.reset()
    return {"ok": True}


@app.get("/api/control/state")
async def control_state():
    """External processes poll this to sync their local CC state."""
    cc = _get_cc()
    if not cc:
        return {"error": "no build running"}

    with cc._mu:
        # We only want to return "new" directives or all of them?
        # Pop them from the server's queue to send to client
        directives = []
        while not cc._directives.empty():
            directives.append(cc._directives.get())

        gates = {}
        for gid, gate in cc._approval_gates.items():
            gates[gid] = {
                "approved": gate.approved,
                "reason":   gate.reject_reason,
            }

    return {
        "stopped":    cc._stopped.is_set(),
        "pause_task": cc._pause_after_task.is_set(),
        "pause_iter": cc._pause_after_iter.is_set(),
        "directives": directives,
        "gates":      gates,
    }


@app.get("/api/live/state")
async def live_state():
    """Current build state: control flags, approval gates, whether streaming is active."""
    cc = _get_cc()
    es = _get_es()
    cc_state = cc.state() if cc else {}
    recent   = es.recent(10) if es else []
    # Derive running state from last few events
    last_types = [e["type"] for e in recent]
    build_running = any(t in ("build_started", "task_started", "iter_started", "aider_token")
                        for t in last_types)
    build_done    = "build_done" in last_types or "stopped" in last_types
    return {
        "build_running": build_running and not build_done,
        "build_done":    build_done,
        **cc_state,
    }


@app.get("/api/live/file")
async def live_file(path: str):
    """
    Read a file from the workspace (partial or complete).
    Used by the UI file peek drawer.
    """
    from pathlib import Path as P
    repo_root = P(__file__).parent.parent
    try:
        import yaml
        ws     = yaml.safe_load((repo_root / "workspace.yaml").read_text())
        output = repo_root / ws.get("paths", {}).get("output", ".")
    except Exception:
        output = repo_root
    target = output / path.lstrip("/")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    # Safety: only serve files under workspace
    try:
        target.resolve().relative_to(output.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside workspace")
    return {
        "path":       path,
        "content":    target.read_text(errors="replace"),
        "size_bytes": target.stat().st_size,
        "exists":     True,
    }


def _get_workspace_paths():
    """Get workspace paths from workspace.yaml."""
    from pathlib import Path
    repo_root = Path(__file__).parent.parent
    try:
        import yaml
        ws = yaml.safe_load((repo_root / "workspace.yaml").read_text()) or {}
        paths = ws.get("paths", {})
        return {
            "root": repo_root,
            "docs": repo_root / paths.get("docs", "docs"),
            "workflow": repo_root / paths.get("workflow", ".ai"),
            "output": repo_root / paths.get("output", "output"),
        }
    except Exception:
        return {
            "root": repo_root,
            "docs": repo_root / "docs",
            "workflow": repo_root / ".ai",
            "output": repo_root / "output",
        }


@app.get("/api/workspace/paths")
async def workspace_paths():
    """Get all workspace folder paths."""
    paths = _get_workspace_paths()
    return {
        "docs": {
            "path": str(paths["docs"].relative_to(paths["root"])),
            "exists": paths["docs"].exists(),
            "label": "Docs",
            "description": "Project requirements, architecture, and design docs",
        },
        "workflow": {
            "path": str(paths["workflow"].relative_to(paths["root"])),
            "exists": paths["workflow"].exists(),
            "label": "Workflow",
            "description": "Iterations, tasks, and agent collaboration",
        },
        "project": {
            "path": str(paths["output"].relative_to(paths["root"])),
            "exists": paths["output"].exists(),
            "label": "Project",
            "description": "Source code and generated artifacts",
        },
    }


@app.get("/api/workspace/files")
async def list_workspace_files(folder: str = "docs", path: str = ""):
    """
    List files and directories in a workspace folder.
    
    Args:
        folder: One of 'docs', 'workflow', 'project'
        path: Relative path within the folder (empty = root)
    """
    from pathlib import Path
    paths = _get_workspace_paths()
    
    folder_map = {
        "docs": paths["docs"],
        "workflow": paths["workflow"],
        "project": paths["output"],
    }
    
    base = folder_map.get(folder, paths["root"])
    if not base.exists():
        return {"files": [], "folder": folder, "path": path, "exists": False}
    
    target = (base / path) if path else base
    if not target.exists() or not target.is_dir():
        return {"files": [], "folder": folder, "path": path, "exists": False}
    
    files = []
    try:
        for item in sorted(target.iterdir()):
            rel_path = str(item.relative_to(base))
            files.append({
                "name": item.name,
                "path": rel_path,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
                "modified": item.stat().st_mtime if item.is_file() else None,
                "extension": item.suffix.lower() if item.is_file() else None,
            })
    except PermissionError:
        return {"files": [], "folder": folder, "path": path, "error": "Permission denied"}
    
    return {
        "files": files,
        "folder": folder,
        "path": path,
        "exists": True,
        "base_path": str(base.relative_to(paths["root"])),
    }


@app.get("/api/workspace/read")
async def read_workspace_file(folder: str = "docs", path: str = ""):
    """
    Read a file from a workspace folder.
    
    Args:
        folder: One of 'docs', 'workflow', 'project'
        path: Relative path to the file
    """
    from pathlib import Path
    paths = _get_workspace_paths()
    
    folder_map = {
        "docs": paths["docs"],
        "workflow": paths["workflow"],
        "project": paths["output"],
    }
    
    base = folder_map.get(folder, paths["root"])
    if not base.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder}")
    
    target = base / path
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Path is a directory")
    
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside workspace")
    
    content = target.read_text(errors="replace")
    lines = content.splitlines()
    
    return {
        "path": path,
        "folder": folder,
        "content": content,
        "lines": lines,
        "line_count": len(lines),
        "size_bytes": len(content.encode('utf-8')),
        "exists": True,
    }


@app.get("/api/live/stream")
async def live_stream():
    """
    SSE stream of EventStream events.
    Alternative to WebSocket for clients that prefer SSE.
    """
    import asyncio
    from fastapi.responses import StreamingResponse

    es = _get_es()
    if not es:
        async def _empty():
            yield "data: {}\n\n"
        return StreamingResponse(_empty(), media_type="text/event-stream")

    q: asyncio.Queue = asyncio.Queue()

    async def _cb(event: dict):
        await q.put(event)

    es.subscribe(_cb)

    async def generate():
        try:
            # Send history first
            for ev in es.recent(100):
                import json
                yield f"data: {json.dumps(ev)}\n\n"
            # Then stream new events
            while True:
                ev = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(ev)}\n\n"
        except asyncio.TimeoutError:
            yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            es.unsubscribe(_cb)

    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache",
                                       "X-Accel-Buffering": "no"})


# ═══════════════════════════════════════════════════════════════════════
# Control endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/control/pause")
async def control_pause():
    """Pause the build after the current task completes."""
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.pause_after_task()
    return {"status": "pause_after_task queued"}


@app.post("/api/control/pause-iter")
async def control_pause_iter():
    """Pause the build after the current iteration completes."""
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.pause_after_iter()
    return {"status": "pause_after_iter queued"}


@app.post("/api/control/resume")
async def control_resume():
    """Resume a paused build."""
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.resume()
    return {"status": "resumed"}


@app.post("/api/control/stop")
async def control_stop():
    """Stop the build cleanly after the current step."""
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.stop()
    return {"status": "stop signal sent"}


@app.post("/api/control/directive")
async def control_directive(body: dict):
    """
    Inject a directive into the next agent's task context.
    Body: {"text": "Use CompletableFuture not Reactor throughout"}
    """
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.inject_directive(text)
    return {"status": "directive queued", "text": text}


@app.post("/api/control/approve")
async def control_approve(body: dict):
    """Approve a pending iteration gate. Body: {"iteration_id": 2}"""
    iter_id = body.get("iteration_id")
    if iter_id is None:
        raise HTTPException(status_code=422, detail="iteration_id required")
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.approve(int(iter_id))
    return {"status": "approved", "iteration_id": iter_id}


@app.post("/api/control/reject")
async def control_reject(body: dict):
    """Reject a pending iteration gate. Body: {"iteration_id": 2, "reason": "..."}"""
    iter_id = body.get("iteration_id")
    reason  = body.get("reason", "Rejected by user")
    if iter_id is None:
        raise HTTPException(status_code=422, detail="iteration_id required")
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.reject(int(iter_id), reason)
    return {"status": "rejected", "iteration_id": iter_id, "reason": reason}


@app.post("/api/control/gates")
async def control_gates(body: dict):
    """Enable or disable approval gates. Body: {"enabled": true}"""
    cc = _get_cc()
    if not cc:
        raise HTTPException(status_code=503, detail="No build running")
    cc.set_approval_gates(bool(body.get("enabled", True)))
    return {"approval_gates_enabled": bool(body.get("enabled", True))}


# ── SPA Catch-all ─────────────────────────────────────────────────────────────
# Serve index.html for any non-API route (enables React Router SPA routing)

@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve index.html for SPA routes."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    return FileResponse(STATIC_DIR / "index.html")
