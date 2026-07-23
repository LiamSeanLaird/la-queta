(() => {
  const page = document.getElementById("study-page");
  if (!page) return;

  const slug = page.dataset.deckSlug;
  const studyCard = document.getElementById("study-card");
  const studyLang = document.getElementById("study-lang");
  const studyWord = document.getElementById("study-word");
  const studyHint = document.getElementById("study-hint");
  const studyProgressText = document.getElementById("study-progress-text");
  const studyRemaining = document.getElementById("study-remaining");
  const studyProgressBar = document.getElementById("study-progress-bar");
  const studyNext = document.getElementById("study-next");
  const studyDone = document.getElementById("study-done");
  const studyError = document.getElementById("study-error");

  let queue = [];
  let index = 0;
  let showingCatalan = true;

  function renderCard() {
    const card = queue[index];
    if (!card) {
      studyCard.hidden = true;
      studyNext.hidden = true;
      studyDone.hidden = false;
      studyProgressText.textContent = "Done";
      studyRemaining.textContent = "";
      studyProgressBar.style.width = "100%";
      return;
    }

    studyCard.hidden = false;
    studyNext.hidden = false;
    studyDone.hidden = true;
    showingCatalan = true;
    studyLang.textContent = "Català";
    studyWord.textContent = card.catalan;
    studyHint.textContent = card.hint ? card.hint : "Tap to flip";

    const total = queue.length;
    const pct = total ? (index / total) * 100 : 0;
    studyProgressText.textContent = `Card ${index + 1} of ${total}`;
    studyRemaining.textContent = `${total - index} remaining`;
    studyProgressBar.style.width = `${pct}%`;
  }

  function flip() {
    const card = queue[index];
    if (!card) return;
    showingCatalan = !showingCatalan;
    if (showingCatalan) {
      studyLang.textContent = "Català";
      studyWord.textContent = card.catalan;
    } else {
      studyLang.textContent = "English";
      studyWord.textContent = card.english;
    }
  }

  async function boot() {
    const { response, body } = await window.LaQueta.api(`/api/decks/${slug}/session`);
    if (!response.ok) {
      window.LaQueta.showError(studyError, body.error || "Could not start study");
      return;
    }
    queue = body.cards || [];
    index = 0;
    renderCard();
  }

  studyCard.addEventListener("click", flip);
  studyCard.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      flip();
    }
  });

  studyNext.addEventListener("click", async () => {
    const card = queue[index];
    if (!card) return;
    window.LaQueta.showError(studyError, "");
    const { response, body } = await window.LaQueta.api(`/api/cards/${card.id}/seen`, {
      method: "POST",
      body: "{}",
    });
    if (!response.ok) {
      window.LaQueta.showError(studyError, body.error || "Could not save seen");
      return;
    }
    index += 1;
    renderCard();
  });

  boot();
})();
