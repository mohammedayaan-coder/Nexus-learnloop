/**
 * Nexus Learn Loop — Learn With Buddies (LWB) Discord-Style Client Logic
 * Handles text channels (tc), voice channels (vc), mic/deafen toggles,
 * real-time messaging, emoji reactions, and screen sharing previews.
 */
document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentChannelType = "text"; // "text" or "voice"
  let currentTextChannel = "general-chat";
  let activeVoiceChannel = null;
  let isMuted = false;
  let isDeafened = false;
  let isScreenSharing = false;
  let isCameraOn = false;

  // DOM Elements
  const textChatView = document.getElementById("text-chat-view");
  const voiceStageView = document.getElementById("voice-stage-view");
  const currentChannelTitle = document.getElementById("current-channel-title");
  const currentChannelDesc = document.getElementById("current-channel-desc");
  const currentChannelIcon = document.getElementById("current-channel-icon");
  const voiceStatusBar = document.getElementById("voice-status-bar");
  const voiceStatusChannel = document.getElementById("voice-status-channel");
  const messageForm = document.getElementById("message-form");
  const messageInput = document.getElementById("message-input");
  const messageFeed = document.getElementById("message-feed");
  const toggleMembersBtn = document.getElementById("toggle-members-btn");
  const membersSidebar = document.getElementById("members-sidebar");
  const channelsSidebar = document.getElementById("channels-sidebar");
  const toggleChannelsBtn = document.getElementById("toggle-channels-btn");

  if (channelsSidebar && toggleChannelsBtn) {
    const closeChannels = () => {
      channelsSidebar.classList.remove("mobile-open");
      toggleChannelsBtn.setAttribute("aria-expanded", "false");
    };
    toggleChannelsBtn.addEventListener("click", () => {
      const open = channelsSidebar.classList.toggle("mobile-open");
      toggleChannelsBtn.setAttribute("aria-expanded", String(open));
    });
    channelsSidebar.querySelectorAll(".text-channel-item, .voice-channel-item").forEach((item) => {
      item.addEventListener("click", closeChannels);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeChannels();
    });
  }

  // User Audio Controls
  const toggleMicBtn = document.getElementById("toggle-mic-btn");
  const toggleDeafenBtn = document.getElementById("toggle-deafen-btn");
  const userMicIcon = document.getElementById("user-mic-icon");
  const userDeafenIcon = document.getElementById("user-deafen-icon");
  const disconnectVoiceBtn = document.getElementById("disconnect-voice-btn");
  const stageLeaveVcBtn = document.getElementById("stage-leave-vc-btn");
  const stageMicBtn = document.getElementById("stage-mic-btn");
  const stageCamBtn = document.getElementById("stage-cam-btn");
  const stageShareBtn = document.getElementById("stage-share-btn");
  const switchChatBtn = document.getElementById("switch-chat-btn");

  // --- Channel Definitions ---
  const channelDescriptions = {
    "general-chat": "Hang out, chat about study goals, and share your daily progress.",
    "code-help-and-debug": "Drop buggy snippets, explain logic errors, and get peer review.",
    "challenge-discussions": "Discuss strategies for today's daily coding challenges.",
    "resource-drop": "Share tutorials, cheatsheets, and recommended dev tools.",
    "showcase-and-wins": "Celebrate completed projects, streak milestones, and quiz scores!"
  };

  // --- Text Channel Switching ---
  document.querySelectorAll(".text-channel-item").forEach((item) => {
    item.addEventListener("click", () => {
      const channelName = item.dataset.channel;
      if (!channelName) return;

      document.querySelectorAll(".text-channel-item").forEach((ch) => {
        ch.classList.remove("bg-[#35373c]", "text-white");
        ch.classList.add("text-[#949ba4]", "hover:bg-[#35373c]/60", "hover:text-[#dbdee1]");
      });

      item.classList.add("bg-[#35373c]", "text-white");
      item.classList.remove("text-[#949ba4]", "hover:bg-[#35373c]/60", "hover:text-[#dbdee1]");

      currentTextChannel = channelName;
      currentChannelType = "text";

      if (currentChannelTitle) currentChannelTitle.textContent = channelName;
      if (currentChannelDesc) currentChannelDesc.textContent = channelDescriptions[channelName] || "Community discussion space.";
      if (currentChannelIcon) currentChannelIcon.textContent = "tag";
      if (messageInput) messageInput.placeholder = `Message #${channelName}...`;

      // Switch view
      if (textChatView) textChatView.classList.remove("hidden");
      if (voiceStageView) voiceStageView.classList.add("hidden");

      // Auto-scroll chat
      if (messageFeed) messageFeed.scrollTop = messageFeed.scrollHeight;
    });
  });

  // --- Voice Channel Switching & Joining ---
  document.querySelectorAll(".voice-channel-item").forEach((item) => {
    item.addEventListener("click", () => {
      const vcName = item.dataset.vc;
      joinVoiceChannel(vcName);
    });
  });

  function joinVoiceChannel(vcName) {
    activeVoiceChannel = vcName;

    // Highlight active VC
    document.querySelectorAll(".voice-channel-item").forEach((ch) => {
      ch.classList.remove("bg-[#35373c]", "text-[#23a55a]");
      ch.classList.add("text-[#949ba4]");
    });

    const activeItem = document.querySelector(`.voice-channel-item[data-vc="${vcName}"]`);
    if (activeItem) {
      activeItem.classList.add("bg-[#35373c]", "text-[#23a55a]");
      activeItem.classList.remove("text-[#949ba4]");
    }

    // Show Voice Connected Dock
    if (voiceStatusBar) {
      voiceStatusBar.classList.remove("hidden");
      voiceStatusBar.classList.add("flex");
    }
    if (voiceStatusChannel) voiceStatusChannel.textContent = `${vcName} / Nexus Hub`;

    // Show Voice Stage View
    if (voiceStageView) {
      voiceStageView.classList.remove("hidden");
      const stageTitle = document.getElementById("stage-vc-title");
      if (stageTitle) stageTitle.textContent = vcName;
    }
    if (textChatView) textChatView.classList.add("hidden");

    if (currentChannelTitle) currentChannelTitle.textContent = vcName;
    if (currentChannelDesc) currentChannelDesc.textContent = "Live Audio & Screen Share Lounge";
    if (currentChannelIcon) currentChannelIcon.textContent = "volume_up";

    // Beep sound simulation / visual feedback
    playNotificationHaptic("Connected to " + vcName);
  }

  function leaveVoiceChannel() {
    activeVoiceChannel = null;
    isScreenSharing = false;
    isCameraOn = false;

    // Reset VC channel item styles
    document.querySelectorAll(".voice-channel-item").forEach((ch) => {
      ch.classList.remove("bg-[#35373c]", "text-[#23a55a]");
      ch.classList.add("text-[#949ba4]");
    });

    if (voiceStatusBar) {
      voiceStatusBar.classList.add("hidden");
      voiceStatusBar.classList.remove("flex");
    }

    // Return to current text channel
    if (voiceStageView) voiceStageView.classList.add("hidden");
    if (textChatView) textChatView.classList.remove("hidden");

    if (currentChannelTitle) currentChannelTitle.textContent = currentTextChannel;
    if (currentChannelDesc) currentChannelDesc.textContent = channelDescriptions[currentTextChannel] || "Community discussion space.";
    if (currentChannelIcon) currentChannelIcon.textContent = "tag";

    playNotificationHaptic("Disconnected from voice");
  }

  if (disconnectVoiceBtn) disconnectVoiceBtn.addEventListener("click", leaveVoiceChannel);
  if (stageLeaveVcBtn) stageLeaveVcBtn.addEventListener("click", leaveVoiceChannel);

  // Switch between stage and text chat while staying connected in VC
  if (switchChatBtn) {
    switchChatBtn.addEventListener("click", () => {
      if (voiceStageView.classList.contains("hidden")) {
        voiceStageView.classList.remove("hidden");
        textChatView.classList.add("hidden");
        switchChatBtn.innerHTML = `<span class="material-symbols-outlined text-[18px]">chat</span><span>Text Chat</span>`;
      } else {
        voiceStageView.classList.add("hidden");
        textChatView.classList.remove("hidden");
        switchChatBtn.innerHTML = `<span class="material-symbols-outlined text-[18px]">group</span><span>Voice Stage</span>`;
      }
    });
  }

  // --- Mic Toggle ---
  function toggleMic() {
    isMuted = !isMuted;
    const icons = [userMicIcon, document.getElementById("stage-mic-icon")];
    icons.forEach((ic) => {
      if (!ic) return;
      ic.textContent = isMuted ? "mic_off" : "mic";
      if (isMuted) {
        ic.classList.add("text-[#f23f43]");
        ic.parentElement.classList.add("bg-[#f23f43]/20");
      } else {
        ic.classList.remove("text-[#f23f43]");
        ic.parentElement.classList.remove("bg-[#f23f43]/20");
      }
    });

    // Update speaking indicator on user tile in stage
    const userStageTile = document.getElementById("user-stage-tile");
    if (userStageTile) {
      const ring = userStageTile.querySelector(".user-speaking-ring");
      if (ring) {
        ring.className = isMuted
          ? "user-speaking-ring absolute inset-0 rounded-2xl border-2 border-transparent transition-all pointer-events-none"
          : "user-speaking-ring absolute inset-0 rounded-2xl border-2 border-[#23a55a] shadow-[0_0_12px_rgba(35,165,90,0.5)] transition-all pointer-events-none animate-pulse";
      }
    }
  }

  if (toggleMicBtn) toggleMicBtn.addEventListener("click", toggleMic);
  if (stageMicBtn) stageMicBtn.addEventListener("click", toggleMic);

  // --- Deafen Toggle ---
  function toggleDeafen() {
    isDeafened = !isDeafened;
    if (userDeafenIcon) {
      userDeafenIcon.textContent = isDeafened ? "headset_off" : "headphones";
      if (isDeafened) {
        userDeafenIcon.classList.add("text-[#f23f43]");
        userDeafenIcon.parentElement.classList.add("bg-[#f23f43]/20");
        if (!isMuted) toggleMic(); // Deafen automatically mutes
      } else {
        userDeafenIcon.classList.remove("text-[#f23f43]");
        userDeafenIcon.parentElement.classList.remove("bg-[#f23f43]/20");
      }
    }
  }
  if (toggleDeafenBtn) toggleDeafenBtn.addEventListener("click", toggleDeafen);

  // --- Screen Share Toggle Simulation ---
  if (stageShareBtn) {
    stageShareBtn.addEventListener("click", () => {
      isScreenSharing = !isScreenSharing;
      const shareIndicator = document.getElementById("screen-share-preview");
      if (shareIndicator) {
        if (isScreenSharing) {
          shareIndicator.classList.remove("hidden");
          stageShareBtn.classList.add("bg-[#23a55a]", "text-white");
          playNotificationHaptic("Screen sharing started");
        } else {
          shareIndicator.classList.add("hidden");
          stageShareBtn.classList.remove("bg-[#23a55a]", "text-white");
          playNotificationHaptic("Screen sharing stopped");
        }
      }
    });
  }

  // --- Camera Toggle Simulation ---
  if (stageCamBtn) {
    stageCamBtn.addEventListener("click", () => {
      isCameraOn = !isCameraOn;
      const camAvatar = document.getElementById("user-stage-avatar");
      const camVideo = document.getElementById("user-stage-camera");
      if (camAvatar && camVideo) {
        if (isCameraOn) {
          camAvatar.classList.add("hidden");
          camVideo.classList.remove("hidden");
          stageCamBtn.classList.add("bg-[#23a55a]", "text-white");
        } else {
          camAvatar.classList.remove("hidden");
          camVideo.classList.add("hidden");
          stageCamBtn.classList.remove("bg-[#23a55a]", "text-white");
        }
      }
    });
  }

  // --- Message Sending ---
  if (messageForm && messageInput && messageFeed) {
    messageForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const content = messageInput.value.trim();
      if (!content) return;

      appendChatMessage("You", "Level 12 Scholar", "#5865f2", content);
      messageInput.value = "";
      messageFeed.scrollTop = messageFeed.scrollHeight;
    });
  }

  function appendChatMessage(username, role, roleColor, text) {
    const wrap = document.createElement("div");
    wrap.className = "group flex items-start gap-3.5 px-3 py-2 rounded-lg hover:bg-[#2e3035] transition-colors";

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Handle code block if wrapped in backticks
    let formattedText = escapeHtml(text);
    if (formattedText.includes("```")) {
      formattedText = formattedText.replace(/```([a-zA-Z]*)\n([\s\S]*?)```/g, (m, lang, code) => {
        return `<div class="rounded-lg overflow-hidden border border-[#1e1f22] bg-[#1e1f22] p-3 my-2 font-mono text-xs text-[#cdd6f4]">
          <div class="text-[#949ba4] text-[10px] uppercase font-bold mb-1">${lang || "code"}</div>
          <pre class="overflow-x-auto"><code>${code.trim()}</code></pre>
        </div>`;
      });
    }

    wrap.innerHTML = `
      <div class="w-10 h-10 rounded-full bg-gradient-to-tr from-[#5865f2] to-[#4752c4] text-white flex items-center justify-center font-bold text-sm shrink-0 shadow-sm mt-0.5">
        ${username.charAt(0)}
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="font-bold text-white text-sm hover:underline cursor-pointer">${escapeHtml(username)}</span>
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[${roleColor}]/20 text-[#c7d5e0] border border-[${roleColor}]/30">${escapeHtml(role)}</span>
          <span class="text-[11px] text-[#949ba4]">${timeStr}</span>
        </div>
        <div class="text-sm text-[#dbdee1] leading-relaxed mt-1 break-words">${formattedText}</div>
        <div class="flex items-center gap-1.5 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button class="reaction-pill px-2 py-0.5 rounded-full bg-[#2b2d31] hover:bg-[#35373c] border border-[#3f4147] text-xs text-[#dbdee1] flex items-center gap-1 transition-all" data-count="1">
            <span>🔥</span><span class="text-[11px] font-bold count">1</span>
          </button>
          <button class="reaction-pill px-2 py-0.5 rounded-full bg-[#2b2d31] hover:bg-[#35373c] border border-[#3f4147] text-xs text-[#dbdee1] flex items-center gap-1 transition-all" data-count="1">
            <span>👍</span><span class="text-[11px] font-bold count">1</span>
          </button>
          <button class="reaction-pill px-2 py-0.5 rounded-full bg-[#2b2d31] hover:bg-[#35373c] border border-[#3f4147] text-xs text-[#dbdee1] flex items-center gap-1 transition-all" data-count="1">
            <span>💻</span><span class="text-[11px] font-bold count">1</span>
          </button>
        </div>
      </div>
    `;

    messageFeed.appendChild(wrap);
    bindReactionPills(wrap);
  }

  // --- Emoji Reactions Interactive Click ---
  function bindReactionPills(container = document) {
    container.querySelectorAll(".reaction-pill").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        let countEl = btn.querySelector(".count");
        let current = parseInt(btn.dataset.count || "0", 10);
        let hasReacted = btn.classList.contains("border-[#5865f2]");

        if (hasReacted) {
          current = Math.max(0, current - 1);
          btn.classList.remove("border-[#5865f2]", "bg-[#5865f2]/20");
        } else {
          current += 1;
          btn.classList.add("border-[#5865f2]", "bg-[#5865f2]/20");
          triggerFloatingReaction(btn.querySelector("span:first-child").textContent);
        }

        btn.dataset.count = current;
        if (countEl) countEl.textContent = current;
      });
    });
  }
  bindReactionPills();

  // Floating reaction animation
  function triggerFloatingReaction(emoji) {
    const floater = document.createElement("div");
    floater.textContent = emoji;
    floater.className = "fixed pointer-events-none text-2xl z-50 animate-bounce";
    floater.style.left = `${Math.random() * 60 + 20}%`;
    floater.style.bottom = "80px";
    floater.style.transition = "transform 1.2s cubic-bezier(0.1, 1, 0.1, 1), opacity 1.2s ease-out";
    document.body.appendChild(floater);

    requestAnimationFrame(() => {
      floater.style.transform = `translateY(-160px) scale(1.4)`;
      floater.style.opacity = "0";
    });

    setTimeout(() => floater.remove(), 1200);
  }

  // Quick action floating emoji buttons in Voice Stage
  document.querySelectorAll(".stage-reaction-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      triggerFloatingReaction(btn.textContent);
    });
  });

  // --- Toggle Right Members Sidebar ---
  if (toggleMembersBtn && membersSidebar) {
    toggleMembersBtn.addEventListener("click", () => {
      membersSidebar.classList.toggle("hidden");
    });
  }

  // Visual notification feedback banner
  function playNotificationHaptic(msg) {
    const toast = document.createElement("div");
    toast.className = "fixed bottom-5 right-5 bg-[#23a55a] text-white px-4 py-2 rounded-xl text-xs font-bold shadow-lg z-50 flex items-center gap-2 animate-fade-in";
    toast.innerHTML = `<span class="material-symbols-outlined text-[16px]">check_circle</span><span>${escapeHtml(msg)}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.4s ease";
      setTimeout(() => toast.remove(), 400);
    }, 2200);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
});
