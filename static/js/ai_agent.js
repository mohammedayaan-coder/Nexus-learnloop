/**
 * Nexus Learn Loop — AI Mentor Client Logic
 * Uses the Flask backend for chat; browser keys remain available for explicit connection tests.
 * Built-in intelligent offline tutor with full markdown and callout rendering.
 */
document.addEventListener("DOMContentLoaded", () => {
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  let selectedTopic = "General";

  function isValidGeminiKey(key) {
    if (!key || typeof key !== "string") return false;
    const clean = key.trim();
    return clean.startsWith("AIzaSy") || clean.startsWith("AQ.") || clean.length >= 35;
  }

  const savedKey = localStorage.getItem("nexus_gemini_key") || "";
  let geminiApiKey = isValidGeminiKey(savedKey) ? savedKey.trim() : "";

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
      chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
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

    // Restore preserved code blocks safely (prevent regex replacement syntax issues)
    codeBlocks.forEach((codeHtml, idx) => {
      resultHtml = resultHtml.replace(`___CODE_BLOCK_${idx}___`, () => codeHtml);
    });

    return resultHtml;
  }

  // Multi-turn conversation history for contextual mentoring
  const chatHistory = [];
  let currentModel = localStorage.getItem("nexus_gemini_model") || "gemini-3.8-flash";
  let hasBackendKey = false;

  // Query backend AI status on startup
  async function checkBackendStatus() {
    const backendEndpoints = ["/api/ai-status"];
    if (window.location.protocol.startsWith("http") && window.location.port !== "5000") {
      backendEndpoints.push("http://127.0.0.1:5000/api/ai-status");
    } else if (!window.location.protocol.startsWith("http")) {
      backendEndpoints.push("http://127.0.0.1:5000/api/ai-status");
    }

    for (const url of backendEndpoints) {
      try {
        const res = await fetch(url, { method: "GET" });
        if (res.ok) {
          const data = await res.json();
          if (data.has_backend_key) {
            hasBackendKey = true;
            const backendInd = document.getElementById("backend-status-indicator");
            if (backendInd) {
              backendInd.className = "font-bold flex items-center gap-1.5 text-emerald-700 text-[11px]";
              backendInd.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500"></span><span>Key configured; response not yet verified</span>`;
            }
            updateKeyBadge();
            return;
          }
        }
      } catch (e) {
        // Continue to next endpoint
      }
    }

    const backendInd = document.getElementById("backend-status-indicator");
    if (backendInd) {
      backendInd.className = "font-bold flex items-center gap-1.5 text-on-surface-variant text-[11px]";
      backendInd.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-400"></span><span>Not detected in .env</span>`;
    }
    updateKeyBadge();
  }
  checkBackendStatus();

  // Optional direct call for an explicitly saved browser key. Server requests remain preferred.
  async function callDirectGemini(query, topic, apiKey, modelChoice = "gemini-3.8-flash") {
    const systemPrompt = `You are the Nexus Learn Loop AI Mentor, a warm, concise programming tutor. Keep the selected topic (${topic}) central. If the learner only greets you, greet them naturally and ask a useful follow-up question. Use recent conversation turns when relevant.`;
    const contents = chatHistory.slice(-12).map((turn) => ({
      role: turn.role === "user" ? "user" : "model",
      parts: [{ text: turn.text }]
    }));
    contents.push({ role: "user", parts: [{ text: `Selected topic: ${topic}\n${query}` }] });
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelChoice}:generateContent`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemPrompt }] },
          contents,
          generationConfig: { maxOutputTokens: 800, temperature: 0.4 }
        }),
        signal: controller.signal
      });
      if (!response.ok) return { success: false, error: `Gemini returned HTTP ${response.status}.` };
      const data = await response.json();
      const parts = data.candidates?.[0]?.content?.parts;
      const answer = Array.isArray(parts) ? parts.map((part) => part.text || "").join("").trim() : "";
      return answer ? { success: true, text: answer, model: modelChoice } : { success: false, error: "Gemini returned an empty answer." };
    } catch (error) {
      return { success: false, error: error.name === "AbortError" ? "Gemini took too long to respond." : "Could not reach Gemini." };
    } finally {
      clearTimeout(timeoutId);
    }
  }

  // --- API Configuration Modal Controls ---
  const configModal = document.getElementById("api-config-modal");
  const configKeyBtn = document.getElementById("config-key-btn");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const apiKeyInput = document.getElementById("api-key-input");
  const modelSelect = document.getElementById("model-select");
  const toggleKeyEye = document.getElementById("toggle-key-eye");
  const eyeIcon = document.getElementById("eye-icon");
  const testConnBtn = document.getElementById("test-connection-btn");
  const testResultBox = document.getElementById("test-result-box");
  const saveKeyBtn = document.getElementById("save-key-btn");
  const clearKeyBtn = document.getElementById("clear-key-btn");
  const clientStatusIndicator = document.getElementById("client-status-indicator");
  const activeModelDisplay = document.getElementById("active-model-display");
  const detectModelsBtn = document.getElementById("detect-models-btn");
  const customModelContainer = document.getElementById("custom-model-container");
  const customModelInput = document.getElementById("custom-model-input");

  function getSelectedModelName() {
    if (!modelSelect) return currentModel || "gemini-3.8-flash";
    if (modelSelect.value === "custom") {
      return (customModelInput && customModelInput.value.trim()) || "gemini-3.8-flash";
    }
    return modelSelect.value || "gemini-3.8-flash";
  }

  function openConfigModal() {
    if (!configModal) return;
    if (apiKeyInput) {
      apiKeyInput.value = localStorage.getItem("nexus_gemini_key") || "";
    }
    const savedModel = localStorage.getItem("nexus_gemini_model") || "gemini-3.8-flash";
    currentModel = savedModel;

    if (modelSelect) {
      let found = false;
      for (const opt of modelSelect.options) {
        if (opt.value === savedModel) {
          modelSelect.value = savedModel;
          found = true;
          break;
        }
      }
      if (!found && savedModel !== "custom") {
        const customOpt = document.createElement("option");
        customOpt.value = savedModel;
        customOpt.textContent = `${savedModel} (Active)`;
        modelSelect.insertBefore(customOpt, modelSelect.firstChild);
        modelSelect.value = savedModel;
      }
      if (modelSelect.value === "custom") {
        if (customModelContainer) customModelContainer.classList.remove("hidden");
        if (customModelInput && savedModel !== "custom") customModelInput.value = savedModel;
      } else {
        if (customModelContainer) customModelContainer.classList.add("hidden");
      }
    }

    if (activeModelDisplay) {
      activeModelDisplay.textContent = getSelectedModelName();
    }

    if (clientStatusIndicator) {
      const cKey = localStorage.getItem("nexus_gemini_key") || "";
      if (isValidGeminiKey(cKey)) {
        clientStatusIndicator.className = "font-bold flex items-center gap-1.5 text-emerald-700 text-[11px]";
        clientStatusIndicator.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500"></span><span>Configured (${cKey.slice(0, 6)}...${cKey.slice(-4)})</span>`;
      } else {
        clientStatusIndicator.className = "font-bold flex items-center gap-1.5 text-on-surface-variant text-[11px]";
        clientStatusIndicator.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-400"></span><span>None (Using Backend or Offline)</span>`;
      }
    }
    if (testResultBox) {
      testResultBox.className = "hidden p-3 rounded-xl text-xs leading-relaxed";
      testResultBox.style.display = "none";
      testResultBox.innerHTML = "";
    }
    configModal.classList.remove("hidden");
    configModal.style.display = "flex";
  }

  function closeConfigModal() {
    if (configModal) {
      configModal.classList.add("hidden");
      configModal.style.display = "none";
    }
  }

  if (configKeyBtn) configKeyBtn.addEventListener("click", openConfigModal);
  const statusBadge = document.getElementById("api-status-badge");
  if (statusBadge) statusBadge.addEventListener("click", openConfigModal);
  if (closeModalBtn) closeModalBtn.addEventListener("click", closeConfigModal);
  if (configModal) {
    configModal.addEventListener("click", (e) => {
      if (e.target === configModal) closeConfigModal();
    });
  }

  // Eye toggle for API key visibility
  if (toggleKeyEye && apiKeyInput && eyeIcon) {
    toggleKeyEye.addEventListener("click", () => {
      if (apiKeyInput.type === "password") {
        apiKeyInput.type = "text";
        eyeIcon.textContent = "visibility_off";
      } else {
        apiKeyInput.type = "password";
        eyeIcon.textContent = "visibility";
      }
    });
  }

  // Model select change handler
  if (modelSelect) {
    modelSelect.addEventListener("change", () => {
      if (modelSelect.value === "custom") {
        if (customModelContainer) customModelContainer.classList.remove("hidden");
        if (customModelInput) customModelInput.focus();
      } else {
        if (customModelContainer) customModelContainer.classList.add("hidden");
      }
      if (activeModelDisplay) {
        activeModelDisplay.textContent = getSelectedModelName();
      }
    });
  }

  // Custom model text input change
  if (customModelInput && activeModelDisplay) {
    customModelInput.addEventListener("input", () => {
      activeModelDisplay.textContent = getSelectedModelName();
    });
  }

  // The server's allowlist is authoritative for model choices.
  if (detectModelsBtn && modelSelect) {
    detectModelsBtn.addEventListener("click", async () => {
      detectModelsBtn.disabled = true;
      detectModelsBtn.innerHTML = `<span class="w-3 h-3 rounded-full border-2 border-primary border-t-transparent animate-spin"></span><span>Loading...</span>`;
      try {
        const res = await fetch("/api/ai-models");
        const data = await res.json();
        if (!res.ok || !Array.isArray(data.models) || data.models.length === 0) throw new Error();
        modelSelect.innerHTML = "";
        data.models.forEach((model) => {
          const option = document.createElement("option");
          option.value = model;
          option.textContent = model;
          modelSelect.appendChild(option);
        });
        modelSelect.value = data.models[0];
        if (activeModelDisplay) activeModelDisplay.textContent = data.models[0];
        if (testResultBox) {
          testResultBox.textContent = "Supported model list loaded from the server.";
          testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-surface-container-high text-on-surface-variant";
          testResultBox.classList.remove("hidden");
        }
      } catch (_error) {
        if (testResultBox) {
          testResultBox.textContent = "Could not load the server's supported model list.";
          testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-amber-500/10 border border-amber-500/30 text-amber-900";
          testResultBox.classList.remove("hidden");
        }
      } finally {
        detectModelsBtn.disabled = false;
        detectModelsBtn.innerHTML = `<span class="material-symbols-outlined text-[13px]">sync</span><span>Detect Available Models</span>`;
      }
    });
  }

  // Test connection button
  if (testConnBtn && testResultBox) {
    testConnBtn.addEventListener("click", async () => {
      const inputVal = apiKeyInput ? apiKeyInput.value.trim() : "";
      const chosenModel = getSelectedModelName();

      testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-surface-container-high text-on-surface flex items-center gap-2";
      testResultBox.style.display = "flex";
      testResultBox.innerHTML = `<span class="w-3 h-3 rounded-full border-2 border-primary border-t-transparent animate-spin"></span><span>Testing connection with Google Gemini API (${chosenModel})...</span>`;
      testResultBox.classList.remove("hidden");

      // 1. If key typed in input, test client-side direct
      if (inputVal) {
        if (!isValidGeminiKey(inputVal)) {
          testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-amber-500/10 border border-amber-500/30 text-amber-900";
          testResultBox.style.display = "block";
          testResultBox.innerHTML = `⚠️ <strong>Key Format Notice</strong>: Key should start with <code>AQ...</code> or <code>AIzaSy...</code>. Please verify key from Google AI Studio.`;
          return;
        }

        try {
          const url = `https://generativelanguage.googleapis.com/v1beta/models/${chosenModel}:generateContent`;
          const res = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-goog-api-key": inputVal
            },
            body: JSON.stringify({
              contents: [{ parts: [{ text: "Hello" }] }],
              generationConfig: { maxOutputTokens: 5 }
            })
          });

          if (res.ok) {
            testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-emerald-500/10 border border-emerald-500/30 text-emerald-900";
            testResultBox.style.display = "block";
            testResultBox.innerHTML = `✅ <strong>Connection Successful!</strong> Google Gemini API accepted your key with <strong>${chosenModel}</strong>. Click <strong>Save Settings</strong> to activate.`;
          } else {
            const errJson = await res.json().catch(() => ({}));
            const msg = errJson?.error?.message || `HTTP ${res.status}`;
            testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-red-500/10 border border-red-500/30 text-red-900";
            testResultBox.style.display = "block";
            testResultBox.innerHTML = `❌ <strong>Google API Error</strong>: ${escapeHtml(msg)}. Please check that the key is active in your Google AI Studio account.`;
          }
        } catch (e) {
          testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-red-500/10 border border-red-500/30 text-red-900";
          testResultBox.style.display = "block";
          testResultBox.innerHTML = `❌ <strong>Network Error</strong>: ${escapeHtml(e.message)}. Please check your internet connection.`;
        }
      } else {
        // No input typed: test backend status endpoint
        try {
          const res = await fetch("/api/ai-test-key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ model: chosenModel })
          });
          if (res.ok) {
            testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-emerald-500/10 border border-emerald-500/30 text-emerald-900";
            testResultBox.style.display = "block";
            testResultBox.innerHTML = `✅ <strong>Backend Connection Verified!</strong> The Gemini API key in your <code>.env</code> is working with <strong>${chosenModel}</strong>.`;
          } else {
            const errData = await res.json().catch(() => ({}));
            testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-amber-500/10 border border-amber-500/30 text-amber-900";
            testResultBox.style.display = "block";
            testResultBox.innerHTML = `⚠️ <strong>Backend Key Status</strong>: ${escapeHtml(errData.error || "No key found in .env")}. You can enter a key in the input above.`;
          }
        } catch (e) {
          testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-amber-500/10 border border-amber-500/30 text-amber-900";
          testResultBox.style.display = "block";
          testResultBox.innerHTML = `ℹ️ Paste a Gemini API key into the input above and click <strong>Test Connection</strong>.`;
        }
      }
    });
  }

  // Save key button
  if (saveKeyBtn) {
    saveKeyBtn.addEventListener("click", () => {
      const cleanKey = apiKeyInput ? apiKeyInput.value.trim() : "";
      const chosenModel = getSelectedModelName();

      if (cleanKey) {
        if (!isValidGeminiKey(cleanKey)) {
          alert("⚠️ Invalid Key Format: Google Gemini keys start with 'AQ...' or 'AIzaSy...'. Please copy your key from https://aistudio.google.com/app/apikey.");
          return;
        }
        localStorage.setItem("nexus_gemini_key", cleanKey);
        geminiApiKey = cleanKey;
      }
      localStorage.setItem("nexus_gemini_model", chosenModel);
      currentModel = chosenModel;

      updateKeyBadge();
      closeConfigModal();
    });
  }


  // Clear key button
  if (clearKeyBtn) {
    clearKeyBtn.addEventListener("click", () => {
      localStorage.removeItem("nexus_gemini_key");
      geminiApiKey = "";
      if (apiKeyInput) apiKeyInput.value = "";
      updateKeyBadge();
      if (testResultBox) {
        testResultBox.className = "p-3 rounded-xl text-xs leading-relaxed bg-surface-container-high text-on-surface-variant";
        testResultBox.innerHTML = `ℹ️ Custom key cleared. Switched to backend .env key or built-in offline tutor.`;
        testResultBox.classList.remove("hidden");
      }
    });
  }

  function updateKeyBadge() {
    const badge = document.getElementById("api-status-badge");
    if (!badge) return;
    const clientKey = localStorage.getItem("nexus_gemini_key") || geminiApiKey;

    if (isValidGeminiKey(clientKey)) {
      badge.className = "px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold flex items-center gap-1.5 cursor-pointer hover:bg-emerald-200 transition-colors shadow-sm";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span><span>Client key saved (not verified)</span>`;
      badge.title = "A browser key is saved. Gemini is only verified after a successful request.";
    } else if (hasBackendKey) {
      badge.className = "px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-bold flex items-center gap-1.5 cursor-pointer hover:bg-emerald-200 transition-colors shadow-sm";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span><span>Server key configured</span>`;
      badge.title = "A server key is configured; each message reports whether Gemini actually answered.";
    } else {
      badge.className = "px-2.5 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant border border-outline-variant text-[10px] font-semibold flex items-center gap-1.5 cursor-pointer hover:bg-surface-container-highest transition-colors shadow-sm";
      badge.innerHTML = `<span class="material-symbols-outlined text-[13px] text-primary">key</span><span>API Settings (Offline Tutor)</span>`;
      badge.title = "Click to configure your Google Gemini API Key and Reasoning Engine.";
    }
  }
  updateKeyBadge();

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
      sendButton.innerHTML = `<span class="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin"></span><span>Thinking?</span>`;
    }
    chatInput.value = "";
    appendUserMessage(query);
    appendTypingIndicator();

    let replied = false;
    let backendFailure = "";
    let transportFailed = false;
    const chosenModel = "gemini-3.8-flash";

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 32000);
      try {
        const response = await fetch("/api/ai-chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: query,
            topic: selectedTopic,
            model: chosenModel,
            history: chatHistory.slice(-12)
          }),
          signal: controller.signal
        });
        const data = await response.json().catch(() => ({}));
        if (response.ok && data.success && data.source === "gemini" && data.reply) {
          appendAgentMessage(data.reply);
          chatHistory.push({ role: "user", text: query });
          chatHistory.push({ role: "model", text: data.reply });
          replied = true;
        } else {
          backendFailure = data.error || "The AI Mentor could not complete this request.";
        }
      } catch (_error) {
        transportFailed = true;
      } finally {
        clearTimeout(timeoutId);
      }

      // Do not issue a second Gemini request after an upstream HTTP error; the
      // server has already handled bounded retries and returned its safe status.
      if (!replied && !backendFailure && transportFailed && isValidGeminiKey(geminiApiKey)) {
        const result = await callDirectGemini(query, selectedTopic, geminiApiKey, chosenModel);
        if (result.success && result.text) {
          appendAgentMessage(result.text);
          chatHistory.push({ role: "user", text: query });
          chatHistory.push({ role: "model", text: result.text });
          replied = true;
        }
      }

      if (!replied && backendFailure) {
        appendAgentMessage(`**Gemini unavailable:** ${backendFailure}`);
      } else if (!replied) {
        const response = `**Offline tutor (Gemini unavailable):**\n\n${generateLocalFallback(query, selectedTopic)}`;
        appendAgentMessage(response);
        chatHistory.push({ role: "user", text: query });
        chatHistory.push({ role: "model", text: response });
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

  function generateLocalFallback(query, topic) {
    const q = query.toLowerCase().trim();

    // Friendly greetings
    if (/^(hi+|hello+|hey+|hola|yo|sup|greetings)[!.?,\s]*$/i.test(q)) {
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
  {% block content %}{% endblock %}
</div>
\`\`\``;
    }

    if (q.includes("sqlite") || q.includes("index") || q.includes("db") || q.includes("sql") || q.includes("query")) {
      return `**SQLite Indexing & Performance**

Creating an index speeds up queries on frequently filtered columns:

\`\`\`sql
-- Single column index
CREATE INDEX idx_users_streak ON users(streak);

-- Composite index
CREATE INDEX idx_scores ON quiz_results(user_id, created_at DESC);
\`\`\`

💡 Use \`EXPLAIN QUERY PLAN\` to verify whether your query utilizes the index.`;
    }

    if (q.includes("git") || q.includes("conflict") || q.includes("merge") || q.includes("branch")) {
      return `**Resolving Git Merge Conflicts**

1. Run \`git status\` to view conflicting files.
2. Open conflicting files and resolve markers (\`<<<<<<<\`, \`=======\`, \`>>>>>>>\`).
3. Stage and commit the resolved files:

\`\`\`bash
git add <filename>
git commit -m "fix: resolve merge conflict"
\`\`\``;
    }

    if (q.includes("list") || q.includes("comprehension") || q.includes("python") || q.includes("dict")) {
      return `**Python List Comprehensions**

List comprehensions provide a concise way to create transformed lists:

\`\`\`python
# Syntax: [expression for item in iterable if condition]
numbers = [1, 2, 3, 4, 5, 6]
evens = [x * 2 for x in numbers if x % 2 == 0]
# Result: [4, 8, 12]
\`\`\``;
    }

    if (q.includes("timer") || q.includes("pomodoro") || q.includes("focus")) {
      return `**Study Timer & Pomodoro Technique**

The 25-minute Pomodoro sprint maximizes cognitive focus:
- **Work interval**: 25 minutes of zero distractions.
- **Short break**: 5 minutes to stretch and hydrate.
- **Long break**: 15–30 minutes after completing 4 consecutive sprints.

Completing sessions on the Nexus Study Timer rewards you with **+30 XP**!`;
    }

    if (q.includes("flask") || q.includes("route") || q.includes("server")) {
      return `**Flask Application Routing**

In Flask, define routes using decorators to map URLs to Python functions:

\`\`\`python
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route("/api/greet", methods=["GET"])
def greet():
    name = request.args.get("name", "Learner")
    return jsonify({"message": f"Hello, {name}!"})
\`\`\``;
    }

    return `**Nexus AI Mentor (${topic})**

You asked: "${escapeHtml(query)}"

1. **Break it down**: Isolate the exact input and expected outcome.
2. **Best practice**: Keep modular functions and write testable logic.
3. **Explore**: Try solving related practice challenges on the platform to reinforce your knowledge.`;
  }
});
