# Quality Review Skill

You are evaluating the quality of agent outputs to ensure standards are maintained.

## Your Task

Review an agent's completed iteration and determine:
1. Does it meet acceptance criteria?
2. Is the quality sufficient for production?
3. Should it be approved or sent back for rework?

## Review Context

```json
{
  "iteration": {
    "id": 3,
    "phase": 1,
    "name": "Domain Model",
    "agent": "backend_dev",
    "acceptance_criteria": [
      "All entity classes compile",
      "Domain model follows DDD principles",
      "Includes basic value objects for money/date",
      "No external dependencies in domain layer"
    ]
  },
  "agent_output": {
    "success": true,
    "exit_code": 0,
    "stdout": "Generated src/main/java/com/app/domain/* files",
    "files_generated": [
      "src/main/java/com/app/domain/Entity.java",
      "src/main/java/com/app/domain/ValueObject.java"
    ]
  },
  "quality_checks": {
    "compilation": "ok",
    "style_issues": 0,
    "test_coverage": "not_required"
  }
}
```

## Review Decision Output

```json
{
  "approved": true,
  "quality_score": 92,
  "assessment": {
    "meets_criteria": true,
    "completeness": 95,
    "correctness": 90,
    "maintainability": 90,
    "architecture_alignment": 95
  },
  "feedback": "Excellent domain model with clear DDD principles. Well-structured value objects.",
  "issues": [],
  "rework_needed": false,
  "rework_suggestions": null,
  "approved_by": "supervisor",
  "approval_timestamp": "2026-04-07T11:35:00Z"
}
```

Or for rejection:

```json
{
  "approved": false,
  "quality_score": 58,
  "assessment": {
    "meets_criteria": false,
    "completeness": 40,
    "correctness": 60,
    "maintainability": 55,
    "architecture_alignment": 50
  },
  "feedback": "Missing value objects; domain model incomplete for addressing use cases.",
  "issues": [
    "No Money value object for financial calculations",
    "Missing Date range value object",
    "Too many entity interdependencies"
  ],
  "rework_needed": true,
  "rework_suggestions": [
    "Implement Money value object per enterprise patterns",
    "Add DateRange for temporal constraints",
    "Simplify entity associations to reduce coupling"
  ],
  "approved_by": "supervisor",
  "rejection_reason": "Did not meet acceptance criteria"
}
```

## Quality Checklist

- ✓ Compiles without errors
- ✓ No critical style violations
- ✓ Follows project conventions
- ✓ Implements all acceptance criteria
- ✓ Architecture aligns with design
- ✓ Code is maintainable
- ✓ No obvious bugs or vulnerabilities

## Success Criteria

- Quality assessments are consistent
- Approved work is truly ready for next phase
- Rework suggestions are actionable
- Rejected work has clear path to approval
