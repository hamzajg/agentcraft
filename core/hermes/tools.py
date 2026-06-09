"""
Hermes Tool Layer — Shell, Git, Filesystem, Browser, Image Generation.
"""

import os
import asyncio
import subprocess
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def to_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ShellTool(BaseTool):
    """Execute shell commands."""

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
            },
            "required": ["command"],
        }

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        command = args.get("command", "")
        cwd = args.get("cwd", os.getcwd())
        timeout = args.get("timeout", 60)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GitTool(BaseTool):
    """Git operations."""

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return "Execute git operations: status, diff, commit, branch, push, pull, log"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["status", "diff", "commit", "branch", "checkout", "push", "pull", "log", "add", "create_branch"],
                    "description": "Git operation to perform",
                },
                "args": {"type": "string", "description": "Additional arguments"},
                "message": {"type": "string", "description": "Commit message (for commit)"},
                "branch": {"type": "string", "description": "Branch name"},
                "cwd": {"type": "string", "description": "Repository path"},
            },
            "required": ["operation"],
        }

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        operation = args.get("operation", "")
        extra_args = args.get("args", "")
        message = args.get("message", "")
        branch = args.get("branch", "")
        cwd = args.get("cwd", os.getcwd())

        cmd_map = {
            "status": "git status",
            "diff": "git diff",
            "log": "git log --oneline -20",
            "add": f"git add {extra_args or '.'}",
            "commit": f'git commit -m "{message}"' if message else "git commit",
            "branch": "git branch",
            "create_branch": f"git checkout -b {branch}" if branch else None,
            "checkout": f"git checkout {branch or extra_args}",
            "push": f"git push {extra_args}",
            "pull": "git pull",
        }

        command = cmd_map.get(operation)
        if not command:
            return {"success": False, "error": f"Unknown operation: {operation}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode(errors="replace"),
                "stderr": stderr.decode(errors="replace"),
                "exit_code": proc.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class FileSystemTool(BaseTool):
    """Read, write, and list files."""

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Read, write, list, and manage files on the filesystem"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "exists", "mkdir", "delete", "copy", "move"],
                    "description": "File operation",
                },
                "path": {"type": "string", "description": "File or directory path"},
                "content": {"type": "string", "description": "Content to write"},
                "destination": {"type": "string", "description": "Destination path for copy/move"},
            },
            "required": ["operation", "path"],
        }

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        operation = args.get("operation", "")
        path = Path(args.get("path", ""))
        content = args.get("content", "")
        destination = args.get("destination", "")

        try:
            if operation == "read":
                if not path.exists():
                    return {"success": False, "error": f"File not found: {path}"}
                text = path.read_text(errors="replace")
                return {"success": True, "content": text, "size": len(text)}

            elif operation == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                return {"success": True, "path": str(path), "size": len(content)}

            elif operation == "list":
                if not path.exists():
                    return {"success": False, "error": f"Directory not found: {path}"}
                items = []
                for item in sorted(path.iterdir()):
                    items.append({
                        "name": item.name,
                        "path": str(item.relative_to(path)),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
                return {"success": True, "items": items}

            elif operation == "exists":
                return {"success": True, "exists": path.exists()}

            elif operation == "mkdir":
                path.mkdir(parents=True, exist_ok=True)
                return {"success": True, "path": str(path)}

            elif operation == "delete":
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                return {"success": True, "path": str(path)}

            elif operation == "copy":
                import shutil
                shutil.copy2(path, destination)
                return {"success": True, "source": str(path), "destination": destination}

            elif operation == "move":
                import shutil
                shutil.move(str(path), destination)
                return {"success": True, "source": str(path), "destination": destination}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


class BrowserTool(BaseTool):
    """Web browsing and scraping."""

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Navigate URLs, fetch page content, and perform web searches"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["fetch", "search"],
                    "description": "Browser operation",
                },
                "url": {"type": "string", "description": "URL to fetch"},
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["operation"],
        }

    async def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import httpx

        operation = args.get("operation", "")

        try:
            if operation == "fetch":
                url = args.get("url", "")
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, follow_redirects=True)
                    return {
                        "success": resp.status_code == 200,
                        "status_code": resp.status_code,
                        "content": resp.text[:50000],
                        "headers": dict(resp.headers),
                    }

            elif operation == "search":
                query = args.get("query", "")
                # Use DuckDuckGo instant answer API
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://api.duckduckgo.com/",
                        params={"q": query, "format": "json"},
                    )
                    data = resp.json()
                    results = []
                    if data.get("AbstractText"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "snippet": data.get("AbstractText", ""),
                            "url": data.get("AbstractURL", ""),
                        })
                    for topic in data.get("RelatedTopics", [])[:5]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "snippet": topic.get("Text", ""),
                                "url": topic.get("FirstURL", ""),
                            })
                    return {"success": True, "results": results}

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

        except Exception as e:
            return {"success": False, "error": str(e)}


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"[tools] Registered: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    def list_names(self) -> List[str]:
        return list(self._tools.keys())

    async def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.get(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}

        start = datetime.utcnow()
        try:
            result = await tool.execute(args)
            duration = int((datetime.utcnow() - start).total_seconds() * 1000)
            result["duration_ms"] = duration
            result["tool"] = name
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "tool": name}


# Global tool registry
tool_registry = ToolRegistry()

# Register built-in tools
tool_registry.register(ShellTool())
tool_registry.register(GitTool())
tool_registry.register(FileSystemTool())
tool_registry.register(BrowserTool())
