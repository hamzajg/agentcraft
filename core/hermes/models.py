"""
Hermes core data models — Full persistent agent platform.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy import JSON, Text
from pydantic import BaseModel


# ─── Enums ────────────────────────────────────────────────────────────────────

class AgentFramework(str, Enum):
    RAW = "raw"
    LANGCHAIN = "langchain"
    CREWAI = "crewai"
    AUTOGEN = "autogen"
    LLAMAINDEX = "llamaindex"
    HAYSTACK = "haystack"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    GROQ = "groq"
    OLLAMA = "ollama"
    LM_STUDIO = "lm_studio"
    AZURE_OPENAI = "azure_openai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    TOGETHER = "together"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_UPDATED = "artifact_updated"
    MEMORY_UPDATED = "memory_updated"
    ERROR = "error"
    THINKING = "thinking"
    TOKEN = "token"


class ArtifactType(str, Enum):
    DOCUMENT = "document"
    CODE = "code"
    IMAGE = "image"
    REPORT = "report"
    CONFIG = "config"
    DATA = "data"
    OTHER = "other"


class MemoryType(str, Enum):
    LONG_TERM = "long_term"
    PROJECT = "project"
    SESSION = "session"
    EPISODIC = "episodic"


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ARTIFACT = "artifact"
    AGENT_MESSAGE = "agent_message"


# ─── Database Models ──────────────────────────────────────────────────────────

class Agent(SQLModel, table=True):
    """Persistent agent definition with full state."""
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    avatar: Optional[str] = Field(default=None)
    status: AgentStatus = Field(default=AgentStatus.IDLE)

    # Identity & Instructions
    system_prompt: str = Field(default="")
    goal: Optional[str] = Field(default=None)
    persona: Optional[str] = Field(default=None)

    # LLM Configuration
    llm_provider: LLMProvider = Field(default=LLMProvider.OLLAMA)
    llm_model: str = Field(default="llama3.2")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None)

    # Framework
    framework: AgentFramework = Field(default=AgentFramework.RAW)

    # Configuration
    config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    tools_enabled: List[str] = Field(default=[], sa_column=Column(JSON))
    skills: List[str] = Field(default=[], sa_column=Column(JSON))

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_active_at: Optional[datetime] = Field(default=None)

    # Relationships
    conversations: List["Conversation"] = Relationship(back_populates="agent")
    artifacts: List["Artifact"] = Relationship(back_populates="agent")
    memories: List["Memory"] = Relationship(back_populates="agent")
    runs: List["AgentRun"] = Relationship(back_populates="agent")


class Conversation(SQLModel, table=True):
    """A conversation session with an agent."""
    id: Optional[str] = Field(default=None, primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    title: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)

    # State
    is_active: bool = Field(default=True)
    message_count: int = Field(default=0)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="conversations")
    messages: List["Message"] = Relationship(back_populates="conversation")


class Message(SQLModel, table=True):
    """A message in a conversation — supports text, tool calls, artifacts."""
    id: Optional[str] = Field(default=None, primary_key=True)
    conversation_id: str = Field(foreign_key="conversation.id", index=True)

    # Content
    message_type: MessageType = Field(default=MessageType.USER)
    content: str = Field(default="", sa_column=Column(Text))

    # Tool call tracking
    tool_name: Optional[str] = Field(default=None)
    tool_args: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    tool_result: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Artifact reference
    artifact_id: Optional[str] = Field(default=None)

    # Token usage
    token_count: Optional[int] = Field(default=None)
    model_used: Optional[str] = Field(default=None)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    conversation: Conversation = Relationship(back_populates="messages")


class Artifact(SQLModel, table=True):
    """Generated output — documents, code, images, reports."""
    id: Optional[str] = Field(default=None, primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversation.id")

    # Content
    name: str = Field(index=True)
    artifact_type: ArtifactType = Field(default=ArtifactType.DOCUMENT)
    mime_type: Optional[str] = Field(default=None)
    content: str = Field(default="", sa_column=Column(Text))
    file_path: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)

    # Extra data
    extra_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    version: int = Field(default=1)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="artifacts")


class Memory(SQLModel, table=True):
    """Agent memory — long-term, project, session, episodic."""
    id: Optional[str] = Field(default=None, primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)

    # Content
    memory_type: MemoryType = Field(default=MemoryType.LONG_TERM)
    key: str = Field(index=True)
    content: str = Field(default="", sa_column=Column(Text))
    context: Optional[str] = Field(default=None)

    # Importance and access
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    access_count: int = Field(default=0)
    last_accessed_at: Optional[datetime] = Field(default=None)

    # Extra data
    extra_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    tags: List[str] = Field(default=[], sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="memories")


class Skill(SQLModel, table=True):
    """Reusable skill that agents can use."""
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    category: str = Field(default="general")

    # Definition
    skill_type: str = Field(default="tool")  # tool, prompt, pipeline
    definition: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # Configuration
    config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    is_builtin: bool = Field(default=False)
    is_enabled: bool = Field(default=True)

    # Metadata
    version: str = Field(default="1.0.0")
    author: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRun(SQLModel, table=True):
    """Agent execution run."""
    id: Optional[str] = Field(default=None, primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversation.id")

    # Execution
    status: RunStatus = Field(default=RunStatus.PENDING)
    mode: ExecutionMode = Field(default=ExecutionMode.SYNC)
    input_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    output_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Metrics
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)
    prompt_tokens: Optional[int] = Field(default=None)
    completion_tokens: Optional[int] = Field(default=None)
    total_tokens: Optional[int] = Field(default=None)

    # Error
    error_message: Optional[str] = Field(default=None)
    error_type: Optional[str] = Field(default=None)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="runs")


class ToolExecution(SQLModel, table=True):
    """Record of a tool being called by an agent."""
    id: Optional[str] = Field(default=None, primary_key=True)
    run_id: Optional[str] = Field(default=None, foreign_key="agentrun.id")
    agent_id: str = Field(foreign_key="agent.id", index=True)

    # Tool details
    tool_name: str = Field(index=True)
    tool_args: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    tool_result: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="pending")  # pending, running, completed, failed

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)

    # Error
    error_message: Optional[str] = Field(default=None)


class AgentMessage(SQLModel, table=True):
    """Agent-to-agent communication message."""
    id: Optional[str] = Field(default=None, primary_key=True)
    from_agent_id: str = Field(foreign_key="agent.id", index=True)
    to_agent_id: Optional[str] = Field(default=None, foreign_key="agent.id")

    # Content
    subject: Optional[str] = Field(default=None)
    content: str = Field(default="", sa_column=Column(Text))
    message_type: str = Field(default="direct")  # direct, broadcast, delegation

    # State
    is_read: bool = Field(default=False)
    is_processed: bool = Field(default=False)

    # Extra data
    extra_data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Pydantic API Models ─────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    description: str = ""
    avatar: Optional[str] = None
    system_prompt: str = ""
    goal: Optional[str] = None
    persona: Optional[str] = None
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    llm_model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    framework: AgentFramework = AgentFramework.RAW
    config: Dict[str, Any] = {}
    tools_enabled: List[str] = []
    skills: List[str] = []


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    status: Optional[AgentStatus] = None
    system_prompt: Optional[str] = None
    goal: Optional[str] = None
    persona: Optional[str] = None
    llm_provider: Optional[LLMProvider] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    framework: Optional[AgentFramework] = None
    config: Optional[Dict[str, Any]] = None
    tools_enabled: Optional[List[str]] = None
    skills: Optional[List[str]] = None


class MessageCreate(BaseModel):
    content: str
    message_type: MessageType = MessageType.USER


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ArtifactCreate(BaseModel):
    name: str
    artifact_type: ArtifactType = ArtifactType.DOCUMENT
    mime_type: Optional[str] = None
    content: str = ""
    file_path: Optional[str] = None
    extra_data: Dict[str, Any] = {}
    tags: List[str] = []


class MemoryCreate(BaseModel):
    memory_type: MemoryType = MemoryType.LONG_TERM
    key: str
    content: str
    context: Optional[str] = None
    importance: float = 0.5
    extra_data: Dict[str, Any] = {}
    tags: List[str] = []


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "general"
    skill_type: str = "tool"
    definition: Dict[str, Any] = {}
    config: Dict[str, Any] = {}
    version: str = "1.0.0"
    author: Optional[str] = None


class RunCreate(BaseModel):
    mode: ExecutionMode = ExecutionMode.ASYNC
    input_data: Dict[str, Any] = {}


class ToolCallRequest(BaseModel):
    tool_name: str
    tool_args: Dict[str, Any] = {}


class AgentMessageCreate(BaseModel):
    to_agent_id: Optional[str] = None
    subject: Optional[str] = None
    content: str
    message_type: str = "direct"
