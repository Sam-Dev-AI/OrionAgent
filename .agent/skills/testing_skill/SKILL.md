---
name: testing_skill
description: Guidelines and standards for hard-level testing in OrionAgent
---

# OrionAgent Testing Skill

This skill defines the methodology for "Hard-Level Testing" to ensure the framework is production-ready.

## Core Principles

1. **Reality Over Mocks**: Use real models (e.g., Gemini Flash) for orchestration tests to verify "intelligent" behaviors like planning and self-learning.
2. **Strategy Stress**: Every test should combine at least two strategies or use complex lists like `["planning", "self_learn"]`.
3. **Parameter Inheritance**: Always verify that `verbose`, `debug`, `model`, and `memory` correctly propagate from `Manager` to child `Agent`s.
4. **Diverse Parameters**: Test multiple memory types (`session`, `persistent`, `chroma`), varying `temperature` (0.0 to 1.0), and different `priority` levels (`high`, `normal`, `low`) across test scripts.
5. **Telemetry Audit**: Use `tracer.history` at the end of every test to verify that every internal step was recorded.
6. **Efficiency Check**: Repetitive tasks in `self_learn` mode MUST show zero extra LLM evaluation calls after the initial learning.

## Real-World Test Examples

### 1. Lead Generation Pipeline
- **Agents**: `Finder`, `Scraper`, `DataWriter`.
- **Flow**: Search for "Wedding Venues in CA", fetch their homepages, extract contact info, and save to a CSV file using `file_manager`.
- **Requirement**: Use `PlanningStrategy` and `persistent` memory.

### 2. Latest News Analyst
- **Agents**: `NewsSource`, `Summarizer`.
- **Flow**: Search for latest AI news, fetch top 3 links, and provides a structured summary.
- **Requirement**: Use `DirectStrategy` and `high` priority.

### 3. Personal Assistant
- **Agents**: `Clock`, `RemindAgent`.
- **Flow**: Get current time, set a reminder for a task after a small delay.
- **Requirement**: Use `system_tools` and `session` memory.

## Bug Prevention Checklist
- [ ] No `TypeError` on optional parameters.
- [ ] Async mode works without blocking the main event loop.
- [ ] Token counts are accurate across multiple generations.
- [ ] Persistent storage (SQLite) actually saves between script runs.
- [ ] Session priority is correctly updated and respected in memory.
