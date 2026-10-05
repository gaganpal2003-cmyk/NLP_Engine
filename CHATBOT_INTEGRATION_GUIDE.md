# 📖 Complete Developer Integration Guide: NLP Database Chatbot API

Welcome to the **NLP Analytics & Database Chatbot Engine**. This guide is prepared for developers, web teams, and application engineers who want to integrate natural-language querying into their **Websites, Dashboards, or Desktop Applications** using your **API URL** and **API Key**.

---

## 🚀 Quick Credentials Summary

To connect your application, you only need two configuration values:

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **`API_URL`** | `https://nlp-engine-bjmy.onrender.com` | Base URL of the live hosted AI Engine |
| **`API_KEY`** | `<YOUR_ASSIGNED_API_KEY>` | Secret key mapped to your client database |
| **`Interactive Docs`** | [https://nlp-engine-bjmy.onrender.com/docs](https://nlp-engine-bjmy.onrender.com/docs) | Interactive Swagger API testing interface |

---

## 🗄️ How to Connect or Change Your Database

Each user or client can query their **own database**. There are three ways you can specify which database the chatbot should query:

### Method 1: On-the-Fly via HTTP Header (`X-Database-URL`) — Most Flexible
You can pass your database connection string directly in the request header with every API call. This allows you to switch databases instantly without changing any server settings:

```http
X-API-Key: <YOUR_API_KEY>
X-Database-URL: mysql+pymysql://username:password@your-db-host:3306/your_database_name
```

### Method 2: Self-Service Registration (Get Your Own Dedicated API Key)
You can register your database connection once, and the server will issue you a unique permanent `API_KEY`:

```bash
curl -X POST https://nlp-engine-bjmy.onrender.com/api/tenants/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Company Surveillance",
    "database_url": "mysql+pymysql://db_user:secret_pass@db.mycompany.com:3306/security_db"
  }'
```

**Response received:**
```json
{
  "status": "success",
  "api_url": "https://nlp-engine-bjmy.onrender.com",
  "api_key": "nlp_live_a1b2c3d4e5f6...",
  "client_name": "My Company Surveillance",
  "database": {
    "connected": true,
    "dialect": "mysql"
  }
}
```
*From now on, any request using this `api_key` automatically queries `security_db`.*

### Method 3: Pre-Configured API Key
The server administrator maps your API Key (e.g. `nlp_talabira_crowd` or `nlp_live_bothra_123`) directly to your database in `tenants.json`.

---

## 🌐 Database Connection String Format

The engine supports **MySQL**, **MariaDB**, **PostgreSQL**, and **SQLite**:

```text
# MySQL / MariaDB:
mysql+pymysql://<user>:<password>@<host>:<port>/<database_name>

# PostgreSQL:
postgresql://<user>:<password>@<host>:<port>/<database_name>

# SQLite:
sqlite:///./data/detections.db
```

> **Important Cloud Networking Note**: Because the engine is hosted in the cloud, your database host must be accessible over the internet (e.g. AWS RDS, DigitalOcean Managed DB, cloud VPS with port 3306 open). If your database is only on your personal laptop (`localhost`), you can expose it using a free tunnel like [ngrok](https://ngrok.com/) (`ngrok tcp 3306`).

---

## 💻 Integration Examples (Choose Your Platform)

---

### Option 1: 1-Line Drop-In Widget (For Websites & Web Dashboards)
Zero frontend coding required. Add this script tag just before the closing `</body>` tag on any HTML, PHP, or WordPress page:

```html
<!-- Drop-in Floating AI Chatbot Widget -->
<script 
  src="https://nlp-engine-bjmy.onrender.com/static/widget.js" 
  data-api-url="https://nlp-engine-bjmy.onrender.com" 
  data-api-key="<YOUR_API_KEY>"
  data-title="Surveillance Analytics AI"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

#### Widget Attributes:
| Attribute | Description | Default |
| :--- | :--- | :--- |
| `data-api-url` | Base URL of the NLP API | `https://nlp-engine-bjmy.onrender.com` |
| `data-api-key` | Your client API key | Required |
| `data-title` | Title shown in chat window header | `Surveillance Analytics Assistant` |
| `data-theme` | Visual theme (`dark` or `light`) | `dark` |
| `data-position`| Screen position (`bottom-right` or `bottom-left`) | `bottom-right` |

---

### Option 2: JavaScript / React / Next.js / Vue (Custom Frontend)
If you want to build your own custom chat UI:

```javascript
/**
 * Sends a user question to the NLP Chatbot API Engine.
 * @param {string} userMessage - Natural language question
 * @returns {Promise<object>} Chatbot response object
 */
async function askChatbot(userMessage) {
  const API_URL = "https://nlp-engine-bjmy.onrender.com";
  const API_KEY = "<YOUR_API_KEY>";

  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      // Optional: uncomment below to dynamically specify a custom database:
      // "X-Database-URL": "mysql+pymysql://user:pass@host:3306/dbname"
    },
    body: JSON.stringify({
      message: userMessage,
      session_id: "user-session-123" // optional
    })
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const data = await response.json();

  console.log("AI Answer:", data.answer);
  console.log("Generated SQL:", data.sql_query);
  console.log("Raw Database Rows:", data.data);
  console.log("Row Count:", data.row_count);
  
  // If the query returned breakdown/category data, Chart.js config is generated automatically:
  if (data.chart_config) {
    console.log("Chart Data:", data.chart_config);
  }

  return data;
}
```

---

### Option 3: Python Desktop App (PyQt5 / PySide / Tkinter)
For desktop surveillance and analytics applications (e.g. PyQt5):

```python
import requests

class NLPClient:
    def __init__(self, api_url="https://nlp-engine-bjmy.onrender.com", api_key="<YOUR_API_KEY>", timeout=15):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def ask(self, message: str, database_url: str = None) -> dict:
        """
        Sends a natural language question to the NLP API engine.
        Returns dict with: answer, sql_query, data, columns, execution_time_ms.
        """
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        if database_url:
            headers["X-Database-URL"] = database_url

        payload = {"message": message}

        try:
            response = requests.post(
                f"{self.api_url}/api/chat",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "answer": f"Connection error: {str(e)}",
                "sql_query": None,
                "data": []
            }

# Usage:
client = NLPClient()
result = client.ask("How many cameras are offline?")
print("Answer:", result["answer"])
print("Executed SQL:", result["sql_query"])
```

---

### Option 4: Python Backend / CLI / Scripts
```python
import requests

API_URL = "https://nlp-engine-bjmy.onrender.com"
API_KEY = "<YOUR_API_KEY>"

response = requests.post(
    f"{API_URL}/api/chat",
    headers={"X-API-Key": API_KEY},
    json={"message": "Show total detections recorded today"}
)

data = response.json()
print("Answer:\n", data["answer"])
```

---

### Option 5: PHP / Laravel / WordPress
```php
<?php
$apiUrl = "https://nlp-engine-bjmy.onrender.com/api/chat";
$apiKey = "<YOUR_API_KEY>";

$payload = json_encode([
    "message" => "Show all offline cameras"
]);

$ch = curl_init($apiUrl);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Content-Type: application/json",
    "X-API-Key: " . $apiKey
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

$response = curl_exec($ch);
curl_close($ch);

$result = json_decode($response, true);
echo $result['answer'];
?>
```

---

## 📡 API Endpoints Reference

### 1. Main Chat Query: `POST /api/chat`
Translates user natural language into safe, read-only SQL, executes it against the client's mapped database, and returns a human-friendly answer.

- **URL**: `https://nlp-engine-bjmy.onrender.com/api/chat`
- **Method**: `POST`
- **Headers**:
  - `Content-Type: application/json`
  - `X-API-Key: <YOUR_API_KEY>`
  - `X-Database-URL: <OPTIONAL_CUSTOM_DB_URL>`
- **Request Body**:
  ```json
  {
    "message": "How many critical alerts happened today?",
    "session_id": "optional-session-id"
  }
  ```

#### Response Structure (`200 OK`):
```json
{
  "answer": "There are **12 critical alerts** recorded today across all cameras.",
  "sql_query": "SELECT count(*) AS total_alerts FROM alerts WHERE severity = 'critical' AND DATE(created_at) = CURRENT_DATE;",
  "data": [
    {
      "total_alerts": 12
    }
  ],
  "columns": ["total_alerts"],
  "row_count": 1,
  "execution_time_ms": 4.8,
  "chart_config": null,
  "client_name": "My Company Surveillance"
}
```

---

### 2. Live Typewriter Streaming: `POST /api/chat/stream`
Server-Sent Events (SSE) streaming endpoint for displaying a real-time typing effect in your web dashboard.

- **URL**: `https://nlp-engine-bjmy.onrender.com/api/chat/stream`
- **Events Emitted**:
  - `event: meta` — Contains metadata (SQL query, chart config, execution time).
  - `event: token` — Chunks of the answer string for typewriter effect.
  - `event: done` — Signals completion.

---

### 3. Verify Connection: `GET /api/auth/verify`
Tests whether your API key is valid and checks connection to your target database.

- **URL**: `https://nlp-engine-bjmy.onrender.com/api/auth/verify`
- **Method**: `GET`
- **Headers**: `X-API-Key: <YOUR_API_KEY>`

#### Response:
```json
{
  "status": "valid",
  "client_name": "My Company Surveillance",
  "database": {
    "connected": true,
    "dialect": "mysql",
    "error": null
  }
}
```

---

### 4. Introspect Schema: `GET /api/database/schema`
Returns all tables, column names, and data types currently detected in your database.

- **URL**: `https://nlp-engine-bjmy.onrender.com/api/database/schema`
- **Method**: `GET`
- **Headers**: `X-API-Key: <YOUR_API_KEY>`

---

## 🔒 Security & Guardrails

The engine is engineered with enterprise security guardrails:
1. **Strict Read-Only AST Validation**: Every query is parsed via AST (`sqlglot`). All `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, and multi-statement injection attacks are blocked.
2. **Row Limits**: Multi-row queries automatically enforce `LIMIT 100` to prevent memory exhaustion.
3. **Sensitive Columns**: Binary BLOB columns (`snapshot`, `imagedata`, `face_encoding`) are automatically excluded from `SELECT` queries to keep payloads lightweight.
4. **Gibberish Protection**: Random keystrokes (e.g. `dfgerg`, `asdf`) or greetings do not invent fake queries; they are answered with helpful guidance.
