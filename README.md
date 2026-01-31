# DevLabo

AI-powered app builder using Brain-Body-Storage architecture.

## Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **uv** - Fast Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Modal CLI** - Serverless compute ([install](https://modal.com/docs/guide))
- **gh CLI** - GitHub CLI (optional, for contributing)

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/patchwork-body/devlabo.git
cd devlabo

# Backend (Python)
uv sync --all-extras

# Client (React)
cd client
npm install
cd ..
```

### 2. Configure Environment

**Modal Secrets** (required for deployment):

```bash
# Authenticate with Modal
modal token new

# Create R2 secret for file storage
modal secret create r2-secret \
  R2_ACCOUNT_ID=<your-account-id> \
  R2_ACCESS_KEY_ID=<your-access-key> \
  R2_SECRET_ACCESS_KEY=<your-secret-key> \
  R2_BUCKET_NAME=<your-bucket>

# Create OpenRouter secret for AI agent
modal secret create openrouter-secret \
  OPENROUTER_API_KEY=<your-api-key>
```

**Client Environment** (for production builds):

```bash
cd client
cp .env.example .env

# Edit .env and set:
# VITE_API_URL=https://your-modal-app--devlabo-gateway.modal.run
```

### 3. Development

**Run tests:**
```bash
uv run pytest
```

**Run client dev server:**
```bash
cd client
npm run dev
# Opens at http://localhost:5173/
```

**Deploy to Modal (for backend testing):**
```bash
modal deploy
```

### 4. Production Build

**Client:**
```bash
cd client
npm run build
# Output in client/dist/
```

Deploy `client/dist/` to Vercel, Cloudflare Pages, or any static host.

## Project Structure

```
devlabo/
├── agent/              # AI orchestration (LangGraph)
│   ├── service.py      # Modal service for DeepAgent
│   ├── tools.py        # Agent tools (read/write files)
│   └── prompts.py      # System prompts
├── gateway/            # HTTP routing layer
│   └── router.py       # FastAPI reverse proxy
├── sandbox/            # Modal container definition
│   ├── image.py        # Container image with Node.js
│   └── process_manager.py
├── common/             # Shared utilities
│   └── r2_sync.py      # Cloudflare R2 sync
├── security/           # Security utilities
│   └── utils.py        # Path traversal validation
├── client/             # React dashboard
│   ├── src/
│   │   ├── components/ # UI components
│   │   ├── hooks/      # React Query hooks
│   │   └── lib/        # Utilities
│   └── package.json
└── tests/              # Python tests
```

## Environment Variables

### Modal Secrets

| Secret Name | Variables | Description |
|-------------|-----------|-------------|
| `r2-secret` | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Cloudflare R2 for file storage |
| `openrouter-secret` | `OPENROUTER_API_KEY` | OpenRouter API for AI models |

### Client Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Production only | Modal gateway URL (e.g., `https://your-app--devlabo-gateway.modal.run`) |

## Architecture

See `ARCHITECT.md` for system architecture and `PLAN.md` for implementation roadmap.

## License

MIT
