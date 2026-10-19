
document.addEventListener("DOMContentLoaded", () => {
  const clock = document.getElementById("timer-clock");
  const status = document.getElementById("timer-status");
  const startButton = document.getElementById("timer-start");
  const resetButton = document.getElementById("timer-reset");
  const saveButton = document.getElementById("timer-save");
  const minutesInput = document.getElementById("timer-minutes");

  if (!clock || !startButton) return;

  let totalSeconds = 25 * 60;
  let remaining = totalSeconds;
  let interval = null;
  let finished = false;

  function renderTime() {
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;

    clock.textContent =
      String(minutes).padStart(2, "0") + ":" +
      String(seconds).padStart(2, "0");
  }

  function stopTimer() {
    if (interval !== null) {
      clearInterval(interval);
      interval = null;
    }
  }

  document.querySelectorAll(".preset").forEach((button) => {
    button.addEventListener("click", () => {
      if (interval !== null) return;

      const minutes = Number(button.dataset.minutes);

      totalSeconds = minutes * 60;
      remaining = totalSeconds;
      finished = false;

      minutesInput.value = String(minutes);
      startButton.disabled = false;
      saveButton.disabled = true;
      status.textContent = "Ready when you are.";
      renderTime();
    });
  });

  startButton.addEventListener("click", () => {
    if (interval !== null || finished) return;

    startButton.disabled = true;
    status.textContent = "Focus in progress...";

    interval = setInterval(() => {
      remaining--;
      renderTime();

      if (remaining <= 0) {
        stopTimer();
        finished = true;
        status.textContent = "Session complete! Great work.";
        saveButton.disabled = false;
      }
    }, 1000);
  });

  resetButton.addEventListener("click", () => {
    stopTimer();
    remaining = totalSeconds;
    finished = false;

    startButton.disabled = false;
    saveButton.disabled = true;
    status.textContent = "Ready when you are.";

    renderTime();
  });

  renderTime();
});
