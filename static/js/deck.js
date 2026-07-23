(() => {
  const page = document.getElementById("deck-page");
  if (!page) return;

  const slug = page.dataset.deckSlug;
  const deckError = document.getElementById("deck-error");
  const button = page.querySelector("[data-unretire]");
  if (!button) return;

  button.addEventListener("click", async () => {
    button.disabled = true;
    window.LaQueta.showError(deckError, "");
    const { response, body } = await window.LaQueta.api(`/api/decks/${slug}/unretire`, {
      method: "POST",
      body: "{}",
    });
    if (!response.ok) {
      window.LaQueta.showError(deckError, body.error || "Could not unretire deck");
      button.disabled = false;
      return;
    }
    window.location.reload();
  });
})();
