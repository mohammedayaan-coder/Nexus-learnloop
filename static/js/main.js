/**
 * Nexus Learn Loop — Main Application JS
 */
document.addEventListener("DOMContentLoaded", () => {
  // 1. Flash alert auto-dismiss
  const flashMessages = document.querySelectorAll(".flash, [role='alert']");
  flashMessages.forEach((message) => {
    window.setTimeout(() => {
      message.style.transition = "opacity 0.4s ease, transform 0.4s ease";
      message.style.opacity = "0";
      message.style.transform = "translateY(-8px)";
      window.setTimeout(() => message.remove(), 450);
    }, 5000);
  });

  // 2. Password visibility toggle
  const togglePwdButtons = document.querySelectorAll("#toggle-pwd, .toggle-password");
  togglePwdButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const parent = btn.closest(".relative") || btn.parentElement;
      const input = parent?.querySelector("input[type='password'], input[type='text']");
      const icon = btn.querySelector(".material-symbols-outlined");
      if (!input) return;

      if (input.type === "password") {
        input.type = "text";
        if (icon) icon.textContent = "visibility_off";
      } else {
        input.type = "password";
        if (icon) icon.textContent = "visibility";
      }
    });
  });

  // 3. Tactile button click feedback
  document.querySelectorAll(".tactile-primary, .tactile-secondary, .tactile-btn, .tactile-ghost").forEach((el) => {
    el.addEventListener("mousedown", () => {
      el.style.transform = "translateY(2px)";
    });
    el.addEventListener("mouseup", () => {
      el.style.transform = "";
    });
    el.addEventListener("mouseleave", () => {
      el.style.transform = "";
    });
  });

  // 4. Smooth internal links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      const targetId = this.getAttribute("href");
      if (targetId && targetId !== "#") {
        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth" });
        }
      }
    });
  });

  // 5. Dynamic GitHub-style activity heatmaps (Zero template leaks)
  const heatmapContainers = document.querySelectorAll("#dashboard-heatmap, #profile-heatmap, .activity-heatmap-grid");
  const shadeClasses = ["bg-surface-container-high", "bg-[#9be9a8]", "bg-[#40c463]", "bg-[#30a14e]", "bg-[#216e39]"];
  heatmapContainers.forEach((container) => {
    container.innerHTML = "";
    for (let i = 0; i < 210; i++) {
      const cell = document.createElement("div");
      const lvl = (i * 7 + 3) % 5;
      cell.className = `w-3 h-3 rounded-sm ${shadeClasses[lvl]}`;
      cell.title = `Contributions: ${lvl * 2 + 1}`;
      container.appendChild(cell);
    }
  });
});
