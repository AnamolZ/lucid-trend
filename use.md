# LucidTrend Operations, CLI & API Reference Guide

> **Note**: This file is mirrored at [docs/use.md](docs/use.md).

Comprehensive user guide for the **LucidTrend Autonomous Tech Intelligence Engine**. This document provides detailed, step-by-step instructions for operating the system, using all CLI subcommands, interacting with all REST API endpoints via cURL and Postman, managing security credentials, and container operations.

---

## Table of Contents
1. [System Architecture & Overview](#1-system-architecture--overview)
2. [Security & Authentication Model](#2-security--authentication-model)
3. [Environment Configuration (`.env`)](#3-environment-configuration-env)
4. [Interactive CLI Guide (`cli.py`)](#4-interactive-cli-guide-clipy)
   - [CLI Authentication Flow](#cli-authentication-flow)
   - [`status` — System Health & Active Schedule](#status--system-health--active-schedule)
   - [`pipeline` — Modular Post Generation & Schedule Reshuffle](#pipeline--modular-post-generation--schedule-reshuffle)
   - [`reshuffle` — Live 12-Hour Schedule Reshuffle](#reshuffle--live-12-hour-schedule-reshuffle)
   - [`rotate-key` / `regenerate-key` — Master-Password Key Rotation](#rotate-key--regenerate-key--master-password-key-rotation)
   - [`generate-image` — Standalone FLUX.1 Visual Generation](#generate-image--standalone-flux1-visual-generation)
   - [`cleanup-temp` — Purge Server Temporary Assets](#cleanup-temp--purge-server-temporary-assets)
5. [REST API Endpoint Reference](#5-rest-api-endpoint-reference)
   - [Authentication Headers](#authentication-headers)
   - [`GET /api/v1/status`](#get-apiv1status)
   - [`POST /api/v1/pipeline/run`](#post-apiv1pipelinerun)
   - [`POST /api/v1/schedule/reshuffle`](#post-apiv1schedulereshuffle)
   - [`POST /api/v1/image/generate`](#post-apiv1imagegenerate)
   - [`GET /temp/{filename}`](#get-tempfilename)
   - [`POST /api/v1/cleanup/temp`](#post-apiv1cleanuptemp)
   - [`POST /api/v1/auth/rotate-key`](#post-apiv1authrotate-key)
6. [Testing with Postman](#6-testing-with-postman)
   - [Postman Environment Setup](#postman-environment-setup)
   - [Configuring Authentication](#configuring-authentication)
   - [Step-by-Step Request Setup](#step-by-step-request-setup)
7. [Docker & Container Operations](#7-docker--container-operations)

---

## 1. System Architecture & Overview

LucidTrend operates with two complementary execution layers:

1. **Continuous Daemon (`main.py`)**:
   - **Autonomous 12-Hour Schedule**: Triggers full intelligence scouting and publishing twice daily with an exact 12-hour separation (e.g., `05:00` and `17:00` Asia/Kathmandu). Supports live random reshuffling.
   - **Celery & Redis Worker**: Handles asynchronous image generation with a 4-key Hugging Face failover ladder.
   - **Temp Cleaner**: Sweeps and removes generated temporary assets every 60 minutes.
   - **FastAPI Management Server**: Exposes authenticated REST endpoints on port `8000`.

2. **Operator Management Interface (`cli.py` & REST API)**:
   - On-demand execution with granular feature toggles (`--without email,db,image`).
   - Dynamic schedule reshuffling on demand or after forced runs.
   - Secure API key rotation protected by a master password.

---

## 2. Security & Authentication Model

Security in LucidTrend is enforced across two distinct credentials:

| Credential | Variable Name | Default / Example | Purpose |
| :--- | :--- | :--- | :--- |
| **API Secret Key** | `API_SECRET_KEY` | `lt_sec_...` | Authenticates all management endpoints and CLI operations. |
| **Master Password** | `MASTER_PASSWORD` | `lucidtrend1379` | Grants administrative rights to rotate and generate a new API Secret Key. |

### How Key Verification Works:
- Every protected endpoint requires either an `X-API-Key: <key>` header or `Authorization: Bearer <key>`.
- Any invalid or missing key returns `HTTP 401 Unauthorized`.
- The server logs a `[Security Alert]` recording the unauthorized client IP and masked key attempt.
- The CLI automatically refuses to execute commands if the server is offline or authentication fails.

### Immediate Old Key Revocation:
When an operator rotates the key using the **Master Password**, the old API key is **revoked immediately** in server memory and on disk. Any subsequent request presenting the old key will be rejected.

---

## 3. Environment Configuration (`.env`)

Create or update your `.env` file in the project root:

```env
# 1. MongoDB Database Settings
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?appName=Cluster0
DATABASE_NAME=portfolio_db
COLLECTION_NAME=posts

# 2. Google Gemini API Keys (comma-separated keys supported for failover)
GOOGLE_API_KEY=your_gemini_key_1,your_gemini_key_2
GEMINI_MODEL=gemini-2.5-flash

# 3. SMTP Newsletter Settings (Brevo / SendGrid / Postmark)
SMTP_SERVER=smtp-relay.brevo.com
SMTP_USER=your_smtp_login@smtp-brevo.com
SMTP_PASSWORD=your_smtp_relay_key

# 4. Celery Task Broker (Redis)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 5. Hugging Face Image Generation Keys (comma-separated for 4-key failover ladder)
HUGGING_FACE_TOKENS=hf_token_1,hf_token_2,hf_token_3,hf_token_4
HUGGING_FACE_TOKEN=hf_token_1

# 6. Management API & CLI Security
API_SECRET_KEY=lt_sec_9293a9b1edbc0db1cad7db0cb8b0eb20
MASTER_PASSWORD=lucidtrend1379
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_URL=http://localhost:8000
```

---

## 4. Interactive CLI Guide (`cli.py`)

The CLI connects directly to the running server (either running natively or inside Docker).

### CLI Authentication Flow
When executing any command (except `rotate-key`), the CLI checks for credentials:
1. **Interactive Prompt**: If `--key` is omitted, the CLI interactively prompts for your key with masked input:
   ```text
   🔑 Enter Server API Key:
   ```
2. **Automated Flag**: Pass `--key <API_SECRET_KEY>` directly in scripted environments.
3. **Piped Input**: Accepts piped stdin: `echo 'my_key' | uv run cli.py status`.

```
               [CLI Command Triggered]
                         |
                         v
            Does --key exist in args?
             /                      \
          (Yes)                    (No)
            |                        |
            v                        v
      Use Passed Key        Interactive Masked Prompt
            \                        /
             v                      v
          Send Request with X-API-Key Header
                         |
                         v
             Server Authentication Check
             /                         \
         (Valid)                    (Invalid)
            |                           |
            v                           v
      Execute Action            [HTTP 401 Unauthorized]
                              Print Access Denied Alert
```

---

### `status` — System Health & Active Schedule
Retrieves live health metrics, active AI model, key pool availability, and current daily schedule.

```bash
uv run cli.py status
```
*(or `python cli.py status --key <YOUR_KEY>`)*

#### Example Output:
```text
=================================================================
 LucidTrend Server Status: CONNECTED & ONLINE
=================================================================
  status                        : online
  service                       : LucidTrend Autonomous System
  active_gemini_model           : gemini-2.5-flash
  active_gemini_key             : AQ.Ab8...9ISw
  huggingface_keys_count        : 4
  huggingface_active_key_index  : 1
  temp_files_count              : 0
  scheduled_daily_runs          : 05:00, 17:00 Asia/Kathmandu (12h gap)
  schedule_interval             : 12 hours (2 runs per day)
  timestamp                     : 2026-10-03 16:59:56
=================================================================
```

---

### `pipeline` — Modular Post Generation & Schedule Reshuffle
Triggers an immediate research and post-synthesis pipeline.

> **Dynamic Reshuffle Feature**: Every time you force a pipeline run via CLI, the server automatically **reshuffles the daily schedule** to two new random times maintaining the **exact 12-hour gap**!

```bash
# Standard run (all modules enabled: DB, Email, Image queue)
uv run cli.py pipeline

# Dry run: Scout and extract articles without modifying database, sending emails, or queuing images
uv run cli.py pipeline --without email,db,image

# Database only: Write to MongoDB and queue images, skip newsletter dispatch
uv run cli.py pipeline --without email --with db,image

# Custom research prompt
uv run cli.py pipeline --prompt "Focus specifically on newly open-sourced multimodal AI models in the past 24 hours"
```

#### Example Output:
```text
=================================================================
 [SUCCESS] Pipeline Execution Completed
=================================================================
  - Articles Scouted  : 2
  - MongoDB Inserted  : True
  - Newsletter Sent   : True
  - Images Queued     : True
  - Schedule Reshuffle: Set to 08:34 and 20:34 Asia/Kathmandu (12h gap)
=================================================================
```

---

### `reshuffle` — Live 12-Hour Schedule Reshuffle
Generates two new randomized execution times separated by an exact 12-hour gap, registers them dynamically in the active scheduler, and clears the previous schedule without restarting the server.

```bash
uv run cli.py reshuffle
```

#### Example Output:
```text
=================================================================
 [SUCCESS] Daily Schedule Reshuffled on Server
=================================================================
  New Daily Run Times : 11:15, 23:15 Asia/Kathmandu
  Schedule Interval   : 12 hours (2 runs per day)
=================================================================
```

---

### `rotate-key` / `regenerate-key` — Master-Password Key Rotation
Regenerates the system API secret key using your master password (`lucidtrend1379`). The old key is **immediately invalidated**, and the new key is persisted to `.env`.

```bash
# Interactive prompt
uv run cli.py rotate-key

# Direct automated flag
uv run cli.py rotate-key --master-password lucidtrend1379
```

#### Example Output:
```text
🔑 Enter Master Password: 

=================================================================
 [SUCCESS] Server API Key Regenerated & Rotated
=================================================================
  Old Key Status : Inactivated & Revoked Immediately
  New API Key    : lt_sec_9293a9b1edbc0db1cad7db0cb8b0eb20
=================================================================
  Notice:
  - The previous API key has been revoked and will no longer work.
  - The new API key is active on the server and saved to .env.
  - Use this new API key for all subsequent CLI commands.
```

---

### `generate-image` — Standalone FLUX.1 Visual Generation
Generates a standalone image through the FLUX.1 model using the 4-key failover ladder. Saves the resulting file locally.

```bash
# Generate from an article title (automatically builds cinematic prompt)
uv run cli.py generate-image --title "Quantum Computing Breakthroughs in 2026"

# Generate with an explicit FLUX prompt
uv run cli.py generate-image --prompt "Cinematic digital illustration of futuristic robotics laboratory, 16:9 composition"

# Specify custom local output path
uv run cli.py generate-image --title "Autonomous Agentic AI" --output ./my_hero_image.png
```

---

### `cleanup-temp` — Purge Server Temporary Assets
Forces an immediate sweep and deletion of all files in the server's temporary cache directory.

```bash
uv run cli.py cleanup-temp
```

---

## 5. REST API Endpoint Reference

Base Server URL: `http://localhost:8000` (or `http://<server-ip>:8000`)

### Authentication Headers
For all endpoints except key rotation:
```http
X-API-Key: lt_sec_your_secret_api_key_here
```
*(Bearer token authentication is also supported: `Authorization: Bearer lt_sec_...`)*

---

### `GET /api/v1/status`
Returns real-time health metrics, active model status, key rotation indexes, and active schedule.

* **Headers**: `X-API-Key: <API_KEY>`
* **cURL Command**:
  ```bash
  curl -X GET http://localhost:8000/api/v1/status \
    -H "X-API-Key: lt_sec_your_api_key_here"
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "status": "online",
    "service": "LucidTrend Autonomous System",
    "active_gemini_model": "gemini-2.5-flash",
    "active_gemini_key": "AQ.Ab8...9ISw",
    "huggingface_keys_count": 4,
    "huggingface_active_key_index": 1,
    "temp_files_count": 0,
    "scheduled_daily_runs": ["05:00", "17:00"],
    "schedule_interval": "12 hours (2 runs per day)",
    "timestamp": "2026-10-03 16:59:56"
  }
  ```

---

### `POST /api/v1/pipeline/run`
Executes on-demand intelligence scouting and synthesis, with modular flags and live 12-hour schedule reshuffling.

* **Headers**:
  - `X-API-Key: <API_KEY>`
  - `Content-Type: application/json`
* **Request Body Schema**:
  ```json
  {
    "with_db": true,
    "with_email": true,
    "with_image": true,
    "research_prompt": "Optional custom Gemini research prompt"
  }
  ```
* **cURL Command**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/pipeline/run \
    -H "X-API-Key: lt_sec_your_api_key_here" \
    -H "Content-Type: application/json" \
    -d '{
      "with_db": true,
      "with_email": false,
      "with_image": true
    }'
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "success": true,
    "articles_count": 2,
    "articles": [
      {
        "id": "post_1727958000_1",
        "title": "Quantum Neural Processing Accelerators",
        "category": "Hardware & AI",
        "description": "Analysis of newly benchmarked quantum accelerator chipsets...",
        "image_prompt": "Cinematic visual of quantum accelerator microchip..."
      }
    ],
    "database_inserted": true,
    "email_dispatched": false,
    "images_queued": true,
    "reshuffled_schedule": ["09:42", "21:42"]
  }
  ```

---

### `POST /api/v1/schedule/reshuffle`
Reshuffles the 2-times-daily scheduler to randomized times maintaining an exact 12-hour gap.

* **Headers**: `X-API-Key: <API_KEY>`
* **cURL Command**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/schedule/reshuffle \
    -H "X-API-Key: lt_sec_your_api_key_here"
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "success": true,
    "message": "Daily pipeline schedule reshuffled successfully.",
    "scheduled_daily_runs": ["10:52", "22:52"],
    "schedule_interval": "12 hours (2 runs per day)"
  }
  ```

---

### `POST /api/v1/image/generate`
Generates an isolated image via FLUX.1 with the 4-key failover ladder.

* **Headers**:
  - `X-API-Key: <API_KEY>`
  - `Content-Type: application/json`
* **Request Body Schema**:
  ```json
  {
    "prompt": "Cinematic digital illustration of quantum server rack in 16:9 aspect ratio",
    "title": "Quantum Server Infrastructure"
  }
  ```
* **cURL Command**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/image/generate \
    -H "X-API-Key: lt_sec_your_api_key_here" \
    -H "Content-Type: application/json" \
    -d '{
      "prompt": "Futuristic neural data visualization, clean 16:9 composition"
    }'
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "success": true,
    "prompt_used": "Futuristic neural data visualization, clean 16:9 composition",
    "filename": "flux_1727958100_a3f81c.png",
    "temp_file_path": "/app/temp/flux_1727958100_a3f81c.png",
    "download_url": "/temp/flux_1727958100_a3f81c.png",
    "size_bytes": 1420850
  }
  ```

---

### `GET /temp/{filename}`
Static download route for downloading generated images directly from the server cache.

* **cURL Command**:
  ```bash
  curl -O http://localhost:8000/temp/flux_1727958100_a3f81c.png
  ```

---

### `POST /api/v1/cleanup/temp`
Purges all cached image files from the server's temporary directory.

* **Headers**: `X-API-Key: <API_KEY>`
* **cURL Command**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/cleanup/temp \
    -H "X-API-Key: lt_sec_your_api_key_here"
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "success": true,
    "files_purged": 3
  }
  ```

---

### `POST /api/v1/auth/rotate-key`
Regenerates the system API secret key using master password authentication. **Immediately revokes the previous API key.**

* **Authentication**: Requires `master_password` in the JSON body. Does **not** require the old API key.
* **Request Body Schema**:
  ```json
  {
    "master_password": "lucidtrend1379"
  }
  ```
* **cURL Command**:
  ```bash
  curl -X POST http://localhost:8000/api/v1/auth/rotate-key \
    -H "Content-Type: application/json" \
    -d '{
      "master_password": "lucidtrend1379"
    }'
  ```
* **Sample Response (200 OK)**:
  ```json
  {
    "success": true,
    "new_api_key": "lt_sec_9293a9b1edbc0db1cad7db0cb8b0eb20",
    "message": "API key successfully rotated and old key invalidated."
  }
  ```
* **Failure Response (403 Forbidden)**:
  ```json
  {
    "detail": "Forbidden: Invalid master password."
  }
  ```

---

## 6. Testing with Postman

### Postman Environment Setup
1. In Postman, open **Environments** $\to$ Click **+** (New Environment) $\to$ Name it `LucidTrend Local`.
2. Add the following environment variables:
   - `baseUrl`: `http://localhost:8000`
   - `apiKey`: `lt_sec_9293a9b1edbc0db1cad7db0cb8b0eb20`
   - `masterPassword`: `lucidtrend1379`
3. Click **Save** and select `LucidTrend Local` in the active environment dropdown (top right).

---

### Configuring Authentication
1. Create a new Collection named **LucidTrend Intelligence API**.
2. Click on the collection $\to$ Select the **Authorization** tab:
   - **Type**: `API Key`
   - **Key**: `X-API-Key`
   - **Value**: `{{apiKey}}`
   - **Add to**: `Header`
3. Click **Save**. All child requests in this collection will automatically inherit this authentication header.

---

### Step-by-Step Request Setup

#### 1. System Health (`GET /api/v1/status`)
- **Method**: `GET`
- **URL**: `{{baseUrl}}/api/v1/status`
- **Authorization**: `Inherit auth from parent`
- **Action**: Click **Send**. Verify response status `200 OK` and active daily schedule.

#### 2. Run Pipeline (`POST /api/v1/pipeline/run`)
- **Method**: `POST`
- **URL**: `{{baseUrl}}/api/v1/pipeline/run`
- **Headers**: `Content-Type: application/json`
- **Body** (`raw` $\to$ `JSON`):
  ```json
  {
    "with_db": true,
    "with_email": false,
    "with_image": true,
    "research_prompt": "Latest breakthrough in semiconductor chip architectures"
  }
  ```
- **Action**: Click **Send**. Note the `reshuffled_schedule` in the response.

#### 3. Reshuffle Schedule (`POST /api/v1/schedule/reshuffle`)
- **Method**: `POST`
- **URL**: `{{baseUrl}}/api/v1/schedule/reshuffle`
- **Action**: Click **Send**. Verifies that new times maintain the 12-hour gap.

#### 4. Generate Image (`POST /api/v1/image/generate`)
- **Method**: `POST`
- **URL**: `{{baseUrl}}/api/v1/image/generate`
- **Headers**: `Content-Type: application/json`
- **Body** (`raw` $\to$ `JSON`):
  ```json
  {
    "prompt": "Cinematic 3D render of holographic neural network interface, 16:9"
  }
  ```
- **Action**: Click **Send**. Copy the `download_url` from the response.

#### 5. Purge Temp Cache (`POST /api/v1/cleanup/temp`)
- **Method**: `POST`
- **URL**: `{{baseUrl}}/api/v1/cleanup/temp`
- **Action**: Click **Send**. Verifies all temp image files are deleted.

#### 6. Rotate Key via Master Password (`POST /api/v1/auth/rotate-key`)
- **Method**: `POST`
- **URL**: `{{baseUrl}}/api/v1/auth/rotate-key`
- **Authorization**: Change to `No Auth` (does not require the current API key).
- **Headers**: `Content-Type: application/json`
- **Body** (`raw` $\to$ `JSON`):
  ```json
  {
    "master_password": "{{masterPassword}}"
  }
  ```
- **Action**: Click **Send**. Copy the returned `new_api_key` and update your `apiKey` environment variable in Postman.
- **Verification**: If you send another request using the old key, it will immediately return `401 Unauthorized`.

---

## 7. Docker & Container Operations

### Starting the Stack
```bash
# Start all containers in the background
docker-compose up -d

# Check running status
docker-compose ps
```

### Viewing Real-Time Logs
```bash
# View app and scheduler logs
docker-compose logs -f app

# View Celery image worker logs
docker-compose logs -f worker
```

### Running CLI Commands Inside Docker
You can execute CLI commands directly within the running container without installing Python locally:

```bash
# Interactive mode
docker exec -it lucid-trend-app-1 python cli.py status

# With direct API key flag
docker exec -it lucid-trend-app-1 python cli.py status --key <YOUR_API_KEY>

# Reshuffle schedule
docker exec -it lucid-trend-app-1 python cli.py reshuffle --key <YOUR_API_KEY>

# Rotate API key
docker exec -it lucid-trend-app-1 python cli.py rotate-key --master-password lucidtrend1379
```

### Restarting the Stack
```bash
# Restart after modifying configuration
docker-compose restart app

# Complete clean rebuild and restart
docker-compose down
docker-compose up -d --build
```
