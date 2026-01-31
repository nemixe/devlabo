# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevLabo is an AI-powered app builder using a **Brain-Body-Storage** architecture:

- **Brain**: Centralized AI Agent (LangGraph/DeepAgents) that orchestrates code generation
- **Body**: Per-project Modal containers running 4 simultaneous dev servers
- **Storage**: Cloudflare R2 for persistent, ephemeral-resistant data

The AI agent reads from `./prototype` (source of truth) and generates code into `./frontend`, `./dbml`, and `./test-case`.

## Architecture

### Workspace Structure (Inside Sandbox Container)
```
/root/workspace/
├── /prototype    [Port 3001] - Raw HTML/React-Lite (source of truth)
├── /frontend     [Port 3002] - Production code (Next.js/Vite)
├── /dbml         [Port 3003] - Database schema visualization
└── /test-case    [Port 3004] - Test runner & reports
```

### Planned Code Structure
```
project-root/
├── sandbox/           - Modal container definition & ProcessManager
├── gateway/           - HTTP routing layer (Modal endpoint)
├── agent/             - AI orchestration (DeepAgents/LangGraph)
│   ├── tools.py       - read_prototype(), write_frontend(), generate_dbml()
│   ├── service.py     - Central Modal service
│   └── prompts/       - System prompts for transformations
├── common/
│   └── r2_sync.py     - R2 pull/push logic
└── security/
    └── utils.py       - Path traversal validation
```

### Gateway Routing
```
/connect/{user}/{project}/prototype/* → Port 3001
/connect/{user}/{project}/frontend/*  → Port 3002
/connect/{user}/{project}/dbml/*      → Port 3003
/connect/{user}/{project}/tests/*     → Port 3004
```

## Tech Stack

- **Compute**: Modal (serverless containers)
- **Storage**: Cloudflare R2 (S3-compatible)
- **AI**: DeepAgents/LangGraph, LangChain
- **Frontend**: React, Vite, Tailwind CSS
- **Testing**: Vitest, Playwright
- **Runtime**: Node.js 20+, Python 3.11+
- **Python Environment**: uv (fast Python package manager)

## Commands

```bash
# Python environment (uv)
uv sync                              # Install dependencies from pyproject.toml
uv run <command>                     # Run command in virtual environment
uv add <package>                     # Add a dependency
uv pip install -e .                  # Install project in editable mode

# Modal deployment
modal secret create r2-secret        # Register R2 credentials
modal deploy                         # Deploy sandbox & agent services

# Dev servers (inside container)
vite serve ./prototype --port 3001
vite serve ./frontend --port 3002
dbml-renderer serve ./dbml --port 3003
vitest-ui serve ./test-case --port 3004

# Tests
npm test                             # Run in sandbox
```

## Key Design Principles

1. **Scoped File Access**: Agent tools are restricted to specific folders (read_prototype reads only ./prototype, write_frontend writes only to ./frontend)
2. **Air-Gapped Persistence**: Files sync to R2; containers are ephemeral
3. **Path Traversal Validation**: All file operations must be validated in security/utils.py

## Implementation Milestones

1. Load "Hello World" HTML via Gateway URL (proves sandbox + routing)
2. Chat message creates file that appears in R2 (proves Agent ↔ Sandbox RPC)
3. Full pipeline: Upload prototype → Agent generates frontend → Live preview updates

## Current Status

Project is in **planning phase**. See:
- `ARCHITECT.md` - System architecture
- `PLAN.md` - Implementation roadmap (5 phases)
- `TASKS.md` - Trackable task checklist
