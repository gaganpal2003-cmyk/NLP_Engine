from __future__ import annotations
import re
import difflib
from datetime import datetime
from typing import Optional, Dict, Any, List
from services.llm_client import llm_client
from database.schema_inspector import schema_inspector
from database.connector import db_connector

# Comprehensive domain typos, phonetic spellings, abbreviations & slang
DOMAIN_SYNONYMS: Dict[str, str] = {
    # Camera & CCTV
    "camra": "camera", "camras": "camera", "cam": "camera", "cams": "camera", 
    "cmra": "camera", "cmera": "camera", "camer": "camera", "caemra": "camera",
    "cctv": "camera", "cctvs": "camera", "webcam": "camera", "videocam": "camera",
    "kemra": "camera", "kamra": "camera", "camara": "camera", "camers": "camera",
    "cemra": "camera", "cammra": "camera",
    # PPE & Safety Equipment
    "pep": "ppe", "pee": "ppe", "ppes": "ppe", "ppee": "ppe", 
    "safty": "safety", "saftey": "safety", "safet": "safety", "sefty": "safety", "safetyy": "safety",
    "helmt": "helmet", "helment": "helmet", "halmet": "helmet", "helmat": "helmet", "helmets": "helmet", 
    "hlmt": "helmet", "hemet": "helmet", "helmtet": "helmet", "helmit": "helmet",
    "vest": "vest", "vests": "vest", "jacket": "vest", "jackets": "vest",
    "glov": "gloves", "glovs": "gloves", "gloves": "gloves",
    # Detection & Violation
    "detecion": "detection", "dtection": "detection", "detecton": "detection", "detec": "detection", 
    "detections": "detection", "detect": "detection", "detects": "detection", "detecshun": "detection",
    "detaction": "detection", "ditaction": "detection", "detetion": "detection", "detectin": "detection",
    "voilation": "violation", "violations": "violation", "violashun": "violation", "voilations": "violation",
    "voilaton": "violation", "violate": "violation", "violat": "violation", "violationn": "violation",
    # Fire & Smoke
    "fir": "fire", "fires": "fire", "smok": "smoke", "somke": "smoke", "smook": "smoke", "smk": "smoke",
    "smoker": "smoke", "smokes": "smoke", "fair": "fire", "fare": "fire",
    # Mobile Phone Usage
    "moble": "mobile", "mobil": "mobile", "mobl": "mobile", "fone": "phone", "phon": "phone", 
    "cell": "mobile", "cellphone": "mobile", "smartphon": "mobile", "smartphone": "mobile",
    "useg": "usage", "usg": "usage", "usge": "usage", "using": "usage",
    # Vehicle / ANPR
    "vehical": "vehicle", "vehcile": "vehicle", "vehicl": "vehicle", "vehicall": "vehicle", 
    "vihecle": "vehicle", "vheicle": "vehicle", "cars": "vehicle", "car": "vehicle", "truck": "vehicle",
    "plate": "anpr", "plates": "anpr", "numberplate": "anpr", "license": "anpr", "licence": "anpr",
    # Person & Fall
    "persn": "person", "parson": "person", "prson": "person", "preson": "person", "personn": "person", 
    "people": "person", "worker": "person", "workers": "person",
    "fal": "fall", "falll": "fall", "faling": "fall", "faal": "fall", "falling": "fall", "fell": "fall",
    # Attendance & Employee
    "attendence": "attendance", "atendance": "attendance", "atendence": "attendance", "attandance": "attendance",
    "employe": "employee", "emloyee": "employee", "emplyee": "employee", "staff": "employee",
    # Alerts & Notifications
    "alart": "alert", "alarts": "alert", "alrt": "alert", "allert": "alert", "alerts": "alert", 
    "elert": "alert", "elart": "alert", "notif": "alert",
    # Time & Dates
    "toady": "today", "todday": "today", "tday": "today", "todai": "today", "2day": "today",
    "yestarday": "yesterday", "yestrday": "yesterday", "yesterdy": "yesterday",
    # Missing & Breakdown
    "mising": "missing", "missin": "missing", "misng": "missing", "misin": "missing",
    "brakedown": "breakdown", "brakdown": "breakdown", "braekdown": "breakdown", "brekdown": "breakdown",
    # Status
    "ofline": "offline", "offine": "offline", "oflline": "offline", "offlinee": "offline",
    "oneline": "online", "runing": "running", "activ": "active",
    # Question words, Contractions, Indian English & Slang
    "hw": "how", "mny": "many", "meny": "many", "mani": "many", "howmny": "how many", "homany": "how many",
    "kitne": "how many", "kitna": "how many", "kya": "what", "wat": "what", "wht": "what",
    "r": "are", "thr": "there", "hai": "are", "he": "is",
    "giv": "give", "sho": "show", "shw": "show", "tel": "tell", "disply": "display", "dsply": "display",
    "datils": "details", "detals": "details", "detais": "details", "detils": "details",
    "totl": "total", "totle": "total", "smry": "summary", "sumry": "summary",
    "plz": "", "pls": "", "please": "", "bhai": "", "sir": "",
}

