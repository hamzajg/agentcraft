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
    """Full message history for one agent channel."""
    return store.list_by_agent(agent_id, limit)


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
        status=MessageStatus.PENDING,
        created_at=datetime.utcnow(),
    )
    # Generate LLM suggestions if agent didn't provide any
    if not msg.suggestions:
        try:
            generated = await generate_suggestions(
                req.agent_id, label, req.question, req.file, req.partial_output
            )
            if generated:
                msg.suggestions = generated
        except Exception:
            pass

    store.save(msg)

    # Create the Future the agent will block on
    pending_store.create_future(msg.id)

    # Push to all open UI tabs immediately
    await manager.broadcast(WsEvent(
        event="clarification",
        payload=msg.model_dump(mode="json"),
    ))

    # Fire external notifications (Slack/Teams if configured)
    await notify_clarification(
        agent_label=label,
        question=req.question,
        file=req.file,
        message_id=msg.id,
    )

    logger.info("[comms] clarification from %s: %s", req.agent_id, req.question[:80])
    return {"message_id": msg.id, "status": "pending"}


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
