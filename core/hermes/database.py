"""
Hermes database setup — uses SQLite for dev, PostgreSQL for prod.
Reuses the same DB_PATH pattern as comms for consistency.
"""

import os
import logging
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

logger = logging.getLogger(__name__)

# Default: SQLite in the comms directory (or wherever comms lives)
# For production, set HERMES_DATABASE_URL to a PostgreSQL URL
DB_PATH = Path(__file__).parent.parent.parent / "comms" / "hermes.db"

DATABASE_URL = os.getenv(
    "HERMES_DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)

# For SQLite, we need to enable same_thread
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL or other databases
    engine = create_engine(DATABASE_URL)


def init_hermes_db():
    """Initialize Hermes database tables"""
    from core.hermes.models import Agent, Conversation, Message, Artifact, Memory, Skill, AgentRun, ToolExecution, AgentMessage  # noqa
    SQLModel.metadata.create_all(engine)
    logger.info("[hermes] database initialised: %s", DATABASE_URL)


def get_hermes_session():
    """Get a Hermes database session (dependency injection for FastAPI)"""
    with Session(engine) as session:
        yield session


def get_hermes_session_direct() -> Session:
    """Get a direct session (for non-FastAPI usage)"""
    return Session(engine)
