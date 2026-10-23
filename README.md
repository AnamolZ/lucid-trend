## LucidTrend

An autonomous technology intelligence engine that continuously scouts developer ecosystems, synthesizes high-impact technical analysis from breaking primary sources, generates custom photorealistic visual assets, narrates full audio briefings, and pre-renders static edge payloads into a unified global publication system.

---

## System Overview

### 1. Research, Multimodal Synthesis & Edge Delivery Pipeline
```mermaid
flowchart LR
    A["WebScout 24h RSS<br/>Primary Intelligence"] --> B["NewsCoordinator<br/>Gemini 3.7 Flash Engine"]
    B --> C["Data Extraction<br/>Zero-Token Parser"]
    C --> D["Turso libSQL<br/>7-Day Retention DB"]
    D --> E["Multimodal Workers<br/>Cloudflare FLUX & Edge TTS"]
    E --> F["Static Edge Baker<br/>Vercel CDN Payloads"]
    F --> G["Newsletter & Push<br/>Brevo SMTP & Firebase FCM"]
```

### 2. High-Precision Image Synthesis Cascade
```mermaid
flowchart LR
    A["Article Ingested<br/>Title & Visual Prompt"] --> B["Visual Grounding Engine<br/>build_grounded_flux_prompt"]
    B --> C{"Tier 1: Cloudflare<br/>Workers AI FLUX Pool<br/>(Multi-Account Rotation)"}
    C -->|Success ~3-5s| E["Turso DB & Flat CDN Assets<br/>/images/post-id.jpg"]
    C -->|Fallback| D["Tier 2: Pollinations.ai<br/>Zero-Auth 16:9 FLUX"]
    D --> E
```

### 3. Interactive Management & CLI
```mermaid
flowchart LR
    A["Operator / Developer<br/>Terminal CLI"] <-->|Authenticated API| B["FastAPI Management Server<br/>Port 8000"]
    B --> C["Modular Pipeline Runs<br/>--without flags"]
    B --> D["On-Demand Image Gen<br/>Cloudflare FLUX Assets"]
    B --> E["Mobile Push Testing<br/>Firebase Topic Broadcast"]
    B --> F["Security & Key Rotation<br/>Master Password Auth"]
```

---

## Autonomous Publishing Schedule

LucidTrend operates on an autonomous 8-slot, 3-hour micro-dispatch cycle synchronized globally. Each slot targets a specific intelligence pillar anchored to international market hours and developer activity cycles.

| Slot | UTC Time | Nepal Time (NPT, UTC+5:45) | Target Category Pillar | Editorial Theme / Focus |
| :---: | :---: | :---: | :--- | :--- |
| **#1** | `00:00 UTC` | **05:45 AM NPT** | **Technology, AI & Research** | Scientific & Security Breakthroughs |
| **#2** | `03:00 UTC` | **08:45 AM NPT** | **Geopolitics & Defense** | Overnight Diplomatic & Strategic Shifts |
| **#3** | `06:00 UTC` | **11:45 AM NPT** | **Finance & Global Markets** | Global, Asian & European Market Intelligence |
| **#4** | `09:00 UTC` | **02:45 PM NPT** | **Technology, AI & Research** | Morning Engineering & Systems Releases |
| **#5** | `12:00 UTC` | **05:45 PM NPT** | **Geopolitics & Defense** | Pre-Market Geopolitical Intelligence |
| **#6** | `15:00 UTC` | **08:45 PM NPT** | **Finance & Global Markets** | Post-Open Market Volatility & Trends |
| **#7** | `18:00 UTC` | **11:45 PM NPT** | **Technology, AI & Research** | Midday Frontier Tech & AI Architecture |
| **#8** | `21:00 UTC` | **02:45 AM NPT** | **Finance & Global Markets** | US Market Close Digest & Macro Movements |

## Detailed Documentation

For in-depth explanations, configuration guides, and complete operational instructions:

* **[Architecture & Mechanism Guide (docs/mechanism.md)](docs/mechanism.md)**: Deep dive into the 2-stage grounded intelligence pipeline, Cloudflare Workers AI FLUX multi-account pool, story-grounded visual prompt engineering, Turso libSQL edge database, Edge TTS narration, and Firebase Cloud Messaging mobile push architecture.
* **[User & Operations Guide (docs/use.md)](docs/use.md)**: Step-by-step setup guide for native and Docker environments, `.env` configuration (Cloudflare, Gemini, Turso, SMTP, Firebase), CLI commands, and REST API documentation.

---

<div align="center">
  <sub>Developed by <a href="https://www.anamoldhakal.com.np/"><strong>Anamol Dhakal</strong></a></sub>
</div>
