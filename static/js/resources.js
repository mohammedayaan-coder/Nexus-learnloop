document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("resource-search");
  const cards = [...document.querySelectorAll(".resource-card")];
  const buttons = [...document.querySelectorAll("#resource-filters button")];
  const emptyMessage = document.getElementById("no-resources");

  if (!search || !emptyMessage) return;

  let selectedCategory = "all";

  function filterResources() {
    let visibleCount = 0;
    const query = search.value.toLowerCase().trim();

    cards.forEach((card) => {
      const textMatches = (card.dataset.title || "").includes(query);
      const categoryMatches =
        selectedCategory === "all" ||
        card.dataset.category === selectedCategory;

      const visible = textMatches && categoryMatches;
      card.classList.toggle("hidden", !visible);
      card.hidden = !visible;

      if (visible) visibleCount++;
    });

    emptyMessage.classList.toggle("hidden", visibleCount > 0);
    emptyMessage.hidden = visibleCount > 0;
  }

  search.addEventListener("input", filterResources);

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => {
        item.classList.remove("active", "bg-primary", "text-on-primary", "border-primary");
        item.classList.add("bg-surface-container-lowest", "text-on-surface-variant", "border-outline-variant");
      });
      button.classList.add("active", "bg-primary", "text-on-primary", "border-primary");
      button.classList.remove("bg-surface-container-lowest", "text-on-surface-variant", "border-outline-variant");

      selectedCategory = button.dataset.category;
      filterResources();
    });
  });
});