# Multi-word regex phrase normalizations
PHRASE_REPLACEMENTS = [
    (r"\b(bar\s*graph|bar\s*chart|in\s+bar\s+graph|in\s+bar\s+chart)\b", "bar graph"),
    (r"\b(pie\s*chart|pie\s*graph)\b", "pie chart"),
    (r"\b(line\s*chart|line\s*graph)\b", "line graph"),
    (r"\b(visuali[sz]e(\s+data)?(\s+in\s+graphs?)?)\b", "bar graph"),
    (r"\b(download|export|generate)\s+(the\s+)?report\b", "download report"),
    (r"\b(hw|how|homany|howmny)\s+(mny|meny|mani|many)\b", "how many"),
    (r"\bhowmny\b", "how many"),
    (r"\bhow\s+much\b", "how many"),
    (r"\b(count|no|num|number)\s+of\b", "how many"),
    (r"\b(tell\s+me|give\s+me|show\s+me|shw\s+me|sho\s+me|giv\s+me)\b", "show"),
    (r"\b(tell|give|shw|sho|giv)\b", "show"),
    (r"\b(list\s+out|display|fetch|get)\b", "show"),
    (r"\b(break\s*down|brake\s*down)\b", "breakdown"),
    (r"\b(not\s*working|not\s*runing|not\s*running|shut\s*down|off\s*line)\b", "offline"),
    (r"\b(number\s*plate|licen[sc]e\s*plate)\b", "anpr"),
    (r"\b(fir[e]?\s*(&|and)?\s*smok[e]?)\b", "fire smoke"),
    (r"\b(mob[i|l]e?\s*(fone|phone)?\s*us[a-z]*)\b", "mobile usage"),
    (r"\b(person\s*fall[a-z]*|parson\s*fall[a-z]*|fall\s*down)\b", "person fall"),
    (r"\b(date\s*wise|datewise|by\s*date|day\s*wise|daywise|daily)\b", "date wise"),
    (r"\b(all\s*feature[s]?|of\s*all\s*feature[s]?|every\s*feature[s]?|features)\b", "all features"),
    (r"\b(feature\s*wise|featurewise|by\s*feature[s]?)\b", "all features"),
]

# Regex stem patterns for words not caught by exact synonym dictionary
STEM_MAPPINGS = [
    (r"^cam[a-z]*", "camera"),
    (r"^(pep|ppe[a-z]*)", "ppe"),
    (r"^helm[a-z]*", "helmet"),
    (r"^vest[a-z]*", "vest"),
    (r"^fir[a-z]*", "fire"),
    (r"^(smok|somk)[a-z]*", "smoke"),
    (r"^(mobl|mobil)[a-z]*", "mobile"),
    (r"^(pers|pars)[a-z]*", "person"),
    (r"^(fal|faal)[a-z]*", "fall"),
    (r"^(vehic|vehc)[a-z]*", "vehicle"),
    (r"^(anpr)[a-z]*", "anpr"),
    (r"^(atten|atend|atnd)[a-z]*", "attendance"),
    (r"^(emplo|emply)[a-z]*", "employee"),
    (r"^(alart|alrt|allert)[a-z]*", "alert"),
    (r"^(voilat|violat)[a-z]*", "violation"),
    (r"^(detec|ditac)[a-z]*", "detection"),
    (r"^(misi|missi)[a-z]*", "missing"),
    (r"^(brake|break)[a-z]*", "breakdown"),
    (r"^(oflin|offlin)[a-z]*", "offline"),
]

CORRECTION_TARGETS = [
    "report",
    "visualize",
    "plot",
    "pie",
    "bar",
    "chart",
    "graph",
    "how", "many", "count", "total", "show", "give", "list", "details", "find", "get", "status",
    "camera", "ppe", "helmet", "vest", "safety", "detection", "alert", "violation",
    "fire", "smoke", "mobile", "phone", "usage", "fall", "person", "vehicle", "anpr",
    "attendance", "employee", "breakdown", "missing", "offline", "online", "running",
    "records", "summary", "overview", "today", "yesterday", "date", "wise", "features",
]

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}

