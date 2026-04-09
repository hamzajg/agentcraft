"""
cicd.py — CI/CD agent.

Responsible for all infrastructure and pipeline files:
  - Dockerfile (multi-stage: build + runtime)
  - docker-compose.yml (full local stack)
  - .github/workflows/*.yml (CI pipeline)
  - Makefile (developer convenience targets)
  - .dockerignore

Runs as a dedicated iteration at the end of each phase.
"""

import logging
from pathlib import Path

from core.base import AiderAgent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent / "prompt.md").read_text() if (Path(__file__).parent / "prompt.md").exists() else """You are the CI/CD Agent. Set up pipelines, Docker, and deployment infrastructure."""


class CiCdAgent(AiderAgent):
    _role = "cicd"

    def __init__(
        self,
        model: str,
        workspace: Path,
        system_prompt: str = None,
        skills: list = None,
        framework_id: str = None,
        task_id: str = None,
        iteration_id: int = None,
        rag_client=None,
        llm_client=None,
    ):
        super().__init__(
            role="cicd",
            model=model,
            workspace=workspace,
            system_prompt=SYSTEM_PROMPT if system_prompt is None else system_prompt,
            skills=skills,
            framework_id=framework_id,
            max_retries=2,
            task_id=task_id,
            iteration_id=iteration_id,
            rag_client=rag_client,
            llm_client=llm_client,
        )

    def build_phase_infra(self, phase: int, docs_dir: Path) -> list[dict]:
        """
        Produce all CI/CD files for a completed phase.
        Returns list of results, one per file written.
        """
        results = []

        if phase == 1:
            results += self._makefile(docs_dir)
        elif phase == 2:
            results += self._dockerfile(docs_dir)
            results += self._docker_compose(docs_dir)
            results += self._github_actions_ci(docs_dir)
            results += self._makefile(docs_dir)
        elif phase >= 3:
            results += self._github_actions_release(docs_dir)

        return results

    # -------------------------------------------------------------------------

    def _makefile(self, docs_dir: Path) -> list[dict]:
        target = self.workspace / "Makefile"
        read_files = list(docs_dir.glob("*.md"))
        message = """
Write a Makefile for this project with the following targets:

setup:        install Python deps, pull Ollama model, install aider
ollama:       start Ollama in background
studio:       start AutoGen Studio on port 8080
gateway:      build and start Spring Boot gateway on port 8081
all:          ollama + studio + gateway in correct order
test:         run all Maven tests
test-unit:    run unit tests only (surefire, excludes *IT.java and *E2ETest.java)
test-it:      run integration tests only
test-e2e:     run E2E tests
clean:        stop all services, clean build artifacts
logs:         tail gateway log
help:         print all targets with descriptions

Use $(MAKE) for recursive calls.
Use .PHONY for all targets.
Include a MODEL variable defaulting to qwen2.5-coder:7b.
"""
        logger.info("[cicd] writing Makefile")
        r = self.run(message=message, read_files=read_files, edit_files=[target], timeout=120, log_callback=self.log_callback)
        r["file"] = "Makefile"
        return [r]

    def _dockerfile(self, docs_dir: Path) -> list[dict]:
        target = self.workspace / "api-gateway" / "Dockerfile"
        target.parent.mkdir(parents=True, exist_ok=True)
        read_files = list(docs_dir.glob("*.md"))

        pom = self.workspace / "api-gateway" / "pom.xml"
        if pom.exists():
            read_files.append(pom)

        message = """
Write a multi-stage Dockerfile for the Spring Boot API gateway.

Stage 1 (builder):
  - FROM eclipse-temurin:21-jdk-alpine AS builder
  - Copy pom.xml and src/
  - Run mvn package -DskipTests

Stage 2 (runtime):
  - FROM eclipse-temurin:21-jre-alpine
  - Copy JAR from builder
  - EXPOSE 8081
  - Non-root user
  - HEALTHCHECK using /actuator/health
  - ENTRYPOINT ["java", "-jar", "app.jar"]

Include .dockerignore as a comment at the bottom noting what to exclude.
"""
        logger.info("[cicd] writing Dockerfile")
        r = self.run(message=message, read_files=read_files, edit_files=[target], timeout=180, log_callback=self.log_callback)
        r["file"] = "api-gateway/Dockerfile"
        return [r]

    def _docker_compose(self, docs_dir: Path) -> list[dict]:
        target = self.workspace / "docker-compose.yml"
        read_files = list(docs_dir.glob("*.md"))
        message = """
Write a docker-compose.yml for the full local stack.

Services:
  ollama:
    image: ollama/ollama
    ports: 11434:11434
    volumes: ollama_data:/root/.ollama
    healthcheck: curl /api/tags

  autogenstudio:
    image: ghcr.io/microsoft/autogen/autogenstudio:latest
    ports: 8080:8080
    depends_on: ollama
    environment: OLLAMA_HOST=http://ollama:11434

  gateway:
    build: ./api-gateway
    ports: 8081:8081
    depends_on: autogenstudio
    environment:
      STUDIO_URL: http://autogenstudio:8080
      AGENT_REGISTRY_PATH: /app/registry/agents
      AGENT_TASK_REGISTRY_PATH: /app/registry/tasks
    volumes: ./agent-registry:/app/registry:ro
    healthcheck: curl /actuator/health

volumes:
  ollama_data:

Use version: "3.9".
Include restart: unless-stopped on all services.
"""
        logger.info("[cicd] writing docker-compose.yml")
        r = self.run(message=message, read_files=read_files, edit_files=[target], timeout=180, log_callback=self.log_callback)
        r["file"] = "docker-compose.yml"
        return [r]

    def _github_actions_ci(self, docs_dir: Path) -> list[dict]:
        target = self.workspace / ".github" / "workflows" / "ci.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        read_files = list(docs_dir.glob("*.md"))
        message = """
Write a GitHub Actions CI workflow: .github/workflows/ci.yml

Trigger: push and pull_request on main and develop branches.

Jobs:

test:
  runs-on: ubuntu-latest
  steps:
    - checkout
    - setup Java 21 (temurin)
    - cache Maven dependencies
    - run unit tests: mvn test -pl api-gateway
    - run integration tests: mvn verify -pl api-gateway -P integration-tests
    - upload test reports as artifact

build:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - checkout
    - setup Java 21
    - build Docker image: docker build ./api-gateway
    - tag with git SHA

lint:
  runs-on: ubuntu-latest
  steps:
    - checkout
    - validate JSON registry files with python3 -m json.tool
    - check shell scripts with shellcheck

Use concurrency to cancel in-progress runs on new push.
"""
        logger.info("[cicd] writing ci.yml")
        r = self.run(message=message, read_files=read_files, edit_files=[target], timeout=180, log_callback=self.log_callback)
        r["file"] = ".github/workflows/ci.yml"
        return [r]

    def _github_actions_release(self, docs_dir: Path) -> list[dict]:
        target = self.workspace / ".github" / "workflows" / "release.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        read_files = list(docs_dir.glob("*.md"))
        message = """
Write a GitHub Actions release workflow: .github/workflows/release.yml

Trigger: push of tags matching v*.*.* 

Jobs:
  release:
    - checkout
    - setup Java 21
    - build: mvn package -DskipTests
    - Docker build + push to ghcr.io using GITHUB_TOKEN
    - Tag image with semver tag and latest
    - Create GitHub release with changelog from git log
"""
        logger.info("[cicd] writing release.yml")
        r = self.run(message=message, read_files=read_files, edit_files=[target], timeout=180, log_callback=self.log_callback)
        r["file"] = ".github/workflows/release.yml"
        return [r]
