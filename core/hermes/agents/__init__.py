"""
Hermes agent definition YAML schema and loader
"""

import yaml
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

from core.hermes.models import LLMProvider, AgentFramework


class LLMPConfig(BaseModel):
    """LLM configuration"""
    provider: LLMProvider = Field(default=LLMProvider.OLLAMA)
    model: str = Field(default="")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None)
    fallback: Optional[List[Dict[str, Any]]] = Field(default=None)


class PromptConfig(BaseModel):
    """Prompt configuration"""
    system: str = Field(default="")
    mid_system: Optional[str] = Field(default=None)
    user_template: str = Field(default="")

    @field_validator('user_template')
    @classmethod
    def validate_template_vars(cls, v: str) -> str:
        """Validate that template variables are properly formatted"""
        if v:
            vars_found = re.findall(r'\{\{(\w+)\}\}', v)
        return v


class AgentYAMLConfig(BaseModel):
    """Complete agent configuration from YAML"""
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(default="", description="Agent description")

    prompt: PromptConfig = Field(default_factory=PromptConfig)
    llm: LLMPConfig = Field(default_factory=LLMPConfig)

    framework: AgentFramework = Field(default=AgentFramework.RAW)

    skills: List[str] = Field(default_factory=list)
    mcp_servers: List[Dict[str, Any]] = Field(default_factory=list)

    config: Dict[str, Any] = Field(default_factory=dict)

    version: str = Field(default="1.0.0")
    author: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)


def load_agent_from_yaml(file_path: Path) -> AgentYAMLConfig:
    """Load agent configuration from YAML file"""
    if not file_path.exists():
        raise FileNotFoundError(f"Agent config file not found: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        yaml_content = yaml.safe_load(f)

    return AgentYAMLConfig(**yaml_content)


def load_agent_from_yaml_string(yaml_string: str) -> AgentYAMLConfig:
    """Load agent configuration from YAML string"""
    yaml_content = yaml.safe_load(yaml_string)
    return AgentYAMLConfig(**yaml_content)


def save_agent_to_yaml(config: AgentYAMLConfig, file_path: Path):
    """Save agent configuration to YAML file"""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            config.model_dump(exclude_none=True),
            f,
            default_flow_style=False,
            sort_keys=False
        )


def agent_yaml_to_db_config(config: AgentYAMLConfig) -> Dict[str, Any]:
    """Convert AgentYAMLConfig to database-compatible format"""
    return {
        "id": config.id,
        "name": config.name,
        "description": config.description,
        "system_prompt": config.prompt.system,
        "mid_system_prompt": config.prompt.mid_system,
        "user_template": config.prompt.user_template,
        "llm_provider": config.llm.provider,
        "llm_model": config.llm.model,
        "temperature": config.llm.temperature,
        "max_tokens": config.llm.max_tokens,
        "framework": config.framework,
        "config": {
            "skills": config.skills,
            "mcp_servers": config.mcp_servers,
            "version": config.version,
            "author": config.author,
            "tags": config.tags,
            "llm_fallback": config.llm.fallback,
            **config.config
        }
    }
