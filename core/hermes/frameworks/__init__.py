"""
LangChain framework adapter for Hermes
"""

from typing import Dict, Any, List
from core.hermes.factory import BaseAgent
from core.hermes.llm import BaseLLMProvider, Message


class LangChainAgent(BaseAgent):
    """LangChain framework adapter"""

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

        self.langchain_config = config.get("langchain_config", {})
        self.tools = config.get("skills", [])

        # Import LangChain lazily
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            self.LangChainAvailable = True
            self.SystemMessage = SystemMessage
            self.HumanMessage = HumanMessage
        except ImportError:
            self.LangChainAvailable = False

    def _build_langchain_messages(self, input_data: Dict[str, Any]) -> List:
        """Build LangChain message list from prompts and input data"""
        if not self.LangChainAvailable:
            raise RuntimeError("LangChain is not installed. Install with: pip install langchain langchain-core")

        messages = []

        if self.system_prompt:
            messages.append(self.SystemMessage(content=self.system_prompt))

        if self.mid_system_prompt:
            messages.append(self.SystemMessage(content=self.mid_system_prompt))

        user_content = self._substitute_template(self.user_template, input_data)
        messages.append(self.HumanMessage(content=user_content))

        return messages

    def _substitute_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in template using {{var}} syntax"""
        result = template
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result

    async def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Execute the LangChain agent"""
        if not self.LangChainAvailable:
            from core.hermes.factory import RawAgent
            raw_agent = RawAgent(self.agent_id, self.config, self.llm_provider)
            return await raw_agent.execute(input_data, **kwargs)

        try:
            messages = self._build_langchain_messages(input_data)

            hermes_messages = [
                Message(role=m.type if hasattr(m, 'type') else 'user', content=m.content)
                for m in messages
            ]

            response = await self.llm_provider.generate(
                messages=hermes_messages,
                **kwargs
            )

            return {
                "success": True,
                "response": response.content,
                "token_usage": response.token_usage,
                "model_used": response.model,
                "provider_used": response.provider_used,
                "finish_reason": response.finish_reason,
                "framework": "langchain"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "framework": "langchain"
            }

    async def execute_stream(self, input_data: Dict[str, Any], **kwargs):
        """Execute the LangChain agent with streaming"""
        if not self.LangChainAvailable:
            from core.hermes.factory import RawAgent
            raw_agent = RawAgent(self.agent_id, self.config, self.llm_provider)
            async for chunk in raw_agent.execute_stream(input_data, **kwargs):
                yield chunk
            return

        try:
            messages = self._build_langchain_messages(input_data)

            hermes_messages = [
                Message(role=m.type if hasattr(m, 'type') else 'user', content=m.content)
                for m in messages
            ]

            async for chunk in self.llm_provider.generate_stream(
                messages=hermes_messages,
                **kwargs
            ):
                yield {
                    "type": "chunk",
                    "content": chunk,
                    "agent_id": self.agent_id,
                    "framework": "langchain"
                }

            yield {
                "type": "done",
                "agent_id": self.agent_id,
                "framework": "langchain"
            }

        except Exception as e:
            yield {
                "type": "error",
                "error": str(e),
                "error_type": type(e).__name__,
                "agent_id": self.agent_id,
                "framework": "langchain"
            }
