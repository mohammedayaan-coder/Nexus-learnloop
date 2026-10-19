
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
      const textMatches = card.dataset.title.includes(query);
      const categoryMatches =
        selectedCategory === "all" ||
        card.dataset.category === selectedCategory;

      const visible = textMatches && categoryMatches;
      card.hidden = !visible;

      if (visible) visibleCount++;
    });

    emptyMessage.hidden = visibleCount > 0;
  }

  search.addEventListener("input", filterResources);

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");

      selectedCategory = button.dataset.category;
      filterResources();
    });
  });
});
