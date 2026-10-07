# LucidTrend System Architecture

LucidTrend is an autonomous technology intelligence and publishing system. It continuously scouts global developer ecosystems, synthesizes comprehensive technical articles from breaking primary sources, generates custom photorealistic visual assets, updates a content database, dispatches clean editorial briefings to subscribers, and provides an authenticated command-line interface for interactive control.

This document details the internal mechanics, algorithmic decisions, and communication protocols governing the entire architecture.

---

## 1. End-to-End System Architecture

The LucidTrend ecosystem is divided into autonomous background services, external model inference networks, storage engines, delivery channels, and an interactive management layer.

```mermaid
flowchart TD
    subgraph Management ["Interactive Management Layer"]
        CLI["LucidTrend CLI (cli.py)"]
        API["FastAPI Server (:8000)"]
        Auth["API Key Middleware"]
        CLI --> |X-API-Key HTTP Request| Auth
        Auth --> API
    end

    subgraph Orchestration ["Core Scheduler & Pipeline (main.py)"]
        Scheduler["Schedule Daemon (05:00 & 17:00)"]
        Cleaner["Hourly Temp Directory Cleaner"]
        Runner["Pipeline Orchestrator (run_pipeline)"]
        API --> |Modular Trigger (--with/--without)| Runner
        Scheduler --> |Scheduled Daily Run| Runner
        Cleaner --> |Purges Expired Files| TempDir["temp/ Directory"]
    end

    subgraph Intelligence ["2-Stage Grounded Intelligence Pipeline"]
        WebScout["WebScout RSS Engine (24h Google News Feeds)"]
        NewsCoordinator["NewsCoordinator (Gemini 3.7 Flash)"]
        GeminiPool["Gemini Model Pool & Key Cascading Coordinator"]
        WebScout --> |Verified Real-Time Dossier| NewsCoordinator
        NewsCoordinator --> GeminiPool
    end

    subgraph Extraction ["Deterministic Local Parsing"]
        LocalParser["Zero-Token Fast Extractor (fast_extract)"]
    end

    subgraph Persistence ["Immediate Publishing Layer"]
        MongoService["MongoDB Service (MongoDBService)"]
        MongoCluster[("MongoDB Atlas (posts collection)")]
        MongoService --> |1. Insert with Default Image| MongoCluster
    end

    subgraph Newsletter ["Editorial Delivery Engine"]
        EmailWorker["Newsletter Dispatcher (send_email_task)"]
        SMTPRelay["SMTP Relay Server (TLS)"]
        Subscribers[("Verified Subscribers")]
        EmailWorker --> |Fetch Verified Addresses| Subscribers
        EmailWorker --> |Transmit Concise HTML Cards| SMTPRelay
    end

    subgraph Imagery ["3-Tier High-Precision Image Cascade"]
        ImageWorker["Celery Worker / Fallback Thread"]
        VisualDirector["Visual Grounding Engine (build_grounded_flux_prompt)"]
        CF_AI["Tier 1: Cloudflare Workers AI FLUX-1-schnell"]
        HF_AI["Tier 2: Hugging Face FLUX.1 (Multi-Key)"]
        Pollinations["Tier 3: Pollinations.ai FLUX (Zero-Auth 16:9)"]
        
        ImageWorker --> VisualDirector
        VisualDirector --> CF_AI
        CF_AI -.->|Fallback| HF_AI
        HF_AI -.->|Fallback| Pollinations
        CF_AI --> |In-Place Base64 Update| MongoCluster
        HF_AI --> |In-Place Base64 Update| MongoCluster
        Pollinations --> |In-Place Base64 Update| MongoCluster
    end

    Runner --> Intelligence
    Intelligence --> LocalParser
    LocalParser --> Persistence
    Persistence --> Newsletter
    Persistence -.-> |Non-Blocking Trigger| Imagery
```

---

## 2. Multi-Model Intelligence Engine and Cascading Failover

