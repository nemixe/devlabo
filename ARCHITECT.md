# **System Architecture: AI App Builder**

## **1\. High-Level Overview**

The system follows a **Brain-Body Separation** pattern using **Modal** for compute and **Cloudflare R2** for "Air-Gapped" storage.

* **The Brain (Control Plane):** A centralized AI Agent (LangGraph/DeepAgents) that orchestrates the "Build" logic. It reads from the prototype folder and generates code into downstream folders (frontend, dbml, test-case).  
* **The Body (Data Plane):** A dedicated Sandbox Container per user project that runs multiple dev servers simultaneously to serve the different artifacts.  
* **The Storage (Persistence):** Cloudflare R2 serves as the source of truth, syncing data to the ephemeral container disks on startup.

## **2\. Directory Structure (The Workspace)**

Inside the Sandbox Container (/root/workspace), the project is organized into four distinct modules. The AI Agent treats ./prototype as the "Source of Truth" to generate the others.

/root/workspace  
├── /prototype       \# \[Port 3001\] The raw concept (HTML/React-Lite)  
│   ├── index.html  
│   └── script.js  
├── /frontend        \# \[Port 3002\] The production-ready code (Next.js/Vite)  
│   ├── package.json  
│   └── src/...  
├── /dbml            \# \[Port 3003\] Database Schema Visualization  
│   └── schema.dbml  \# Rendered via a lightweight DBML viewer  
└── /test-case       \# \[Port 3004\] Test Runner & Reports  
    └── tests.spec.js

## **3\. Core Components**

### **A. The Gateway (Router)**

**Endpoint:** https://gateway-url.modal.run/connect/{user}/{project}/{module}/{path}

* **Role:** Routes incoming HTTP requests to the correct internal port of the correct container.  
* **Routing Logic:**  
  * /connect/alice/proj1/prototype/\* → Container alice-proj1 : Port **3001**  
  * /connect/alice/proj1/frontend/\* → Container alice-proj1 : Port **3002**  
  * /connect/alice/proj1/dbml/\* → Container alice-proj1 : Port **3003**

### **B. The Sandbox Body (ProjectInstance)**

**Infrastructure:** Modal parameterized class @app.cls.

**Features:**

* **R2 Sync:** Downloads project files on boot; Watcher uploads changes on save.  
* **Process Manager:** Runs a lightweight Python supervisor that manages 4 subprocesses:  
  1. vite serve ./prototype \--port 3001  
  2. vite serve ./frontend \--port 3002  
  3. dbml-renderer serve ./dbml \--port 3003 (Static viewer)  
  4. vitest-ui serve ./test-case \--port 3004 (Test UI)

### **C. The Brain (DeepAgent)**

**Infrastructure:** Centralized Modal Service.

**Workflow:**

1. **Ingest:** Reads all files in ./prototype.  
2. **Plan:** Creates a transformation plan (e.g., "Convert HTML form to React Hook Form").  
3. **Generate:** Writes files to ./frontend or ./dbml.  
4. **Verify:** Runs npm test in the sandbox to ensure generated code works.

## **4\. Data Flow (Prototype to Frontend)**

1. **User:** "Convert this prototype to a Next.js app."  
2. **Brain:** \- Reads /prototype/index.html.  
   * Generates React Components.  
   * Calls sandbox.write\_file("frontend/src/App.jsx", code).  
3. **Sandbox:** \- Writes file to disk.  
   * **Watcher:** Uploads frontend/src/App.jsx to R2.  
   * **Vite (Port 3002):** Hot Reloads the Frontend preview.