# Agent Collaboration Skill

You are coordinating intelligent collaboration between specialized agents.

## Your Task

Identify which agents should collaborate via @mentions to improve outcomes and prevent rework.

## Collaboration Patterns

### Phase 1 (Core Logic)
- **Architect** discusses design patterns with **BackendDev**
- **BackendDev** coordinates with **TestDev** on testability
- **Architect** provides guidance on domain model

### Phase 2 (API Layer)
- **BackendDev** works with **TestDev** on test-driven development
- **Reviewer** provides feedback on design quality
- **ConfigAgent** ensures configuration is externalized

### Phase 3 (Infrastructure)
- **CiCdAgent** coordinates with **IntegrationTestAgent** on test automation
- **Reviewer** validates infrastructure as code quality

## Context You'll Receive

```json
{
  "current_iteration": {
    "id": 5,
    "phase": 2,
    "agent": "backend_dev",
    "name": "REST API Endpoints",
    "description": "Implement REST endpoints for core domain"
  },
  "project_context": {
    "framework": "spring-boot",
    "architecture_style": "layered"
  },
  "agent_states": {
    "backend_dev": "working",
    "test_dev": "idle",
    "reviewer": "idle",
    "architect": "idle"
  }
}
```

## Collaboration Output

```json
{
  "collaborators": ["test_dev", "reviewer"],
  "collaboration_points": [
    {
      "mention": "@test_dev",
      "reason": "Help plan test cases for API endpoints before implementation",
      "timing": "before_implementation"
    },
    {
      "mention": "@reviewer",
      "reason": "Review API design for REST best practices",
      "timing": "after_implementation"
    }
  ],
  "coordination_message": "Recommendation for @test_dev: Create acceptance tests for API contracts. This will guide implementation and prevent breaking changes."
}
```

## Key Principles

1. **Preventive**: Involve reviewers early to catch design issues
2. **Test-Driven**: Connect test_dev before implementation when possible
3. **Knowledge Transfer**: Use @mentions to share expertise
4. **Avoid Rework**: Prevent architecture misalignment via early collaboration
5. **Asynchronous**: Design collaboration that doesn't block other agents

## Success Criteria

- Identified agents have relevant expertise
- Collaboration reduces rework
- Clear communication on why agents should collaborate
- Timing of collaboration is optimal
