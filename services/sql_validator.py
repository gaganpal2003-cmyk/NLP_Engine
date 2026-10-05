from __future__ import annotations
import re
from typing import Tuple, Optional
import sqlglot
from sqlglot import exp
from config import settings

FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "SHUTDOWN", "KILL", "MERGE",
    "REPLACE", "CALL", "INTO OUTFILE", "INTO DUMPFILE", "INFORMATION_SCHEMA"
}

class SQLValidator:
    """Validates generated SQL queries to enforce read-only execution, prevent SQL injection, and enforce limits."""

    @classmethod
    def validate_and_sanitize(cls, query: str, max_limit: Optional[int] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validates that the SQL query is strictly a read-only SELECT statement.
        Enforces MAX_ROW_LIMIT.
        Returns: (is_valid, sanitized_query, error_message)
        """
        if not query or not query.strip():
            return False, "", "Empty SQL query."

        clean_sql = query.strip()
        # Clean accidental markdown code fences or 'sql' prefix
        clean_sql = re.sub(r"^```(?:sql)?\s*", "", clean_sql, flags=re.IGNORECASE).strip()
        clean_sql = re.sub(r"```\s*$", "", clean_sql).strip()
        if clean_sql.lower().startswith("sql\n") or clean_sql.lower().startswith("sql "):
            clean_sql = clean_sql[3:].strip()
        if clean_sql.startswith("`") and clean_sql.endswith("`"):
            clean_sql = clean_sql.strip("`").strip()

        # Remove trailing semicolon
        clean_sql = re.sub(r";+\s*$", "", clean_sql)

        # Check for multiple statements
        statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
        if len(statements) > 1:
            return False, "", "Multi-statement SQL queries are strictly prohibited."

        single_stmt = statements[0]

        # Fast keyword check
        upper_stmt = single_stmt.upper()
        for kw in FORBIDDEN_KEYWORDS:
            pattern = rf"\b{kw}\b"
            if re.search(pattern, upper_stmt):
                return False, "", f"Operation '{kw}' is forbidden. Only SELECT queries are permitted."

        limit_to_enforce = max_limit or settings.MAX_ROW_LIMIT

        # AST Parsing with sqlglot for robust AST verification
        try:
            parsed = sqlglot.parse_one(single_stmt)
            # Ensure top level statement is a Select or Union
            if not isinstance(parsed, (exp.Select, exp.Union)):
                return False, "", f"Statement type '{type(parsed).__name__}' is not permitted. Only SELECT queries are allowed."

            # Verify no mutation expressions exist in children
            for node in parsed.walk():
                if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
                    return False, "", "Query contains forbidden modification syntax."

            # Check existing limit
            existing_limit = parsed.args.get("limit")
            if existing_limit:
                try:
                    limit_val = int(str(existing_limit.expression))
                    if limit_val > limit_to_enforce:
                        parsed = parsed.limit(limit_to_enforce)
                except Exception:
                    parsed = parsed.limit(limit_to_enforce)
            else:
                parsed = parsed.limit(limit_to_enforce)

            sanitized = parsed.sql()
            return True, sanitized, None

        except sqlglot.errors.ParseError as pe:
            # Fallback if dialect quirk: verify starts with SELECT or WITH
            if single_stmt.strip().upper().startswith("SELECT") or single_stmt.strip().upper().startswith("WITH"):
                if not re.search(r"\bLIMIT\s+\d+", single_stmt, re.IGNORECASE):
                    single_stmt = f"{single_stmt} LIMIT {limit_to_enforce}"
                return True, single_stmt, None
            return False, "", f"SQL syntax error: {str(pe)}"
        except Exception as e:
            return False, "", f"Validation error: {str(e)}"
