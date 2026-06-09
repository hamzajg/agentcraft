"""
LLM provider factory for Hermes
"""

from typing import Optional, Dict, Any
from core.hermes.llm import BaseLLMProvider
from core.hermes.llm.openai_provider import OpenAIProvider
from core.hermes.llm.ollama_provider import OllamaProvider
from core.hermes.models import LLMProvider as LLMProviderEnum


class ProviderFactory:
    """Factory for creating LLM provider instances"""

    @staticmethod
    def create_provider(
        provider: LLMProviderEnum,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseLLMProvider:
        """Create an LLM provider instance"""
        if provider == LLMProviderEnum.OPENAI:
            return OpenAIProvider(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        elif provider == LLMProviderEnum.OLLAMA:
            return OllamaProvider(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        elif provider == LLMProviderEnum.ANTHROPIC:
            raise NotImplementedError("Anthropic provider not yet implemented")
        elif provider == LLMProviderEnum.GEMINI:
            raise NotImplementedError("Gemini provider not yet implemented")
        elif provider == LLMProviderEnum.GROQ:
            raise NotImplementedError("Groq provider not yet implemented")
        elif provider == LLMProviderEnum.AZURE_OPENAI:
            raise NotImplementedError("Azure OpenAI provider not yet implemented")
        elif provider == LLMProviderEnum.COHERE:
            raise NotImplementedError("Cohere provider not yet implemented")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def create_provider_from_config(config: Dict[str, Any]) -> BaseLLMProvider:
        """Create an LLM provider from a configuration dictionary"""
        provider = LLMProviderEnum(config.get("provider", "ollama"))
        model = config.get("model", "llama3.2")
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens")

        kwargs = {k: v for k, v in config.items()
                  if k not in ["provider", "model", "temperature", "max_tokens"]}

        return ProviderFactory.create_provider(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
