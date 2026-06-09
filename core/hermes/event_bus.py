"""
Hermes Event Bus — In-process asyncio implementation
"""

import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime
import json
import uuid
from dataclasses import dataclass, field

from core.hermes.models import EventType


@dataclass
class HermesEvent:
    """Event data structure"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    event_type: EventType = EventType.THINKING
    agent_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "type": self.event_type.value,
            "agent_id": self.agent_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence
        }

    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())


class EventBus:
    """In-process asyncio event bus for event streaming"""

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._global_subscribers: Set[asyncio.Queue] = set()
        self._sequence_counters: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def publish(self, event: HermesEvent) -> None:
        """Publish an event to all subscribers"""
        async with self._lock:
            if event.run_id not in self._sequence_counters:
                self._sequence_counters[event.run_id] = 0
            event.sequence = self._sequence_counters[event.run_id]
            self._sequence_counters[event.run_id] += 1

            if event.run_id in self._subscribers:
                for queue in self._subscribers[event.run_id]:
                    try:
                        await queue.put(event)
                    except Exception as e:
                        print(f"Error delivering event to subscriber: {e}")

            for queue in self._global_subscribers:
                try:
                    await queue.put(event)
                except Exception as e:
                    print(f"Error delivering event to global subscriber: {e}")

    async def subscribe_to_run(self, run_id: str) -> asyncio.Queue:
        """Subscribe to events for a specific run"""
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue()

            if run_id not in self._subscribers:
                self._subscribers[run_id] = set()

            self._subscribers[run_id].add(queue)
            self._queues[queue.__str__()] = queue

            return queue

    async def subscribe_global(self) -> asyncio.Queue:
        """Subscribe to all events globally"""
        async with self._lock:
            queue: asyncio.Queue = asyncio.Queue()
            self._global_subscribers.add(queue)
            self._queues[queue.__str__()] = queue
            return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe a queue from all events"""
        async with self._lock:
            queue_str = queue.__str__()

            for run_id in self._subscribers:
                if queue in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(queue)

            if queue in self._global_subscribers:
                self._global_subscribers.remove(queue)

            to_delete = [run_id for run_id, subs in self._subscribers.items() if not subs]
            for run_id in to_delete:
                del self._subscribers[run_id]

            if queue_str in self._queues:
                del self._queues[queue_str]

    def clear_run(self, run_id: str) -> None:
        """Clear all subscribers for a run"""
        if run_id in self._sequence_counters:
            del self._sequence_counters[run_id]


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Event helper functions

async def emit_run_started(run_id: str, agent_id: str) -> None:
    """Emit a run started event"""
    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.RUN_STARTED,
        agent_id=agent_id,
        data={"status": "started"}
    )
    await get_event_bus().publish(event)


async def emit_run_completed(
    run_id: str,
    agent_id: str,
    output_data: Dict[str, Any],
    token_usage: Optional[Dict[str, int]] = None
) -> None:
    """Emit a run completed event"""
    data = {"status": "completed", "output": output_data}
    if token_usage:
        data["token_usage"] = token_usage

    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.RUN_COMPLETED,
        agent_id=agent_id,
        data=data
    )
    await get_event_bus().publish(event)


async def emit_run_failed(
    run_id: str,
    agent_id: str,
    error_message: str,
    error_type: str = "Exception"
) -> None:
    """Emit a run failed event"""
    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.RUN_FAILED,
        agent_id=agent_id,
        data={
            "status": "failed",
            "error": error_message,
            "error_type": error_type
        }
    )
    await get_event_bus().publish(event)


async def emit_tool_called(
    run_id: str,
    agent_id: str,
    tool_name: str,
    tool_args: Dict[str, Any]
) -> None:
    """Emit a tool called event"""
    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.TOOL_CALLED,
        agent_id=agent_id,
        data={
            "tool": tool_name,
            "args": tool_args
        }
    )
    await get_event_bus().publish(event)


async def emit_tool_result(
    run_id: str,
    agent_id: str,
    tool_name: str,
    result: Any
) -> None:
    """Emit a tool result event"""
    from typing import Any
    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.TOOL_RESULT,
        agent_id=agent_id,
        data={
            "tool": tool_name,
            "result": result
        }
    )
    await get_event_bus().publish(event)


async def emit_error(
    run_id: str,
    agent_id: str,
    error_message: str,
    error_context: Optional[Dict[str, Any]] = None
) -> None:
    """Emit an error event"""
    data = {"error": error_message}
    if error_context:
        data["context"] = error_context

    event = HermesEvent(
        run_id=run_id,
        event_type=EventType.ERROR,
        agent_id=agent_id,
        data=data
    )
    await get_event_bus().publish(event)
