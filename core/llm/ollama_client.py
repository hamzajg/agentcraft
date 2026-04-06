"""
ollama_client.py — unified local LLM interface via Ollama.

Replaces any cloud LLM calls in:
  - comms server smart reply suggestions
  - TaskPlannerService LLM fallback (planning prompt → JSON plan)
  - Any ad-hoc reasoning calls agents need beyond Aider

Uses Ollama /api/chat for multi-turn and /api/generate for single-shot.
Streaming supported via server-sent events.

All models are local. No API keys. No cloud.
"""

import json
import logging
from typing import Iterator, Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE    = "http://localhost:11434"
DEFAULT_MODEL  = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT = 120


class OllamaClient:
    """
    Synchronous Ollama client.

    Usage:
        llm = OllamaClient(model="qwen2.5-coder:7b")
        response = llm.chat("Explain what this Java class does")
        plan_json = llm.chat(planning_prompt, temperature=0.2)
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        timeout: int = DEFAULT_TIMEOUT,
        system_prompt: Optional[str] = None,
    ):
        self.model         = model
        self.temperature   = temperature
        self.timeout       = timeout
        self.system_prompt = system_prompt
        self._history:     list[dict] = []

    def chat(
        self,
        user_message: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        reset_history: bool = False,
    ) -> str:
        """
        Send a message and get a response. Maintains conversation history
        unless reset_history=True.
        """
        if reset_history:
            self._history.clear()

        messages = []
        sys = system or self.system_prompt
        if sys:
            messages.append({"role": "system", "content": sys})
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_message})

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{OLLAMA_BASE}/api/chat",
                    json={
                        "model":    self.model,
                        "messages": messages,
                        "stream":   False,
                        "options":  {
                            "temperature": temperature or self.temperature,
                        },
                    },
                )
                resp.raise_for_status()
                content = resp.json()["message"]["content"]

                # Append to history for multi-turn
                self._history.append({"role": "user",      "content": user_message})
                self._history.append({"role": "assistant", "content": content})

                return content

        except Exception as e:
            logger.error("[ollama] chat failed (model=%s): %s", self.model, e)
            return ""

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Single-shot generation — no history, just prompt → response."""
        try:
            payload: dict = {
                "model":  self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature or self.temperature},
            }
            if system or self.system_prompt:
                payload["system"] = system or self.system_prompt

            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json()["response"]

        except Exception as e:
            logger.error("[ollama] generate failed: %s", e)
            return ""

    def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> Iterator[str]:
        """Stream tokens from Ollama. Yields token strings."""
        try:
            payload: dict = {
                "model":  self.model,
                "prompt": prompt,
                "stream": True,
            }
            if system or self.system_prompt:
                payload["system"] = system or self.system_prompt

            with httpx.Client(timeout=self.timeout) as client:
                with client.stream("POST", f"{OLLAMA_BASE}/api/generate", json=payload) as resp:
                    for line in resp.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            if token := chunk.get("response"):
                                yield token
                            if chunk.get("done"):
                                break
        except Exception as e:
            logger.error("[ollama] stream failed: %s", e)

    def extract_json(self, prompt: str, system: Optional[str] = None) -> Optional[dict]:
        """
        Generate a response and parse it as JSON.
        Strips markdown fences before parsing.
        Useful for planning calls that must return structured output.
        """
        raw = self.generate(prompt, system=system, temperature=0.1)
        if not raw:
            return None

        # Strip ```json fences
        import re
        clean = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`").strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to find the first JSON object or array
            for start, end in [('{', '}'), ('[', ']')]:
                s = clean.find(start)
                if s >= 0:
                    depth = 0
                    for i, ch in enumerate(clean[s:], s):
                        if ch == start:   depth += 1
                        elif ch == end:   depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(clean[s:i+1])
                            except Exception:
                                break
            logger.warning("[ollama] JSON parse failed for extract_json response")
            return None

    def reset(self):
        """Clear conversation history."""
        self._history.clear()

    def is_available(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(f"{OLLAMA_BASE}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                base   = self.model.split(":")[0]
                return any(m.startswith(base) for m in models)
        except Exception:
            return False
