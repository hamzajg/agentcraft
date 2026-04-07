# Aider Commands Guide

## Overview

Agents can use aider slash commands to optimize performance, manage context, and execute tasks more efficiently.

## Performance Commands

### Context Management
- **`/reset`** - Clear chat history and drop all files (automatically added)
- **`/clear`** - Clear chat history but keep files
- **`/tokens`** - Show current token usage (automatically added)

### File Management
- **`/add <file>`** - Add file to chat for editing (automatically added for edit_files)
- **`/read-only <file>`** - Add file for reference only (automatically added for read_files)
- **`/drop <file>`** - Remove file from chat to free context
- **`/ls`** - List all files and their status

### Execution Commands
- **`/run <command>`** - Execute shell command (e.g., tests, builds)
  ```
  /run pytest tests/
  /run make build
  /run python -m pytest -v
  ```

### Model Control
- **`/model <model>`** - Switch to different model
- **`/think-tokens <count>`** - Set thinking token budget (e.g., `8k`, `16k`, `0` to disable)
- **`/reasoning-effort <level>`** - Set reasoning level (low/medium/high)

## Usage Examples

### Example 1: Run tests after generating code
```python
self.run(
    message="Implement the User model with validation",
    edit_files=["src/models/user.py"],
    aider_commands=[
        "/run pytest tests/test_user.py -v",  # Run tests after implementation
    ],
)
```

### Example 2: Clear context for large files
```python
self.run(
    message="Refactor this module",
    read_files=["docs/spec.md"],
    edit_files=["src/large_module.py"],
    aider_commands=[
        "/drop ../skills/deep-research/SKILL.md",  # Drop skills to free tokens
        "/think-tokens 4k",  # Limit thinking tokens for performance
    ],
)
```

### Example 3: Check token usage
```python
self.run(
    message="Generate API documentation",
    edit_files=["docs/api.md"],
    aider_commands=[
        "/tokens",  # Check before
        # ... task executes ...
        "/tokens",  # Check after (will appear in output)
    ],
)
```

## Automatic Commands

These commands are automatically added by the framework:
1. `/reset` - Starts with clean context
2. `/read-only <file>` - For each read_files entry
3. `/add <file>` - For each edit_files entry
4. `/tokens` - Shows token usage before task

## Best Practices

1. **Drop unused files**: Use `/drop` to remove large files from context
2. **Run tests**: Use `/run` to validate generated code
3. **Monitor tokens**: Check token usage to avoid context overflow
4. **Limit thinking**: Use `/think-tokens` on low-performance hardware
5. **Clear history**: Use `/clear` between unrelated tasks

## Console Output

With aider commands enabled, you'll see:
```
[agent] [stdout] /reset
[agent] [stdout] Chat history cleared
[agent] [stdout] /read-only docs/spec.md
[agent] [stdout] Added docs/spec.md (read-only)
[agent] [stdout] /add src/user.py
[agent] [stdout] Added src/user.py
[agent] [stdout] /tokens
[agent] [stdout] Tokens: 4,200 / 8,192 (51%)
[agent] [stdout] 
[agent] [stdout] Implement the User model...
[agent] [stdout] 
[agent] [stdout] User: Implement the User model...
[agent] [stdout] Assistant: Here's the implementation...
```