def extract_date_from_text(text: str) -> Optional[str]:
    """
    Extracts explicit date from user query and returns standard 'YYYY-MM-DD' format.
    Supports DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY, DD Month YYYY, Month DD YYYY.
    """
    t = text.lower()
    
    # 1. DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
    m1 = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", t)
    if m1:
        d, m, y = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        try:
            from datetime import date
            date(y, m, d)
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    # 2. YYYY-MM-DD or YYYY/MM/DD
    m2 = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", t)
    if m2:
        y, m, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            from datetime import date
            date(y, m, d)
            return f"{y:04d}-{m:02d}-{d:02d}"
        except Exception:
            pass

    # 3. DD Month YYYY (e.g. 23rd September 2026, 23 Sep 2026)
    m3 = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]{3,10})\s+(\d{4})\b", t)
    if m3:
        d = int(m3.group(1))
        month_str = m3.group(2).lower()
        y = int(m3.group(3))
        for k, v in MONTH_MAP.items():
            if month_str.startswith(k):
                try:
                    from datetime import date
                    date(y, v, d)
                    return f"{y:04d}-{v:02d}-{d:02d}"
                except Exception:
                    pass

    # 4. Month DD YYYY (e.g. September 23 2026)
    m4 = re.search(r"\b([a-zA-Z]{3,10})\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b", t)
    if m4:
        month_str = m4.group(1).lower()
        d = int(m4.group(2))
        y = int(m4.group(3))
        for k, v in MONTH_MAP.items():
            if month_str.startswith(k):
                try:
                    from datetime import date
                    date(y, v, d)
                    return f"{y:04d}-{v:02d}-{d:02d}"
                except Exception:
                    pass

    return None

