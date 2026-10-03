## LucidTrend

An intelligent platform that operates with multi-level workflows to scout developer ecosystems, analyze engineering updates, and publish technical reports. It brings together automated web research, reliable database storage, background image generation, and clean editorial email delivery into one unified system.

---

## System Overview

### 1. Research and Publishing Pipeline
```mermaid
flowchart LR
    A[Scout & Research\nGemini + Google Search] --> B[Data Extraction\nLocal JSON Parsing]
    B --> C[Immediate Publish\nMongoDB Database]
    C --> D[Editorial Newsletter\nText-Only Delivery]
```

### 2. Background Image Generation
```mermaid
flowchart LR
    A[Published Article\nDefault Thumbnail] --> B[Background Worker\nFLUX.1 4-Key Ladder]
    B --> C[In-Place Update\nMongoDB Image]
```

### 3. Interactive Management and CLI
```mermaid
flowchart LR
    A[Operator / Developer\nCLI Terminal] <-->|Authenticated API| B[FastAPI Management Server\nPort 8000]
    B --> C[Modular Pipeline Runs\n--with / --without flags]
    B --> D[On-Demand Image Gen\nFLUX.1 Visual Assets]
```

---

## Detailed Documentation

For in-depth explanations, configuration guides, and architectural diagrams, refer to the dedicated documentation files:

* **[Architecture & Mechanism Guide (docs/mechanism.md)](docs/mechanism.md)**: Comprehensive deep dive into the cascading failover algorithms, asynchronous image ladder, deterministic data extraction, and component communication protocols with full Mermaid flowcharts.
* **[User & Operations Guide (docs/use.md)](docs/use.md)**: Complete step-by-step instructions for quick start, cloning, setting up `.env` credentials, running natively or via Docker Compose, manual API testing with Postman and cURL, and full CLI usage.

---

<div align="center">
  <sub>Developed by <a href="https://www.anamoldhakal.com.np/"><strong>Anamol Dhakal</strong></a></sub>
</div>
