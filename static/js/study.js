(() => {
  const page = document.getElementById("study-page");
  if (!page) return;

  const slug = page.dataset.deckSlug;
  const studyCard = document.getElementById("study-card");
  const studyLang = document.getElementById("study-lang");
  const studyWord = document.getElementById("study-word");
  const studyPronunciation = document.getElementById("study-pronunciation");
  const studyGrammar = document.getElementById("study-grammar");
  const studyForms = document.getElementById("study-forms");
  const studyHint = document.getElementById("study-hint");
  const studyProgressText = document.getElementById("study-progress-text");
  const studyRemaining = document.getElementById("study-remaining");
  const studyProgressBar = document.getElementById("study-progress-bar");
  const studyNext = document.getElementById("study-next");
  const studyDone = document.getElementById("study-done");
  const studyError = document.getElementById("study-error");

  const POS_LABELS = {
    noun: "noun",
    verb: "verb",
    adjective: "adj",
    adverb: "adv",
    number: "num",
    interjection: "interj",
  };

  let queue = [];
  let index = 0;
  let showingCatalan = true;

  function grammarHtml(card) {
    const pills = [];
    if (card.pos && card.pos !== "phrase") {
      pills.push(
        `<span class="gram-pill gram-pill--pos">${POS_LABELS[card.pos] || card.pos}</span>`
      );
    }
    if (card.gender === "m") {
      pills.push('<span class="gram-pill gram-pill--m">masculine</span>');
    }
    if (card.gender === "f") {
      pills.push('<span class="gram-pill gram-pill--f">feminine</span>');
    }
    if (card.plural && card.plural !== "—") {
      pills.push(`<span class="gram-pill gram-pill--pl">pl: ${card.plural}</span>`);
    }
    return pills.join("");
  }

  function verbFormsText(card) {
    if (card.pos !== "verb" || !card.forms || !card.forms.length) return "";
    return card.forms.join(" · ");
  }

  function setMeta(card, showCatalanSide) {
    const pronunciation = showCatalanSide ? card.pronunciation || "" : "";
    studyPronunciation.textContent = pronunciation;
    studyPronunciation.hidden = !pronunciation;

    const grammar = showCatalanSide ? grammarHtml(card) : "";
    studyGrammar.innerHTML = grammar;
    studyGrammar.hidden = !grammar;

    const forms = showCatalanSide ? verbFormsText(card) : "";
    studyForms.textContent = forms;
    studyForms.hidden = !forms;

    if (showCatalanSide) {
      studyHint.textContent = card.hint || "Tap to flip";
    } else {
      studyHint.textContent = card.hint || "Tap to flip";
    }
  }

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
    setMeta(card, true);

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
      setMeta(card, true);
    } else {
      studyLang.textContent = "English";
      studyWord.textContent = card.english;
      setMeta(card, false);
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
