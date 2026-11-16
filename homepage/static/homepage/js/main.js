// Текущий год в подвале сайта.
const yearElement = document.getElementById("current-year");
if (yearElement) {
    yearElement.textContent = new Date().getFullYear();
}

// Быстрый поиск по карточкам на странице без перезагрузки.
document.querySelectorAll("[data-filter-target]").forEach((input) => {
    const cards = document.querySelectorAll(input.dataset.filterTarget);
    input.addEventListener("input", () => {
        const query = input.value.trim().toLowerCase();
        cards.forEach((card) => {
            const text = card.textContent.toLowerCase();
            card.hidden = query !== "" && !text.includes(query);
        });
    });
});
