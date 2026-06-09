"""
Ollama LLM provider implementation
"""

import os
import json
from typing import Dict, Any, Optional, List, AsyncGenerator
import httpx
import logging

from core.hermes.llm import BaseLLMProvider, Message, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""

    def __init__(
        self,
        model: str = "llama3.2",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
        **kwargs
    ):
        super().__init__(model, temperature, max_tokens, **kwargs)

        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert internal Message format to Ollama format"""
        ollama_messages = []
        for msg in messages:
            ollama_msg = {
                "role": msg.role,
                "content": msg.content
            }
            if msg.tool_call_id:
                ollama_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                ollama_msg["tool_calls"] = msg.tool_calls
            ollama_messages.append(ollama_msg)
        return ollama_messages

    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Generate a response using Ollama API"""
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }

        if self.max_tokens:
            payload["options"]["num_predict"] = self.max_tokens
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        for key, value in self.extra_params.items():
            if key not in payload:
                payload[key] = value

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                content = result.get("message", {}).get("content", "")
                eval_count = result.get("eval_count", 0)
                prompt_eval_count = result.get("prompt_eval_count", 0)

                token_usage = {
                    "prompt_tokens": prompt_eval_count,
                    "completion_tokens": eval_count,
                    "total_tokens": eval_count + prompt_eval_count
                } if eval_count or prompt_eval_count else None

                return LLMResponse(
                    content=content,
                    finish_reason="stop",
                    token_usage=token_usage,
                    model=self.model,
                    provider_used=self.provider_name,
                    tool_calls=None
                )

        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Ollama generation error: {str(e)}")

    async def generate_stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using Ollama API"""
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
            }
        }

        if self.max_tokens:
            payload["options"]["num_predict"] = self.max_tokens
        if "max_tokens" in kwargs:
            payload["options"]["num_predict"] = kwargs["max_tokens"]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk_data = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            if token := chunk_data.get("message", {}).get("content"):
                                yield token

                            if chunk_data.get("done"):
                                break

        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama streaming error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Ollama stream generation error: {str(e)}")

    def validate_config(self) -> bool:
        """Validate Ollama configuration"""
        try:
            import asyncio
            async def check():
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{self.base_url}/api/tags")
                    response.raise_for_status()
                    models = [m["name"] for m in response.json().get("models", [])]
                    base = self.model.split(":")[0]
                    return any(m.startswith(base) for m in models)
            return asyncio.run(check())
        except Exception as e:
            logger.warning(f"Ollama config validation failed: {e}")
            return False

    def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information"""
        info = super().get_model_info()
        info.update({
            "base_url": self.base_url,
            "timeout": self.timeout,
            "is_local": True
        })
        return info

    async def list_models(self) -> List[str]:
        """List available Ollama models"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return [m["name"] for m in response.json().get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
