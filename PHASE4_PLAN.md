# Phase 4: Client Canvas - Implementation Plan

## Overview

Build a React dashboard (Vite + React) served from the Modal sandbox that provides:
- 4-pane view for Prototype, Frontend, DBML, and Tests
- Chat interface connected to the AI Agent
- Project file browser

## Architecture

```
client/                     # Vite + React app
  ├── src/
  │   ├── components/
  │   │   ├── Layout.tsx
  │   │   ├── Sidebar.tsx
  │   │   ├── ChatPanel.tsx
  │   │   ├── PreviewPane.tsx
  │   │   └── FileTree.tsx
  │   ├── hooks/
  │   │   ├── useAgent.ts
  │   │   └── useSandbox.ts
  │   ├── App.tsx
  │   └── main.tsx
  ├── index.html
  ├── package.json
  ├── vite.config.ts
  └── tailwind.config.js

Build output → sandbox serves at /app/*
```

## Flow

```
User Browser
    ↓
Modal Gateway (/app/*)  →  Serves built React app
    ↓
React App (iframes)
    ├── /connect/{user}/{project}/prototype/*  →  Prototype preview
    ├── /connect/{user}/{project}/frontend/*   →  Frontend preview
    ├── /connect/{user}/{project}/dbml/*       →  DBML preview
    └── /connect/{user}/{project}/tests/*      →  Test runner

React App (API calls)
    └── Modal Agent (devlabo-agent)  →  Chat/file operations
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `client/package.json` | Dependencies: React, Vite, Tailwind |
| `client/vite.config.ts` | Vite config with base path `/app/` |
| `client/tailwind.config.js` | Tailwind setup |
| `client/tsconfig.json` | TypeScript config |
| `client/index.html` | Entry HTML |
| `client/src/main.tsx` | React entry point |
| `client/src/App.tsx` | Main app with routing |
| `client/src/components/Layout.tsx` | Main layout with sidebar + content |
| `client/src/components/Sidebar.tsx` | Navigation + file tree |
| `client/src/components/ChatPanel.tsx` | AI chat interface |
| `client/src/components/PreviewPane.tsx` | Iframe preview component |
| `client/src/components/PreviewTabs.tsx` | Tabbed 4-pane view |
| `client/src/hooks/useAgent.ts` | Hook for agent API calls |
| `client/src/hooks/useSandbox.ts` | Hook for sandbox file operations |
| `client/src/types.ts` | TypeScript types |

## Files to Modify

| File | Changes |
|------|---------|
| `sandbox/instance.py` | Serve `/app/*` from built client |
| `gateway/router.py` | Add route for `/app/*` static files |
| `agent/service.py` | Add CORS headers for browser requests |

---

## Task 1: Initialize Client Project

```bash
cd client
npm create vite@latest . -- --template react-ts
npm install tailwindcss postcss autoprefixer
npm install @tanstack/react-query  # For API state management
npx tailwindcss init -p
```

**package.json:**
```json
{
  "name": "devlabo-client",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.0.0",
    "postcss": "^8.0.0"
  }
}
```

---

## Task 2: Create Layout Components

**Layout.tsx** - Main app layout:
```tsx
export function Layout() {
  return (
    <div className="h-screen flex">
      <Sidebar className="w-64 border-r" />
      <main className="flex-1 flex flex-col">
        <PreviewTabs />
      </main>
      <ChatPanel className="w-80 border-l" />
    </div>
  )
}
```

**PreviewTabs.tsx** - 4-pane tabbed view:
```tsx
const TABS = [
  { id: 'prototype', label: 'Prototype', port: 3001 },
  { id: 'frontend', label: 'Frontend', port: 3002 },
  { id: 'dbml', label: 'DBML', port: 3003 },
  { id: 'tests', label: 'Tests', port: 3004 },
]

export function PreviewTabs() {
  const [activeTab, setActiveTab] = useState('prototype')
  const baseUrl = window.location.origin

  return (
    <>
      <div className="flex border-b">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={activeTab === tab.id ? 'bg-blue-500 text-white' : ''}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <iframe
        src={`${baseUrl}/connect/default/default/${activeTab}/`}
        className="flex-1 w-full"
      />
    </>
  )
}
```

**ChatPanel.tsx** - AI chat interface:
```tsx
export function ChatPanel() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const { mutate: sendMessage, isPending } = useAgent()

  const handleSend = () => {
    sendMessage(input, {
      onSuccess: (response) => {
        setMessages(prev => [...prev,
          { role: 'user', content: input },
          { role: 'assistant', content: response }
        ])
        setInput('')
      }
    })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'text-right' : ''}>
            {msg.content}
          </div>
        ))}
      </div>
      <div className="border-t p-4">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Ask the AI..."
          className="w-full border rounded p-2"
        />
      </div>
    </div>
  )
}
```

---

## Task 3: Create API Hooks

**useAgent.ts:**
```tsx
const AGENT_URL = 'https://rafel-ami--devlabo-agent-deepagent-chat.modal.run'

export function useAgent() {
  return useMutation({
    mutationFn: async (message: string) => {
      const res = await fetch(AGENT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      })
      return res.json()
    }
  })
}
```

---

## Task 4: Add Agent Web Endpoint

Modify `agent/service.py` to expose a web endpoint:

```python
@app.function(
    image=agent_image,
    secrets=[modal.Secret.from_name("openrouter-secret")],
)
@modal.web_endpoint(method="POST")
def chat_endpoint(request: dict) -> dict:
    """Web endpoint for browser chat requests."""
    message = request.get("message", "")
    user_id = request.get("user_id", "default")
    project_id = request.get("project_id", "default")

    agent = DeepAgent(user_id=user_id, project_id=project_id)
    return agent.chat.remote(message=message)
```

---

## Task 5: Serve Client from Gateway

Modify `gateway/router.py` to serve `/app/*`:

```python
from fastapi.staticfiles import StaticFiles

# Mount built client at /app
app.mount("/app", StaticFiles(directory="/root/client/dist", html=True), name="client")
```

---

## Task 6: Build & Deploy Pipeline

1. Build client locally:
```bash
cd client && npm run build
```

2. Include built files in sandbox image:
```python
sandbox_image = (
    modal.Image.debian_slim()
    .copy_local_dir("client/dist", "/root/client/dist")
    # ... rest of image
)
```

---

## Implementation Order

1. Initialize client project structure
2. Create basic Layout + PreviewTabs (iframe only)
3. Test iframe preview works
4. Add ChatPanel UI
5. Add agent web endpoint with CORS
6. Connect chat to agent
7. Add Sidebar with file tree
8. Build & integrate with sandbox
9. Test full flow

---

## Verification

### Milestone: Full UI Flow

1. Open `https://gateway-url/app/`
2. See 4-pane tabbed view with prototype iframe
3. Type in chat: "Create a button component in frontend"
4. See agent response
5. Switch to Frontend tab, see new file
6. Refresh iframe, see component

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Vite + React | Fast dev, simple build |
| Tailwind CSS | Rapid UI development |
| iframes for preview | Isolation, real browser rendering |
| React Query | Handles loading/error states |
| Web endpoint for agent | Browser can call directly |