The intelligence subsystem synthesizes technical news articles using Google Agent Development Kit (ADK) and the Gemini family of language models, wrapped in a 45-second circuit breaker with automatic failover across multiple API keys and model tiers.

```mermaid
flowchart TD
    Start([Pipeline Trigger]) --> Scout[Step 1: WebScout Fetches 24h RSS Intel]
    Scout --> Dossier[Format Verified Real-Time Dossier]
    Dossier --> InitAgent[Step 2: Initialize NewsCoordinator with Dossier]
    InitAgent --> CheckActive[Read Active Model & Key from KeyModelCoordinator]
    
    subgraph FailoverLoop ["Cascading Failover Engine"]
        Execute[Execute Editorial Synthesis via Google ADK]
        Success{Success within 45s?}
        Is429{Rate Limit or Quota Error 429?}
        IsAuth{Key Invalid or Denied 401/403?}
        RotateKey[Rotate to Next API Key in Pool]
        CascadeModel[Cascade Down to Next Model Tier]
    end

    CheckActive --> Execute
    Execute --> Success
    Success -- Yes --> ReturnRaw[Return Synthesized JSON Articles]
    Success -- No --> Is429
    
    Is429 -- Yes --> RotateKey
    Is429 -- No --> IsAuth
    
    IsAuth -- Yes --> Blacklist[Blacklist Key for Session] --> RotateKey
    IsAuth -- No --> CascadeModel
    
    RotateKey --> KeysRemaining{More Keys Available?}
    KeysRemaining -- Yes --> Execute
    KeysRemaining -- No --> CascadeModel
    CascadeModel --> Execute
```

### Model Cascade Ladder

| Tier | Model ID | Timeout | Primary Purpose |
| :---: | :--- | :---: | :--- |
| **Tier 1** | `gemini-3.7-flash` | 45s | Flagship hybrid reasoning, highly detailed technical journalism. |
| **Tier 2** | `gemini-3.5-flash-lite` | 45s | High-efficiency fallback model for high-throughput synthesis. |
| **Tier 3** | `gemini-3.1-flash-lite` | 45s | Resilient secondary fallback model. |
| **Tier 4** | `gemini-flash-latest` | 45s | Ultimate fallback targeting Gemini Flash stable channel. |

---

## 3. Asynchronous Decoupling Architecture

To ensure immediate frontend availability and rapid email delivery, visual generation is completely decoupled from article persistence:

```mermaid
sequenceDiagram
    autonumber
    actor Scheduler as Scheduler / Operator
    participant Runner as run_pipeline()
    participant Mongo as MongoDB Atlas
    participant Email as Celery (send_email_task)
    participant Celery as Celery (generate_image_task)
    participant CF as Cloudflare Workers AI FLUX

    Scheduler->>Runner: Trigger Pipeline Cycle
    Runner->>Runner: 2-Stage Grounded Intelligence Synthesis
    Runner->>Runner: Deterministic Local JSON Extraction
    
    rect rgb(235, 248, 255)
        note right of Runner: Phase 1: Immediate Content Availability
        Runner->>Mongo: insert_documents() [Default Placeholder Image]
        Mongo-->>Runner: Confirm IDs Inserted
        Runner->>Email: send_email_task.delay() [Asynchronous]
        Runner->>Celery: generate_and_update_image_task.delay() [Asynchronous]
    end
    
    note over Runner: Pipeline Cycle Finishes in ~30s Total
    
    critical Background Image Generation (~2-4 seconds)
        Celery->>CF: Dispatch Grounded FLUX Prompt
        CF-->>Celery: Return Base64 JPEG/PNG
        Celery->>Mongo: update_post_image(post_id, new_image_url)
        Note over Mongo: Post image field replaced in-place
    end
```

---

## 4. High-Precision Image Synthesis & 3-Tier Multi-Provider Cascade

Rather than relying on generic diffusion prompts that produce abstract floating dots in dark space, LucidTrend utilizes an automated **Visual Grounding Engine** paired with a resilient 3-tier cascade:

