"""
Hermes Agent Factory — Creates agent instances from definitions
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from core.hermes.models import (
    Agent,
    LLMProvider,
    AgentFramework,
)
from core.hermes.llm import BaseLLMProvider, Message
from core.hermes.llm.factory import ProviderFactory


@dataclass
class AgentDefinition:
    """Bridge dataclass for factory — compatible with old interface."""
    id: str = "unknown"
    name: str = "Unnamed Agent"
    description: str = ""
    system_prompt: str = ""
    mid_system_prompt: Optional[str] = None
    user_template: str = ""
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    llm_model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    framework: AgentFramework = AgentFramework.RAW
    config: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Base class for all agent instances"""

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        llm_provider: BaseLLMProvider
    ):
        self.agent_id = agent_id
        self.config = config
        self.llm_provider = llm_provider
        self.created_at = datetime.utcnow()

    @abstractmethod
    async def execute(
        self,
        input_data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the agent with given input"""
        pass

    @abstractmethod
    async def execute_stream(
        self,
        input_data: Dict[str, Any],
        **kwargs
    ):
        """Execute the agent with streaming output"""
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "agent_id": self.agent_id,
            "framework": self.config.get("framework", "raw"),
            "llm_provider": self.llm_provider.provider_name,
            "llm_model": self.llm_provider.model,
            "created_at": self.created_at.isoformat()
        }


class RawAgent(BaseAgent):
    """Raw API agent — direct LLM calls with minimal abstraction"""

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        llm_provider: BaseLLMProvider
    ):
        super().__init__(agent_id, config, llm_provider)

        self.system_prompt = config.get("system_prompt", "")
        self.mid_system_prompt = config.get("mid_system_prompt")
        self.user_template = config.get("user_template", "")

    def _build_messages(
        self,
        input_data: Dict[str, Any]
    ) -> List[Message]:
        """Build message list from prompts and input data"""
        messages = []

        if self.system_prompt:
            messages.append(Message(
                role="system",
                content=self.system_prompt
            ))

        if self.mid_system_prompt:
            messages.append(Message(
                role="system",
                content=self.mid_system_prompt
            ))

        user_content = self._substitute_template(self.user_template, input_data)
        messages.append(Message(
            role="user",
            content=user_content
        ))

        return messages

    def _substitute_template(
        self,
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """Substitute variables in template using {{var}} syntax"""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result

    async def execute(
        self,
        input_data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute the raw agent"""
        messages = self._build_messages(input_data)

        try:
            response = await self.llm_provider.generate(
                messages=messages,
                **kwargs
            )

            return {
                "success": True,
                "response": response.content,
                "token_usage": response.token_usage,
                "model_used": response.model,
                "provider_used": response.provider_used,
                "finish_reason": response.finish_reason
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    async def execute_stream(
        self,
        input_data: Dict[str, Any],
        **kwargs
    ):
        """Execute the raw agent with streaming"""
        messages = self._build_messages(input_data)

        try:
            async for chunk in self.llm_provider.generate_stream(
                messages=messages,
                **kwargs
            ):
                yield {
                    "type": "chunk",
                    "content": chunk,
                    "agent_id": self.agent_id
                }

            yield {
                "type": "done",
                "agent_id": self.agent_id
            }

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__,
                "agent_id": self.agent_id
            }


class AgentFactory:
    """Factory for creating agent instances"""

    @staticmethod
    def create_agent(
        agent_definition: AgentDefinition
    ) -> BaseAgent:
        """Create an agent instance from a database definition"""
        # Create LLM provider
        llm_config = {
            "provider": agent_definition.llm_provider,
            "model": agent_definition.llm_model,
            "temperature": agent_definition.temperature,
            "max_tokens": agent_definition.max_tokens
        }

        llm_config.update(agent_definition.config.get("llm_config", {}))
        llm_provider = ProviderFactory.create_provider_from_config(llm_config)

        # Build agent config
        agent_config = {
            "framework": agent_definition.framework,
            "system_prompt": agent_definition.system_prompt,
            "mid_system_prompt": agent_definition.mid_system_prompt,
            "user_template": agent_definition.user_template,
            "skills": agent_definition.config.get("skills", []),
            "mcp_servers": agent_definition.config.get("mcp_servers", []),
            **agent_definition.config
        }

        framework = agent_definition.framework

        if framework == AgentFramework.RAW:
            return RawAgent(
                agent_id=agent_definition.id,
                config=agent_config,
                llm_provider=llm_provider
            )
        elif framework == AgentFramework.LANGCHAIN:
            from core.hermes.frameworks.langchain_adapter import LangChainAgent
            return LangChainAgent(
                agent_id=agent_definition.id,
                config=agent_config,
                llm_provider=llm_provider
            )
        elif framework == AgentFramework.CREWAI:
            raise NotImplementedError("CrewAI adapter not yet implemented")
        elif framework == AgentFramework.AUTOGEN:
            raise NotImplementedError("AutoGen adapter not yet implemented")
        elif framework == AgentFramework.LLAMAINDEX:
            raise NotImplementedError("LlamaIndex adapter not yet implemented")
        else:
            raise ValueError(f"Unsupported framework: {framework}")

    @staticmethod
    def create_agent_from_dict(
        agent_dict: Dict[str, Any]
    ) -> BaseAgent:
        """Create an agent instance from a dictionary"""
        agent_def = AgentDefinition(
            id=agent_dict.get("id", "unknown"),
            name=agent_dict.get("name", "Unnamed Agent"),
            description=agent_dict.get("description", ""),
            system_prompt=agent_dict.get("system_prompt", ""),
            mid_system_prompt=agent_dict.get("mid_system_prompt"),
            user_template=agent_dict.get("user_template", ""),
            llm_provider=LLMProvider(agent_dict.get("llm_provider", "ollama")),
            llm_model=agent_dict.get("llm_model", "llama3.2"),
            temperature=agent_dict.get("temperature", 0.7),
            max_tokens=agent_dict.get("max_tokens"),
            framework=AgentFramework(agent_dict.get("framework", "raw")),
            config=agent_dict.get("config", {})
        )

        return AgentFactory.create_agent(agent_def)
