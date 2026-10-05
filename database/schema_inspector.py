from __future__ import annotations
from typing import Dict, List, Any, Optional
import sqlalchemy as sa
from sqlalchemy import inspect, text
from database.connector import DatabaseConnector, db_connector

class SchemaInspector:
    """Inspects and formats database schema metadata for LLM prompt context and Web API per database URL."""

    def __init__(self, connector: DatabaseConnector = db_connector):
        self.connector = connector
        self._cached_schema_dicts: Dict[str, Dict[str, Any]] = {}
        self._cached_prompt_texts: Dict[str, str] = {}

    def refresh(self, url: Optional[str] = None) -> None:
        """Clears the cached schema and forces re-inspection for the specified URL or all URLs."""
        if url:
            target_url = self.connector._normalize_url(url)
            self._cached_schema_dicts.pop(target_url, None)
            self._cached_prompt_texts.pop(target_url, None)
        else:
            self._cached_schema_dicts.clear()
            self._cached_prompt_texts.clear()

    def get_schema_dict(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Returns structured dictionary of tables, columns, primary keys, and foreign keys."""
        target_url = self.connector._normalize_url(url or self.connector.url)
        if target_url in self._cached_schema_dicts:
            return self._cached_schema_dicts[target_url]

        engine = self.connector.get_engine(target_url)
        if not engine:
            return {"dialect": "unknown", "tables": []}

        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        dialect = self.connector.get_dialect(target_url)

        tables_data = []
        for t_name in table_names:
            columns = []
            for col in inspector.get_columns(t_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": str(col.get("default", "")) if col.get("default") is not None else None,
                })

            pk_constraint = inspector.get_pk_constraint(t_name)
            primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []

            fks = []
            for fk in inspector.get_foreign_keys(t_name):
                fks.append({
                    "constrained_columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table", ""),
                    "referred_columns": fk.get("referred_columns", []),
                })

            # Get row count estimate
            row_count = 0
            try:
                with engine.connect() as conn:
                    cnt_res = conn.execute(text(f"SELECT COUNT(*) FROM {t_name}"))
                    row_count = cnt_res.scalar() or 0
            except Exception:
                row_count = 0

            tables_data.append({
                "table_name": t_name,
                "row_count": row_count,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": fks,
            })

        schema_dict = {
            "dialect": dialect,
            "table_count": len(table_names),
            "tables": tables_data,
        }
        self._cached_schema_dicts[target_url] = schema_dict
        return schema_dict

    def get_schema_prompt_text(self, url: Optional[str] = None) -> str:
        """
        Formats schema into concise, token-efficient text for LLM SQL generation.
        Includes table names, column names with types, and sample distinct values for categorical columns.
        """
        target_url = self.connector._normalize_url(url or self.connector.url)
        if target_url in self._cached_prompt_texts:
            return self._cached_prompt_texts[target_url]

        schema = self.get_schema_dict(target_url)
        engine = self.connector.get_engine(target_url)
        dialect = schema.get("dialect", "sqlite")
        lines = [f"Database Dialect: {dialect.upper()}", "Schema Tables:"]

        for table in schema.get("tables", []):
            t_name = table["table_name"]
            cols = [f"{col['name']} ({col['type']})" for col in table["columns"]]
            pks = table.get("primary_keys", [])
            fks = table.get("foreign_keys", [])

            lines.append(f"\nTable `{t_name}` (estimated rows: {table.get('row_count', 0)}):")
            lines.append(f"  Columns: {', '.join(cols)}")
            if pks:
                lines.append(f"  Primary Key: {', '.join(pks)}")
            if fks:
                fk_strs = [
                    f"{', '.join(fk['constrained_columns'])} -> {fk['referred_table']}({', '.join(fk['referred_columns'])})"
                    for fk in fks
                ]
                lines.append(f"  Foreign Keys: {'; '.join(fk_strs)}")

            # Sample values for enum/categorical columns (e.g. status, severity, object_type)
            cat_cols = [
                c["name"] for c in table["columns"]
                if c["name"].lower() in ("severity", "status", "object_type", "alert_type", "log_level", "missing_ppe")
            ]
            if cat_cols:
                distinct_samples = []
                for c_name in cat_cols:
                    try:
                        with engine.connect() as conn:
                            res = conn.execute(text(f"SELECT DISTINCT {c_name} FROM {t_name} WHERE {c_name} IS NOT NULL LIMIT 8"))
                            vals = [str(r[0]) for r in res.fetchall()]
                            if vals:
                                distinct_samples.append(f"{c_name}: {vals}")
                    except Exception:
                        pass
                if distinct_samples:
                    lines.append(f"  Allowed / Known Values: {'; '.join(distinct_samples)}")

        prompt_text = "\n".join(lines)
        self._cached_prompt_texts[target_url] = prompt_text
        return prompt_text

# Global singleton inspector
schema_inspector = SchemaInspector()
