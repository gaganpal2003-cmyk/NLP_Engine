from __future__ import annotations
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy import text, inspect
from config import settings
from database.sample_db import init_sample_database

class DatabaseConnector:
    """
    Manages multi-tenant database connection pooling, query execution,
    and dynamic database routing based on client API keys.
    """

    def __init__(self, initial_url: Optional[str] = None):
        self._override_url = initial_url
        self._engines: Dict[str, sa.engine.Engine] = {}
        self.engine = self.get_engine(self.url)

    @property
    def url(self) -> str:
        if self._override_url:
            return self._normalize_url(self._override_url)
        return self._normalize_url(settings.get_effective_database_url())

    @url.setter
    def url(self, val: Optional[str]) -> None:
        self._override_url = val

    def _normalize_url(self, url: str) -> str:
        """Ensures MySQL uses the PyMySQL driver and SQLite paths resolve to engine root."""
        u = url.strip()
        if u.startswith("mysql://"):
            u = u.replace("mysql://", "mysql+pymysql://", 1)
        
        # Auto-encode unencoded $ in MySQL password
        if "mysql" in u and ":" in u and "@" in u:
            u = re.sub(r':([^/@:]+)\$([^/@:]*)@', r':%24@', u)

        # Resolve relative SQLite paths relative to NLP_ENGINE root directory
        if "sqlite:///" in u:
            raw_path = u.replace("sqlite:///", "")
            if raw_path.startswith("./"):
                raw_path = raw_path[2:]
            path_obj = Path(raw_path)
            if not path_obj.is_absolute():
                base_dir = Path(__file__).resolve().parent.parent
                abs_path = (base_dir / path_obj).resolve()
                u = f"sqlite:///{abs_path.as_posix()}"
        return u

    def get_engine(self, url: Optional[str] = None) -> sa.engine.Engine:
        """Returns or creates a cached SQLAlchemy engine for the specified database URL."""
        target_url = self._normalize_url(url or settings.get_effective_database_url())
        self.url = target_url

        if target_url in self._engines:
            return self._engines[target_url]

        # Auto-create sample sqlite db if sqlite is selected and not found
        if "sqlite" in target_url.lower():
            db_path = target_url.replace("sqlite:///", "").replace("sqlite://", "")
            init_sample_database(db_path)

        # Connection pool settings depending on driver
        connect_args = {}
        if "sqlite" in target_url.lower():
            connect_args["check_same_thread"] = False

        engine = sa.create_engine(
            target_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            future=True,
        )
        self._engines[target_url] = engine
        return engine

    def switch_database(self, new_url: str) -> Tuple[bool, Optional[str]]:
        """Switches the default active database connection and verifies connectivity."""
        old_url = self.url
        try:
            norm_url = self._normalize_url(new_url)
            self.url = norm_url
            self.engine = self.get_engine(norm_url)
            success, err = self.test_connection(norm_url)
            if not success:
                self.url = old_url
                self.engine = self.get_engine(old_url)
                return False, err
            return True, None
        except Exception as e:
            self.url = old_url
            self.engine = self.get_engine(old_url)
            return False, str(e)

    def test_connection(self, url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Tests if the database engine can establish a live connection."""
        try:
            eng = self.get_engine(url)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, None
        except Exception as e:
            return False, str(e)

    def get_dialect(self, url: Optional[str] = None) -> str:
        """Returns the database dialect name (e.g., 'mysql', 'postgresql', 'sqlite')."""
        eng = self.get_engine(url)
        return eng.dialect.name

    def execute_query(self, query: str, url: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[str], float]:
        """
        Executes a validated read-only SQL query against the target database.
        Returns: (rows as list of dicts, column names, execution_time_ms)
        """
        eng = self.get_engine(url)
        start_time = time.time()
        rows: List[Dict[str, Any]] = []
        columns: List[str] = []

        with eng.connect() as connection:
            result = connection.execute(text(query))
            if result.returns_rows:
                columns = list(result.keys())
                raw_rows = result.fetchall()
                for row in raw_rows:
                    row_dict: Dict[str, Any] = {}
                    for col_name, val in zip(columns, row):
                        # Serialize datetimes / dates / timedeltas
                        if isinstance(val, (datetime, date)):
                            row_dict[col_name] = val.isoformat()
                        elif isinstance(val, timedelta):
                            row_dict[col_name] = str(val)
                        elif isinstance(val, bytes):
                            row_dict[col_name] = f"<bytes len={len(val)}>"
                        elif isinstance(val, Decimal):
                            row_dict[col_name] = int(val) if val % 1 == 0 else float(val)
                        else:
                            row_dict[col_name] = val
                    rows.append(row_dict)

        duration_ms = round((time.time() - start_time) * 1000, 2)
        return rows, columns, duration_ms

# Global singleton database connector
db_connector = DatabaseConnector()
