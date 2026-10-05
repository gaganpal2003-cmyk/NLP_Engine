// Web Dashboard NLP Engine Chatbot Frontend Logic

document.addEventListener("DOMContentLoaded", () => {
  const chatStream = document.getElementById("chatStream");
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const sendBtn = document.getElementById("sendBtn");
  const tableList = document.getElementById("tableList");

  // Status Elements
  const statusDot = document.getElementById("statusDot");
  const statusTitle = document.getElementById("statusTitle");
  const dbDialect = document.getElementById("dbDialect");
  const dbTablesCount = document.getElementById("dbTablesCount");
  const llmStatusBadge = document.getElementById("llmStatusBadge");

  // Modals
  const dbModal = document.getElementById("dbModal");
  const llmModal = document.getElementById("llmModal");
  const openDbModalBtn = document.getElementById("openDbModalBtn");
  const openLlmModalBtn = document.getElementById("openLlmModalBtn");
  const closeDbModal = document.getElementById("closeDbModal");
  const closeLlmModal = document.getElementById("closeLlmModal");
  const cancelDbBtn = document.getElementById("cancelDbBtn");
  const cancelLlmBtn = document.getElementById("cancelLlmBtn");
  const dbConnectForm = document.getElementById("dbConnectForm");
  const llmConfigForm = document.getElementById("llmConfigForm");

  let chartCounter = 0;

  // Initialize
  fetchHealth();
  fetchSchema();

  // Polling / Periodic Health Check
  async function fetchHealth() {
    try {
      const res = await fetch("/api/health", { headers: { "X-Demo-UI": "true" } });
      const data = await res.json();
      if (data.database.connected) {
        statusDot.className = "status-indicator online";
        statusTitle.textContent = "Live Connected";
        dbDialect.textContent = data.database.dialect.toUpperCase();
      } else {
        statusDot.className = "status-indicator offline";
        statusTitle.textContent = "DB Disconnected";
        dbDialect.textContent = "Error";
      }

      if (data.llm.configured) {
        llmStatusBadge.textContent = data.llm.model;
        llmStatusBadge.style.color = "var(--accent-emerald)";
      } else {
        llmStatusBadge.textContent = "Heuristic (Ready)";
        llmStatusBadge.style.color = "var(--accent-amber)";
      }
    } catch (err) {
      statusDot.className = "status-indicator offline";
      statusTitle.textContent = "API Offline";
    }
  }

  async function fetchSchema() {
    try {
      const res = await fetch("/api/database/schema", { headers: { "X-Demo-UI": "true" } });
      const data = await res.json();
      dbTablesCount.textContent = data.table_count || 0;

      tableList.innerHTML = "";
      if (data.tables && data.tables.length > 0) {
        data.tables.forEach((t) => {
          const item = document.createElement("div");
          item.className = "table-item";
          item.innerHTML = `
            <span>${t.table_name}</span>
            <span class="table-rows-badge">${t.row_count} rows</span>
          `;
          tableList.appendChild(item);
        });
      } else {
        tableList.innerHTML = `<div style="font-size:0.8rem;color:var(--text-muted);">No tables detected</div>`;
      }
    } catch (err) {
      tableList.innerHTML = `<div style="font-size:0.8rem;color:var(--accent-rose);">Failed to load schema</div>`;
    }
  }

  // Handle Chat Submit
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    // Append User Message
    appendUserMessage(query);
    userInput.value = "";
    sendBtn.disabled = true;

    // Append Typing Indicator
    const typingId = appendTypingIndicator();
    scrollToBottom();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Demo-UI": "true"
        },
        body: JSON.stringify({ message: query }),
      });
      const data = await res.json();

      // Remove typing indicator
      removeElement(typingId);

      // Append Assistant Response
      appendAssistantMessage(data);
    } catch (err) {
      removeElement(typingId);
      appendAssistantMessage({
        answer: `❌ **Network Connection Error**: Unable to contact the NLP Engine API. (${err.message})`,
        sql_query: null,
        data: [],
        columns: [],
      });
    } finally {
      sendBtn.disabled = false;
      scrollToBottom();
    }
  });

  // Quick Chips Click Handler
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      userInput.value = prompt;
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
      <div class="avatar">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </div>
      <div class="message-content">
        <div class="bubble">
          <p>${escapeHtml(text)}</p>
        </div>
      </div>
    `;
    chatStream.appendChild(row);
  }

  function appendTypingIndicator() {
    const id = "typing-" + Date.now();
    const row = document.createElement("div");
    row.id = id;
    row.className = "message-row assistant";
    row.innerHTML = `
      <div class="avatar">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <div class="message-content">
        <div class="bubble">
          <div class="typing-dots">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>
    `;
    chatStream.appendChild(row);
    return id;
  }

  function appendAssistantMessage(resp) {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    const msgId = "msg-" + Date.now();

    const formattedAnswer = formatMarkdown(resp.answer);

    let traysHtml = "";
    if (resp.sql_query || (resp.data && resp.data.length > 0)) {
      traysHtml = `
        <div class="result-trays">
          <div class="tray-buttons">
            ${
              resp.sql_query
                ? `<button class="tray-toggle" data-toggle="sql-${msgId}">
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
                    Executed SQL (${resp.execution_time_ms}ms)
                  </button>`
                : ""
            }
            ${
              resp.data && resp.data.length > 0
                ? `<button class="tray-toggle" data-toggle="data-${msgId}">
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
                    Raw Data (${resp.row_count} rows)
                  </button>`
                : ""
            }
          </div>
          ${
            resp.sql_query
              ? `<div id="sql-${msgId}" class="tray-panel"><code>${escapeHtml(resp.sql_query)}</code></div>`
              : ""
          }
          ${
            resp.data && resp.data.length > 0
              ? `<div id="data-${msgId}" class="tray-panel">${renderDataTable(resp.columns, resp.data)}</div>`
              : ""
          }
        </div>
      `;
    }

    let chartContainerHtml = "";
    let chartCanvasId = "";
    if (resp.chart_config) {
      chartCanvasId = "chart-" + (++chartCounter);
      chartContainerHtml = `
        <div class="chart-box">
          <canvas id="${chartCanvasId}"></canvas>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="avatar">
        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      </div>
      <div class="message-content">
        <div class="bubble">
          ${formattedAnswer}
          ${chartContainerHtml}
          ${traysHtml}
        </div>
      </div>
    `;

    chatStream.appendChild(row);

    // Render Chart.js if present
    if (resp.chart_config && chartCanvasId) {
      setTimeout(() => renderChart(chartCanvasId, resp.chart_config), 50);
    }

    // Attach tray toggle handlers
    row.querySelectorAll(".tray-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-toggle");
        const panel = document.getElementById(targetId);
        if (panel) {
          panel.classList.toggle("open");
        }
      });
    });
  }

  function renderChart(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const colors = [
      "#06b6d4", "#3b82f6", "#10b981", "#f59e0b",
      "#f43f5e", "#8b5cf6", "#ec4899", "#14b8a6"
    ];

    new Chart(ctx, {
      type: config.type || "bar",
      data: {
        labels: config.labels,
        datasets: [
          {
            label: config.value_name || "Value",
            data: config.values,
            backgroundColor: config.type === "doughnut" ? colors : "rgba(6, 182, 212, 0.7)",
            borderColor: config.type === "doughnut" ? "#111827" : "#06b6d4",
            borderWidth: 1.5,
            borderRadius: config.type === "bar" ? 6 : 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: config.type === "doughnut",
            labels: { color: "#94a3b8", font: { family: "Inter" } },
          },
          title: {
            display: true,
            text: config.title || "Chart Analytics",
            color: "#f8fafc",
            font: { size: 13, family: "Inter", weight: "600" },
          },
        },
        scales: config.type === "bar" ? {
          x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
          y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        } : undefined,
      },
    });
  }

  function renderDataTable(columns, rows) {
    if (!rows || rows.length === 0) return "<p>No data</p>";
    let html = "<table><thead><tr>";
    columns.forEach((c) => {
      html += `<th>${escapeHtml(c)}</th>`;
    });
    html += "</tr></thead><tbody>";
    rows.slice(0, 25).forEach((r) => {
      html += "<tr>";
      columns.forEach((c) => {
        html += `<td>${escapeHtml(String(r[c] !== undefined ? r[c] : ""))}</td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    return html;
  }

  function formatMarkdown(text) {
    if (!text) return "";

    // 1. Process markdown tables into structured HTML
    const lines = text.split("\n");
    let inTable = false;
    let tableHtml = "";
    const processed = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      const isTableRow = line.startsWith("|") && line.endsWith("|");
      const isSeparator = isTableRow && /^\|(\s*:?-+:?\s*\|)+$/.test(line);

      if (isTableRow) {
        if (!inTable) {
          inTable = true;
          tableHtml = '<div class="table-responsive"><table class="markdown-table"><thead>';
          const cells = line.slice(1, -1).split("|").map((c) => c.trim());
          tableHtml += "<tr>" + cells.map((c) => `<th>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
        } else if (isSeparator) {
          // Skip markdown separator row (|---|---|)
          continue;
        } else {
          const cells = line.slice(1, -1).split("|").map((c) => c.trim());
          tableHtml += "<tr>" + cells.map((c) => `<td>${escapeHtml(c)}</td>`).join("") + "</tr>";
        }
      } else {
        if (inTable) {
          tableHtml += "</tbody></table></div>";
          processed.push(tableHtml);
          inTable = false;
          tableHtml = "";
        }
        processed.push(line);
      }
    }
    if (inTable) {
      tableHtml += "</tbody></table></div>";
      processed.push(tableHtml);
    }

    let html = processed.join("\n");

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Italics
    html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
    // Inline code
    html = html.replace(/`(.*?)`/g, "<code style='background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px;color:#38bdf8;'>$1</code>");
    // Markdown list items
    html = html.replace(/^\s*-\s+(.*)$/gm, "<li>$1</li>");
    html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
    
    // Paragraphs
    html = html.split("\n\n").map((p) => {
      const trimmed = p.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("<div class=\"table-responsive\"") || trimmed.startsWith("<ul>")) {
        return trimmed;
      }
      return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
    }).join("");

    return html;
  }

  function escapeHtml(string) {
    return String(string)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function scrollToBottom() {
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  // Modals logic
  openDbModalBtn.addEventListener("click", () => dbModal.classList.add("open"));
  closeDbModal.addEventListener("click", () => dbModal.classList.remove("open"));
  cancelDbBtn.addEventListener("click", () => dbModal.classList.remove("open"));

  openLlmModalBtn.addEventListener("click", () => llmModal.classList.add("open"));
  closeLlmModal.addEventListener("click", () => llmModal.classList.remove("open"));
  cancelLlmBtn.addEventListener("click", () => llmModal.classList.remove("open"));

  // Connect Database Form
  dbConnectForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("dbUrlInput").value.trim();
    const payload = url ? { url } : {
      db_type: document.getElementById("dbTypeSelect").value,
      host: document.getElementById("dbHostInput").value,
      port: parseInt(document.getElementById("dbPortInput").value),
      user: document.getElementById("dbUserInput").value,
      password: document.getElementById("dbPassInput").value,
      db_name: document.getElementById("dbNameInput").value,
    };

    const saveBtn = document.getElementById("saveDbBtn");
    saveBtn.disabled = true;
    saveBtn.textContent = "Connecting...";

    try {
      const res = await fetch("/api/database/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        alert(`Successfully connected! Found ${data.tables_found} tables in database.`);
        dbModal.classList.remove("open");
        fetchHealth();
        fetchSchema();
      } else {
        alert(`Connection Failed: ${data.detail || "Error connecting"}`);
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Connect & Inspect Schema";
    }
  });

  // LLM Config Form
  llmConfigForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      api_key: document.getElementById("llmApiKeyInput").value.trim(),
      base_url: document.getElementById("llmBaseUrlInput").value.trim(),
      model: document.getElementById("llmModelInput").value.trim(),
    };

    try {
      const res = await fetch("/api/config/llm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        alert("LLM Provider updated successfully!");
        llmModal.classList.remove("open");
        fetchHealth();
      } else {
        alert("Failed to update LLM configuration.");
      }
    } catch (err) {
      alert("Error: " + err.message);
    }
  });
});
