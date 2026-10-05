from __future__ import annotations
import json
import time
import re
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Security, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from pathlib import Path

from config import settings
from database.connector import db_connector
from database.schema_inspector import schema_inspector
from database.tenant_manager import tenant_manager, TenantConfig
from services.chat_engine import chat_engine
from services.sql_validator import SQLValidator
from services.llm_client import llm_client

app = FastAPI(
    title="NLP Analytics & Alert Chatbot API Engine",
    description="Multi-tenant Conversational Query API for Surveillance, Detections, and Alert Dashboards",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------
# CORS Configuration (Ensures web team can call from any dashboard origin)
# ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# Security & Multi-Tenant Dependency
# ---------------------------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def get_current_tenant(
    request: Request,
    header_key: Optional[str] = Security(api_key_header),
    param_key: Optional[str] = Query(None, alias="api_key"),
) -> TenantConfig:
    """
    Extracts and validates the client API Key from:
    1. 'X-API-Key' header
    2. 'Authorization: Bearer <key>' header
    3. '?api_key=' query parameter
    Resolves the key to the client's mapped database connection.
    """
    key = header_key or param_key

    # Check Authorization: Bearer <key>
    if not key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            key = auth_header.replace("Bearer ", "", 1).strip()

    # Dynamic Database URL override from header or query parameter
    custom_db_url = request.headers.get("X-Database-URL") or request.query_params.get("database_url")
    if custom_db_url and custom_db_url.strip():
        client_name = request.headers.get("X-Client-Name", "Dynamic Client Database")
        return TenantConfig(
            api_key=key or "custom_db_user",
            client_name=client_name,
            database_url=custom_db_url.strip(),
            max_rows=settings.MAX_ROW_LIMIT,
            enabled=True,
            description="Dynamic database provided via X-Database-URL header"
        )

    if key:
        tenant = tenant_manager.get_tenant(key)
        if tenant:
            return tenant
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or revoked API Key: '{key}'. Please verify your dashboard configuration.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Allow fallback for built-in demo UI or when REQUIRE_API_KEY is disabled
    referer = request.headers.get("Referer", "")
    is_demo_request = (
        request.headers.get("X-Demo-UI") == "true" 
        or "/demo" in referer 
        or referer.rstrip("/").endswith(f":{settings.PORT}")
    )
    if is_demo_request or not settings.REQUIRE_API_KEY:
        default_tenant = tenant_manager.get_default_tenant()
        if default_tenant:
            return default_tenant

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing API Key. Provide your client API key in the 'X-API-Key' header or '?api_key=' parameter.",
        headers={"WWW-Authenticate": "ApiKey"},
    )

def require_admin(
    admin_key: Optional[str] = Security(admin_key_header),
    api_key: Optional[str] = Security(api_key_header),
) -> bool:
    """Verifies admin authorization for API key management endpoints."""
    provided_key = admin_key or api_key
    if provided_key and provided_key == settings.ADMIN_API_KEY:
        return True
    # If in DEBUG mode and calling without keys, allow for local dev
    if settings.DEBUG and not provided_key:
        return True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required. Provide 'X-Admin-Key' header."
    )

# ---------------------------------------------------------------------
# Pydantic Request & Response Models
# ---------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="User's natural language question", example="How many critical alerts occurred today?")
    session_id: Optional[str] = Field(None, description="Optional session or conversation ID")

class ChatResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    data: List[Dict[str, Any]] = []
    columns: List[str] = []
    row_count: int = 0
    execution_time_ms: float = 0.0
    chart_config: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    client_name: Optional[str] = None

class RawQueryRequest(BaseModel):
    query: str = Field(..., description="Read-only SQL query to execute", example="SELECT * FROM alerts LIMIT 10")

class RawQueryResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    sanitized_sql: str
    client_name: Optional[str] = None

class CreateTenantRequest(BaseModel):
    client_name: str = Field(..., example="Bothra Surveillance Dashboard", description="Client or Dashboard name")
    database_url: str = Field(..., example="mysql+pymysql://root:pass@localhost:3306/bothera_db", description="Target database connection string")
    api_key: Optional[str] = Field(None, example="nlp_live_bothra_123", description="Optional custom key (auto-generated if omitted)")
    max_rows: Optional[int] = Field(100, example=100, description="Max rows returned per query")
    description: Optional[str] = Field("", example="Detections & alerts database")

