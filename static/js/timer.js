document.addEventListener("DOMContentLoaded", () => {
  const clock = document.getElementById("timer-clock");
  const status = document.getElementById("timer-status");
  const startButton = document.getElementById("timer-start");
  const resetButton = document.getElementById("timer-reset");
  const skipButton = document.getElementById("skip-btn");
  const saveButton = document.getElementById("timer-save");
  const saveForm = document.getElementById("timer-save-form");
  const minutesInput = document.getElementById("timer-minutes");
  const startedAtInput = document.getElementById("timer-started-at");
  const timerRing = document.getElementById("timer-ring");
  const headerCta = document.getElementById("timer-cta");

  if (!clock || !startButton) return;

  const RADIUS = 130;
  const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ~816.81
  if (timerRing) {
    timerRing.style.strokeDasharray = `${CIRCUMFERENCE}`;
    timerRing.style.strokeDashoffset = "0";
  }

  let currentMinutes = 25;
  let totalSeconds = currentMinutes * 60;
  let remaining = totalSeconds;
  let interval = null;
  let isRunning = false;
  let finished = false;
  let startedAt = null;

  function updateRing() {
    if (!timerRing) return;
    const progress = (totalSeconds - remaining) / totalSeconds;
    const offset = CIRCUMFERENCE * progress;
    timerRing.style.strokeDashoffset = `${offset}`;
  }

  function renderTime() {
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;

    clock.textContent =
      String(minutes).padStart(2, "0") + ":" +
      String(seconds).padStart(2, "0");

    updateRing();
  }

  function stopTimer() {
    if (interval !== null) {
      clearInterval(interval);
      interval = null;
    }
    isRunning = false;
  }

  function updateStartButtonState() {
    if (isRunning) {
      startButton.innerHTML = `
        <span class="material-symbols-outlined text-[26px]" style="font-variation-settings:'FILL' 1;">pause</span>
        <span>Pause</span>
      `;
      startButton.classList.replace("bg-primary", "bg-amber-600");
    } else {
      startButton.innerHTML = `
        <span class="material-symbols-outlined text-[26px]" style="font-variation-settings:'FILL' 1;">play_arrow</span>
        <span>Start Focus</span>
      `;
      startButton.classList.replace("bg-amber-600", "bg-primary");
    }
  }

  // Presets (Pomodoro, Short Break, Deep Hack)
  const presetButtons = document.querySelectorAll(".preset");
  presetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      stopTimer();

      presetButtons.forEach((btn) => {
        btn.className = "preset px-5 py-2 rounded-full text-on-surface-variant hover:text-on-surface font-label-bold text-label-bold transition-all hover:bg-surface-container-high/60 flex items-center gap-1.5";
        const dot = btn.querySelector(".w-1\\.5");
        if (dot) dot.remove();
      });

      button.className = "preset px-5 py-2 rounded-full bg-surface-container-lowest text-primary font-label-bold text-label-bold shadow-sm transition-all flex items-center gap-1.5";
      const dot = document.createElement("span");
      dot.className = "w-1.5 h-1.5 rounded-full bg-primary";
      button.prepend(dot);

      currentMinutes = Number(button.dataset.minutes) || 25;
      totalSeconds = currentMinutes * 60;
      remaining = totalSeconds;
      finished = false;
      startedAt = null;

      if (minutesInput) minutesInput.value = String(currentMinutes);
      if (saveButton) saveButton.disabled = true;
      if (saveForm) saveForm.classList.add("hidden");

      status.textContent = "Ready when you are.";
      updateStartButtonState();
      renderTime();
    });
  });

  // Start / Pause toggle
  function handleStartPause() {
    if (finished) return;

    if (isRunning) {
      stopTimer();
      status.textContent = "Session paused.";
      updateStartButtonState();
      return;
    }

    isRunning = true;
    if (!startedAt) startedAt = new Date();
    updateStartButtonState();
    status.textContent = "Focus sprint in progress...";

    interval = setInterval(() => {
      remaining--;
      renderTime();

      if (remaining <= 0) {
        stopTimer();
        finished = true;
        updateStartButtonState();
        status.textContent = "Session complete! +30 XP unlocked 🎉";
        if (minutesInput) minutesInput.value = String(currentMinutes);
        if (startedAtInput && startedAt) startedAtInput.value = startedAt.toISOString();
        if (saveButton) saveButton.disabled = false;
        if (saveForm) saveForm.classList.remove("hidden");
      }
    }, 1000);
  }

  startButton.addEventListener("click", handleStartPause);
  if (headerCta) {
    headerCta.addEventListener("click", handleStartPause);
  }

  // Reset
  resetButton.addEventListener("click", () => {
    stopTimer();
    remaining = totalSeconds;
    finished = false;
    startedAt = null;

    if (saveButton) saveButton.disabled = true;
    if (saveForm) saveForm.classList.add("hidden");

    status.textContent = "Ready when you are.";
    updateStartButtonState();
    renderTime();
  });

  // Skip
  if (skipButton) {
    skipButton.addEventListener("click", () => {
      stopTimer();
      remaining = 0;
      finished = true;
      startedAt = null;
      updateStartButtonState();
      status.textContent = "Session skipped. Next loop ready.";
      renderTime();
    });
  }

  // Soundscape selector
  const soundscapeButtons = document.querySelectorAll("aside button");
  soundscapeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!btn.querySelector(".material-symbols-outlined")) return;
      const soundName = btn.querySelector("span:last-child")?.textContent?.trim();
      if (soundName && (soundName.includes("Rain") || soundName.includes("Stream") || soundName.includes("Binaural") || soundName.includes("Coffee"))) {
        soundscapeButtons.forEach((b) => {
          b.classList.remove("border-primary", "bg-primary-fixed", "border-2");
          b.classList.add("border-outline-variant", "bg-surface-container-low");
        });
        btn.classList.add("border-primary", "bg-primary-fixed", "border-2");
        btn.classList.remove("border-outline-variant", "bg-surface-container-low");
      }
    });
  });

  renderTime();
});
