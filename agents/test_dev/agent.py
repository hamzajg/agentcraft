"""
test_dev.py — Test developer agent (TDD).

Writes a failing unit or acceptance test BEFORE the implementation exists.
This is always the first task for any Java class.

For use case acceptance tests, reads use_cases.md.
For unit tests, derives the test contract from the task spec alone.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text()


class TestDevAgent(AiderAgent):
    _role = "test_dev"

    def __init__(self, model: str, workspace: Path, system_prompt: str = None, skills: list = None, framework_id: str = None, task_id: str = None, iteration_id: int = None):
        super().__init__(
            role="test_dev",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT,
            max_retries=3,
        )

    def write_unit_test(self, task: dict, docs_dir: Path) -> dict:
        """
        Write a unit test for a Java class that does not yet exist.

        The test file path is derived from the impl file:
          src/main/java/.../Foo.java → src/test/java/.../FooTest.java
        """
        impl_file = task["file"]
        test_file = _impl_to_test_path(impl_file)
        target    = self.workspace / test_file
        target.parent.mkdir(parents=True, exist_ok=True)

        ai_dir    = self.workspace / ".ai"
        use_cases = ai_dir / "use_cases.md"
        spec_file = ai_dir / "spec.md"

        read_files = list(docs_dir.glob("*.md"))
        for f in [use_cases, spec_file]:
            if f.exists():
                read_files.append(f)

        context_files = [
            self.workspace / f
            for f in task.get("context_files", [])
            if (self.workspace / f).exists()
        ]
        read_files += context_files

        criteria = "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
        message = (
            f"Write test file: {task['file']}\n\n"
            f"Test this: {task['description']}\n\n"
            + (f"Must cover:\n{criteria}\n\n" if criteria else "")
            + "The class under test may not exist yet — that is fine.\n"
            + "Output the complete test file only. No explanation."
        )
        logger.info("[test_dev] writing unit test: %s", test_file)
        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[target],
            timeout=120,
            log_callback=self.log_callback,
        )
        result["test_file"] = test_file
        return result

    def write_acceptance_test(self, use_case_id: str, docs_dir: Path, spec_files: list[Path]) -> dict:
        """
        Write an acceptance test for a specific use case from use_cases.md.
        Placed in src/test/java/.../acceptance/UC_N_Test.java
        """
        test_file = f"api-gateway/src/test/java/com/localai/gateway/acceptance/{use_case_id.replace('-','_')}_Test.java"
        target    = self.workspace / test_file
        target.parent.mkdir(parents=True, exist_ok=True)

        read_files = list(docs_dir.glob("*.md")) + spec_files

        message = (
            f"Write acceptance test for use case {use_case_id}.\n\n"
            f"File: {test_file}\n\n"
            "Use @SpringBootTest(webEnvironment=RANDOM_PORT).\n"
            "Use WebTestClient or TestRestTemplate.\n"
            "Mock external services with @MockBean.\n"
            "Output the complete test file only."
        )
        logger.info("[test_dev] writing acceptance test: %s", test_file)
        result = self.run(
            message=message,
            read_files=read_files,
            edit_files=[target],
            timeout=120,
            log_callback=self.log_callback,
        )
        result["test_file"] = test_file
        return result


# ---- helpers ----

def _impl_to_test_path(impl_file: str) -> str:
    """Convert src/main/java/.../Foo.java → src/test/java/.../FooTest.java"""
    return impl_file.replace("src/main/java", "src/test/java").replace(".java", "Test.java")


def _test_class_name(impl_file: str) -> str:
    """AgentMessage.java → AgentMessageTest"""
    return Path(impl_file).stem + "Test"


def _test_package(impl_file: str) -> str:
    """src/main/java/com/localai/gateway/model/Foo.java → com.localai.gateway.model"""
    parts = Path(impl_file).parts
    try:
        java_idx = list(parts).index("java")
        pkg_parts = parts[java_idx + 1:-1]
        return ".".join(pkg_parts)
    except ValueError:
        return "com.localai.gateway"
