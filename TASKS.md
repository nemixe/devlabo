# **Trackable Tasks**

## **1\. Infrastructure (Modal & R2)**

* [ ] Create Cloudflare R2 Bucket ai-app-builder.
* [ ] Generate R2 Access Key & Secret.
* [ ] Run modal secret create r2-secret with credentials.
* [x] Implement common/r2\_sync.py (The Pull/Push logic).
* [x] Implement security/utils.py (Path traversal validation).
* [x] Create sandbox/image.py (Pure Modal image with Node 20 + Python 3.11).
* [x] Set up pyproject.toml with uv-based Python environment.
* [x] Write unit tests for security and R2 sync modules (109 tests passing).

## **2\. Sandbox Engine (The Body)**

* [x] Create sandbox/instance.py (The Modal Class).
* [x] Implement ProcessManager to handle multiple subprocess.Popen calls.
* [x] Configure vite in /prototype to run on Port 3001\.
* [x] Configure vite in /frontend to run on Port 3002\.
* [x] Implement Gateway endpoint in gateway/router.py to route traffic.
* [x] **Milestone:** Verify you can load a "Hello World" HTML file from the Gateway URL.

## **3\. AI Agent (The Brain)**

* \[ \] Install deepagents and langchain in the Agent image.  
* \[ \] Implement RemoteBackend class to bridge Agent \-\> Sandbox RPC.  
* \[ \] Create agent/tools.py with list\_files, read\_file, write\_file.  
* \[ \] Implement agent/service.py (The Central Modal Class).  
* \[ \] **Milestone:** Send a chat message "Create a file in /frontend" and verify it appears in R2.

## **4\. Feature Implementation**

### **Feature 1: Prototype**

* \[ \] Create a default "Scaffold" for /prototype (basic HTML/Tailwind setup).  
* \[ \] Ensure index.html serves correctly via the Gateway.

### **Feature 2: Frontend Generation**

* \[ \] Write System Prompt: "You are a React Refactor Specialist. Read ./prototype and output ./frontend."  
* \[ \] Implement agent.convert\_to\_frontend() function.

### **Feature 3: DBML Generation**

* \[ \] Add dbml-renderer or similar tool to the Sandbox image.  
* \[ \] Write System Prompt: "Extract data schema from these UI inputs."  
* \[ \] Create a simple index.html viewer in ./dbml to render the .dbml file.

### **Feature 4: Test Cases**

* \[ \] Add vitest or playwright to the Sandbox image.  
* \[ \] Create a Test Runner UI (or use Vitest UI) on Port 3004\.  
* \[ \] Write System Prompt: "Generate test assertions based on these button clicks."