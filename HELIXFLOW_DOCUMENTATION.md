# HelixFlow Gateway: Architecture & Documentation

## 1. System Overview
HelixFlow Gateway is a high-performance, low-latency API proxy and routing engine designed to intercept, analyze, and intelligently route Large Language Model (LLM) traffic. It acts as a transparent reverse-proxy compatible with the OpenAI API standard (`/v1/chat/completions`) but dynamically routes requests to the optimal provider (DeepSeek, Gemini, or Claude) based on defined policies (e.g., speed, reasoning depth, code generation).

### Key Features
- **Intelligent Routing**: Dynamically shifts traffic based on cost, latency, or model capability requirements.
- **Unified Telemetry**: Normalizes logs across all providers to calculate Time-to-First-Token (TTFT), internal latency, and total ROI/Savings.
- **Mission Control UI**: A dark-mode, cyberpunk-themed dashboard for real-time monitoring and governance.
- **Enterprise Governance**: Mocked structures in place for PII redaction and payload sanitization via Redis-backed metrics.

---

## 2. Directory Structure & Code Components

```text
C:\Users\mcmur\Desktop\Router\HelixFlow\
â”œâ”€â”€ helixflow_gateway/               # Core Application Directory
â”‚   â”œâ”€â”€ bootstrap.py                 # FastAPI Application Entrypoint
â”‚   â”œâ”€â”€ requirements.txt             # Python Dependencies
â”‚   â”œâ”€â”€ infrastructure/
â”‚   â”‚   â””â”€â”€ fabric_connectors.py     # Backend integrations to external APIs
â”‚   â”œâ”€â”€ controllers/
â”‚   â”‚   â””â”€â”€ dashboard.py             # API endpoints serving telemetry data to the UI
â”‚   â””â”€â”€ static/                      # Frontend UI (Dashboard)
â”‚       â”œâ”€â”€ index.html               # Main DOM structure and Tab definitions
â”‚       â”œâ”€â”€ app.js                   # Client-side routing, API fetching, and Chart.js logic
â”‚       â””â”€â”€ style.css                # Premium Dark "Monolithic Cyberpunk" Theme
â”œâ”€â”€ deploy_gateway.ps1               # PowerShell CI/CD script for DigitalOcean droplet
â””â”€â”€ test_*.py                        # Various diagnostic and integration tests
```

---

## 3. The Frontend Dashboard (`static/`)

The web dashboard is designed as a single-page application (SPA). It uses vanilla JavaScript, CSS3, and HTML5 with `Chart.js` for data visualization. 

### Core UI Tabs & Their Functions

1. **Usage & Spend (`dashboard`)**: 
   - Displays overarching metrics like total spend, average latency, and percentage splits across DeepSeek, Gemini, and Anthropic.
   - Contains highly optimized `Chart.js` graphs (`chart.update('none')`) visualizing daily token volume, spend by model, cumulative savings, and project ingestion.
2. **Live Logs (`logs`)**: 
   - A real-time data table streaming individual model completions.
   - **Transaction Drawer**: Clicking a row opens a sliding right-hand drawer to inspect raw completion payloads and transaction IDs.
3. **Configure Router (`configure`)**:
   - Allows administrators to toggle global parameters, switch routing modes (e.g., Lowest Cost, Lowest Latency), and manage caching mechanisms.
4. **LLM Simulator (`simulator`)**:
   - A dual-pane testing arena. Developers can fire a single prompt and watch Model A (e.g., Speed Edge) race Model B (e.g., Dense Reasoning) side-by-side to compare latency, tokens, and TTFT.
5. **Security & Governance (`security`)**:
   - Tracks data privacy operations. Displays metrics for PII strings scrubbed and prompt injections blocked.
   - Includes "Manual Circuit Breakers", allowing an admin to instantly isolate a failing vendor and force failover routing.

### Frontend Technical Highlights
- **Performance**: The UI polling (`startHealthPoller()`) checks gateway health every 5 seconds without blocking the main thread.
- **Asynchronous Telemetry**: `securityTelemetryMock` is built to simulate rapid `HGETALL` Redis lookups, preparing the system for backend plumbing in the next sprint without requiring UI rewrites.

---

## 4. Backend Architecture & APIs

### Tech Stack
- **Framework**: `FastAPI` running on `uvicorn` with `uvloop` for maximum async throughput.
- **In-Memory Store**: `redis-server` handles rapid caching, rate limiting, and telemetry aggregation.

