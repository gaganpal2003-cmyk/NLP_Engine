# Web Team Integration Guide: NLP Analytics Chatbot API

This guide provides everything the frontend/web team needs to connect your surveillance, detection, and alert web dashboard to the **NLP Analytics API Engine** using your **API URL** and **API Key**.

---

## 🚀 Key Integration Concept

Just like the **PPE / Detection Engine**, the web team only needs two configuration parameters:
1. **`API_URL`**: The base URL of the running NLP Engine (e.g., `http://<SERVER_IP>:8000`).
2. **`API_KEY`**: The client API key issued for your specific dashboard (e.g., `cairo_nlp_default` or `nlp_live_bothra_xxxx`).

> **How it works**: The API Key identifies your dashboard and automatically routes natural language queries to your **exact database** (where your PPE detections, alerts, cameras, and events are stored).

---

## ⚡ Option 1: Drop-In Embeddable Chat Widget (1-Line Integration)

The fastest way to add the chatbot to your web dashboard is using our pre-built, floating dark-mode widget. Simply add this script to your HTML:

```html
<!-- Add before closing </body> tag in your dashboard -->
<script 
  src="http://localhost:8000/static/widget.js" 
  data-api-url="http://localhost:8000" 
  data-api-key="cairo_nlp_default"
  data-title="Surveillance Analytics Assistant"
  data-theme="dark"
  data-position="bottom-right">
</script>
```

### Configurable Attributes:
| Attribute | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data-api-url` | `string` | Current origin | Base URL of the NLP Engine API |
| `data-api-key` | `string` | `cairo_nlp_default` | Your client API key mapped to your database |
| `data-title` | `string` | `Surveillance Analytics Assistant` | Header title of the chat window |
| `data-theme` | `string` | `dark` | Visual theme (`dark` or `light`) |
| `data-position`| `string` | `bottom-right` | Launcher position (`bottom-right` or `bottom-left`) |

---

## 🔌 Option 2: Custom Dashboard Frontend Integration (REST API)

If you are building a custom UI or integrating into React, Vue, Angular, or jQuery, use the REST API endpoints below.

### 2.1 Main Chatbot Endpoint: `POST /api/chat`
Translates user natural language questions into safe read-only SQL, queries your mapped database, and returns synthesized answers + raw data + optional chart configuration.

#### Request Headers
```http
POST /api/chat HTTP/1.1
Host: localhost:8000
Content-Type: application/json
X-API-Key: cairo_nlp_default
```
*(You can also use `Authorization: Bearer <API_KEY>` or query parameter `?api_key=<API_KEY>`)*

#### Request Payload
```json
{
  "message": "How many PPE detections were recorded today?",
  "session_id": "optional-user-session-id"
}
```

#### Successful Response (`200 OK`)
```json
{
  "answer": "There are **18 PPE detections** recorded today.",
  "sql_query": "SELECT count(*) AS ppe_detections_today FROM bothra_ppe_detection_detection WHERE DATE(date) = CURRENT_DATE;",
  "data": [
    {
      "ppe_detections_today": 18
    }
  ],
  "columns": [
    "ppe_detections_today"
  ],
  "row_count": 1,
  "execution_time_ms": 6.2,
  "chart_config": null,
  "session_id": "optional-user-session-id",
  "client_name": "Default Dashboard (Bothra / FRS)"
}
```

#### Response with Chart Recommendation (e.g., Breakdown Queries)
When the user asks for distributions or categories (e.g. *"Show missing PPE breakdown"*), `chart_config` is automatically returned:
```json
{
  "answer": "Here is the breakdown of missing PPE items...",
  "chart_config": {
    "type": "doughnut",
    "title": "Count by Missing Ppe",
    "labels": ["No Helmet", "No Vest", "No Gloves"],
    "values": [42.0, 28.0, 15.0],
    "label_name": "Missing Ppe",
    "value_name": "Count"
  }
}
```

---

### 2.2 Streaming Chatbot Endpoint: `POST /api/chat/stream`
Uses **Server-Sent Events (SSE)** for a typewriter streaming effect in your chat widget.

#### JavaScript Frontend Example:
```javascript
async function streamChatbot(question, onMeta, onToken, onDone) {
  const response = await fetch("http://localhost:8000/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": "cairo_nlp_default"
    },
    body: JSON.stringify({ message: question }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n\n");
    buffer = lines.pop(); // keep partial

    for (const block of lines) {
      if (!block.trim()) continue;
      const eventMatch = block.match(/event:\s*(\w+)/);
      const dataMatch = block.match(/data:\s*(.+)/);
      if (!eventMatch || !dataMatch) continue;

      const event = eventMatch[1];
      const payload = JSON.parse(dataMatch[1]);

      if (event === "meta" && onMeta) onMeta(payload);
      if (event === "token" && onToken) onToken(payload.chunk);
      if (event === "done" && onDone) onDone();
    }
  }
}
```

---

### 2.3 Verify API Key & Database Status: `GET /api/auth/verify`
Use this endpoint during dashboard initialization to confirm the API key is active and connected to the database:

```bash
curl -X GET "http://localhost:8000/api/auth/verify" \
  -H "X-API-Key: cairo_nlp_default"
```

**Response:**
```json
{
  "status": "valid",
  "api_key_masked": "cairo_...ault",
  "client_name": "Default Dashboard (Bothra / FRS)",
  "database": {
    "connected": true,
    "dialect": "mysql",
    "error": null
  }
}
```

---

### 2.4 Introspected Database Schema: `GET /api/database/schema`
Returns all tables, columns, data types, and row count estimates for the connected client database:

```bash
curl -X GET "http://localhost:8000/api/database/schema" \
  -H "X-API-Key: cairo_nlp_default"
```

---

## 🛠️ API Key Management (Admin)

### Generating or Mapping a New API Key to a Client Database

To register a new dashboard or client database:

#### Method A: Via Command Line (CLI)
```powershell
python -m database.tenant_manager create "Client B Dashboard" "mysql+pymysql://root:pass@192.168.1.50:3306/client_b_db"
```

#### Method B: Via Admin REST Endpoint
```bash
curl -X POST "http://localhost:8000/api/admin/keys" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: cairo_admin_secret_key" \
  -d '{
    "client_name": "Bothra Surveillance Dashboard",
    "database_url": "mysql+pymysql://root:cairo$123@localhost:3306/bothera_db",
    "api_key": "nlp_live_bothra_123"
  }'
```

#### List All Registered API Keys
```bash
curl -X GET "http://localhost:8000/api/admin/keys" \
  -H "X-Admin-Key: cairo_admin_secret_key"
```

---

## ⚠️ Error Codes & Handling

| HTTP Status | Error Detail | Solution |
| :--- | :--- | :--- |
| `401 Unauthorized` | Missing API Key | Pass `X-API-Key: <key>` header in your requests |
| `401 Unauthorized` | Invalid or revoked API Key | Verify key is registered in `data/tenants.json` or create via `/api/admin/keys` |
| `400 Bad Request` | Security/Validation Error | Natural language generated a query with disallowed keywords (`DROP`, `DELETE`) |
| `400 Bad Request` | Database execution error | Target database connection was lost or table schema mismatch |
| `500 Server Error` | Internal Server Error | Verify NLP Engine server logs |
