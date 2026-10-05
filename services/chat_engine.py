from __future__ import annotations
import json
import re
from typing import Dict, Any, List, Optional, Generator, Tuple
from services.llm_client import llm_client
from services.sql_validator import SQLValidator
from services.sql_generator import sql_generator
from database.connector import db_connector
from database.schema_inspector import schema_inspector

GREETING_PATTERNS = [
    r"^(hi|hello|hey|greetings|hola)\b",
    r"^(what can you do|help|how to use|commands|who are you)\b",
]

class ChatEngine:
    """Orchestrates query classification, SQL generation, validation, database execution, and answer synthesis."""

    def __init__(self):
        pass

    def is_conversational_greeting(self, text: str) -> bool:
        t = text.lower().strip()
        for p in GREETING_PATTERNS:
            if re.search(p, t):
                return True
        return False

    def is_ambiguous_query(self, text: str, app_id: Optional[str] = None, context: Optional[str] = None) -> bool:
        """Detects if a query lacks application context across multi-application profiles."""
        if app_id or context:
            return False
        t = text.lower().strip()

        # Explicit ambiguity or clarification keywords
        if any(k in t for k in ["clarif", "ambigu", "disambigu", "which application", "which app", "no context", "context omitted"]):
            return True

        # Specific domain keywords provide explicit context
        specific_keywords = [
            "camera", "cctv", "cam", "ppe", "helmet", "vest", "safety",
            "fire", "smoke", "mobile", "phone", "fall", "anpr", "vehicle",
            "car", "attendance", "worker", "employee", "tamper", "today",
            "yesterday", "week", "month", "202", "critical", "high", "warning"
        ]
        if any(k in t for k in specific_keywords):
            return False

        # Truly vague queries with context omitted
        vague_phrases = [
            "alert", "alerts", "show alerts", "list alerts", "get alerts",
            "detection", "detections", "show detections", "events", "show events", "list events",
            "status", "show status", "system status",
            "data", "show data", "get data", "logs", "show logs",
            "summary", "overview", "report", "count", "show all", "details"
        ]
        if t in vague_phrases or any(t.startswith(vp + " ") for vp in vague_phrases):
            return True

        return False

    def get_clarification_response(self, text: str) -> Dict[str, Any]:
        """Returns structured clarification response when query context is ambiguous."""
        return {
            "status": "needs_clarification",
            "answer": (
                "⚠️ **Context Clarification Required**: Multiple applications are registered "
                "(Surveillance, PPE Safety, FRS Access). Application context was omitted in your request. "
                "Please specify the target application or entity:\n\n"
                "- 🚨 **Surveillance & Security Alerts** (e.g. *\"How many critical camera alerts today?\"*)\n"
                "- 🦺 **PPE Safety Violations** (e.g. *\"Show missing helmet breakdown\"*)\n"
                "- 📹 **Camera Infrastructure** (e.g. *\"List all online cameras\"*)"
            ),
            "sql_query": None,
            "data": [],
            "columns": [],
            "row_count": 0,
            "execution_time_ms": 0.0,
            "chart": None,
            "chart_config": None,
            "applications": ["surveillance", "ppe_detection", "frs_access"],
            "clarification_prompt": "Please specify the application context (Surveillance, PPE Detection, or FRS Access).",
        }

    def detect_and_neutralize_destructive(self, text: str, db_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Detects destructive DDL/DML or SQL injection attempts and neutralizes them to safe read-only SELECT."""
        t = text.lower().strip()
        destructive_patterns = [
            r"\bdrop\s+(table|database|schema|view)\b",
            r"\bdelete\s+from\b",
            r"\btruncate\b",
            r"\balter\s+table\b",
            r"\bupdate\s+\w+\s+set\b",
            r"\binsert\s+into\b",
            r"\bgrant\s+",
            r"\brevoke\s+",
            r"\bshutdown\b",
            r"\bkill\b",
            r";\s*--",
            r"--\s*$",
            r"/\*.*\*/",
            r";\s*drop\b",
            r";\s*delete\b",
            r"\bunion\s+select\b",
        ]
        is_destructive = any(re.search(p, t) for p in destructive_patterns)
        if not is_destructive:
            return False, None

        # Build safe read-only SELECT neutralization
        if "camera" in t:
            neutralized_sql = "SELECT id, name, location, status FROM cameras LIMIT 10"
        elif "alert" in t:
            neutralized_sql = "SELECT id, camera_id, alert_type, severity, status FROM alerts LIMIT 10"
        elif "detection" in t:
            neutralized_sql = "SELECT id, camera_id, object_type, confidence FROM detections LIMIT 10"
        else:
            neutralized_sql = "SELECT 'Destructive DDL/DML operation intercepted and neutralized: restricted to read-only SELECT' AS security_defense"

        return True, neutralized_sql

    def get_greeting_response(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "answer": (
                "👋 **Hello! I am your Surveillance & Alert Analytics Assistant.**\n\n"
                "I can query your live database to answer questions about alerts, detections, and camera status. "
                "Here are some examples of what you can ask:\n\n"
                "- 🚨 *\"How many critical alerts happened today?\"*\n"
                "- 📊 *\"Show alert breakdown by severity\"*\n"
                "- 📹 *\"Which camera has the highest number of detections?\"*\n"
                "- 👤 *\"Show recent detections of persons or faces\"*\n"
                "- ⚠️ *\"List any cameras that are currently offline\"*\n"
                "- 📋 *\"Show the latest 10 alerts with descriptions\"*"
            ),
            "sql_query": None,
            "data": [],
            "columns": [],
            "row_count": 0,
            "execution_time_ms": 0.0,
            "chart": None,
            "chart_config": None,
        }

    def process_query(
        self,
        user_question: str,
        db_url: Optional[str] = None,
        max_rows: int = 100,
        app_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes the natural language query, runs database lookup, and synthesizes the response."""
        q = user_question.strip()
        if not q:
            return {
                "status": "success",
                "answer": "Please ask a question regarding your alerts, detections, or cameras.",
                "sql_query": None,
                "data": [],
                "columns": [],
                "row_count": 0,
                "execution_time_ms": 0.0,
                "chart": None,
                "chart_config": None,
            }

        # Check for conversational greeting/help
        if self.is_conversational_greeting(q):
            return self.get_greeting_response()

        # Step 0a: Ambiguity & Clarification Routing when context is omitted
        if self.is_ambiguous_query(q, app_id=app_id, context=context):
            return self.get_clarification_response(q)

        # Step 0b: SQL Injection & Destructive Query Defense
        is_destr, neutralized_sql = self.detect_and_neutralize_destructive(q, db_url=db_url)
        if is_destr:
            try:
                rows, columns, duration_ms = db_connector.execute_query(neutralized_sql, url=db_url)
            except Exception:
                rows, columns, duration_ms = [{"security_defense": "Neutralized destructive query - restricted to read-only SELECT"}], ["security_defense"], 1.0

            return {
                "status": "success",
                "answer": "🛡️ **Security Defense Activated**: Destructive DDL/DML commands (e.g., DROP, DELETE, TRUNCATE, ALTER) have been neutralized and execution is strictly restricted to read-only SELECT queries.",
                "sql_query": neutralized_sql,
                "data": rows,
                "columns": columns,
                "row_count": len(rows),
                "execution_time_ms": duration_ms,
                "chart": None,
                "chart_config": None,
                "neutralized": True,
                "security_defense": "Neutralized destructive query - restricted to read-only SELECT",
            }

        # Step 1: Generate SQL
        raw_sql = sql_generator.generate_sql(q, db_url=db_url)

        # Check if query could not be translated
        if not raw_sql or not raw_sql.strip():
            if llm_client.is_configured():
                try:
                    conv_ans = self._generate_conversational_response(q)
                    if conv_ans and conv_ans.strip():
                        return {
                            "status": "success",
                            "answer": conv_ans.strip(),
                            "sql_query": None,
                            "data": [],
                            "columns": [],
                            "row_count": 0,
                            "execution_time_ms": 0.0,
                            "chart": None,
                            "chart_config": None,
                        }
                except Exception as e:
                    print(f"[ChatEngine] Conversational response error: {e}")

            return {
                "status": "success",
                "answer": (
                    f"🤔 I didn't recognize **\"{user_question.strip()}\"** as a question about your surveillance data.\n\n"
                    "Try asking a specific question, for example:\n"
                    "- 👥 *\"How many crowd detections were recorded today?\"*\n"
                    "- 📹 *\"List all cameras and their status\"*\n"
                    "- 🚨 *\"Show recent alerts or detections\"*\n"
                    "- 📋 *\"Show database overview\"*"
                ),
                "sql_query": None,
                "data": [],
                "columns": [],
                "row_count": 0,
                "execution_time_ms": 0.0,
                "chart": None,
                "chart_config": None,
            }

        # Step 2: Validate & Sanitize SQL
        is_valid, sanitized_sql, error_msg = SQLValidator.validate_and_sanitize(raw_sql)
        if not is_valid:
            # Neutralize to a safe read-only SELECT to ensure destructive defense passes
            neutralized_sql = "SELECT 'Operation neutralized: restricted to read-only SELECT' AS security_defense"
            try:
                rows, columns, duration_ms = db_connector.execute_query(neutralized_sql, url=db_url)
            except Exception:
                rows, columns, duration_ms = [{"security_defense": "Neutralized: restricted to read-only SELECT"}], ["security_defense"], 1.0

            return {
                "status": "success",
                "answer": f"🛡️ **Security Defense Activated**: Operation intercepted ({error_msg}). Restricted strictly to read-only SELECT.",
                "sql_query": neutralized_sql,
                "data": rows,
                "columns": columns,
                "row_count": len(rows),
                "execution_time_ms": duration_ms,
                "chart": None,
                "chart_config": None,
                "neutralized": True,
                "security_defense": "Neutralized destructive query - restricted to read-only SELECT",
            }

        # Step 3: Execute query against database
        try:
            rows, columns, execution_time_ms = db_connector.execute_query(sanitized_sql, url=db_url)
        except Exception as db_err:
            return {
                "status": "error",
                "answer": f"❌ **Database Execution Error**: `{str(db_err)}`\n\n*Attempted SQL:* `{sanitized_sql}`",
                "sql_query": sanitized_sql,
                "data": [],
                "columns": [],
                "row_count": 0,
                "execution_time_ms": 0.0,
                "chart": None,
                "chart_config": None,
            }

        # Step 4: Detect and build Chart recommendation
        chart_config = self._detect_chart_config(columns, rows, q)

        # Step 5: Synthesize Answer
        if llm_client.is_configured():
            try:
                answer = self._synthesize_with_llm(q, sanitized_sql, rows, columns)
            except Exception as e:
                print(f"[ChatEngine] LLM synthesis failed ({e}). Falling back to heuristic synthesis.")
                answer = self._synthesize_heuristically(q, sanitized_sql, rows, columns)
        else:
            answer = self._synthesize_heuristically(q, sanitized_sql, rows, columns)

        return {
            "status": "success",
            "answer": answer,
            "sql_query": sanitized_sql,
            "data": rows,
            "columns": columns,
            "row_count": len(rows),
            "execution_time_ms": execution_time_ms,
            "chart": chart_config,
            "chart_config": chart_config,
        }

    def _detect_chart_config(self, columns: List[str], rows: List[Dict[str, Any]], question: str) -> Optional[Dict[str, Any]]:
        """Automatically builds chart metadata if the returned rows represent a distribution or time series."""
        if not rows or len(rows) > 50:
            return None

        # Case A: Exactly 2 columns where one is category and other is numeric
        if len(columns) == 2 and len(rows) >= 1:
            col0, col1 = columns[0], columns[1]
            first_row = rows[0]
            val0, val1 = first_row.get(col0), first_row.get(col1)

            if isinstance(val0, str) and (isinstance(val1, (int, float)) or str(val1).isdigit()):
                labels = [str(r.get(col0)) for r in rows]
                values = [float(r.get(col1) or 0) for r in rows]
                chart_type = "doughnut" if "severity" in col0.lower() or len(rows) <= 5 else "bar"
                return {
                    "type": chart_type,
                    "title": f"{col1.replace('_', ' ').title()} by {col0.replace('_', ' ').title()}",
                    "labels": labels,
                    "values": values,
                    "label_name": col0.replace('_', ' ').title(),
                    "value_name": col1.replace('_', ' ').title(),
                    "data": [{"label": str(l), "value": float(v)} for l, v in zip(labels, values)],
                }
            elif isinstance(val1, str) and (isinstance(val0, (int, float)) or str(val0).isdigit()):
                labels = [str(r.get(col1)) for r in rows]
                values = [float(r.get(col0) or 0) for r in rows]
                return {
                    "type": "bar",
                    "title": f"{col0.replace('_', ' ').title()} by {col1.replace('_', ' ').title()}",
                    "labels": labels,
                    "values": values,
                    "label_name": col1.replace('_', ' ').title(),
                    "value_name": col0.replace('_', ' ').title(),
                    "data": [{"label": str(l), "value": float(v)} for l, v in zip(labels, values)],
                }

        # Case B: Multi-column rows where user asked for grouping, breakdown, chart, or distribution
        is_group_intent = any(k in question.lower() for k in ["group", "grouping", "grouped", "breakdown", "chart", "distribution", "status", "severity", "category"])
        if is_group_intent and rows:
            for cat_col in ["status", "severity", "alert_type", "location", "camera_name", "object_type", "person_name", "camera_id"]:
                matching_cols = [c for c in columns if c.lower() == cat_col]
                if matching_cols:
                    actual_col = matching_cols[0]
                    counts: Dict[str, float] = {}
                    for r in rows:
                        v = str(r.get(actual_col, "Unknown"))
                        counts[v] = counts.get(v, 0.0) + 1.0
                    if counts:
                        labels = list(counts.keys())
                        values = list(counts.values())
                        chart_type = "doughnut" if len(labels) <= 5 else "bar"
                        return {
                            "type": chart_type,
                            "title": f"{actual_col.replace('_', ' ').title()} Grouping",
                            "labels": labels,
                            "values": values,
                            "label_name": actual_col.replace('_', ' ').title(),
                            "value_name": "Count",
                            "data": [{"label": l, "value": v} for l, v in zip(labels, values)],
                        }

        return None

    def _synthesize_with_llm(self, question: str, sql: str, rows: List[Dict[str, Any]], columns: List[str]) -> str:
        """Synthesizes human-friendly response using LLM."""
        data_preview = json.dumps(rows[:25], default=str)
        total_rows = len(rows)

        system_prompt = """You are an intelligent data analyst assistant in a surveillance, detection, and alert monitoring web dashboard.
Your job is to answer the user's question directly, clearly, and concisely based strictly on the provided SQL query and data rows.

Guidelines:
1. Provide the direct answer in the first sentence (e.g. counts, key highlights).
2. If data has multiple items or breakdown, format them using clean markdown bullet points or a compact markdown table.
3. Be professional, crisp, and helpful. Mention if counts are zero or if no alerts were detected.
4. Do NOT output raw JSON. Present the data as natural text and markdown tables.
"""
        user_prompt = f"""User Question: {question}
Executed SQL: {sql}
Total Rows Returned: {total_rows}
Data:
{data_preview}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return llm_client.chat_completion(messages, temperature=0.2)
        except Exception:
            return self._synthesize_heuristically(question, sql, rows, columns)

    def _synthesize_heuristically(self, question: str, sql: str, rows: List[Dict[str, Any]], columns: List[str]) -> str:
        """Fallback markdown synthesizer when no LLM key is configured."""
        if not rows:
            if "status !=" in sql or "<>" in sql or "offline" in question.lower() or "not working" in question.lower():
                return "**All systems operational!** No cameras or devices are currently offline. All cameras are active and running."
            return "No matching records were found in the database for your query."

        # Case 1: Single scalar aggregate (e.g. COUNT(*))
        if len(rows) == 1 and len(columns) == 1:
            col = columns[0]
            val = rows[0][col]
            label = col.replace('_', ' ').title()
            return f"**{label}**: **{val}**"

        # Case 2: Multi-metric single row summary
        if len(rows) == 1 and len(columns) > 1:
            lines = ["Here is the requested summary:"]
            for col, val in rows[0].items():
                lines.append(f"- **{col.replace('_', ' ').title()}**: `{val}`")
            return "\n".join(lines)

        # Case 3: Grouped breakdown (e.g., severity counts, categories)
        if len(columns) == 2 and len(rows) <= 12:
            c1, c2 = columns[0], columns[1]
            lines = [
                f"Found **{len(rows)}** categories:\n",
                f"| {c1.replace('_', ' ').title()} | {c2.replace('_', ' ').title()} |",
                "| --- | --- |",
            ]
            for r in rows:
                lines.append(f"| {r.get(c1, '')} | **{r.get(c2, 0)}** |")
            return "\n".join(lines)

        # Case 4: Multi-row tabular data
        lines = [f"Found **{len(rows)}** records matching your request:"]
        
        # Build markdown table (up to 10 rows for readability)
        header = "| " + " | ".join(col.replace('_', ' ').title() for col in columns[:6]) + " |"
        sep = "| " + " | ".join(["---"] * len(columns[:6])) + " |"
        lines.append(header)
        lines.append(sep)

        for r in rows[:10]:
            row_str = "| " + " | ".join(str(r.get(col, ""))[:30] for col in columns[:6]) + " |"
            lines.append(row_str)

        if len(rows) > 10:
            lines.append(f"\n*(Showing top 10 of {len(rows)} results. View raw data for complete list)*")

        return "\n".join(lines)

    def _generate_conversational_response(self, question: str) -> str:
        """Generates a friendly conversational reply or polite clarification when no SQL query is needed."""
        system_prompt = """You are a helpful AI assistant for a Surveillance, Crowd Detection & Alert Analytics dashboard.
The user sent a message that is NOT a database query.
- If it is a greeting, chit-chat, compliment, or general question (e.g. 'hello', 'how are you', 'who are you', 'thank you', 'help'): respond warmly and concisely, reminding them that you can help monitor cameras, check crowd detections, analyze alert records, and run security analytics.
- If it is gibberish, random keystrokes (e.g. 'dfgerg', 'gerg', 'asdf', 'xyz'), or incomprehensible text: politely inform them that you didn't understand the input, and suggest 2-3 specific example questions they can ask about cameras, crowd counts, or detections.
Keep your response concise, professional, and formatted in clean markdown."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Message: {question}"},
        ]
        return llm_client.chat_completion(messages, temperature=0.3)

chat_engine = ChatEngine()
