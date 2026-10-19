
document.addEventListener("DOMContentLoaded", () => {
  const messages = document.querySelectorAll(".flash");

  messages.forEach((message) => {
    // Keep messages visible long enough to read.
    window.setTimeout(() => {
      message.style.transition = "opacity 0.4s ease";
      message.style.opacity = "0";
      window.setTimeout(() => message.remove(), 450);
    }, 5000);
  });
});
