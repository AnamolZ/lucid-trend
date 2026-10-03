# LucidTrend Operational and User Guide

This guide explains how to install, configure, operate, and interact with the LucidTrend system. It covers environment provisioning, API key acquisition, manual API testing with Postman and cURL, and full usage of the interactive command-line interface (CLI).

---

## 1. Prerequisites and Installation

LucidTrend can be deployed either via **Docker Compose** (recommended for production daemon deployment) or run **natively with Python and `uv`**.

### System Requirements
* Python 3.11+
* Git
* `uv` package manager (or standard `pip` / `venv`)
* Docker & Docker Compose (optional, for containerized execution)
* Redis (used for Celery task queuing; optional in lightweight local CLI mode)

### Cloning the Repository
```bash
git clone https://github.com/AnamolZ/lucid-trend.git
cd lucid-trend
```

### Virtual Environment Setup (Native)
Using `uv`:
```bash
# Create and activate virtual environment
uv venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install all dependencies
uv sync
```

---

## 2. Environment Configuration (`.env`)

Copy the template file to create your local `.env`:
```bash
cp .env.example .env
```

Open `.env` in your text editor. Here is the full configuration schema:

```env
# 1. MongoDB Database Settings
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?appName=Cluster0
DATABASE_NAME=portfolio_db
COLLECTION_NAME=posts

# 2. Google Gemini API Keys (comma-separated keys supported for failover)
GOOGLE_API_KEY=your_gemini_key_1,your_gemini_key_2
GEMINI_MODEL=gemini-3.7-flash

# 3. SMTP Newsletter Settings
SMTP_SERVER=smtp-relay.brevo.com
SMTP_USER=your_smtp_login@smtp-brevo.com
SMTP_PASSWORD=your_smtp_relay_key

# 4. Celery Task Broker (Redis)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 5. Hugging Face Image Generation Keys (comma-separated for 4-key failover)
HUGGING_FACE_TOKENS=hf_key_1,hf_key_2,hf_key_3,hf_key_4
HUGGING_FACE_TOKEN=hf_key_1

# 6. Management API & CLI Security
API_SECRET_KEY=lt_sec_your_secret_api_key_here
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_URL=http://localhost:8000
```

---

## 3. Where and How to Obtain API Credentials

