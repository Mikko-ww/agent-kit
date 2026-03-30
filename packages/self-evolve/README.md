# self-evolve

Self-evolving agent skill toolkit for [agent-kit](https://github.com/Mikko-ww/agent-kit).

## Overview

`self-evolve` lets agents continuously learn from experience through a structured evolution loop:

**Capture → Analyze → Promote → Extract**

- **Capture**: Record structured learning entries from task experience
- **Analyze**: Detect patterns, link related entries, identify promotion candidates
- **Promote**: Elevate validated learnings to permanent rules
- **Extract**: Convert learnings into reusable Agent Skills (`SKILL.md`)

## Installation

```bash
agent-kit plugins install self-evolve
```

## Quick Start

### 1. Configure

```bash
agent-kit self-evolve wizard
```

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

### 5. Extract as a skill

```bash
agent-kit self-evolve extract-skill L-20260330-001 \
  --name env-var-validator
```

### 6. Check evolution status

```bash
agent-kit self-evolve status
```

## Commands

| Command | Description |
|---------|-------------|
| `wizard` | Interactive configuration wizard |
| `capture` | Capture a new learning entry |
| `list` | List learning entries with filtering |
| `analyze` | Analyze patterns and detect duplicates |
| `promote` | Promote a learning to a permanent rule |
| `extract-skill` | Extract a learning as a reusable skill |
| `status` | Show evolution status overview |

## Configuration

Config file: `~/.config/agent-kit/plugins/self-evolve/config.jsonc`

```jsonc
{
  "plugin_id": "self-evolve",
  "config_version": 1,
  "skills_target_dir": "~/.agents/skills",
  "promotion_threshold": 3,
  "promotion_window_days": 30,
  "min_task_count": 2
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `skills_target_dir` | Directory for extracted skills | `~/.agents/skills` |
| `promotion_threshold` | Recurrence count needed for promotion | `3` |
| `promotion_window_days` | Time window for promotion eligibility | `30` |
| `min_task_count` | Minimum distinct tasks for promotion | `2` |

## Data Storage

```
~/.local/share/agent-kit/plugins/self-evolve/
├── learnings/
│   ├── L-20260330-001.jsonc
│   ├── L-20260330-002.jsonc
│   └── ...
└── rules.jsonc
```

## Language Support

Supports `en` (English) and `zh-CN` (Chinese). Language is resolved via:

1. `AGENT_KIT_LANG` environment variable
2. Global config `~/.config/agent-kit/config.jsonc`
3. System locale
4. Default: `en`
