(() => {
  const page = document.getElementById("browse-page");
  if (!page) return;

  const browseError = document.getElementById("browse-error");

  page.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-retire]");
    if (!button) return;
    const row = button.closest("[data-card-id]");
    if (!row) return;
    const cardId = row.dataset.cardId;
    window.LaQueta.showError(browseError, "");
    button.disabled = true;
    const { response, body } = await window.LaQueta.api(`/api/cards/${cardId}/retire`, {
      method: "POST",
      body: "{}",
    });
    if (!response.ok) {
      button.disabled = false;
      window.LaQueta.showError(browseError, body.error || "Could not retire");
      return;
    }
    row.classList.add("is-retired");
    const meta = row.querySelector(".vocab-meta");
    if (meta) {
      const dots = meta.querySelector(".seen-dots");
      if (dots) dots.remove();
      button.remove();
      if (!meta.querySelector(".badge--done")) {
        const badge = document.createElement("span");
        badge.className = "badge badge--done";
        badge.textContent = "Retired";
        meta.appendChild(badge);
      }
    }
  });
})();
