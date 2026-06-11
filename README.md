# HelixFlow Gateway

HelixFlow Gateway is an enterprise-grade, high-performance, low-latency API proxy and routing engine designed to intercept, analyze, and dynamically route Large Language Model (LLM) traffic across multiple providers.

It serves as a transparent reverse-proxy compatible with the OpenAI API standard (`/v1/chat/completions`), allowing seamless integration with existing applications. By applying advanced routing policies, HelixFlow ensures optimal model selection—balancing cost, latency, and reasoning depth dynamically.

## 🚀 Features

- **Intelligent Routing**: Instantly shift traffic based on explicit policies (e.g., Speed Edge, Dense Reasoning) or implicit vendor constraints.
- **Unified Telemetry**: Normalizes logs across DeepSeek, Google Gemini, and Anthropic Claude. Automatically calculates Time-to-First-Token (TTFT), gateway overhead, and overall cumulative ROI.
- **Enterprise Governance**: Built-in PII scrubbing and prompt injection interception powered by a high-throughput async processing pipeline.
- **Live Mission Control UI**: A "dark-cosmic" dashboard providing real-time infrastructure data points and configuration overlays.

---

## 📸 Dashboard Walkthrough

### Usage & Spend
The primary analytics view showcasing daily token volume, spend distribution across models, and overarching latency baselines.
![Usage & Spend](docs/images/usage_and_spend.png)

### Live Logs
A real-time telemetry stream of individual LLM completions. Click on any transaction to open the sliding Transaction Drawer and inspect raw payload blocks and trace IDs.
![Live Logs](docs/images/live_logs.png)

### LLM Simulator
A dual-pane testing arena. Fire a single prompt and watch Model A race Model B side-by-side to visually compare latency, cost, and tokens in real-time.
![LLM Simulator](docs/images/llm_simulator.png)

### Security & Governance
Tracks data privacy operations, including PII strings scrubbed and prompt injections blocked. Also includes Manual Circuit Breakers to instantly isolate failing vendors.
![Security & Governance](docs/images/security_governance.png)

### Configure Router
Allows administrators to toggle global parameters, switch routing modes (e.g., Lowest Cost vs. Lowest Latency), and manage caching hierarchies.
![Configure Router](docs/images/configure_router.png)

---

## 🛠 Architecture

- **Core Router Engine**: `FastAPI` + `uvicorn` + `uvloop`
- **Data Plane**: `Redis` (In-Memory Metrics & Pub/Sub Telemetry)
- **Vendors Supported**: DeepSeek (`/v1/chat/completions`), Google Gemini (Vertex AI), Anthropic Claude (Messages API).
- **Frontend**: Vanilla JS SPA with `Chart.js` for optimized graph updates via `chart.update('none')`.

See `HELIXFLOW_DOCUMENTATION.md` for deeper architectural concepts.
