# self-evolve

Project-based self-evolution toolkit for [agent-kit](https://github.com/Mikko-ww/agent-kit).

## Overview

`self-evolve` enables project-level self-evolution by integrating as an **Agent Skill** into mainstream coding agents — Cursor, VS Code Copilot, Codex and more. It captures development experience within a project and evolves it into reusable rules that are automatically synced to a unified skill file under `.agents/skills/self-evolve/SKILL.md`, discoverable by any agent.

**Capture → Analyze → Promote → Sync**

- **Capture**: Record structured learning entries from task experience (project-scoped)
- **Analyze**: Detect patterns, link related entries, identify promotion candidates
- **Promote**: Elevate validated learnings to permanent rules
- **Sync**: Write rules to a unified skill file (`.agents/skills/self-evolve/SKILL.md`)

## Installation

```bash
agent-kit plugins install self-evolve
```

## Quick Start

### 1. Initialize project

```bash
cd your-project
agent-kit self-evolve init
```

This creates `.agents/self-evolve/` directory and generates the initial skill file at `.agents/skills/self-evolve/SKILL.md`.

### 2. Capture a learning

```bash
agent-kit self-evolve capture \
  --summary "Always validate env vars before startup" \
  --domain debugging \
  --priority high \
  --pattern-key env-var-validation \
  --task-id task-42
```

### 3. Analyze patterns

```bash
agent-kit self-evolve analyze
```

### 4. Promote to a rule

```bash
agent-kit self-evolve promote L-20260330-001 \
  --rule "Validate all required environment variables at application startup"
```

### 5. Sync rules to skill file

```bash
agent-kit self-evolve sync
```

### 6. One-step evolution

```bash
agent-kit self-evolve evolve
```

This runs the full cycle: analyze → auto-promote eligible → sync.

### 7. Check status

```bash
agent-kit self-evolve status
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize self-evolution for the current project |
| `capture` | Capture a new learning entry |
| `list` | List learning entries with filtering |
| `analyze` | Analyze patterns and detect duplicates |
| `promote` | Promote a learning to a permanent rule |
| `sync` | Sync promoted rules to the unified skill file |
| `evolve` | One-step: analyze + auto-promote + sync |
| `status` | Show evolution status overview |

## Skill Discovery

All promoted rules are output to a single unified skill file:

| Output File | Description |
|------------|-------------|
| `.agents/skills/self-evolve/SKILL.md` | Unified skill file discoverable by any agent |

Any agent that supports `.agents/skills/` skill discovery (Cursor, Copilot, Codex, etc.) can automatically find and use this skill file. No per-agent configuration is needed.

## Configuration

Config file: `<project-root>/.agents/self-evolve/config.jsonc`

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 3,
  "promotion_threshold": 3,
  "promotion_window_days": 30,
  "min_task_count": 2,
  "auto_promote": false
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `promotion_threshold` | Recurrence count needed for promotion | `3` |
| `promotion_window_days` | Time window for promotion eligibility | `30` |
| `min_task_count` | Minimum distinct tasks for promotion | `2` |
| `auto_promote` | Auto-promote eligible entries in evolve | `false` |

## Data Storage

```
<project-root>/
├── .agents/
│   ├── self-evolve/
│   │   ├── config.jsonc          # Project config
│   │   ├── learnings/            # Learning entries
│   │   │   ├── L-20260330-001.jsonc
│   │   │   └── ...
│   │   └── rules.jsonc           # Promoted rules
│   └── skills/
│       └── self-evolve/
│           └── SKILL.md          # Unified skill file (auto-generated)
```

## Language Support

Supports `en` (English) and `zh-CN` (Chinese). Language is resolved via:

1. `AGENT_KIT_LANG` environment variable
2. Global config `~/.config/agent-kit/config.jsonc`
3. System locale
4. Default: `en`
