# NLP Analytics Chatbot API Engine

An intelligent, secure, and production-ready **Natural Language to SQL (NL-to-SQL)** API Engine designed for Surveillance, Facial Recognition (FRS), Detection, and Alert Web Dashboards.

---

## 🚀 Key Capabilities

1. **Configurable Database Connectivity**:
   - Supports **MySQL / MariaDB**, **PostgreSQL**, and **SQLite**.
   - Automatic schema discovery: introspects tables, columns, data types, foreign keys, and distinct values dynamically.
   - Built-in sample detection & alert database for zero-config testing.
2. **Safe Read-Only Guardrails**:
   - Strict AST parsing via `sqlglot` ensures **SELECT-only** execution.
   - Blocks all `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and multi-statement attacks.
   - Automatic row limiting (`LIMIT 100`) to prevent server memory exhaustion.
3. **Conversational Synthesis & Visualization**:
   - Converts raw database rows into crisp human answers with markdown tables.
   - Automatic **chart configuration generator** (Bar / Doughnut charts for categorical and breakdown metrics).
4. **Developer & Web Team Friendly**:
   - Fast, async REST API built with **FastAPI**.
   - CORS enabled out-of-the-box for any frontend origin.
   - Server-Sent Events (SSE) streaming endpoint (`/api/chat/stream`) for live typing effect.
   - Interactive Swagger API docs (`/docs`) and built-in Dark Mode Web Dashboard UI (`/demo`).

---

## 📁 Project Architecture

```
e:\API_Engines\NLP_ENGINE\
├── config.py                       # Environment and server settings
├── main.py                         # FastAPI application & routes
├── requirements.txt                # Python dependencies
├── .env.example                    # Sample configuration
├── .env                            # Active environment file
├── WEBTEAM_INTEGRATION_GUIDE.md    # Frontend integration guide for web team
├── database/
│   ├── connector.py                # Multi-tenant connection pool manager & query runner
│   ├── tenant_manager.py           # API Key registry mapped to client databases
│   ├── schema_inspector.py         # Dynamic schema introspection & prompt formatter
│   └── sample_db.py                # Surveillance/Alerts demo database generator
├── services/
│   ├── llm_client.py               # Multi-provider LLM client (OpenAI, Gemini, Ollama)
│   ├── sql_validator.py            # AST security parser & guardrails
│   ├── sql_generator.py            # Natural Language to SQL translator
│   └── chat_engine.py              # Orchestration, synthesis & chart detection
└── static/
    ├── widget.js                   # Drop-in floating chatbot widget for web dashboards
    ├── index.html                  # Interactive test dashboard
    ├── style.css                   # Glassmorphism dark-mode styling
    └── app.js                      # Client logic & Chart.js rendering
```

---

## ⚙️ Configuration (.env)

Edit the `.env` file to configure your target database and LLM provider:

```ini
# Server Settings
HOST=0.0.0.0
PORT=8000
DEBUG=True
CORS_ORIGINS=*

# Target Database Connection
# MySQL Example:
# DATABASE_URL=mysql+pymysql://user:password@localhost:3306/detection_db

# PostgreSQL Example:
# DATABASE_URL=postgresql://user:password@localhost:5432/detection_db

# SQLite Default:
DATABASE_URL=sqlite:///./data/detections.db

# LLM Provider (OpenAI, Gemini, Ollama, DeepSeek)
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

---

## 🏃 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API Engine
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- Open **http://localhost:8000** to test queries directly in the interactive UI.
- Open **http://localhost:8000/docs** to view the full OpenAPI / Swagger documentation.