def get_table_date_col(t_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """Dynamically finds the timestamp or date column for a given table schema."""
    if not t_info:
        return None
    col_names = [c["name"].lower() for c in t_info.get("columns", [])]
    for candidate in ["date", "attendance_date", "created_at", "timestamp", "datetime", "detection_date"]:
        if candidate in col_names:
            return candidate
    return None

def build_date_where_clause(
    date_col: Optional[str],
    target_date: Optional[str],
    is_today: bool,
    is_yesterday: bool,
    is_week: bool,
    is_month: bool,
    dialect: str = "mysql",
) -> str:
    """Builds standard SQL date filtering clause."""
    if not date_col:
        return ""
    is_mysql = "mysql" in dialect.lower()
    if target_date:
        return f"DATE({date_col}) = '{target_date}'"
    if is_today:
        return f"DATE({date_col}) = CURRENT_DATE" if is_mysql else f"DATE({date_col}) = DATE('now')"
    if is_yesterday:
        return f"DATE({date_col}) = DATE_SUB(CURRENT_DATE, INTERVAL 1 DAY)" if is_mysql else f"DATE({date_col}) = DATE('now', '-1 day')"
    if is_week:
        return f"DATE({date_col}) >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)" if is_mysql else f"DATE({date_col}) >= DATE('now', '-7 days')"
    if is_month:
        return f"DATE({date_col}) >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)" if is_mysql else f"DATE({date_col}) >= DATE('now', '-30 days')"
    return ""

class SQLGenerator:
    """Generates precise SQL from natural language questions with fault-tolerant typo understanding."""

    def __init__(self):
        pass

    def generate_sql(self, question: str, db_url: Optional[str] = None) -> str:
        """
        Translates a natural language question into valid, executable SQL.
        Uses heuristics with deep typo-tolerance first or when LLM is unavailable/rate-limited.
        """
        # Step 1: Normalize query to handle any misspellings and extract date
        schema = schema_inspector.get_schema_dict(db_url)
        all_table_names = [t["table_name"].lower() for t in schema.get("tables", [])]
        target_date = extract_date_from_text(question)
        normalized_q = self._normalize_query(question, all_table_names)

        # Step 2: If LLM is configured and not in quota cooldown, attempt LLM generation
        if llm_client.is_configured():
            try:
                schema_prompt = schema_inspector.get_schema_prompt_text(db_url)
                dialect = db_connector.get_dialect(db_url)
                system_prompt = f"""You are an expert SQL engineer for a surveillance, crowd detection, security, and alert monitoring system.
Given a database schema and a user question, generate a single valid, read-only {dialect} SQL query.

Rules:
1. If the user question asks for database data or surveillance/crowd metrics, ONLY return the SQL query inside ```sql ``` code fences.
2. Only generate SELECT queries. No INSERT, UPDATE, DELETE, DROP, or ALTER.
3. Use exact column names and table names from the schema.
4. For multi-row queries, append LIMIT 25 unless explicitly asked for all.
5. If table contains image or binary BLOB columns (snapshot, imagedata, photo, etc.), DO NOT SELECT THEM.
6. When calculating counts or aggregates, use descriptive column aliases (e.g. SELECT COUNT(*) AS total_cameras FROM camera).
7. CRITICAL: If the user question is gibberish, random letters/keystrokes (e.g. 'dfgerg', 'gerg', 'asdf', 'xyz'), conversational greetings (e.g. 'hi', 'hello', 'how are you', 'thank you'), or completely unrelated to querying the database, DO NOT invent a query. Return ONLY the word: NONE
8. When the question asks for 'bar graph', 'graph', 'chart', 'pie chart', 'visualize', 'grouping', 'breakdown', 'distribution', 'by status', 'by location', 'by camera', or 'by severity', ALWAYS generate an aggregated GROUP BY query with COUNT(*) (e.g. SELECT camera_id, COUNT(*) AS total_detections FROM detections GROUP BY camera_id ORDER BY total_detections DESC LIMIT 10, or SELECT severity, COUNT(*) AS total_alerts FROM alerts GROUP BY severity). If the user asks for 'all info in bar graph' or 'visualize data in graphs', group detections by camera or alerts by severity. NEVER say you cannot generate graphs.
9. When the question asks to 'download report', 'export report', or 'generate report', generate a SELECT query retrieving the recent 50 records (e.g. SELECT * FROM detections ORDER BY timestamp DESC LIMIT 50).
"""
                user_prompt = f"""Database Schema:
{schema_prompt}

User Question: {normalized_q} (Original: {question})
"""
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                llm_response = llm_client.chat_completion(messages, temperature=0.0)
                extracted_sql = self._extract_sql(llm_response)
                if extracted_sql:
                    if extracted_sql.strip().upper() in ["NONE", "SELECT 1", "SELECT 1;", "SELECT 1 AS RESULT", "SELECT 1 AS RESULT;"]:
                        return ""
                    # If grouping was requested but LLM returned a plain list without GROUP BY, use heuristic GROUP BY
                    if any(k in question.lower() for k in ["group", "grouping", "breakdown", "distribution"]) and "GROUP BY" not in extracted_sql.upper():
                        heuristic_grp = self._generate_with_heuristics(normalized_q, db_url=db_url, raw_q=question, target_date=target_date)
                        if heuristic_grp and "GROUP BY" in heuristic_grp.upper():
                            return heuristic_grp
                    return extracted_sql
                elif "NONE" in llm_response.strip().upper():
                    return ""
            except Exception as e:
                print(f"[SQLGenerator] LLM generation skipped or failed ({e}). Using robust heuristic engine.")

        # Step 3: Heuristic generator with deep typo and date tolerance
        return self._generate_with_heuristics(normalized_q, db_url=db_url, raw_q=question, target_date=target_date)

    def _extract_sql(self, text: str) -> str:
        """Extracts clean SQL from LLM response fences."""
        clean_text = text.strip()
        if clean_text.upper() == "NONE" or clean_text.upper().startswith("NONE"):
            return ""
        m = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
        else:
            lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("--")]
            candidate = " ".join(lines)

        # Strip accidental markdown code fence or 'sql' language specifier
        candidate = re.sub(r"^```(?:sql)?\s*", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"```\s*$", "", candidate).strip()
        if candidate.lower().startswith("sql\n") or candidate.lower().startswith("sql "):
            candidate = candidate[3:].strip()
        if candidate.startswith("`") and candidate.endswith("`"):
            candidate = candidate.strip("`").strip()

        if candidate.upper().startswith("SELECT") or candidate.upper().startswith("WITH"):
            if candidate.upper() in ["SELECT 1", "SELECT 1;", "SELECT 1 AS RESULT", "SELECT 1 AS RESULT;"]:
                return ""
            return candidate
        return ""

    def _normalize_query(self, text: str, table_names: List[str]) -> str:
        """Deep fault-tolerant spell correction and natural language normalization."""
        t = text.lower().strip()

        # 1. Apply multi-word phrase replacements
        for pattern, repl in PHRASE_REPLACEMENTS:
            t = re.sub(pattern, repl, t)

        # 2. Tokenize words
        words = re.findall(r"[a-zA-Z0-9]+", t)
        normalized: List[str] = []

        all_targets = CORRECTION_TARGETS + [t.lower() for t in table_names]

        for w in words:
            # Step A: Exact dictionary lookup
            if w in DOMAIN_SYNONYMS:
                syn = DOMAIN_SYNONYMS[w]
                if syn:
                    normalized.append(syn)
                continue

            # Step B: Stem pattern matching (e.g. 'camras' -> 'camera', 'pep' -> 'ppe')
            stemmed = False
            for pattern, repl in STEM_MAPPINGS:
                if re.match(pattern, w):
                    normalized.append(repl)
                    stemmed = True
                    break
            if stemmed:
                continue

            # Step C: Fuzzy match against domain targets (ONLY for words length >= 4)
            if len(w) >= 4:
                matches = difflib.get_close_matches(w, all_targets, n=1, cutoff=0.60)
                if matches:
                    normalized.append(matches[0])
                    continue

            # Step D: Keep original word
            normalized.append(w)

        return " ".join(normalized)

    def _generate_with_heuristics(
        self,
        normalized_q: str,
        db_url: Optional[str] = None,
        raw_q: str = "",
        target_date: Optional[str] = None,
    ) -> str:
        """
        High-precision query generator for surveillance and alert databases.
        Inspects existing tables dynamically and understands dates, timelines, and multi-feature breakdowns.
        """
        dialect = db_connector.get_dialect(db_url).lower()
        q = f"{normalized_q.lower()} {raw_q.lower()}"

        # Fetch actual tables from current database
        schema = schema_inspector.get_schema_dict(db_url)
        table_dict: Dict[str, Dict[str, Any]] = {
            t["table_name"].lower(): t for t in schema.get("tables", [])
        }
        all_table_names = list(table_dict.keys())

        # Date detection
        target_date = target_date or extract_date_from_text(raw_q) or extract_date_from_text(normalized_q)
        is_today = any(k in q for k in ["today", "todays", "2day"])
        is_yesterday = any(k in q for k in ["yesterday", "yestarday", "yestrday"])
        is_week = any(k in q for k in ["this week", "past week", "last 7 days", "last week"])
        is_month = any(k in q for k in ["this month", "past month", "last 30 days", "last month"])
        has_date_filter = bool(target_date or is_today or is_yesterday or is_week or is_month)

        is_date_wise = any(k in q for k in ["date wise", "datewise", "by date", "day wise", "daywise", "daily", "timeline", "trend", "per day", "each day"])
        is_all_features = any(k in q for k in ["all feature", "all features", "every feature", "of all feature", "of all features", "all detections", "all alert", "all violations", "overall", "total of all", "features"])

        # Helper to get non-blob columns for clean display
        def get_display_columns(table_name: str, limit: int = 7) -> str:
            t_info = table_dict.get(table_name.lower())
            if not t_info:
                return "*"
            excluded = {"snapshot", "imagedata", "employee_face", "face_encoding", "vehicalimg", "photo", "image_path", "face_img"}
            cols = [
                c["name"] for c in t_info["columns"]
                if c["name"].lower() not in excluded
            ]
            return ", ".join(cols[:limit]) if cols else "*"

        # Check intent types
        is_count = any(k in q for k in ["how many", "count", "number of", "total", "amount", "are there", "is there", "exist", "sum", "kitne"])
        is_breakdown = any(k in q for k in ["breakdown", "by type", "by camera", "by severity", "types of", "distribution", "category", "categories", "group by"])
        is_chart_intent = any(k in q for k in ["bar graph", "graph", "chart", "bar", "pie", "pie chart", "visualize", "plot", "histogram", "trend", "doughnut"])
        is_report_intent = any(k in q for k in ["download report", "export report", "download csv", "download excel", "download pdf", "generate report", "report"])

        # Candidate table finders
        cam_table = self._find_table(all_table_names, ["camera", "bothra_ppe_detection_camera", "cameras"])
        alert_table = self._find_table(all_table_names, ["alerts", "alert", "cairo_alerts", "bothra_alerts"])
        ppe_table = self._find_table(all_table_names, ["ppe_detection", "bothra_ppe_detection_detection", "ppe"])
        det_table = self._find_table(all_table_names, ["detection", "ppe_detection", "bothra_ppe_detection_detection", "detections"])
        fire_table = self._find_table(all_table_names, ["fire_smoke", "fire", "smoke"])
        mobile_table = self._find_table(all_table_names, ["mobile_usage", "mobile", "phone"])
        fall_table = self._find_table(all_table_names, ["person_fall", "fall"])
        anpr_table = self._find_table(all_table_names, ["anpr_detection", "anpr", "vehicle"])
        tamper_table = self._find_table(all_table_names, ["camera_tempering", "camera_tampering", "tampering", "tempering"])
        att_table = self._find_table(all_table_names, ["employee_attendance", "cairo_attendance_room", "attendance"])
        client_table = self._find_table(all_table_names, ["api_clients", "client_employees", "client_access_events"])

        # Standard surveillance feature list
        feature_tables = [
            (t, label) for t, label in [
                (ppe_table, "PPE Violations"),
                (fire_table, "Fire & Smoke"),
                (mobile_table, "Mobile Usage"),
                (fall_table, "Person Fall"),
                (anpr_table, "Vehicle ANPR"),
                (tamper_table, "Camera Tampering"),
            ] if t
        ]

        # -------------------------------------------------------------
                # -------------------------------------------------------------
        # Chart & Graph Intent Handling (e.g. "all info in bar graph")
        # -------------------------------------------------------------
        if is_chart_intent or (is_breakdown and not is_count):
            if det_table:
                t_cols = [c["name"].lower() for c in table_dict.get(det_table.lower(), {}).get("columns", [])]
                if "camera_id" in t_cols:
                    return f"SELECT camera_id, count(*) AS total_detections FROM {det_table} GROUP BY camera_id ORDER BY total_detections DESC LIMIT 10"
                elif "object_type" in t_cols:
                    return f"SELECT object_type, count(*) AS total_detections FROM {det_table} GROUP BY object_type ORDER BY total_detections DESC LIMIT 10"
                else:
                    first_col = t_cols[1] if len(t_cols) > 1 else t_cols[0]
                    return f"SELECT {first_col}, count(*) AS total_detections FROM {det_table} GROUP BY {first_col} ORDER BY total_detections DESC LIMIT 10"
            elif alert_table:
                t_cols = [c["name"].lower() for c in table_dict.get(alert_table.lower(), {}).get("columns", [])]
                if "severity" in t_cols:
                    return f"SELECT severity, count(*) AS alert_count FROM {alert_table} GROUP BY severity ORDER BY alert_count DESC"
                elif "alert_type" in t_cols:
                    return f"SELECT alert_type, count(*) AS alert_count FROM {alert_table} GROUP BY alert_type ORDER BY alert_count DESC"
            elif cam_table:
                return f"SELECT status, count(*) AS camera_count FROM {cam_table} GROUP BY status"

        # -------------------------------------------------------------
        # Report Intent Handling (e.g. "download report", "export report")
        # -------------------------------------------------------------
        if is_report_intent:
            if det_table:
                return f"SELECT * FROM {det_table} ORDER BY 1 DESC LIMIT 50"
            elif alert_table:
                return f"SELECT * FROM {alert_table} ORDER BY 1 DESC LIMIT 50"
            elif cam_table:
                return f"SELECT * FROM {cam_table} LIMIT 50"

        # 0. Date-Wise Trend / Timeline Grouping
        # -------------------------------------------------------------
        if is_date_wise:
            # Check if specific feature table is requested
            target_single = None
            if any(k in q for k in ["ppe", "helmet", "vest"]) and ppe_table:
                target_single = ppe_table
            elif ("fire" in q or "smoke" in q) and fire_table:
                target_single = fire_table
            elif ("mobile" in q or "phone" in q) and mobile_table:
                target_single = mobile_table
            elif "fall" in q and fall_table:
                target_single = fall_table
            elif ("anpr" in q or "vehicle" in q or "car" in q) and anpr_table:
                target_single = anpr_table
            elif "attendance" in q and att_table:
                target_single = att_table
            elif "alert" in q and alert_table:
                target_single = alert_table

            if target_single:
                d_col = get_table_date_col(table_dict.get(target_single))
                if d_col:
                    return f"SELECT DATE({d_col}) AS detection_date, count(*) AS total_count FROM {target_single} GROUP BY DATE({d_col}) ORDER BY detection_date DESC LIMIT 30"

            # Multi-table date-wise summary
            date_sub = []
            for t_name, label in feature_tables:
                d_col = get_table_date_col(table_dict.get(t_name))
                if d_col:
                    date_sub.append(f"SELECT DATE({d_col}) AS detection_date, count(*) AS total_count FROM {t_name} GROUP BY DATE({d_col})")
            if date_sub:
                unioned = " UNION ALL ".join(date_sub)
                return f"SELECT detection_date, SUM(total_count) AS total_detections FROM ({unioned}) AS all_dates GROUP BY detection_date ORDER BY detection_date DESC LIMIT 30"

        # -------------------------------------------------------------
        # 1. Multi-Feature Summary (With or Without Specific Date Filter)
        # -------------------------------------------------------------
        is_general_query = not any(k in q for k in [
            "camera", "cctv", "client", "attendance", "employee", "alert",
            "ppe", "helmet", "vest", "safety", "fire", "smoke",
            "mobile", "phone", "fall", "anpr", "vehicle", "tamper", "tempering"
        ])
        if is_all_features or (has_date_filter and is_general_query):
            summary_sub = []
            for t_name, label in feature_tables:
                d_col = get_table_date_col(table_dict.get(t_name))
                where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
                where_str = f" WHERE {where}" if where else ""
                summary_sub.append(f"SELECT '{label}' AS feature, count(*) AS total_count FROM {t_name}{where_str}")
            if summary_sub:
                return " UNION ALL ".join(summary_sub)

        # -------------------------------------------------------------
        # 2. Cameras (camera, cctv, cams, grouping & status)
        # -------------------------------------------------------------
        if ("camera" in q or "cctv" in q or "cam" in q) and cam_table and not any(k in q for k in ["ppe", "helmet", "vest"]):
            cols = get_display_columns(cam_table)
            t_info = table_dict.get(cam_table.lower(), {})
            cam_cols = [c["name"].lower() for c in t_info.get("columns", [])]

            # 2a. Grouped Breakdown for cameras / camera grouping
            if is_breakdown or any(k in q for k in ["group", "grouping", "grouped", "breakdown", "by status", "by location", "distribution"]):
                if "alert" in q and alert_table:
                    return f"SELECT camera_id, count(*) AS alert_count FROM {alert_table} GROUP BY camera_id ORDER BY alert_count DESC LIMIT 10"
                if "detection" in q and det_table:
                    return f"SELECT camera_id, count(*) AS detection_count FROM {det_table} GROUP BY camera_id ORDER BY detection_count DESC LIMIT 10"
                if "location" in q and "location" in cam_cols:
                    return f"SELECT location, count(*) AS camera_count FROM {cam_table} GROUP BY location ORDER BY camera_count DESC LIMIT 10"
                if "status" in cam_cols:
                    return f"SELECT status, count(*) AS camera_count FROM {cam_table} GROUP BY status ORDER BY camera_count DESC"
                return f"SELECT id, name, status FROM {cam_table} LIMIT 25"

            if any(k in q for k in ["offline", "inactive", "down", "not working", "disconnected"]):
                return f"SELECT {cols} FROM {cam_table} WHERE status != 'online' AND status != '1'"
            if is_count:
                return f"SELECT count(*) AS total_cameras FROM {cam_table}"
            return f"SELECT {cols} FROM {cam_table} LIMIT 25"

        # -------------------------------------------------------------
        # 2b. Alerts & Security Incidents
        # -------------------------------------------------------------
        if ("alert" in q or "security" in q) and alert_table:
            t_info = table_dict.get(alert_table.lower(), {})
            alert_cols = [c["name"].lower() for c in t_info.get("columns", [])]
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""

            # Grouped Breakdown for alerts
            if is_breakdown or any(k in q for k in ["group", "grouping", "grouped", "breakdown", "distribution"]):
                if any(k in q for k in ["camera", "cam"]) and "camera_id" in alert_cols:
                    return f"SELECT camera_id, count(*) AS alert_count FROM {alert_table} {where_clause}GROUP BY camera_id ORDER BY alert_count DESC LIMIT 10"
                if any(k in q for k in ["type", "alert_type"]) and "alert_type" in alert_cols:
                    return f"SELECT alert_type, count(*) AS alert_count FROM {alert_table} {where_clause}GROUP BY alert_type ORDER BY alert_count DESC"
                if "severity" in alert_cols:
                    return f"SELECT severity, count(*) AS alert_count FROM {alert_table} {where_clause}GROUP BY severity ORDER BY alert_count DESC"

            if is_count:
                return f"SELECT count(*) AS total_alerts FROM {alert_table} {where_clause}".strip()
            cols = get_display_columns(alert_table)
            return f"SELECT {cols} FROM {alert_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 3. PPE & General Detections
        # -------------------------------------------------------------
        target_det = ppe_table or det_table
        if (any(k in q for k in ["ppe", "helmet", "vest", "safety"]) or (det_table and "detection" in q)) and target_det:
            t_info = table_dict.get(target_det.lower(), {})
            col_names = [c["name"].lower() for c in t_info.get("columns", [])]
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""

            # Breakdown by missing PPE or objectname or camera
            if is_breakdown or any(k in q for k in ["missing", "types", "violations", "by object"]):
                group_col = "missing_ppe" if "missing_ppe" in col_names else ("objectname" if "objectname" in col_names else "camera")
                return f"SELECT {group_col}, count(*) AS total_count FROM {target_det} {where_clause}GROUP BY {group_col} ORDER BY total_count DESC"
            # PPE grouped by camera
            if any(k in q for k in ["by camera", "per camera"]) and "camera" in col_names:
                camloc_col = ", camloc" if "camloc" in col_names else ""
                return f"SELECT camera{camloc_col}, count(*) AS violation_count FROM {target_det} {where_clause}GROUP BY camera{camloc_col} ORDER BY violation_count DESC"
            # Count PPE / Detections
            if is_count:
                return f"SELECT count(*) AS total_{target_det} FROM {target_det} {where_clause}".strip()
            # List detection records
            cols = get_display_columns(target_det)
            return f"SELECT {cols} FROM {target_det} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 4. Fire & Smoke
        # -------------------------------------------------------------
        if ("fire" in q or "smoke" in q) and fire_table:
            t_info = table_dict.get(fire_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            if is_count:
                return f"SELECT count(*) AS total_fire_smoke_alerts FROM {fire_table} {where_clause}".strip()
            cols = get_display_columns(fire_table)
            return f"SELECT {cols} FROM {fire_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 5. Mobile Phone Usage
        # -------------------------------------------------------------
        if ("mobile" in q or "phone" in q or "usage" in q) and mobile_table:
            t_info = table_dict.get(mobile_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            if is_count:
                return f"SELECT count(*) AS total_mobile_usage_events FROM {mobile_table} {where_clause}".strip()
            cols = get_display_columns(mobile_table)
            return f"SELECT {cols} FROM {mobile_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 6. Person Fall Detection
        # -------------------------------------------------------------
        if ("fall" in q or ("person" in q and "attendance" not in q and "employee" not in q)) and fall_table:
            t_info = table_dict.get(fall_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            if is_count:
                return f"SELECT count(*) AS total_person_fall_events FROM {fall_table} {where_clause}".strip()
            cols = get_display_columns(fall_table)
            return f"SELECT {cols} FROM {fall_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 7. ANPR / Vehicle Detection
        # -------------------------------------------------------------
        if ("anpr" in q or "vehicle" in q or "car" in q or "plate" in q) and anpr_table:
            t_info = table_dict.get(anpr_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            if is_count:
                return f"SELECT count(*) AS total_vehicle_detections FROM {anpr_table} {where_clause}".strip()
            cols = get_display_columns(anpr_table)
            return f"SELECT {cols} FROM {anpr_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 8. Camera Tampering
        # -------------------------------------------------------------
        if ("tamper" in q or "tempering" in q) and tamper_table:
            t_info = table_dict.get(tamper_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            if is_count:
                return f"SELECT count(*) AS total_camera_tampering FROM {tamper_table} {where_clause}".strip()
            cols = get_display_columns(tamper_table)
            return f"SELECT {cols} FROM {tamper_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 9. Employee / Attendance
        # -------------------------------------------------------------
        if ("attendance" in q or "employee" in q or "worker" in q) and att_table:
            t_info = table_dict.get(att_table.lower(), {})
            d_col = get_table_date_col(t_info)
            where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
            where_clause = f"WHERE {where} " if where else ""
            cols = get_display_columns(att_table)
            if is_count:
                return f"SELECT count(*) AS total_attendance_records FROM {att_table} {where_clause}".strip()
            return f"SELECT {cols} FROM {att_table} {where_clause}ORDER BY id DESC LIMIT 20"

        # -------------------------------------------------------------
        # 10. Direct Table Name Mention (exact or normalized)
        # -------------------------------------------------------------
        for t_name in all_table_names:
            clean_t = t_name.replace("_", " ")
            if t_name in q or clean_t in q:
                t_info = table_dict.get(t_name.lower(), {})
                d_col = get_table_date_col(t_info)
                where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
                where_clause = f"WHERE {where} " if where else ""
                if is_count:
                    return f"SELECT count(*) AS total_{t_name} FROM {t_name} {where_clause}".strip()
                cols = get_display_columns(t_name)
                return f"SELECT {cols} FROM {t_name} {where_clause}LIMIT 20"

        # -------------------------------------------------------------
        # 11. Global Overview / Stats / Summary
        # -------------------------------------------------------------
        if any(k in q for k in ["overview", "summary", "stats", "statistics", "all tables", "database", "dashboard"]):
            summary_parts = []
            for t_name, label in feature_tables:
                d_col = get_table_date_col(table_dict.get(t_name))
                where = build_date_where_clause(d_col, target_date, is_today, is_yesterday, is_week, is_month, dialect)
                where_sql = f" WHERE {where}" if where else ""
                summary_parts.append(f"SELECT '{label}' AS feature, count(*) AS total_count FROM {t_name}{where_sql}")
            if summary_parts:
                return " UNION ALL ".join(summary_parts)

        # 12. No matching heuristic pattern found
        return ""

    def _find_table(self, table_names: List[str], candidates: List[str]) -> Optional[str]:
        """Finds the best matching table name from candidates with exact match priority."""
        for c in candidates:
            for t in table_names:
                if c.lower() == t.lower():
                    return t
        for c in candidates:
            for t in table_names:
                if c.lower() in t.lower() and not ("camera" in t.lower() and "camera" not in c.lower()):
                    return t
        for c in candidates:
            for t in table_names:
                if c.lower() in t.lower():
                    return t
        return None

sql_generator = SQLGenerator()
