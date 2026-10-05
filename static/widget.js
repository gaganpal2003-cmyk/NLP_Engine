/**
 * Cairo NLP Analytics Chatbot - Embeddable Floating Web Widget
 * 
 * Usage for Web Team:
 * <script 
 *   src="http://<API_HOST>:8000/static/widget.js" 
 *   data-api-url="http://<API_HOST>:8000" 
 *   data-api-key="nlp_live_bothra_xxxx"
 *   data-title="Surveillance Analytics"
 *   data-theme="dark"
 *   data-position="bottom-right">
 * </script>
 */

(function () {
  "use strict";

  // Find the script tag and read configurations
  const scriptTag = document.currentScript || document.querySelector('script[data-api-key]');
  const API_URL = (scriptTag?.getAttribute("data-api-url") || window.location.origin).replace(/\/$/, "");
  const API_KEY = scriptTag?.getAttribute("data-api-key") || "cairo_nlp_default";
  const WIDGET_TITLE = scriptTag?.getAttribute("data-title") || "Surveillance Analytics Assistant";
  const POSITION = scriptTag?.getAttribute("data-position") || "bottom-right";
  const THEME = scriptTag?.getAttribute("data-theme") || "dark";

  // Prevent multiple injections
  if (document.getElementById("cairo-chatbot-root")) return;

  // Scoped CSS styles
  const styles = `
    #cairo-chatbot-root {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #e2e8f0;
      position: fixed;
      z-index: 999999;
      ${POSITION === "bottom-left" ? "left: 24px;" : "right: 24px;"}
      bottom: 24px;
    }

    #cairo-chatbot-root * {
      box-sizing: border-box;
    }

    /* Floating Launcher Button */
    .cairo-chat-launcher {
      width: 58px;
      height: 58px;
      border-radius: 50%;
      background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
      box-shadow: 0 10px 25px rgba(29, 78, 216, 0.45);
      border: 2px solid rgba(255, 255, 255, 0.2);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .cairo-chat-launcher:hover {
      transform: scale(1.08) translateY(-2px);
      box-shadow: 0 15px 30px rgba(29, 78, 216, 0.6);
    }

    .cairo-chat-launcher svg {
      width: 26px;
      height: 26px;
      fill: currentColor;
    }

    /* Chat Window Container */
    .cairo-chat-window {
      position: absolute;
      bottom: 70px;
      ${POSITION === "bottom-left" ? "left: 0;" : "right: 0;"}
      width: 420px;
      height: 600px;
      max-width: calc(100vw - 32px);
      max-height: calc(100vh - 100px);
      background: #0f172a;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 18px;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6), 0 0 1px rgba(255, 255, 255, 0.2);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      opacity: 0;
      transform: translateY(20px) scale(0.96);
      pointer-events: none;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .cairo-chat-window.open {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }

    /* Header */
    .cairo-chat-header {
      background: #1e293b;
      padding: 14px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .cairo-chat-title-group {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .cairo-chat-badge {
      width: 10px;
      height: 10px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
    }

    .cairo-chat-title {
      font-weight: 600;
      font-size: 15px;
      color: #f8fafc;
    }

    .cairo-chat-subtitle {
      font-size: 11px;
      color: #94a3b8;
    }

    .cairo-chat-close-btn {
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      padding: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      transition: background 0.2s;
    }

    .cairo-chat-close-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }

    /* Message Stream */
    .cairo-chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .cairo-msg {
      display: flex;
      gap: 10px;
      max-width: 90%;
    }

    .cairo-msg.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .cairo-msg.assistant {
      align-self: flex-start;
    }

    .cairo-msg-bubble {
      padding: 10px 14px;
      border-radius: 14px;
      line-height: 1.45;
      font-size: 13.5px;
      word-break: break-word;
    }

    .cairo-msg.user .cairo-msg-bubble {
      background: #2563eb;
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }

    .cairo-msg.assistant .cairo-msg-bubble {
      background: #1e293b;
      color: #f1f5f9;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-bottom-left-radius: 4px;
    }

    /* Markdown & SQL Previews inside assistant bubble */
    .cairo-msg-bubble table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0;
      font-size: 12px;
    }

    .cairo-msg-bubble th, .cairo-msg-bubble td {
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 5px 8px;
      text-align: left;
    }

    .cairo-msg-bubble th {
      background: rgba(255, 255, 255, 0.05);
    }

    .cairo-sql-preview {
      margin-top: 8px;
      padding: 8px 10px;
      background: #090d16;
      border-radius: 6px;
      font-family: monospace;
      font-size: 11.5px;
      color: #38bdf8;
      border-left: 3px solid #38bdf8;
      overflow-x: auto;
    }

    /* Suggestion Chips */
    .cairo-chips-bar {
      padding: 8px 12px;
      display: flex;
      gap: 6px;
      overflow-x: auto;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
      background: #0b1120;
    }

    .cairo-chip {
      white-space: nowrap;
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 4px 10px;
      font-size: 11.5px;
      color: #94a3b8;
      cursor: pointer;
      transition: all 0.2s;
    }

    .cairo-chip:hover {
      background: rgba(37, 99, 235, 0.25);
      border-color: #3b82f6;
      color: #93c5fd;
    }

    /* Input Footer */
    .cairo-chat-footer {
      padding: 12px;
      background: #1e293b;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      gap: 8px;
    }

    .cairo-chat-input {
      flex: 1;
      background: #0f172a;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 10px;
      padding: 9px 12px;
      color: #f8fafc;
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s;
    }

    .cairo-chat-input:focus {
      border-color: #3b82f6;
    }

    .cairo-chat-send-btn {
      background: #2563eb;
      border: none;
      border-radius: 10px;
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      cursor: pointer;
      transition: background 0.2s;
    }

    .cairo-chat-send-btn:hover {
      background: #1d4ed8;
    }

    .cairo-chat-send-btn svg {
      width: 18px;
      height: 18px;
      fill: currentColor;
    }
  `;

  // Inject Styles
  const styleEl = document.createElement("style");
  styleEl.textContent = styles;
  document.head.appendChild(styleEl);

  // Widget Root HTML
  const root = document.createElement("div");
  root.id = "cairo-chatbot-root";
  root.innerHTML = `
    <!-- Floating Launcher Button -->
    <div class="cairo-chat-launcher" id="cairoLauncher" title="Open Surveillance Analytics Chat">
      <svg viewBox="0 0 24 24">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/>
      </svg>
    </div>

    <!-- Popup Chat Window -->
    <div class="cairo-chat-window" id="cairoWindow">
      <div class="cairo-chat-header">
        <div class="cairo-chat-title-group">
          <div class="cairo-chat-badge"></div>
          <div>
            <div class="cairo-chat-title">${WIDGET_TITLE}</div>
            <div class="cairo-chat-subtitle">Live Database Connected</div>
          </div>
        </div>
        <button class="cairo-chat-close-btn" id="cairoCloseBtn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="cairo-chat-messages" id="cairoMessages">
        <div class="cairo-msg assistant">
          <div class="cairo-msg-bubble">
            👋 <strong>Hello! I am your AI Surveillance Analytics Assistant.</strong><br/><br/>
            Ask me anything about your detections, alerts, or cameras. Examples:
            <ul style="margin: 6px 0 0 16px; padding: 0;">
              <li><em>"How many PPE detections today?"</em></li>
              <li><em>"Show missing PPE breakdown"</em></li>
              <li><em>"Any critical alerts in the last 24h?"</em></li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Quick Chips -->
      <div class="cairo-chips-bar">
        <div class="cairo-chip" data-q="How many PPE detections?">🦺 PPE Count</div>
        <div class="cairo-chip" data-q="Show missing PPE breakdown">📊 Missing PPE</div>
        <div class="cairo-chip" data-q="How many alerts today?">🚨 Alerts Today</div>
        <div class="cairo-chip" data-q="Which cameras have the most detections?">📹 Top Cameras</div>
      </div>

      <!-- Input Footer -->
      <div class="cairo-chat-footer">
        <input type="text" class="cairo-chat-input" id="cairoInput" placeholder="Ask about detections, alerts, cameras..." />
        <button class="cairo-chat-send-btn" id="cairoSendBtn">
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  `;
  document.body.appendChild(root);

  // Elements
  const launcher = document.getElementById("cairoLauncher");
  const win = document.getElementById("cairoWindow");
  const closeBtn = document.getElementById("cairoCloseBtn");
  const messages = document.getElementById("cairoMessages");
  const input = document.getElementById("cairoInput");
  const sendBtn = document.getElementById("cairoSendBtn");

  // Toggle Window
  launcher.addEventListener("click", () => {
    win.classList.toggle("open");
    if (win.classList.contains("open")) {
      input.focus();
    }
  });

  closeBtn.addEventListener("click", () => {
    win.classList.remove("open");
  });

  // Suggestion chips
  root.querySelectorAll(".cairo-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-q");
      if (q) {
        input.value = q;
        sendMessage();
      }
    });
  });

  // Send message on Enter or Send click
  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  function appendMessage(text, role, sql) {
    const row = document.createElement("div");
    row.className = `cairo-msg ${role}`;

    let html = `<div class="cairo-msg-bubble">${formatMarkdown(text)}`;
    if (sql) {
      html += `<div class="cairo-sql-preview"><strong>SQL:</strong> ${escapeHtml(sql)}</div>`;
    }
    html += `</div>`;

    row.innerHTML = html;
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
    return row;
  }

  function appendTyping() {
    const row = document.createElement("div");
    row.className = "cairo-msg assistant";
    row.id = "cairoTyping";
    row.innerHTML = `
      <div class="cairo-msg-bubble" style="opacity: 0.8; font-style: italic;">
        Querying database...
      </div>
    `;
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
    return row;
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    input.value = "";
    input.disabled = true;

    const typing = appendTyping();

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({ message: text }),
      });

      if (typing) typing.remove();

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        appendMessage(`⚠️ **Error (${response.status})**: ${err.detail || "Failed to fetch response"}`, "assistant");
        return;
      }

      const data = await response.json();
      appendMessage(data.answer, "assistant", data.sql_query);
    } catch (e) {
      if (typing) typing.remove();
      appendMessage(`❌ **Connection Error**: Unable to reach NLP API Engine at \`${API_URL}\``, "assistant");
    } finally {
      input.disabled = false;
      input.focus();
    }
  }

  function escapeHtml(str) {
    return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatMarkdown(text) {
    if (!text) return "";

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
          tableHtml = '<div style="overflow-x:auto;margin:8px 0;border-radius:6px;border:1px solid rgba(255,255,255,0.1);"><table style="width:100%;border-collapse:collapse;font-size:12px;"><thead>';
          const cells = line.slice(1, -1).split("|").map((c) => c.trim());
          tableHtml += "<tr style='background:rgba(255,255,255,0.06);'>" + cells.map((c) => `<th style='padding:6px 10px;color:#38bdf8;border-bottom:1px solid rgba(255,255,255,0.1);text-align:left;'>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
        } else if (isSeparator) {
          continue;
        } else {
          const cells = line.slice(1, -1).split("|").map((c) => c.trim());
          tableHtml += "<tr style='border-bottom:1px solid rgba(255,255,255,0.04);'>" + cells.map((c) => `<td style='padding:6px 10px;white-space:nowrap;'>${escapeHtml(c)}</td>`).join("") + "</tr>";
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

    let s = processed.join("\n");
    // Bold
    s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Italics
    s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");
    // Code inline
    s = s.replace(/`([^`]+)`/g, "<code style='background:rgba(255,255,255,0.1);padding:2px 4px;border-radius:4px;'>$1</code>");
    // Markdown list items
    s = s.replace(/^\s*-\s+(.*)$/gm, "<li>$1</li>");
    s = s.replace(/(<li>.*<\/li>)/gs, "<ul style='margin:4px 0 4px 16px;padding:0;'>$1</ul>");
    // Newlines
    s = s.replace(/\n/g, "<br/>");
    return s;
  }
})();
