# LucidTrend - Autonomous Tech News Agent System

LucidTrend is an advanced, fully automated autonomous agent system designed to scout, analyze, and publish high-impact technology news. It differentiates itself by operating without human intervention, leveraging a swarm of AI agents to perform the work of a dedicated editorial team—from research to publication.

## Core Philosophy: "Zero-Touch" Operation

The system is built on the principle of **autonomous recurrence**. Once deployed, it exists as a self-sustaining entity that triggers itself, self-heals from minor API errors, and manages its own resource consumption. It turns raw information into polished, distributed content through a rigid, fault-tolerant pipeline.

## System Architecture

The architecture is containerized and orchestrated via Docker Compose, splitting responsibilities across three specialized services:

```mermaid
graph TD
    subgraph "Docker Swarm"
        Scheduler[App Container<br/>(Scheduler & Orchestrator)]
        Worker[Worker Container<br/>(Celery & Heavy Lifting)]
        Broker[Redis Container<br/>(Message Broker)]
    end

    User([End User]) --> |Subscribes| MongoDB[(MongoDB)]
    
    Scheduler --> |1. Triggers| AgentEngine[Agent Engine]
    Scheduler --> |4. Queues Tasks| Broker
    
    Broker --> |5. Distributes| Worker
    
    subgraph "Intelligent Processing"
        AgentEngine --> NewsAgent[News Coordinator]
        AgentEngine --> DeepSearch[Deep Search]
        AgentEngine --> RootAgent[Root Agent]
        
        NewsAgent --> |Scouts| GeminiAPI[Google Gemini 2.5]
        DeepSearch --> |Investigates| GeminiAPI
        RootAgent --> |Synthesizes| GeminiAPI
    end
    
    Worker --> |6. Gen Image| HF[HuggingFace / Unsplash]
    Worker --> |7. Send Email| SMTP[SMTP Server]
    
    Worker --> |8. Persist| MongoDB
    SMTP --> |9. Deliver| User
```

## Deep Dive: How It Functions

The system operates on a strictly defined **Daily Cycle**, orchestrated by `main.py`. Here is the step-by-step breakdown of what happens at **05:00 AM** and **10:00 PM** every day:

### Phase 1: The Wake-Up Call (Scheduler)
The `app` container runs a lightweight scheduler (`schedule` library). When the clock hits the target time:
1.  **Environment Check**: It validates that all API keys (Gemini, Mongo, HuggingFace) are present.
2.  **Cycle Start**: It initiates the asynchronous `run_daily_cycle()` function.

### Phase 2: The Agent Swarm (News Discovery)
This is the "Brain" of the operation. The `AgentEngine` spins up three distinct AI personas using Google's Gemini 2.5 Flash model:

1.  **News Coordinator Agent**:
    *   *Role*: The Scout.
    *   *Action*: Scans the past 24 hours of global tech events. It filters out noise (generic product launches, minor updates) and identifies "High Impact" stories.
    *   *Output*: A list of potential headlines.

2.  **Deep Search Agent**:
    *   *Role*: The Investigator.
    *   *Action*: Takes the meaningful headlines found by the Coordinator and performs a "Deep Dive". It looks for context, implications, financial impact, and related historical data.
    *   *Output*: Detailed context and facts for each story.

3.  **Root Agent (The Editor)**:
    *   *Role*: The Synthesizer.
    *   *Action*: Consumes the raw facts from the Deep Search Agent. It applies editorial guidelines (tone, style, formatting) to produce a cohesive, engaging narrative.
    *   *Output*: A raw JSON structure containing the final articles.

### Phase 3: Data Hygiene & Fault Tolerance
AI output can be unpredictable. The system employs a robust cleaning layer (`gemini.py`) before trusting the data:
*   **JSON Repair**: If the AI returns malformed JSON (e.g., missing quotes), the system catches the error and feeds it back into a "Repair Agent" to fix the syntax.
*   **Duplicate Detection**: Before saving, it checks MongoDB to ensure the same story hasn't been covered recently.

### Phase 4: Asynchronous Parallel Processing (Celery)
To ensure the scheduler remains responsive, heavy I/O tasks are offloaded to the **Celery Worker**:

1.  **Image Generation Task**:
    *   For each article, the worker asks Gemini to describe a visual concept (e.g., "Cybersecurity Shield crumbling").
    *   It sends a prompt to **Hugging Face (FLUX.1-dev)** to generate a photorealistic image.
    *   *Fallback*: If image generation fails (API limits), it searches **Unsplash** for a relevant stock photo.
    *   The final image URL is injected into the article and saved to MongoDB.

2.  **Email Broadcast Task**:
    *   Once all articles are processed, a final task is queued.
    *   It fetches all verified subscribers from MongoDB.
    *   It generates a dynamic, engaging email subject line based on the specific news content of that batch.
    *   It compiles the HTML newsletter and broadcasts it via SMTP.

## Directory Structure & Logic

### `app/` (Root)
*   **`main.py`**: The commander. Initializes the cycle, handles errors, and ensures the loop runs forever.
*   **`docker-compose.yml`**: The infrastructure blueprint. Defines how the Scheduler, Worker, and Redis talk to each other.

### `service/`
*   **`tasks/tasks.py`**: The muscle. Contains the code that runs on the worker nodes (Image Gen, Email Sending). Separating this ensures the main app doesn't freeze while waiting for an image to generate.
*   **`mongodb/`**: Database interaction layer. All read/write operations to the persistent storage happen here.
*   **`data_cleaning/`**: The sanitization layer. Ensures that whatever the AI outputs is converted into valid, usable code structures.

## Why this Architecture?

*   **Docker**: Ensures the environment is identical on development and production machines. No "it works on my machine" issues.
*   **uv**: Used instead of `pip` for lightning-fast dependency resolution and installation.
*   **Celery & Redis**: Decouples the "thinking" (AI generation) from the "doing" (Image gen/Email). If the image API hangs for 30 seconds, the main scheduler proceeds to the next step immediately.
*   **Gemini 2.5 Flash**: Chosen for its balance of speed, cost, and high context window, crucial for processing large amounts of news data.

<!-- docker-compose up --build -d -->
<!-- docker-compose logs -f -->