class DatabaseConnectRequest(BaseModel):
    url: Optional[str] = Field(None, description="Complete SQLAlchemy URL (e.g. mysql+pymysql://user:pass@host:3306/db)")
    db_type: Optional[str] = Field("mysql", description="mysql, postgresql, or sqlite")
    host: Optional[str] = "localhost"
    port: Optional[int] = 3306
    user: Optional[str] = "root"
    password: Optional[str] = ""
    db_name: Optional[str] = "detection_db"

class LLMConfigRequest(BaseModel):
    api_key: str = Field(..., description="API Key for OpenAI, Gemini, or other provider")
    base_url: Optional[str] = Field("https://api.openai.com/v1", description="API Base URL (use http://localhost:11434/v1 for Ollama)")
    model: Optional[str] = Field("gpt-4o-mini", description="Model name (e.g. gpt-4o-mini, gemini-1.5-flash, llama3:8b)")

# ---------------------------------------------------------------------
# API Routes: Chatbot & Queries (Secured by Client API Key)
# ---------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse, tags=["Chatbot"])
@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chatbot"])
def chat(request: ChatRequest, tenant: TenantConfig = Depends(get_current_tenant)):
    """
    Main Chatbot endpoint for Web Dashboard.
    Translates user question into safe SQL, executes it on the database mapped to the API key,
    and returns synthesized answer + data rows + chart recommendation.
    """
    result = chat_engine.process_query(
        user_question=request.message,
        db_url=tenant.database_url,
        max_rows=tenant.max_rows,
    )
    result["session_id"] = request.session_id
    result["client_name"] = tenant.client_name
    return result

@app.post("/api/chat/stream", tags=["Chatbot"])
@app.post("/api/v1/chat/stream", tags=["Chatbot"])
def chat_stream(request: ChatRequest, tenant: TenantConfig = Depends(get_current_tenant)):
    """
    Server-Sent Events (SSE) streaming endpoint for live typewriter effect in web dashboard.
    Streams JSON events: 'meta' (SQL & chart info), 'token' (answer tokens), and 'done'.
    """
    def event_generator():
        result = chat_engine.process_query(
            user_question=request.message,
            db_url=tenant.database_url,
            max_rows=tenant.max_rows,
        )
        meta = {
            "sql_query": result["sql_query"],
            "columns": result["columns"],
            "row_count": result["row_count"],
            "execution_time_ms": result["execution_time_ms"],
            "chart_config": result["chart_config"],
            "data": result["data"][:25],
            "client_name": tenant.client_name,
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"

        answer = result["answer"]
        chunk_size = 8
        for i in range(0, len(answer), chunk_size):
            chunk = answer[i:i + chunk_size]
            yield f"event: token\ndata: {json.dumps({'chunk': chunk})}\n\n"
            time.sleep(0.015)

        yield f"event: done\ndata: {json.dumps({'status': 'finished'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/query/raw", response_model=RawQueryResponse, tags=["Database"])
@app.post("/api/v1/query/raw", response_model=RawQueryResponse, tags=["Database"])
def execute_raw_sql(request: RawQueryRequest, tenant: TenantConfig = Depends(get_current_tenant)):
    """
    Executes a direct read-only SQL query against the client's database with AST security validation.
    Enforces SELECT-only and row limits.
    """
    is_valid, sanitized_sql, error_msg = SQLValidator.validate_and_sanitize(request.query)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security/Validation Error: {error_msg}"
        )
    try:
        rows, columns, duration_ms = db_connector.execute_query(sanitized_sql, url=tenant.database_url)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": duration_ms,
            "sanitized_sql": sanitized_sql,
            "client_name": tenant.client_name,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database execution error: {str(e)}"
        )


@app.get("/api/database/schema", tags=["Database"])
@app.get("/api/v1/database/schema", tags=["Database"])
def get_database_schema(tenant: TenantConfig = Depends(get_current_tenant)):
    """Returns the introspected database schema for the client's mapped database."""
    return schema_inspector.get_schema_dict(url=tenant.database_url)

