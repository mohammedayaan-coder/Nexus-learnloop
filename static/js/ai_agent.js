/**
 * Nexus Learn Loop — AI Mentor Client Logic
 * Supports both Flask backend (/api/ai-chat) and direct Google Gemini API calls for file:// previews.
 */
document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  let selectedTopic = "General";

  // Pre-configured API key from .env / localStorage
  const DEFAULT_KEY = "AQ.Ab8RN6J4HTJr0zWr2LMojtZXUqNh4GMqqt4u9i4ugkj7kTcWTw";
  let geminiApiKey = localStorage.getItem("nexus_gemini_key") || DEFAULT_KEY;

  if (!chatMessages || !chatForm || !chatInput) return;

  // Topic filter selection
  document.querySelectorAll(".topic-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".topic-chip").forEach((b) => {
        b.className = "topic-chip px-3 py-1 rounded-full bg-surface-container-low border border-outline-variant text-on-surface-variant hover:text-on-surface font-bold text-xs whitespace-nowrap transition-colors";
      });
      btn.className = "topic-chip active px-3 py-1 rounded-full bg-primary text-on-primary font-bold text-xs whitespace-nowrap transition-colors";
      selectedTopic = btn.dataset.topic;
      chatInput.placeholder = `Ask a question about ${selectedTopic}...`;
    });
  });

  // Prompt suggestions
  document.querySelectorAll(".prompt-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      chatInput.value = pill.querySelector("span:last-child").textContent;
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  function appendUserMessage(text) {
    const wrap = document.createElement("div");
    wrap.className = "flex items-start justify-end gap-3";
    wrap.innerHTML = `
      <div class="p-3.5 rounded-2xl rounded-tr-sm bg-primary text-on-primary text-xs leading-relaxed max-w-xl shadow-sm">
        ${escapeHtml(text)}
      </div>
      <div class="w-8 h-8 rounded-lg bg-primary-fixed text-primary font-bold text-xs flex items-center justify-center shrink-0 shadow-sm mt-0.5">
        U
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendAgentMessage(text) {
    const wrap = document.createElement("div");
    wrap.className = "flex items-start gap-3 max-w-2xl";
    wrap.innerHTML = `
      <div class="w-8 h-8 rounded-lg bg-primary text-on-primary flex items-center justify-center shrink-0 shadow-sm mt-0.5">
        <span class="material-symbols-outlined text-[18px]">smart_toy</span>
      </div>
      <div class="p-4 rounded-2xl rounded-tl-sm bg-surface-container-low border border-outline-variant text-xs text-on-surface leading-relaxed space-y-2.5">
        ${formatAgentResponse(text)}
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendTypingIndicator() {
    const wrap = document.createElement("div");
    wrap.id = "typing-indicator";
    wrap.className = "flex items-start gap-3 max-w-2xl";
    wrap.innerHTML = `
      <div class="w-8 h-8 rounded-lg bg-primary text-on-primary flex items-center justify-center shrink-0 shadow-sm mt-0.5">
        <span class="material-symbols-outlined text-[18px]">smart_toy</span>
      </div>
      <div class="p-3.5 rounded-2xl rounded-tl-sm bg-surface-container-low border border-outline-variant flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full bg-primary animate-bounce"></span>
        <span class="w-2 h-2 rounded-full bg-primary animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-2 h-2 rounded-full bg-primary animate-bounce" style="animation-delay: 0.3s"></span>
      </div>
    `;
    chatMessages.appendChild(wrap);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function removeTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatAgentResponse(raw) {
    let formatted = raw.replace(/```([a-zA-Z]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<div class="rounded-xl overflow-hidden border border-outline-variant bg-[#1e1e2e] text-[#cdd6f4] p-3 my-2 font-label-code text-[11px]">
        <div class="text-[#6c7086] text-[10px] mb-1 uppercase font-bold">${lang || 'code'}</div>
        <pre class="overflow-x-auto"><code>${escapeHtml(code.trim())}</code></pre>
      </div>`;
    });

    formatted = formatted.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-surface-container-high font-label-code text-primary font-bold">$1</code>');
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-on-surface font-bold">$1</strong>');
    return formatted.split("\n\n").map(p => `<p>${p.replace(/\n/g, "<br/>")}</p>`).join("");
  }

  // Direct Google Gemini API caller
  async function callDirectGemini(query, topic, apiKey) {
    const models = ["gemini-2.5-flash", "gemini-flash-latest"];
    const systemPrompt = `You are the Nexus Learn Loop AI Mentor, a friendly, concise programming tutor inspired by Duolingo. The student is asking about: ${topic}. Provide clear explanations with brief code examples and best practices. Keep answers under 200 words.`;

    const payload = {
      contents: [{
        parts: [{
          text: `${systemPrompt}\n\nStudent Query: ${query}`
        }]
      }],
      generationConfig: {
        maxOutputTokens: 600,
        temperature: 0.4
      }
    };

    let lastError = null;

    for (const model of models) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(apiKey)}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          const data = await res.json();
          const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
          if (text) return { success: true, text };
        } else {
          const errData = await res.json().catch(() => ({}));
          lastError = errData?.error?.message || `HTTP ${res.status}`;
        }
      } catch (e) {
        lastError = e.message;
      }
    }
    return { success: false, error: lastError };
  }

  // Key configuration modal / prompt
  const keyConfigBtn = document.getElementById("config-key-btn");
  if (keyConfigBtn) {
    keyConfigBtn.addEventListener("click", () => {
      const current = localStorage.getItem("nexus_gemini_key") || "";
      const entered = prompt(
        "Enter your Google Gemini API Key (starts with 'AIzaSy...'):\nGet a free key at: https://aistudio.google.com/app/apikey",
        current
      );
      if (entered !== null) {
        const clean = entered.trim();
        if (clean) {
          localStorage.setItem("nexus_gemini_key", clean);
          geminiApiKey = clean;
          alert("✅ Gemini API Key saved! Try asking a question now.");
          updateKeyBadge();
        } else {
          localStorage.removeItem("nexus_gemini_key");
          geminiApiKey = DEFAULT_KEY;
          alert("Key cleared. Default fallback restored.");
          updateKeyBadge();
        }
      }
    });
  }

  function updateKeyBadge() {
    const badge = document.getElementById("api-status-badge");
    if (!badge) return;
    const key = localStorage.getItem("nexus_gemini_key") || geminiApiKey;
    if (key && key.startsWith("AIzaSy")) {
      badge.className = "px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold flex items-center gap-1 cursor-pointer hover:bg-emerald-200 transition-colors";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse"></span><span>Live Gemini Key Active</span>`;
    } else {
      badge.className = "px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300 text-[10px] font-bold flex items-center gap-1 cursor-pointer hover:bg-amber-200 transition-colors";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-600"></span><span>Set Gemini Key</span>`;
    }
  }
  updateKeyBadge();

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;

    chatInput.value = "";
    appendUserMessage(query);
    appendTypingIndicator();

    let replied = false;
    let apiErrorMsg = null;

    // 1. Try local Flask backend if running over HTTP
    if (window.location.protocol.startsWith("http")) {
      try {
        const res = await fetch("/api/ai-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: query, topic: selectedTopic })
        });
        if (res.ok) {
          const data = await res.json();
          if (data.reply) {
            removeTypingIndicator();
            appendAgentMessage(data.reply);
            replied = true;
          }
        }
      } catch (err) {
        // Backend not reachable, fall to direct API
      }
    }

    // 2. Direct Gemini API call if not yet answered
    if (!replied && geminiApiKey) {
      const result = await callDirectGemini(query, selectedTopic, geminiApiKey);
      if (result.success && result.text) {
        removeTypingIndicator();
        appendAgentMessage(result.text);
        replied = true;
      } else if (result.error) {
        apiErrorMsg = result.error;
      }
    }

    // 3. Fallback to smart offline tutor if both API paths failed
    if (!replied) {
      removeTypingIndicator();
      let response = generateLocalFallback(query, selectedTopic);
      if (apiErrorMsg && (!geminiApiKey || !geminiApiKey.startsWith("AIzaSy"))) {
        response = `> [!NOTE]\n> **Notice**: The current Gemini API Key was rejected by Google (*"${escapeHtml(apiErrorMsg)}"*). Gemini API keys start with \`AIzaSy...\`. You can click **"Set Gemini Key"** in the top right to paste a valid key from [Google AI Studio](https://aistudio.google.com/app/apikey).\n\n` + response;
      }
      appendAgentMessage(response);
    }
  });

  function generateLocalFallback(query, topic) {
    const q = query.toLowerCase().trim();

    // Friendly greetings
    if (["hi", "hello", "hey", "hola", "yo", "sup", "greetings"].includes(q) || q.startsWith("hi ") || q.startsWith("hello ")) {
      return `**Hello! 👋 Welcome to Nexus Learn Loop!**

I'm your AI Mentor for **${topic}**. I'm here to help you:
- Explain programming concepts (Python, Flask, SQL, Git, etc.)
- Debug tricky syntax errors or logic issues
- Walk through practice problems and daily quiz concepts

What would you like to explore or learn today?`;
    }

    if (q.includes("jinja") || q.includes("template")) {
      return `**Jinja2 Template Interpolation**

In Flask and Jinja2:
1. **Expressions**: Use double curly braces \`{{ variable }}\` to print escaped output.
2. **Statements**: Use \`{% for item in items %}\` and \`{% if condition %}\` for logic.
3. **Inheritance**: Define a base layout with blocks, then child templates extend it.

\`\`\`html
<!-- Example base layout block -->
<div class="main-content">
  <!-- Content from child template -->
</div>
\`\`\``;
    }

    if (q.includes("sqlite") || q.includes("index") || q.includes("db")) {
      return `**SQLite Indexing & Performance**

Creating an index speeds up queries on filtered columns:

\`\`\`sql
-- Single column index
CREATE INDEX idx_users_streak ON users(streak);

-- Composite index
CREATE INDEX idx_scores ON quiz_results(user_id, created_at DESC);
\`\`\`

💡 Use \`EXPLAIN QUERY PLAN\` to verify whether your query utilizes the index.`;
    }

    if (q.includes("git") || q.includes("conflict") || q.includes("merge")) {
      return `**Resolving Git Merge Conflicts**

1. Run \`git status\` to see files with conflicts.
2. Open conflicting files and choose the incoming or current changes.
3. Remove conflict markers and commit:

\`\`\`bash
git add <filename>
git commit -m "fix: resolve merge conflict"
\`\`\``;
    }

    if (q.includes("list") || q.includes("comprehension") || q.includes("python")) {
      return `**Python List Comprehensions**

List comprehensions provide a concise way to create lists:

\`\`\`python
# [expression for item in iterable if condition]
numbers = [1, 2, 3, 4, 5, 6]
evens = [x * 2 for x in numbers if x % 2 == 0]
# Result: [4, 8, 12]
\`\`\``;
    }

    return `**Nexus AI Mentor (${topic})**

You asked: "${escapeHtml(query)}"

1. **Break it down**: Isolate the exact input and expected outcome.
2. **Best practice**: Keep modular functions and write testable logic.
3. **Explore**: Try solving related practice challenges on the platform to reinforce your knowledge.`;
  }
});
