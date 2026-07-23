(() => {
  const page = document.getElementById("study-page");
  if (!page) return;

  const RETIRE_SKIP_KEY = "la-queta-retire-skip-confirm";
  const TIP_SKIP_KEY = "la-queta-study-tip-skip";

  const slug = page.dataset.deckSlug;
  const deckUrl = page.dataset.deckUrl;
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
  const studyActions = document.getElementById("study-actions");
  const studyBack = document.getElementById("study-back");
  const studyNext = document.getElementById("study-next");
  const studyRetire = document.getElementById("study-retire");
  const studyDone = document.getElementById("study-done");
  const studyError = document.getElementById("study-error");
  const tipDialog = document.getElementById("study-tip-dialog");
  const tipDontShow = document.getElementById("study-tip-dont-show");
  const retireDialog = document.getElementById("retire-dialog");
  const retireDontShow = document.getElementById("retire-dont-show");

  const POS_LABELS = {
    noun: "noun",
    verb: "verb",
    adjective: "adj",
    adverb: "adv",
    number: "num",
    interjection: "interj",
    phrase: "phrase",
  };

  let queue = [];
  let index = 0;
  let showingCatalan = true;
  let advancing = false;

  function dialogOpen() {
    return (tipDialog && tipDialog.open) || (retireDialog && retireDialog.open);
  }

  function grammarHtml(card) {
    const pills = [];
    if (card.pos) {
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

    const hint = showCatalanSide && card.hint ? card.hint : "";
    studyHint.textContent = hint;
    studyHint.hidden = !hint;
  }

  function showFace(catalanSide) {
    const card = queue[index];
    if (!card) return;
    showingCatalan = catalanSide;
    if (catalanSide) {
      studyLang.textContent = "Català";
      studyWord.textContent = card.catalan;
      setMeta(card, true);
    } else {
      studyLang.textContent = "English";
      studyWord.textContent = card.english;
      setMeta(card, false);
    }
  }

  function finishSession() {
    studyCard.hidden = true;
    studyActions.hidden = true;
    studyDone.hidden = false;
    studyProgressText.textContent = "Done";
    studyRemaining.textContent = "";
    studyProgressBar.style.width = "100%";
    if (deckUrl) {
      window.location.assign(deckUrl);
    }
  }

  function renderCard() {
    const card = queue[index];
    if (!card) {
      finishSession();
      return;
    }

    studyCard.hidden = false;
    studyActions.hidden = false;
    studyDone.hidden = true;
    studyBack.disabled = index === 0;
    showFace(true);

    const total = queue.length;
    const pct = total ? (index / total) * 100 : 0;
    studyProgressText.textContent = `Card ${index + 1} of ${total}`;
    studyRemaining.textContent = `${total - index} remaining`;
    studyProgressBar.style.width = `${pct}%`;
  }

  function flipToEnglish() {
    if (!queue[index] || !showingCatalan) return;
    showFace(false);
  }

  async function advanceSeen() {
    const card = queue[index];
    if (!card || advancing) return;
    advancing = true;
    window.LaQueta.showError(studyError, "");
    try {
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
    } finally {
      advancing = false;
    }
  }

  /** Tap / Enter / Next: Catalan → English → next card (seen++). */
  async function stepThrough() {
    if (!queue[index] || advancing) return;
    if (showingCatalan) {
      flipToEnglish();
      return;
    }
    await advanceSeen();
  }

  function goBack() {
    if (index === 0 || advancing) return;
    index -= 1;
    renderCard();
  }

  async function retireCurrent() {
    const card = queue[index];
    if (!card || advancing) return;
    advancing = true;
    window.LaQueta.showError(studyError, "");
    try {
      const { response, body } = await window.LaQueta.api(
        `/api/cards/${card.id}/retire`,
        { method: "POST", body: "{}" }
      );
      if (!response.ok) {
        window.LaQueta.showError(studyError, body.error || "Could not retire");
        return;
      }
      index += 1;
      renderCard();
    } finally {
      advancing = false;
    }
  }

  function requestRetire() {
    if (!queue[index] || advancing) return;
    if (localStorage.getItem(RETIRE_SKIP_KEY) === "1") {
      retireCurrent();
      return;
    }
    retireDontShow.checked = true;
    retireDialog.showModal();
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
    if (queue[index]) {
      maybeShowTip();
    }
  }

  function maybeShowTip() {
    if (!tipDialog || localStorage.getItem(TIP_SKIP_KEY) === "1") return;
    tipDontShow.checked = true;
    tipDialog.showModal();
  }

  studyCard.addEventListener("click", () => {
    if (dialogOpen()) return;
    stepThrough();
  });

  document.addEventListener("keydown", (event) => {
    if (dialogOpen()) return;
    const tag = event.target && event.target.tagName;
    if (tag && ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tag)) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      stepThrough();
    }
  });

  studyNext.addEventListener("click", () => stepThrough());
  studyBack.addEventListener("click", goBack);
  studyRetire.addEventListener("click", requestRetire);

  tipDialog.addEventListener("close", () => {
    if (tipDialog.returnValue !== "ok") return;
    if (tipDontShow.checked) {
      localStorage.setItem(TIP_SKIP_KEY, "1");
    }
  });

  retireDialog.addEventListener("close", () => {
    if (retireDialog.returnValue !== "confirm") return;
    if (retireDontShow.checked) {
      localStorage.setItem(RETIRE_SKIP_KEY, "1");
    }
    retireCurrent();
  });

  boot();
})();
