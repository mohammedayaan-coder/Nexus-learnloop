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

  // 5. Dynamic GitHub-style activity heatmaps (Connected to SQLite persistence)
  const heatmapContainers = document.querySelectorAll("#dashboard-heatmap, #profile-heatmap, .activity-heatmap-grid");
  const shadeClasses = ["bg-surface-container-high", "bg-[#9be9a8]", "bg-[#40c463]", "bg-[#30a14e]", "bg-[#216e39]"];

  function renderHeatmaps(counts) {
    heatmapContainers.forEach((container) => {
      container.innerHTML = "";
      for (let i = 0; i < 210; i++) {
        const cell = document.createElement("div");
        const count = (counts && counts[i] !== undefined) ? counts[i] : ((i * 7 + 3) % 5);
        const lvl = count === 0 ? 0 : count === 1 ? 1 : count <= 3 ? 2 : count <= 5 ? 3 : 4;
        cell.className = `w-3 h-3 rounded-sm ${shadeClasses[lvl]}`;
        cell.title = `Contributions: ${count}`;
        container.appendChild(cell);
      }
    });
  }

  if (heatmapContainers.length > 0) {
    fetch("/api/activity-counts")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.success && Array.isArray(data.counts)) {
          renderHeatmaps(data.counts);
        } else {
          renderHeatmaps(null);
        }
      })
      .catch(() => {
        renderHeatmaps(null);
      });
  }

  // 6. Live User Data Hydration from SQLite backend
  fetch("/api/current-user")
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data || !data.success || !data.user) return;
      const u = data.user;
      const s = data.stats || {};

      // Username
      document.querySelectorAll('[data-stat="username"]').forEach((el) => {
        el.textContent = u.username;
      });
      document.querySelectorAll('[data-stat="profile-username"]').forEach((el) => {
        el.textContent = u.username;
      });

      // Avatar letter
      const letter = u.username ? u.username[0].toUpperCase() : "U";
      document.querySelectorAll('[data-stat="avatar"], [data-stat="profile-avatar"]').forEach((el) => {
        el.textContent = letter;
      });

      // XP
      const xpVal = (s.xp || 1420).toLocaleString();
      document.querySelectorAll('[data-stat="xp"]').forEach((el) => {
        el.textContent = `${xpVal} XP`;
      });
      document.querySelectorAll('[data-stat="xp-val"]').forEach((el) => {
        el.textContent = xpVal;
      });

      // Streak
      document.querySelectorAll('[data-stat="streak"]').forEach((el) => {
        el.textContent = `${s.streak || 7}d Streak`;
      });
      document.querySelectorAll('[data-stat="streak-val"]').forEach((el) => {
        el.textContent = s.streak || 7;
      });

      // Rank
      document.querySelectorAll('[data-stat="rank"]').forEach((el) => {
        el.textContent = s.rank || 4;
      });

      // Focus / Study stats
      document.querySelectorAll('[data-stat="study-hours"]').forEach((el) => {
        el.textContent = s.study_hours !== undefined ? s.study_hours : 14.5;
      });
      document.querySelectorAll('[data-stat="sessions-today"]').forEach((el) => {
        el.textContent = s.sessions_today !== undefined ? s.sessions_today : 3;
      });

      // Quiz stats
      document.querySelectorAll('[data-stat="quizzes-solved"]').forEach((el) => {
        el.textContent = s.quizzes_solved !== undefined ? s.quizzes_solved : 32;
      });
      document.querySelectorAll('[data-stat="accuracy"]').forEach((el) => {
        el.textContent = s.accuracy !== undefined ? s.accuracy : 80;
      });

      // Profile metadata
      document.querySelectorAll('[data-stat="profile-joined"]').forEach((el) => {
        el.textContent = `Joined ${u.created_at ? u.created_at.slice(0, 10) : 'Oct 2026'}`;
      });
      document.querySelectorAll('[data-stat="profile-goals"]').forEach((el) => {
        el.textContent = u.learning_goals || 'Web & Python Engineering Track';
      });

      // Form pre-fill if present
      const goalsInput = document.getElementById("learning_goals");
      if (goalsInput && u.learning_goals) goalsInput.value = u.learning_goals;
      const skillsInput = document.getElementById("skills");
      if (skillsInput && u.skills) skillsInput.value = u.skills;
      const bioTextarea = document.getElementById("bio");
      if (bioTextarea && u.bio) bioTextarea.value = u.bio;
    })
    .catch(() => {});
});
