from __future__ import annotations
import json
import secrets
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from config import settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TENANTS_FILE = DATA_DIR / "tenants.json"

class TenantConfig(BaseModel):
    api_key: str = Field(..., description="Unique API key for client/dashboard")
    client_name: str = Field(..., description="Display name for client dashboard")
    database_url: str = Field(..., description="SQLAlchemy connection URL")
    max_rows: int = Field(100, description="Max rows returned per query")
    enabled: bool = Field(True, description="Whether this API key is active")
    description: str = Field("", description="Optional notes or details")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class TenantManager:
    """Manages client API keys and maps each key to its specific database connection URL."""

    def __init__(self, file_path: Path = TENANTS_FILE):
        self.file_path = file_path
        self._tenants: Dict[str, TenantConfig] = {}
        self._load()

    def _ensure_dir(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        self._ensure_dir()
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._tenants = {
                        k: TenantConfig(**v) for k, v in data.items()
                    }
            except Exception as e:
                print(f"[TenantManager] Error reading {self.file_path}: {e}")
                self._tenants = {}

        # Always ensure the API_KEY from .env is registered and active
        # AND synchronize to the latest DATABASE_URL in .env if it was changed!
        db_url = settings.get_effective_database_url()
        env_keys = [
            getattr(settings, "API_KEY", None),
            getattr(settings, "DEFAULT_CLIENT_API_KEY", None),
            "cairo_nlp_default",
            "nlp_live_bothra_123",
        ]
        updated = False
        for k in env_keys:
            if not k or not k.strip():
                continue
            clean_k = k.strip()
            if clean_k not in self._tenants:
                self._tenants[clean_k] = TenantConfig(
                    api_key=clean_k,
                    client_name="Active Surveillance Dashboard",
                    database_url=db_url,
                    max_rows=settings.MAX_ROW_LIMIT,
                    enabled=True,
                    description="Configured from .env",
                    created_at=datetime.now().isoformat(),
                )
                updated = True
            elif self._tenants[clean_k].database_url != db_url:
                # User changed DATABASE_URL in .env! Update the registered client immediately!
                print(f"[TenantManager] Syncing key '{clean_k}' to updated DATABASE_URL from .env: {db_url}")
                self._tenants[clean_k].database_url = db_url
                updated = True

        if updated:
            self._save()

    def _save(self) -> None:
        self._ensure_dir()
        data = {k: v.model_dump() for k, v in self._tenants.items()}
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def generate_api_key(self, prefix: str = "nlp_live_") -> str:
        """Generates a secure, human-readable API key."""
        return f"{prefix}{secrets.token_hex(12)}"

    def register_tenant(
        self,
        client_name: str,
        database_url: str,
        api_key: Optional[str] = None,
        max_rows: int = 100,
        description: str = "",
    ) -> TenantConfig:
        """Registers or updates a client API key mapped to a database."""
        key = api_key.strip() if api_key and api_key.strip() else self.generate_api_key()
        
        # Normalize mysql:// to mysql+pymysql://
        norm_url = database_url.strip()
        if norm_url.startswith("mysql://"):
            norm_url = norm_url.replace("mysql://", "mysql+pymysql://", 1)

        tenant = TenantConfig(
            api_key=key,
            client_name=client_name.strip(),
            database_url=norm_url,
            max_rows=max_rows,
            enabled=True,
            description=description.strip(),
            created_at=datetime.now().isoformat(),
        )
        self._tenants[key] = tenant
        self._save()
        return tenant

    def get_tenant(self, api_key: str) -> Optional[TenantConfig]:
        """Retrieves tenant config by API key if valid and enabled."""
        if not api_key:
            return None
        clean_key = api_key.strip()

        # Reload from .env & sync in case database was updated
        self._load()
        tenant = self._tenants.get(clean_key)
        if tenant and tenant.enabled:
            return tenant

        return None

    def list_tenants(self) -> List[TenantConfig]:
        """Returns all registered tenants."""
        self._load()
        return list(self._tenants.values())

    def delete_tenant(self, api_key: str) -> bool:
        """Removes an API key from registry."""
        if api_key in self._tenants:
            del self._tenants[api_key]
            self._save()
            return True
        return False

    def get_default_tenant(self) -> Optional[TenantConfig]:
        """Returns the first enabled tenant or default."""
        self._load()
        env_key = getattr(settings, "API_KEY", None) or getattr(settings, "DEFAULT_CLIENT_API_KEY", "nlp_live_bothra_123")
        if env_key and env_key in self._tenants:
            return self._tenants[env_key]
        for t in self._tenants.values():
            if t.enabled:
                return t
        return None

tenant_manager = TenantManager()

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args or args[0] == "list":
        print(f"\n--- Registered Tenants ({len(tenant_manager.list_tenants())}) ---")
        for t in tenant_manager.list_tenants():
            print(f"Key: {t.api_key} | Name: {t.client_name} | DB: {t.database_url}")
    elif args[0] == "create" and len(args) >= 3:
        client_name = args[1]
        db_url = args[2]
        key = args[3] if len(args) >= 4 else None
        res = tenant_manager.register_tenant(client_name, db_url, api_key=key)
        print(f"\nSuccessfully created tenant:\n  Key: {res.api_key}\n  Client: {res.client_name}\n  DB: {res.database_url}")
    else:
        print("Usage:")
        print("  python -m database.tenant_manager list")
        print("  python -m database.tenant_manager create <client_name> <database_url> [custom_api_key]")