### The Routing Loop (`fabric_connectors.py` & `bootstrap.py`)
1. **Interception**: A client sends a standard OpenAI REST payload to the gateway.
2. **Evaluation**: The gateway's `HelixRouter` evaluates the `policy` or `model` tag.
3. **Dispatch**: The request is translated to the native API format of the target vendor (Google Vertex, Anthropic, or DeepSeek).
4. **Telemetry Capture**: Before returning the response, the gateway calculates exact internal latency (overhead) vs. external provider TTFT.

### Available APIs on the Gateway
- `POST /v1/chat/completions`: The universal inference proxy endpoint.
- `GET /health`: Returns basic connectivity and cache hit rates.
- `GET /api/dashboard/stats`: Returns aggregated spend analytics and chart vectors.
- `GET /stream`: Server-Sent Events (SSE) endpoint providing live log streaming to the dashboard.

---

## 5. Deployment & CI/CD Pipeline

The entire system is deployed to a remote Linux instance (DigitalOcean Droplet: `165.227.185.117`) via the custom `deploy_gateway.ps1` PowerShell script.

### How `deploy_gateway.ps1` Works
1. **Pre-flight Checks**: Tests SSH connectivity utilizing the local `HelixFlow` private key.
2. **Archiving**: Bundles the `helixflow_gateway` directory locally into `helixflow-gateway.tar.gz` (ignoring environments and caches).
3. **Transmission**: Uses `scp` to push the archive to `/tmp/` on the Droplet.
4. **Extraction & Provisioning**:
   - Extracts files to `/opt/helixflow-gateway`.
   - Uses `apt-get` to ensure `redis-server` is running.
   - Re-builds the Python virtual environment (`venv`) to ensure exact binary matching.
   - Generates the `helixflow-gateway.service` systemd unit file to run the FastAPI app daemonized on port 8000.
5. **Launch**: Reloads `systemctl`, enabling and starting the gateway, meaning the API recovers automatically upon server reboot.

---

## 6. Recent Development & Changelog (Ecosystem Integration)

The HelixFlow Gateway has recently undergone a major push for production readiness and seamless integration into the broader Helix Ecosystem. The following milestones were achieved:

### Repository Sanitization & Security
- **Artifact Cleanup**: Scrubbed all local temporary artifacts, debugging scratchpads (`test_traffic.py`, `run_local_mock.py`), and legacy planning markdown documents from the version control system to ensure a pristine `main` branch.
- **Credential Protection**: Implemented strict `.gitignore` rules and purged all hardcoded API keys (`sk-...`) prior to pushing the repository to GitHub, moving entirely to `.env` based configurations (`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`).
- **Telemetry Wipe**: Cleared the Redis testing state locally and on the live droplet to ensure no anomalous test artifacts leaked into production logging.

### Telemetry Injection & Dashboard Visualization
- Executed specialized Python subroutines (`inject.py`) directly against the live DigitalOcean droplet (`165.227.185.117`) to artificially synthesize high-volume, realistic LLM traffic across DeepSeek, Gemini, and Anthropic.
- This allowed the frontend UI to populate beautiful `Chart.js` graphs detailing Latency, Time-to-First-Token (TTFT), and Cost Savings logic.
- Leveraged an autonomous browser subagent to snapshot the active, data-rich UI in real-time, capturing high-resolution PNGs of every single dashboard tab (Usage & Spend, Live Logs, Simulator, Security, Configuration).

### Enterprise Documentation Rollout
- Rewrote the main `README.md` to feature an enterprise-grade architectural map, drop-in Python/cURL execution snippets, and embedded the newly generated high-resolution screenshots.
- Resolved environment variable discrepancies between the `.env` template and the actual `env_spec.py` Pydantic models.

### Integration with Helix Engine & Website
- **Helix Engine Sync**: Accessed the primary `Helix-Engine` codebase, purged legacy "AirCode" branding, nuked lingering `.aider` caches and `__pycache__` artifacts, and explicitly updated its README to route LLM requests through the new HelixFlow Gateway for multiplexing.
- **Helix Website Sync**: Deployed updates to the `Helix-Website` (Next.js) landing page. Expanded the installation UI from a 2-column to a 3-column grid to proudly feature the `HelixFlow Gateway` alongside the Engine and Diagnostic Lab, effectively formalizing the 3-pillar ecosystem.
