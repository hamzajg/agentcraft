# agent-capability-manifest — specifications by example
# Scenario tags @w<N> map items to delivery waves (see WAVES.md / BACKLOG.md).

Feature: agent-capability-manifest
  The capability surface (agents, frameworks, skills) is exposed as a single
  deterministic, machine-readable manifest plus a human-readable summary.

  # ── Wave 1 — manifest core ────────────────────────────────────────────────

  @w1 @happy-path
  Scenario: manifest lists every installed agent with its class
    Given the AgentCraft repo with its agents/ folder
    When build_manifest is called for the repo root
    Then every installed agent folder appears once in the agents section
    And each entry exposes the agent id and its agent class name

  @w1
  Scenario: manifest is deterministic and carries a schema version
    Given the same repository state
    When build_manifest is called twice
    Then the two manifests are equal
    And the manifest declares an integer schema_version

  @w1
  Scenario: each agent reports its active framework and persona
    Given a manifest built with framework "openspec"
    When the architect agent entry is inspected
    Then its framework is "openspec"
    And its persona is the framework persona configured for that agent

  # ── Wave 2 — skill resolution & frameworks ────────────────────────────────

  @w2
  Scenario: resolved skill records its source and framework shadows global
    Given a skill name that exists both globally and in the active framework
    When the manifest resolves that agent's skills
    Then the resolved entry's source is "framework"

  @w2
  Scenario: a missing skill is reported rather than dropped
    Given an agent config that names a skill resolvable nowhere
    When the manifest resolves that agent's skills
    Then the entry is present with source "missing" and exists false

  @w2
  Scenario: manifest lists frameworks with their global skills
    Given the AgentCraft repo with its frameworks/ folder
    When build_manifest is called for the repo root
    Then the frameworks section lists each framework id and label
    And each framework lists its global skills

  # ── Wave 3 — CLI surface ──────────────────────────────────────────────────

  @w3
  Scenario: summary format renders a human-readable inventory
    Given the manifest command is run with --format summary
    When it completes successfully
    Then it prints the agent count and the agent ids in a readable layout

  @w3
  Scenario: manifest command emits valid JSON to stdout
    Given the manifest command is run with --format json
    When its stdout is parsed as JSON
    Then it contains the keys schema_version and agents
