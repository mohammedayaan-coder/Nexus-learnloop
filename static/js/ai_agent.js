/**
 * Nexus Learn Loop — AI Mentor Client Logic
 * Sends user prompts to the Flask backend (/api/ai-chat) which uses
 * the server-configured Google Gemini API key. No keys are ever handled client-side.
 */
document.addEventListener("DOMContentLoaded", () => {
  // Purge any legacy client keys or configuration from localStorage
  try {
    localStorage.removeItem("nexus_gemini_key");
    localStorage.removeItem("nexus_gemini_model");
  } catch (_) {}

  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  let selectedTopic = "General";

  if (!chatMessages || !chatForm || !chatInput) return;

  // Topic filter selection
  document.querySelectorAll(".topic-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".topic-chip").forEach((b) => {
        b.className = "topic-chip px-3 py-1 rounded-full bg-surface-container-low border border-outline-variant text-on-surface-variant hover:text-on-surface font-bold text-xs whitespace-nowrap transition-colors";
      });
      btn.className = "topic-chip active px-3 py-1 rounded-full bg-primary text-on-primary font-bold text-xs whitespace-nowrap transition-colors";
      selectedTopic = btn.dataset.topic || "General";
      chatInput.placeholder = `Ask a question about ${selectedTopic}...`;
    });
  });

  // Prompt suggestions
  document.querySelectorAll(".prompt-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const textSpan = pill.querySelector("span:last-child");
      if (textSpan) {
        chatInput.value = textSpan.textContent;
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  });

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute("content")) {
      return meta.getAttribute("content");
    }
    const input = document.getElementById("csrf-token");
    if (input && input.value) {
      return input.value;
    }
    return "";
  }

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
      <div class="p-4 rounded-2xl rounded-tl-sm bg-surface-container-low border border-outline-variant text-xs text-on-surface leading-relaxed space-y-3">
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
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatAgentResponse(raw) {
    if (!raw) return "";

    // 1. Extract and preserve code blocks
    const codeBlocks = [];
    let text = raw.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const placeholder = `___CODE_BLOCK_${codeBlocks.length}___`;
      codeBlocks.push(`
        <div class="rounded-xl overflow-hidden border border-outline-variant bg-[#1e1e2e] text-[#cdd6f4] p-3 my-2 font-label-code text-[11px] shadow-sm">
          <div class="text-[#89b4fa] text-[10px] mb-1 uppercase font-bold tracking-wider">${escapeHtml(lang || 'code')}</div>
          <pre class="overflow-x-auto"><code>${escapeHtml(code.trim())}</code></pre>
        </div>
      `);
      return placeholder;
    });

    // Model output is untrusted. Escape it before adding the formatter's own markup.
    text = escapeHtml(text);

    // 2. Parse GitHub Alerts / Callout Boxes: > [!NOTE], > [!WARNING], > [!TIP]
    text = text.replace(/^>\s*\[!(NOTE|INFO|WARNING|TIP|CAUTION|IMPORTANT)\]\s*\n((?:>.*(?:\n|$))*)/gim, (match, type, content) => {
      const alertType = type.toUpperCase();
      const body = content.replace(/^>\s?/gm, '').trim();

      let boxClass = "bg-primary-fixed/20 border-primary/30 text-on-surface";
      let icon = "info";
      let label = "Note";

      if (alertType === "WARNING" || alertType === "CAUTION") {
        boxClass = "bg-amber-500/10 border-amber-500/30 text-amber-900";
        icon = "warning";
        label = "Notice";
      } else if (alertType === "TIP") {
        boxClass = "bg-emerald-500/10 border-emerald-500/30 text-emerald-900";
        icon = "tips_and_updates";
        label = "Tip";
      }

      return `<div class="p-3 my-2 rounded-xl border ${boxClass} text-xs space-y-1">
        <div class="flex items-center gap-1.5 font-bold text-[11px]">
          <span class="material-symbols-outlined text-[15px]">${icon}</span>
          <span>${label}</span>
        </div>
        <div class="leading-relaxed pl-5">${body.replace(/\n/g, '<br/>')}</div>
      </div>\n\n`;
    });

    // 3. Parse standard blockquotes: > text
    text = text.replace(/^>(?!\[!)(.*)$/gm, (match, content) => {
      return `<blockquote class="border-l-2 border-primary pl-3 py-1 text-on-surface-variant italic text-xs my-1">${content.trim()}</blockquote>`;
    });

    // 4. Parse markdown links: [text](url)
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-primary font-bold underline underline-offset-2 hover:opacity-80 transition-opacity">$1</a>');

    // 5. Bold: **text**
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-on-surface font-bold">$1</strong>');

    // 6. Inline code: `code`
    text = text.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-surface-container-high font-label-code text-primary font-bold text-[11px]">$1</code>');

    // 7. Parse paragraphs and bullet/numbered lists
    const paragraphs = text.split(/\n\s*\n/).map(block => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("<div") || trimmed.startsWith("<blockquote") || trimmed.startsWith("___CODE_BLOCK_")) {
        return trimmed;
      }

      const lines = trimmed.split("\n");

      // Check if all or most lines are bullet points
      const hasBullets = lines.some(l => /^\s*[-*]\s+/.test(l));
      if (hasBullets) {
        let insideList = false;
        let htmlOut = "";

        lines.forEach(line => {
          const bulletMatch = line.match(/^\s*[-*]\s+(.*)/);
          if (bulletMatch) {
            if (!insideList) {
              htmlOut += `<ul class="space-y-1.5 my-2 text-xs">`;
              insideList = true;
            }
            htmlOut += `<li class="flex items-start gap-2"><span class="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0"></span><span>${bulletMatch[1]}</span></li>`;
          } else {
            if (insideList) {
              htmlOut += `</ul>`;
              insideList = false;
            }
            htmlOut += `<p class="leading-relaxed">${line}</p>`;
          }
        });
        if (insideList) htmlOut += `</ul>`;
        return htmlOut;
      }

      // Check for numbered lists
      const hasNumbers = lines.some(l => /^\s*\d+\.\s+/.test(l));
      if (hasNumbers) {
        let insideList = false;
        let htmlOut = "";

        lines.forEach(line => {
          const numMatch = line.match(/^\s*(\d+)\.\s+(.*)/);
          if (numMatch) {
            if (!insideList) {
              htmlOut += `<ol class="space-y-1.5 my-2 text-xs">`;
              insideList = true;
            }
            htmlOut += `<li class="flex items-start gap-2"><span class="font-bold text-primary font-label-code shrink-0">${numMatch[1]}.</span><span>${numMatch[2]}</span></li>`;
          } else {
            if (insideList) {
              htmlOut += `</ol>`;
              insideList = false;
            }
            htmlOut += `<p class="leading-relaxed">${line}</p>`;
          }
        });
        if (insideList) htmlOut += `</ol>`;
        return htmlOut;
      }

      return `<p class="leading-relaxed">${trimmed.replace(/\n/g, "<br/>")}</p>`;
    });

    let resultHtml = paragraphs.filter(Boolean).join("");

    // Restore preserved code blocks safely
    codeBlocks.forEach((codeHtml, idx) => {
      resultHtml = resultHtml.replace(`___CODE_BLOCK_${idx}___`, () => codeHtml);
    });

    return resultHtml;
  }

  // Multi-turn conversation history for contextual mentoring
  const chatHistory = [];

  // Chat message submit handler
  let sendingMessage = false;
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (sendingMessage) return;
    const query = chatInput.value.trim();
    if (!query) return;

    sendingMessage = true;
    const sendButton = document.getElementById("send-btn");
    chatInput.disabled = true;
    if (sendButton) {
      sendButton.disabled = true;
      sendButton.dataset.originalText = sendButton.innerHTML;
      sendButton.innerHTML = `<span class="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin"></span><span>Thinking...</span>`;
    }
    chatInput.value = "";
    appendUserMessage(query);
    appendTypingIndicator();

    try {
      const csrfToken = getCsrfToken();
      const controller = new AbortController();
      // Flask bounds Gemini generation to 20 seconds; keep a small transport margin.
      const timeoutId = setTimeout(() => controller.abort(), 25000);

      try {
        const response = await fetch("/api/ai-chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken
          },
          body: JSON.stringify({
            message: query,
            topic: selectedTopic,
            csrf_token: csrfToken,
            history: chatHistory.slice(-12)
          }),
          signal: controller.signal
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
          appendAgentMessage("Please **[sign in](/login)** or **[create an account](/register)** to chat with the AI Mentor.");
        } else if (response.status === 403) {
          appendAgentMessage("Your security session expired. Please refresh the page and try again.");
        } else if (response.ok && data.success && data.reply) {
          appendAgentMessage(data.reply);
          chatHistory.push({ role: "user", text: query });
          chatHistory.push({ role: "model", text: data.reply });
        } else {
          const errorMsg = data.error || "AI Mentor is temporarily unavailable. Please try again later.";
          appendAgentMessage(`**AI Mentor is temporarily unavailable.** ${errorMsg}`);
        }
      } catch (err) {
        if (err.name === "AbortError") {
          appendAgentMessage("**AI Mentor unavailable:** The request took too long to complete. Please try again.");
        } else {
          appendAgentMessage("**AI Mentor unavailable:** Could not reach the server. Please check your connection and try again.");
        }
      } finally {
        clearTimeout(timeoutId);
      }
    } finally {
      removeTypingIndicator();
      sendingMessage = false;
      chatInput.disabled = false;
      if (sendButton) {
        sendButton.disabled = false;
        sendButton.innerHTML = sendButton.dataset.originalText || `<span>Send</span><span class="material-symbols-outlined text-[16px]">send</span>`;
        delete sendButton.dataset.originalText;
      }
      chatInput.focus();
    }
  });
});
