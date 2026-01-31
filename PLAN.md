# **Implementation Plan**

## **Phase 1: Infrastructure Foundation (The "Air Gap")**

**Goal:** A secure, syncing sandbox that can survive restart.

* \[ \] **R2 Setup:** Configure Cloudflare R2 bucket and generate API keys.  
* \[ \] **Modal Secret:** Create r2-secret in Modal dashboard.  
* \[ \] **Sync Engine:** Build the R2Sync Python class (pull/push logic with ignore lists).  
* \[ \] **Base Image:** Create a Docker image with Node.js, Python, vite, boto3, and watchdog.

## **Phase 2: The Multi-Process Sandbox**

**Goal:** A single container that can serve Prototype, Frontend, and DBML simultaneously.

* \[ \] **Supervisor Script:** Write a Python ProcessManager class to spawn and kill subprocesses on specific ports (3001-3004).  
* \[ \] **Gateway Router:** Build the Modal HTTP endpoint to route URL paths /prototype and /frontend to the respective internal ports.  
* \[ \] **Live Test:** Verify that index.html in /prototype and App.jsx in /frontend can be viewed in two browser tabs simultaneously.

## **Phase 3: The "Brain" (Deep Agent Integration)**

**Goal:** Connect the AI so it can read ./prototype and write to other folders.

* \[ \] **Agent Backend:** Implement the DeepAgents backend that communicates via RPC to the Sandbox.  
* \[ \] **Tooling:** Create specific tools for the Agent:  
  * read\_prototype() (Scoped to ./prototype folder)  
  * write\_frontend() (Scoped to ./frontend folder)  
  * generate\_dbml() (Writes to ./dbml)  
* \[ \] **System Prompts:** Design the specialized prompts for "Prototype \-\> Frontend" conversion logic.

## **Phase 4: The Client Canvas (Frontend UI)**

**Goal:** A React dashboard for the user to interact with the system.

* \[ \] **Project Manager:** UI to create/select projects (folders in R2).  
* \[ \] **The "4-Pane" View:** A tabbed interface allowing the user to switch between Prototype, Frontend, DBML, and Test views (IFrames).  
* \[ \] **Chat Interface:** A side panel connected to the Modal Agent endpoint.

## **Phase 5: Specialized Pipelines (The Logic)**

**Goal:** Implement the specific transformation rules.

* \[ \] **Frontend Pipeline:** Logic to parse vanilla HTML/JS and output React/Tailwind.  
* \[ \] **DBML Pipeline:** Logic to infer data structures from UI inputs and generate schema.  
* \[ \] **Test Pipeline:** Logic to read user stories/prototype interactions and generate Playwright/Vitest scripts.