@app.post("/api/database/connect", tags=["Database"])
def connect_database(req: DatabaseConnectRequest):
    """
    Dynamically switches or updates the active database connection at runtime.
    Validates live connection, re-introspects schema, synchronizes default client tenant,
    and updates .env so the changes persist.
    """
    if req.url and req.url.strip():
        target_url = req.url.strip()
    else:
        db_type = (req.db_type or "mysql").lower()
        if db_type in ("mysql", "mariadb"):
            pwd = f":{req.password}" if req.password else ""
            target_url = f"mysql+pymysql://{req.user}{pwd}@{req.host}:{req.port}/{req.db_name}"
        elif db_type in ("postgres", "postgresql"):
            pwd = f":{req.password}" if req.password else ""
            target_url = f"postgresql://{req.user}{pwd}@{req.host}:{req.port}/{req.db_name}"
        elif db_type == "sqlite":
            target_url = f"sqlite:///./data/{req.db_name}.db"
        else:
            target_url = f"mysql+pymysql://{req.user}@{req.host}:{req.port}/{req.db_name}"

    # Verify and switch database
    success, err = db_connector.switch_database(target_url)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {err}"
        )

        

    # Invalidate schema cache & introspect fresh tables
    schema_inspector.refresh(target_url)
    schema = schema_inspector.get_schema_dict(target_url)

    # Update default tenant mapping in tenants.json
    default_tenant = tenant_manager.get_default_tenant()
    if default_tenant:
        tenant_manager.register_tenant(
            client_name=default_tenant.client_name,
            database_url=target_url,
            api_key=default_tenant.api_key,
            max_rows=default_tenant.max_rows,
            description="Updated via Web UI Switch Database",
        )

    # Persist to .env
    try:
        env_path = Path(__file__).resolve().parent / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            if re.search(r"^DATABASE_URL=.*$", content, flags=re.MULTILINE):
                new_content = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={target_url}", content, flags=re.MULTILINE)
            else:
                new_content = content + f"\nDATABASE_URL={target_url}\n"
            env_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        print(f"[Warning] Failed to write updated DATABASE_URL to .env: {e}")

    return {
        "status": "connected",
        "database_url_masked": _mask_url(target_url),
        "dialect": db_connector.get_dialect(target_url),
        "tables_found": schema.get("table_count", 0),
        "tables": [t["table_name"] for t in schema.get("tables", [])],
    }

@app.get("/api/auth/verify", tags=["Authentication"])
@app.get("/api/v1/auth/verify", tags=["Authentication"])
def verify_api_key(tenant: TenantConfig = Depends(get_current_tenant)):
    """Verifies that an API Key is valid and returns its client profile and database connection status."""
    db_ok, db_err = db_connector.test_connection(tenant.database_url)
    dialect = db_connector.get_dialect(tenant.database_url)
    return {
        "status": "valid",
        "api_key_masked": tenant.api_key[:6] + "..." + tenant.api_key[-4:] if len(tenant.api_key) > 10 else "****",
        "client_name": tenant.client_name,
        "database": {
            "connected": db_ok,
            "dialect": dialect,
            "error": db_err,
        },
    }

# ---------------------------------------------------------------------
# Admin API: Client API Key & Database Management
# ---------------------------------------------------------------------
@app.get("/api/admin/keys", tags=["Admin"])
def list_api_keys(_: bool = Depends(require_admin)):
    """Lists all registered client API keys and their target databases."""
    tenants = tenant_manager.list_tenants()
    return [
        {
            "api_key": t.api_key,
            "client_name": t.client_name,
            "database_url_masked": _mask_url(t.database_url),
            "max_rows": t.max_rows,
            "enabled": t.enabled,
            "description": t.description,
            "created_at": t.created_at,
        }
        for t in tenants
    ]

@app.post("/api/admin/keys", tags=["Admin"])
def create_api_key(req: CreateTenantRequest, _: bool = Depends(require_admin)):
    """Registers a new client API key and tests the connection to their database."""
    # Test target connection before saving
    db_ok, db_err = db_connector.test_connection(req.database_url)
    if not db_ok:
        # We can still register or warn
        print(f"[Warning] Target database test failed for '{req.client_name}': {db_err}")

    tenant = tenant_manager.register_tenant(
        client_name=req.client_name,
        database_url=req.database_url,
        api_key=req.api_key,
        max_rows=req.max_rows or 100,
        description=req.description or "",
    )
    return {
        "status": "created",
        "api_key": tenant.api_key,
        "client_name": tenant.client_name,
        "database_url_masked": _mask_url(tenant.database_url),
        "database_connected": db_ok,
        "database_warning": db_err if not db_ok else None,
    }

