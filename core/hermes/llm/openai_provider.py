"""
OpenAI LLM provider implementation
"""

import os
from typing import Dict, Any, Optional, List, AsyncGenerator
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from core.hermes.llm import BaseLLMProvider, Message, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        super().__init__(model, temperature, max_tokens, **kwargs)

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert internal Message format to OpenAI format"""
        openai_messages = []
        for msg in messages:
            openai_msg = {
                "role": msg.role,
                "content": msg.content
            }
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            openai_messages.append(openai_msg)
        return openai_messages

    async def generate(
        self,
        messages: List[Message],
        **kwargs
    ) -> LLMResponse:
        """Generate a response using OpenAI API"""
        openai_messages = self._convert_messages(messages)

        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]

        for key, value in self.extra_params.items():
            if key not in params:
                params[key] = value

        try:
            response: ChatCompletion = await self.client.chat.completions.create(**params)

            token_usage = None
            if response.usage:
                token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            tool_calls = None
            if response.choices[0].message.tool_calls:
                tool_calls = [
                    tc.model_dump()
                    for tc in response.choices[0].message.tool_calls
                ]

            return LLMResponse(
                content=response.choices[0].message.content or "",
                finish_reason=response.choices[0].finish_reason,
                token_usage=token_usage,
                model=response.model,
                provider_used=self.provider_name,
                tool_calls=tool_calls
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {str(e)}")

    async def generate_stream(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using OpenAI API"""
        openai_messages = self._convert_messages(messages)

        params = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True
        }

        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]

        for key, value in self.extra_params.items():
            if key not in params:
                params[key] = value

        try:
            stream = await self.client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise RuntimeError(f"OpenAI streaming error: {str(e)}")

    def validate_config(self) -> bool:
        """Validate OpenAI configuration"""
        if not self.api_key:
            return False
        return True

    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information"""
        info = super().get_model_info()
        info.update({
            "api_configured": bool(self.api_key),
            "available_models": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo"
            ]
        })
        return info
