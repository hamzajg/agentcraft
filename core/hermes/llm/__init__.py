"""
Base LLM provider interface for Hermes
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class Message(BaseModel):
    """Chat message"""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMResponse(BaseModel):
    """LLM response"""
    content: str
    finish_reason: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    model: str
    provider_used: str
    tool_calls: Optional[List[Dict[str, Any]]] = None


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs

    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Message],
        **kwargs
    ):
        """Generate a streaming response from the LLM"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name"""
        pass

    def validate_config(self) -> bool:
        """Validate provider configuration"""
        return True

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