@app.delete("/api/admin/keys/{api_key}", tags=["Admin"])
def revoke_api_key(api_key: str, _: bool = Depends(require_admin)):
    """Revokes or deletes a client API key."""
    deleted = tenant_manager.delete_tenant(api_key)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked", "api_key": api_key}

# ---------------------------------------------------------------------
# Public Multi-Tenant Self-Service Onboarding
# ---------------------------------------------------------------------
class ClientRegistrationRequest(BaseModel):
    client_name: str = Field(..., example="My Surveillance Dashboard", description="Client or dashboard name")
    database_url: str = Field(..., example="mysql+pymysql://user:pass@host:3306/db_name", description="Client's target MySQL or PostgreSQL connection URL")
    description: Optional[str] = Field("", description="Optional details or location")

@app.post("/api/tenants/register", tags=["Multi-Tenant Onboarding"])
def register_client_tenant(req: ClientRegistrationRequest, request: Request):
    """
    Public self-service endpoint for external web teams/users to register their database connection URL.
    Returns a unique client API key, API URL, and ready-to-use embed widget script.
    """
    db_ok, db_err = db_connector.test_connection(req.database_url)
    
    tenant = tenant_manager.register_tenant(
        client_name=req.client_name,
        database_url=req.database_url,
        description=req.description or "Self-registered tenant",
    )
    
    base_url = str(request.base_url).rstrip("/")
    
    return {
        "status": "success",
        "api_url": base_url,
        "api_key": tenant.api_key,
        "client_name": tenant.client_name,
        "database": {
            "connected": db_ok,
            "warning": db_err if not db_ok else None,
            "dialect": db_connector.get_dialect(req.database_url)
        },
        "integration": {
            "rest_endpoint": f"{base_url}/api/chat",
            "header_name": "X-API-Key",
            "embed_widget_script": (
                f'<script src="{base_url}/static/widget.js" '
                f'data-api-url="{base_url}" '
                f'data-api-key="{tenant.api_key}" '
                f'data-title="{tenant.client_name} Assistant"></script>'
            )
        }
    }

# ---------------------------------------------------------------------
# System Health & Runtime Config
# ---------------------------------------------------------------------
@app.get("/api/health", tags=["System"])
@app.get("/api/v1/health", tags=["System"])
@app.get("/health", tags=["System"])
def health_check(request: Request, api_key: Optional[str] = Query(None)):
    """Health check endpoint to verify server, database connection, and LLM status."""
    active_url = None
    
    if api_key:
        t = tenant_manager.get_tenant(api_key)
        if t:
            
            active_url = t.database_url

    active_url = active_url or db_connector.url
    db_ok, db_err = db_connector.test_connection(active_url)
    return {
        "status": "online",
        "timestamp": time.time(),
        "database": {
            "connected": db_ok,
            "dialect": db_connector.get_dialect(active_url),
            "url_masked": _mask_url(active_url),
            "error": db_err,
        },
        "llm": {
            "configured": llm_client.is_configured(),
            "model": llm_client.model,
            "base_url": llm_client.base_url,
        },
        "multi_tenant": {
            "active_clients": len(tenant_manager.list_tenants()),
            "require_api_key": settings.REQUIRE_API_KEY,
        }
    }

@app.post("/api/config/llm", tags=["System"])
def configure_llm(req: LLMConfigRequest):
    """Dynamically updates the LLM API credentials at runtime."""
    llm_client.update_credentials(
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model,
    )
    return {
        "status": "updated",
        "model": llm_client.model,
        "base_url": llm_client.base_url,
        "configured": llm_client.is_configured(),
    }

# ---------------------------------------------------------------------
# Static Files & Interactive Demo Dashboard
# ---------------------------------------------------------------------
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
@app.get("/demo", response_class=HTMLResponse, tags=["Dashboard UI"])
def serve_demo_ui():
    """Serves the built-in interactive Web Dashboard Chatbot Demo for testing."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>NLP Engine API running. Visit <a href='/docs'>/docs</a> for Swagger documentation.</h2>")

# ---------------------------------------------------------------------
# Helpers

# ---------------------------------------------------------------------
def _mask_url(url: str) -> str:
    """Masks database passwords in connection URLs for secure logging and display."""
    return re.sub(r":([^:@/]+)@", ":****@", url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG, reload_includes=["*.py", "*.env", ".env"])