### A. Google Gemini API Key
* **Cost**: Free tier available.
* **Portal**: [Google AI Studio](https://aistudio.google.com/)
* **Steps**:
  1. Sign in with your Google account.
  2. Click **Get API key** in the top navigation.
  3. Create a new key in a free project.
  4. Paste the string into `GOOGLE_API_KEY`. You can supply multiple keys separated by commas for automated failover.

### B. Hugging Face Access Tokens (FLUX.1-schnell)
* **Cost**: Free inference tier.
* **Portal**: [Hugging Face Settings > Tokens](https://huggingface.co/settings/tokens)
* **Steps**:
  1. Create a free Hugging Face account and navigate to **Settings > Access Tokens**.
  2. Click **Create new token**.
  3. Select token type **Read** (or grant **Make calls to the serverless Inference API** under Fine-grained permissions).
  4. Repeat to create up to 4 keys for rotation.
  5. Add them as a comma-separated list under `HUGGING_FACE_TOKENS`.

### C. Brevo SMTP Relay (Newsletter Dispatch)
* **Cost**: Free tier includes 300 emails per day.
* **Portal**: [Brevo (formerly Sendinblue)](https://www.brevo.com/)
* **Steps**:
  1. Create a free account and navigate to **Transactional > Settings**.
  2. Under **SMTP Configuration**, copy your SMTP Server (`smtp-relay.brevo.com`), Port (`587`), and Login.
  3. Generate an SMTP Key and paste it into `SMTP_PASSWORD`.

### D. MongoDB Atlas Cluster
* **Cost**: Free M0 Sandbox cluster.
* **Portal**: [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
* **Steps**:
  1. Create a free Shared Cluster.
  2. Under **Database Access**, create a user with read/write permissions.
  3. Under **Network Access**, whitelist your IP address (or `0.0.0.0/0` for cloud deployment).
  4. Click **Connect > Drivers** and copy your connection string into `MONGO_URI`.

---

## 4. Running the System

### Option 1: Native Execution (Terminal)
To start the autonomous daemon (scheduled runs at 05:00 and 17:00 Asia/Kathmandu, hourly temp directory cleaner, and FastAPI management server):
```bash
python main.py
```

To run an immediate single pipeline cycle on startup while keeping the API server active:
```bash
python main.py --now
```

To run exclusively the API server (for CLI interactions without scheduled scouting):
```bash
python main.py --api-only
```

### Option 2: Docker Compose (Full Stack)
The compose setup starts Redis, Celery workers, and the application scheduler with the management API exposed on port `8000`:
```bash
# Build and run containers in detached mode
docker-compose up -d --build

# View application logs
docker-compose logs -f app

# Stop containers
docker-compose down
```

---

## 5. Management REST API Documentation

The system includes a secure FastAPI management server listening on port `8000`. All requests must supply authentication via the `X-API-Key` header or `Authorization: Bearer <key>`.

### Authentication Header
```http
X-API-Key: lt_sec_your_secret_api_key_here
```

---

### Endpoint 1: Health & System Status
* **Method**: `GET`
* **Path**: `/api/v1/status`
* **Description**: Returns active model, failover key index, Hugging Face key count, and temp directory status.

#### cURL Example
```bash
curl -X GET http://localhost:8000/api/v1/status \
  -H "X-API-Key: lt_sec_your_secret_api_key_here"
```

#### Response (200 OK)
```json
{
  "status": "online",
  "service": "LucidTrend Autonomous System",
  "active_gemini_model": "gemini-3.7-flash",
  "active_gemini_key": "AQ.Ab8...9ISw",
  "huggingface_keys_count": 4,
  "huggingface_active_key_index": 1,
  "temp_files_count": 0,
  "timestamp": "2026-10-03 15:25:16"
}
```

---

### Endpoint 2: Modular Pipeline Execution
* **Method**: `POST`
* **Path**: `/api/v1/pipeline/run`
* **Description**: Triggers news generation with granular module toggles (`with_db`, `with_email`, `with_image`).

#### Request Body
```json
{
  "with_db": true,
  "with_email": false,
  "with_image": true,
  "research_prompt": "Identify the top 2 breakthrough technology developments from the past 24 hours."
}
```

#### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "X-API-Key: lt_sec_your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"with_db": false, "with_email": false, "with_image": false}'
```

---

### Endpoint 3: On-Demand Image Generation
* **Method**: `POST`
* **Path**: `/api/v1/image/generate`
* **Description**: Generates an image using FLUX.1 with 4-key failover and 5-minute retry ladder. Saves to server `temp/` folder and returns binary download URL.

#### Request Body
```json
{
  "prompt": "Cinematic digital illustration of quantum server rack in 16:9 aspect ratio",
  "title": "Quantum Computing Breakthroughs"
}
```

#### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/image/generate \
  -H "X-API-Key: lt_sec_your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"title": "Autonomous Agentic AI"}'
```

#### Response (200 OK)
```json
{
  "success": true,
  "prompt_used": "Cinematic digital illustration of Autonomous Agentic AI, futuristic, high tech aesthetic, clean 16:9 composition",
  "filename": "flux_1791020460_05255d.png",
  "temp_file_path": "/app/temp/flux_1791020460_05255d.png",
  "download_url": "/temp/flux_1791020460_05255d.png",
  "size_bytes": 1386724
}
```

---

### Endpoint 4: Temporary Directory Cleanup
* **Method**: `POST`
* **Path**: `/api/v1/cleanup/temp`
* **Description**: Forces an immediate purge of files in the temporary directory.

#### cURL Example
```bash
curl -X POST http://localhost:8000/api/v1/cleanup/temp \
  -H "X-API-Key: lt_sec_your_secret_api_key_here"
```

---

## 6. Testing via Postman

1. Open Postman and create a new request collection named **LucidTrend Management**.
2. Under the collection's **Authorization** tab:
   * Type: **API Key**
   * Key: `X-API-Key`
   * Value: Your `API_SECRET_KEY` string
   * Add to: **Header**
3. Create requests for each endpoint above (`GET /api/v1/status`, `POST /api/v1/pipeline/run`, etc.).
4. Send requests against `http://localhost:8000`.

---

## 7. Command-Line Interface (`cli.py`)

The CLI provides an interactive client that communicates directly with the running server.

> **Important**: The CLI enforces an active server connection. If the LucidTrend server is not running or credentials do not match, the CLI will cleanly refuse execution.

### Checking Server Connectivity
```bash
python cli.py status
```

### Selective Pipeline Execution
Generate news only without touching the database, sending emails, or waiting for images:
```bash
python cli.py pipeline --without email,db,image
```

Generate news and write to MongoDB, but skip email dispatch:
```bash
python cli.py pipeline --without email --with db,image
```

Specify a custom research query:
```bash
python cli.py pipeline --prompt "Focus specifically on breakthrough database engine releases in the last 24 hours"
```

### On-Demand Image Generation
Generate an image by providing a title (automatically builds a cinematic 16:9 prompt):
```bash
python cli.py generate-image --title "Autonomous Agentic AI"
```

Generate an image by providing a custom prompt:
```bash
python cli.py generate-image --prompt "A sleek server rack illuminated by soft neon blue and cyan lights, high-tech engineering aesthetic, 16:9"
```

Specify a custom local file output name:
```bash
python cli.py generate-image --title "Quantum Architecture" --output my_image.png
```

### Manual Temp Directory Cleanup
```bash
python cli.py cleanup-temp
```

### Overriding Server URL or Key via CLI
You can connect to a remote server or Docker host by passing `--server` and `--key`:
```bash
python cli.py --server http://192.168.1.100:8000 --key your_secret_key status
```
