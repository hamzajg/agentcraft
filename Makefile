# Makefile — convenience aliases for agentcraft CLI
# The canonical interface is the agentcraft command directly.
# These targets exist for muscle memory and CI pipelines.

.PHONY: help init diagnose build resume comms monitor validate hooks \
        rag-stats rag-files rag-queries rag-search rag-reindex \
        frameworks skills new-agent

CLI     = python agentcraft
MODEL  ?=
FRAMEWORK ?=
FROM   ?= 1
PHASE  ?=
PORT   ?= 7000
Q      ?=

# ── Setup ─────────────────────────────────────────────────────────────────────

## Interactive project setup
init:
	$(CLI) init

## Detect hardware and select optimal models
diagnose:
	$(CLI) diagnose

## Detect and pull Ollama models
diagnose-pull:
	$(CLI) diagnose --pull

# ── Build ─────────────────────────────────────────────────────────────────────

## Run the full agent team build
build:
	$(CLI) build $(if $(MODEL),--model $(MODEL),) $(if $(FRAMEWORK),--framework $(FRAMEWORK),)

## Resume from iteration N:  make resume FROM=5
resume:
	$(CLI) resume --from $(FROM) $(if $(MODEL),--model $(MODEL),) $(if $(FRAMEWORK),--framework $(FRAMEWORK),)

## Build with BMAD methodology
bmad:
	$(CLI) build --framework bmad-method $(if $(MODEL),--model $(MODEL),)

## Build with OpenSpec framework
openspec:
	$(CLI) build --framework openspec $(if $(MODEL),--model $(MODEL),)

## Build with RAG enabled
build-rag:
	$(CLI) build --rag $(if $(MODEL),--model $(MODEL),) $(if $(FRAMEWORK),--framework $(FRAMEWORK),)

## Preview build without running agents
dry-run:
	$(CLI) build --dry-run $(if $(MODEL),--model $(MODEL),) $(if $(FRAMEWORK),--framework $(FRAMEWORK),)

## Build phase N only:  make phase PHASE=1
phase:
	$(CLI) build --phase $(PHASE) --skip-spec $(if $(MODEL),--model $(MODEL),)

# ── Communication UI ──────────────────────────────────────────────────────────

## Start the agent comms UI
comms:
	$(CLI) comms --port $(PORT)

## Comms in dev mode (hot reload)
comms-dev:
	$(CLI) comms --port $(PORT) --dev

## Build the React frontend
comms-build:
	bash comms/build.sh

# ── Monitoring ────────────────────────────────────────────────────────────────

## Live system monitor
monitor:
	$(CLI) monitor

## Single metrics snapshot
monitor-once:
	$(CLI) monitor --once

# ── RAG ───────────────────────────────────────────────────────────────────────

## RAG index health summary
rag-stats:
	$(CLI) rag stats

## Per-file breakdown
rag-files:
	$(CLI) rag files

## Query activity log
rag-queries:
	$(CLI) rag queries

## Test semantic search:  make rag-search Q="session expiry scenario"
rag-search:
	$(CLI) rag search "$(Q)"

## Re-index docs and repo root
rag-reindex:
	$(CLI) rag reindex

# ── Validation ────────────────────────────────────────────────────────────────

## Validate ownership boundary
validate:
	$(CLI) validate

## Install git pre-commit hook
hooks:
	@echo '#!/bin/bash' > .git/hooks/pre-commit
	@echo 'python agentcraft validate --staged' >> .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed"

# ── Discovery ─────────────────────────────────────────────────────────────────

## List installed agents
agents:
	@python -c "from agents import list_agents; [print('  ' + a) for a in list_agents()]"

## List frameworks
frameworks:
	$(CLI) frameworks

## List skills
skills:
	$(CLI) skills

## Scaffold a new agent:  make new-agent NAME=security_auditor
new-agent:
	$(CLI) new-agent $(NAME)

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  AgentCraft — Autonomous AI Agent Team"
	@echo ""
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /'
	@echo ""
	@echo "  Variables: MODEL=$(MODEL)  FRAMEWORK=$(FRAMEWORK)  PORT=$(PORT)"
	@echo "  Direct CLI: python agentcraft --help"
	@echo ""
