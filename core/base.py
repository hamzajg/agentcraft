"""
base.py — AiderAgent base class.

Prompt composition per task:
  Layer 1: base system prompt   (prompts/<role>.md)
  Layer 2: active persona       (frameworks/<fw>/personas/<n>.md)
  Layer 3: declared skills      (skills/**/*.md)
  Layer 4: RAG context          (top-k retrieved chunks — automatic)
  Layer 5: task message         (--message)

Layers 1+2 → --system-prompt
Layers 3+4  → --read files
Layer 5     → --message

Additional capabilities every agent inherits:
  self.retrieve(query)    — semantic search via RAG
  self.ingest(path)       — index a file after writing it
  self.ask(question)      — block until human replies via comms UI
  self.ask_local(prompt)  — reason with local Ollama LLM directly
  self.report_status()    — update comms UI sidebar dot
"""

import subprocess
import json
import re
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Optional integrations (graceful degradation) ──────────────────────────────

_COMMS_AVAILABLE = False
_COMMS_AVAILABLE = False
try:
    from comms.clarification_client import ClarificationClient
    _COMMS_AVAILABLE = True
except ImportError:
    pass

from core.skill_runner import SkillRunner

class AiderAgent:

    _role: str = "agent"   # subclasses set this

    def __init__(
        self,
        role: str = None,
        model: str = "qwen2.5-coder:7b",
        workspace: Path = None,
        system_prompt: str = None,
        skills: list = None,
        framework_id: str = None,
        max_retries: int = 2,
        task_id: str = None,
        iteration_id: int = None,
        rag_client=None,           # RagClient | None
        llm_client=None,           # OllamaClient | None
    ):
        self.role          = role or self.__class__._role
        self.model         = model
        self.workspace     = workspace or Path(".")
        self.system_prompt = system_prompt or f"# {self.role}\nYou are a helpful AI agent."
        self.skills        = skills or []
        self.framework_id  = framework_id
        self.max_retries   = max_retries
        self.task_id       = task_id or "unknown"
        self.iteration_id  = iteration_id
        self._rag          = rag_client
        self._llm          = llm_client
        self.log_callback  = None  # set by orchestrator

        self._skill_runner = SkillRunner(framework_id=framework_id)

        self._clarifier: Optional["ClarificationClient"] = None
        if _COMMS_AVAILABLE:
            self._clarifier = ClarificationClient(
                agent_id=self.role,
                task_id=self.task_id,
                iteration_id=iteration_id,
            )

        # ── AgentBus registration ──────────────────────────────────────────────
        try:
            from core.bus import AgentBus
            bus = AgentBus.instance()
            bus.register_agent(self.role, self)
            # Auto-register handle_query if subclass overrides it
            if (hasattr(self.__class__, "handle_query")
                    and "handle_query" in self.__class__.__dict__):
                logger.info("[bus] auto-registering handler for '%s'", self.role)
                bus.register_handler(self.role, self.handle_query)
            else:
                logger.info("[bus] no handle_query override in '%s' (hasattr=%s, in_dict=%s)", 
                           self.role, 
                           hasattr(self.__class__, "handle_query"),
                           "handle_query" in self.__class__.__dict__)
        except Exception as e:
            logger.warning("[bus] failed to register agent '%s': %s", self.role, e)

    # ── Query handler (override in subclasses) ────────────────────────────────

    def handle_query(self, question: str, context: dict) -> str:
        """Override to handle queries from other agents via ask_agent()."""
        if self._llm:
            prompt = (
                f"You are the {self.role} agent. Another agent asks:\n\n"
                f"{question}\n\n"
                + (f"Context: {context}\n\n" if context else "")
                + "Give a concise, expert answer."
            )
            return self._llm.chat(prompt) or ""
        return ""

    # ── RAG ───────────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        collection: str = None,
        language: str = None,
    ) -> list[Path]:
        """
        Semantic search. Returns paths to temp files with retrieved chunks.
        Pass as --read to Aider for context injection.
        Returns [] if RAG is not configured.
        """
        if self._rag is None or not self._rag.enabled:
            return []
        return self._rag.retrieve(query, top_k=top_k,
                                   collection=collection, language=language)

    def ingest(self, path: Path, collection: str = "codebase"):
        """Index a file into RAG immediately after writing it."""
        if self._rag and self._rag.enabled:
            self._rag.ingest_file(path, collection)

    # ── Local LLM ─────────────────────────────────────────────────────────────

    def ask_local(
        self,
        prompt: str,
        system: str = None,
        as_json: bool = False,
    ) -> str | dict | None:
        """
        Reason with local Ollama LLM directly (not via Aider).
        Use for planning decisions, JSON extraction, or short reasoning tasks.
        Returns str normally; returns dict if as_json=True.
        Returns "" / None if LLM is not configured.
        """
        if self._llm is None:
            logger.warning("[%s] LLM client not configured for ask_local", self.role)
            return {} if as_json else ""
        if as_json:
            return self._llm.extract_json(prompt, system=system)
        return self._llm.generate(prompt, system=system)

    # ── Human communication ───────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        file: str = None,
        partial_output: str = None,
        suggestions: list = None,
        timeout: int = 3600,
    ) -> str:
        """Block until human replies via comms UI. Gracefully degrades."""
        if self._clarifier is None:
            logger.warning("[%s] comms unavailable — fallback: %s", self.role, question[:60])
            return (suggestions or [""])[0]
        return self._clarifier.ask(
            question=question, file=file,
            partial_output=partial_output,
            suggestions=suggestions or [],
            timeout=timeout,
        )

    def report_status(self, status: str, file: str = None):
        if self._clarifier:
            self._clarifier.report_status(status, file)

    # ── Agent ↔ Agent communication ───────────────────────────────────────────

    def ask_agent(
        self,
        target_role: str,
        question:    str,
        context:     dict = None,
        timeout:     float = 30.0,
    ) -> str:
        """
        Ask another agent a question and get a reply.

        The target agent's registered handler is called synchronously.
        Falls back to local LLM if the target has no handler registered.
        Falls back to empty string if neither is available.

        Example:
            answer = self.ask_agent(
                "reviewer",
                "Is it correct to use a sealed interface here?",
                context={"file": "AgentMessage.java", "code_snippet": "..."},
            )
        """
        from core.bus import AgentBus
        return AgentBus.instance().ask(
            from_role=self.role,
            to_role=target_role,
            question=question,
            context=context or {},
            task_id=self.task_id,
            iter_id=self.iteration_id,
            timeout=timeout,
            fallback_llm=self._llm,
        )

    def share_context(self, key: str, value) -> None:
        """
        Publish a value to the shared context store.
        Any other agent can read it with read_context(key).

        Key convention: "<role>.<topic>"  (role prefix added automatically)
        Example:
            self.share_context("domain_model", {"entities": ["Agent", "Task"]})
            # stored as "spec.domain_model"

            self.share_context("architect.iteration_plan", iterations)
            # stored as-is (already namespaced)
        """
        from core.bus import AgentBus
        AgentBus.instance().publish(
            from_role=self.role,
            key=key,
            value=value,
            task_id=self.task_id,
            iter_id=self.iteration_id,
        )

    def read_context(self, key: str):
        """
        Read a value from the shared context store.
        Returns None if the key does not exist yet.

        Example:
            plan = self.read_context("architect.iteration_plan")
            domain = self.read_context("spec.domain_model")
        """
        from core.bus import AgentBus
        return AgentBus.instance().read(key, requester=self.role)

    def delegate(
        self,
        target_role: str,
        task:        dict,
        docs_dir:    "Path" = None,
    ) -> dict:
        """
        Ask another agent to execute a full task and return the result.
        Blocks until the delegated agent finishes.

        The orchestrator does not see delegated tasks — they are
        a private coordination between agents.

        Example:
            result = self.delegate(
                "test_dev",
                {"id": "subtask-1", "file": "SessionTest.java",
                 "description": "Write test for session expiry scenario"},
            )
        """
        from core.bus import AgentBus
        return AgentBus.instance().delegate(
            from_role=self.role,
            to_role=target_role,
            task=task,
            docs_dir=docs_dir or self.workspace,
            task_id=self.task_id,
            iter_id=self.iteration_id,
        )

    def broadcast(self, event: str, data: dict = None) -> None:
        """
        Announce a state change to all agents on the bus.
        Example:
            self.broadcast("iteration_complete", {"iteration": 2, "files": [...]})
        """
        from core.bus import AgentBus
        AgentBus.instance().broadcast(
            from_role=self.role,
            event=event,
            data=data or {},
            task_id=self.task_id,
            iter_id=self.iteration_id,
        )

    def register_query_handler(self, fn) -> None:
        """
        Register a function that handles queries from other agents.
        Called automatically by __init__ if the subclass defines handle_query().

        fn signature: (question: str, context: dict) -> str
        """
        from core.bus import AgentBus
        AgentBus.instance().register_handler(self.role, fn)

    # ── Aider execution ───────────────────────────────────────────────────────

    def _build_aider_commands(self, message: str, read_files: list, edit_files: list, custom_commands: list = None) -> str:
        """
        Build message for aider. We rely on --read and --file CLI flags instead of slash commands.
        
        Returns the message to send to aider.
        """
        # Just return the message - file handling is done via CLI flags
        if self.system_prompt:
            return f"{self.system_prompt}\n\n{message}"
        return message

    def run(
        self,
        message: str,
        read_files: list = None,
        edit_files: list = None,
        timeout: int = None,  # Will be set based on model
        rag_query: str = None,      # if set, retrieve context before running
        log_callback: callable = None,  # callback(agent_id: str, message: str)
        aider_commands: list = None,  # Custom aider slash commands to prepend
    ) -> dict:
        read_files = list(read_files or [])
        edit_files = list(edit_files or [])

        # Set timeout based on model size (7B models need more time on low-perf hardware)
        if timeout is None:
            if "7b" in self.model.lower():
                timeout = 300  # 5 minutes for 7B models
            elif "13b" in self.model.lower():
                timeout = 480  # 8 minutes for 13B models
            else:
                timeout = 180  # 3 minutes default

        # Layer 3: declared skills
        skill_files = self._skill_runner.resolve(self.skills)

        # Layer 4: RAG context (injected as --read before task context)
        rag_files: list[Path] = []
        if rag_query or message:
            rag_files = self.retrieve(rag_query or message[:200])
            if rag_files:
                logger.debug("[%s] RAG: injecting %d context files", self.role, len(rag_files))

        # Order: skills → RAG → explicit read_files
        all_reads = skill_files + rag_files + read_files

        # Build message with aider commands for better context management
        full_message = self._build_aider_commands(message, all_reads, edit_files, aider_commands)

        cmd = [
            "aider",
            "--model", f"ollama/{self.model}",
            "--no-git", "--yes",
            "--verbose",  # Enable verbose output to see LLM chat
            "--stream",   # Force streaming mode
            "--message", full_message,
        ]
        for f in all_reads:
            cmd += ["--read", str(f)]
        # Always add --file for edit_files (aider needs this to know what to create/edit)
        for f in edit_files:
            cmd += ["--file", str(f)]

        self.report_status("running")
        logger.info("[%s] run (skills=%s, rag=%d, timeout=%ds): %s",
                    self.role, self.skills, len(rag_files), timeout, message[:80])

        for attempt in range(1, self.max_retries + 1):
            try:
                proc = subprocess.Popen(
                    cmd, cwd=str(self.workspace),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                stdout_lines = []
                stderr_lines = []

                def read_stream(stream, lines, name):
                    for line in iter(stream.readline, ''):
                        lines.append(line)
                        if log_callback:
                            try:
                                log_callback(self.role, f"[{name}] {line.rstrip()}")
                            except Exception as e:
                                logger.debug("[%s] log callback error: %s", self.role, e)
                    stream.close()

                stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines, 'stdout'))
                stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines, 'stderr'))
                stdout_thread.daemon = True  # Don't block on exit
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                logger.info("[%s] aider process started, waiting for completion...", self.role)

                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raise

                stdout_thread.join()
                stderr_thread.join()

                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)

                out = {
                    "success":   proc.returncode == 0,
                    "stdout":    stdout,
                    "stderr":    stderr,
                    "exit_code": proc.returncode,
                    "parsed":    self._try_parse_json(stdout),
                }
                if out["success"]:
                    self.report_status("idle")
                    # Auto-ingest any files we edited
                    for ef in edit_files:
                        self.ingest(Path(ef))
                    return out
                logger.warning("[%s] attempt %d failed (exit %d)",
                               self.role, attempt, proc.returncode)
            except subprocess.TimeoutExpired:
                logger.error("[%s] timeout %ds (attempt %d)", self.role, timeout, attempt)

        self.report_status("idle")
        return {"success": False, "stdout": "", "stderr": "all attempts failed",
                "exit_code": -1, "parsed": None}

    def run_readonly(
        self,
        message: str,
        read_files: list = None,
        timeout: int = 120,
        rag_query: str = None,
    ) -> str:
        read_files  = list(read_files or [])
        skill_files = self._skill_runner.resolve(self.skills)
        rag_files   = self.retrieve(rag_query or message[:200]) if (rag_query or message) else []
        all_reads   = skill_files + rag_files + read_files

        full_message = f"{self.system_prompt}\n\n{message}" if self.system_prompt else message

        cmd = [
            "aider", "--model", f"ollama/{self.model}",
            "--no-git", "--yes",
            "--message", full_message,
        ]
        for f in all_reads:
            cmd += ["--read", str(f)]

        try:
            result = subprocess.run(
                cmd, cwd=str(self.workspace),
                capture_output=True, text=True, timeout=timeout,
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("[%s] readonly timeout", self.role)
            return ""

    @staticmethod
    def read_json(self, path, default=None):
        """Read JSON from a file Aider wrote. Strips markdown fences."""
        try:
            raw = path.read_text().strip()
            raw = re.sub(r"```(?:json)?\n?", "", raw).strip()
            for sc, ec in [("[", "]"), ("{", "}")]:
                s = raw.find(sc)
                if s == -1: continue
                depth = 0
                for i, ch in enumerate(raw[s:], s):
                    if ch == sc:   depth += 1
                    elif ch == ec: depth -= 1
                    if depth == 0:
                        import json as _j; return _j.loads(raw[s:i+1])
        except Exception as e:
            logger.debug("[%s] read_json %s: %s", self.role, path, e)
        return default

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict]:
        text = re.sub(r"```(?:json)?\n?", "", text).strip()
        for sc, ec in [('{', '}'), ('[', ']')]:
            s = text.find(sc)
            if s == -1: continue
            depth = 0
            for i, ch in enumerate(text[s:], s):
                if ch == sc:   depth += 1
                elif ch == ec: depth -= 1
                if depth == 0:
                    try:    return json.loads(text[s:i+1])
                    except: break
        return None