```mermaid
flowchart TD
    StartTask([Image Generation Task]) --> GroundPrompt[build_grounded_flux_prompt]
    
    subgraph Grounding ["Story-Specific Visual Anchoring"]
        DetectDomain{Domain Detection}
        AI_Domain[Supercomputing Labs & Formal Proof Blackboards]
        Dev_Domain[Engineers at Modern Multi-Monitor IDE Workstations]
        Chip_Domain[Macro Photography of Silicon Microprocessor Dies]
        Quantum_Domain[Gold-Plated Dilution Refrigerator Cryostats]
        Cyber_Domain[Panoramic SOC Security Operations Command Centers]
        Cloud_Domain[Cavernous Cloud Datacenter Server Halls]
    end
    
    GroundPrompt --> DetectDomain
    DetectDomain --> AI_Domain & Dev_Domain & Chip_Domain & Quantum_Domain & Cyber_Domain & Cloud_Domain
    
    subgraph ProviderCascade ["3-Tier Provider Cascade"]
        Tier1["Tier 1: Cloudflare Workers AI FLUX-1-schnell (~2.0s)"]
        Tier2["Tier 2: Hugging Face FLUX.1 (Multi-Key)"]
        Tier3["Tier 3: Pollinations.ai FLUX (Zero-Auth 16:9 Fallback)"]
    end
    
    AI_Domain & Dev_Domain & Chip_Domain & Quantum_Domain & Cyber_Domain & Cloud_Domain --> Tier1
    
    Tier1 -->|Success 200 OK| ReturnImage[/Return Base64 Data URI/]
    Tier1 -->|401/403/Error| Tier2
    Tier2 -->|Success 200 OK| ReturnImage
    Tier2 -->|402/Quota Exhausted| Tier3
    Tier3 --> ReturnImage
    
    ReturnImage --> UpdateDB[(Update Post in MongoDB Atlas)]
```

### Visual Grounding Principles
- **Hardware & Semiconductors**: Macro shots of etched silicon dies, gold wire bonds, and liquid cooling rather than generic digital graphics.
- **Developer Tools & Frameworks**: Software engineers in modern studios with ultra-wide screens displaying actual IDE code syntax, debug consoles, and twilight city views.
- **Mathematical Reasoning & AI**: Modern research laboratories with illuminated formal logic blackboards and operator terminals.
- **Quantum Computing**: Dilution cryostats with gold-plated plates and braided copper wiring in cleanroom environments.

---

## 5. Concise Editorial Newsletter Architecture

The email distribution subsystem is designed specifically for technical professionals, focusing on clarity, typography, and deliverability.

```mermaid
flowchart TD
    Articles[/Synthesized Articles/] --> Formatter["Editorial Card Formatter (_format_article_html)"]
    
    subgraph ContentAssembly ["Content Assembly"]
        CategoryBadge["Category Badge (e.g. AI & ML)"]
        Headline["High-Impact Clean Headline"]
        ConciseSummary["Concise 2-3 Sentence Analytical Summary"]
        ImpactBox["Key Engineering Impact Highlight Box"]
    end
    
    Formatter --> ContentAssembly
    ContentAssembly --> FullBlocks[/Formatted Editorial Briefing Cards/]
    
    FullBlocks --> Template["Editorial Template (notify_subscriber_template)"]
    Subscribers[("Verified Subscribers Collection")] --> EmailLoop["Delivery Loop (send_noreply_email)"]
    Template --> EmailLoop
    EmailLoop --> SMTP["Brevo SMTP Relay (TLS Port 587)"]
    SMTP --> Inboxes([Subscriber Inboxes])
```

- **Clean Typography**: Eliminates raw 500-word markdown code dumps and ASCII diagrams from email inboxes while preserving the complete deep-dive content on the website.
- **Key Engineering Impact**: Highlighting critical takeaways, migration hurdles, or benchmark gains in a dedicated callout box.
