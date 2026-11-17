(() => {
  const page = document.getElementById("study-page");
  if (!page) return;

  const RETIRE_SKIP_KEY = "la-queta-retire-skip-confirm";
  const TIP_SKIP_KEY = "la-queta-study-tip-skip";

  const sessionUrl = page.dataset.sessionUrl;
  // Only daily vocab sets this: finishing it counts toward the streak.
  const completeUrl = page.dataset.completeUrl;
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
  const studyFlip = document.getElementById("study-flip");
  const studyGrade = document.getElementById("study-grade");
  const studyNotYet = document.getElementById("study-not-yet");
  const studyKnew = document.getElementById("study-knew");
  const studyRetire = document.getElementById("study-retire");
  const studyDone = document.getElementById("study-done");
  const studyDoneTitle = document.getElementById("study-done-title");
  const studyDoneText = document.getElementById("study-done-text");
  const studyAgain = document.getElementById("study-again");
  const studyExit = document.getElementById("study-exit");
  const studyNextLesson = document.getElementById("study-next-lesson");
  const studyProgress = document.getElementById("study-progress");
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
    pronoun: "pron",
    interjection: "interj",
    phrase: "phrase",
  };

  let queue = [];
  let index = 0;
  let showingCatalan = true;
  let advancing = false;
  // Card ids the learner retired in this session, by tapping Retire or by
  // reaching the seen threshold. Cards that were already retired don't count.
  const retiredThisSession = new Set();
  // Card ids already counted in this session (graded or retired). Going Back
  // and grading a card again, or meeting a Not yet card again at the end of
  // the session, must not count it a second time.
  const countedThisSession = new Set();
  // Card ids the learner graded Knew it the first time they met them.
  const knewThisSession = new Set();
  // Card ids graded Not yet and queued again at the end (once per session).
  const requeuedThisSession = new Set();

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
    // The grade buttons only make sense once the learner has seen the answer.
    studyFlip.hidden = !catalanSide;
    studyGrade.hidden = catalanSide;
  }

  function plural(count, word) {
    return `${count} ${word}${count === 1 ? "" : "s"}`;
  }

  /** Distinct cards in the session; Not yet cards appear in the queue twice. */
  function uniqueCardCount() {
    return new Set(queue.map((card) => card.id)).size;
  }

  function summaryText() {
    const total = uniqueCardCount();
    const retired = retiredThisSession.size;
    if (retired === total) {
      return `You went through ${plural(total, "card")} and retired all of them.`;
    }
    const knew = `You knew ${knewThisSession.size} of ${plural(total, "card")}`;
    const retiredPart = retired > 0 ? ` and retired ${retired}` : "";
    return `${knew}${retiredPart}. ` +
      "A card retires after you knew it 3 times, or when you tap Retire.";
  }

  function browserTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch (error) {
      return "";
    }
  }

  async function recordComplete() {
    if (!completeUrl) return;
    const { response, body } = await window.LaQueta.api(completeUrl, {
      method: "POST",
      body: JSON.stringify({ timezone: browserTimezone() }),
    });
    if (!response.ok) {
      window.LaQueta.showError(studyError, body.error || "Could not save today's session");
    }
  }

  function finishSession() {
    studyCard.hidden = true;
    studyGrade.hidden = true;
    studyActions.hidden = true;
    studyDone.hidden = false;
    studyRemaining.textContent = "";
    if (queue.length) {
      studyProgressText.textContent = "Done";
      studyProgressBar.style.width = "100%";
      studyDoneTitle.textContent = "Session complete";
      studyDoneText.textContent = summaryText();
      recordComplete();
    } else {
      studyProgress.hidden = true;
      studyDoneTitle.textContent = "Nothing to study";
      studyDoneText.textContent = studyDoneText.dataset.emptyText;
    }
    // Studying again only helps if this session left unretired cards behind.
    const canStudyAgain = uniqueCardCount() > retiredThisSession.size;
    studyAgain.hidden = !canStudyAgain;
    // Without Study again, the next button down becomes the main one:
    // the next lesson when there is one, else the way back.
    if (studyNextLesson) {
      studyNextLesson.classList.toggle("btn--primary", !canStudyAgain);
      studyNextLesson.classList.toggle("btn--secondary", canStudyAgain);
    } else {
      studyExit.classList.toggle("btn--primary", !canStudyAgain);
      studyExit.classList.toggle("btn--secondary", canStudyAgain);
    }
  }

  function noteRetired(card, body) {
    if (body && body.retired && !card.retired) {
      retiredThisSession.add(card.id);
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

  /** Tap / Enter / Show answer: turn the card over (either way). */
  function flip() {
    if (!queue[index] || advancing) return;
    showFace(!showingCatalan);
  }

  function requeue(card) {
    if (requeuedThisSession.has(card.id)) return;
    requeuedThisSession.add(card.id);
    queue.push(card);
  }

  /** Knew it / Not yet: save the grade once per card, then move on. */
  async function gradeCurrent(grade) {
    const card = queue[index];
    if (!card || advancing || showingCatalan) return;
    if (countedThisSession.has(card.id)) {
      index += 1;
      renderCard();
      return;
    }
    advancing = true;
    window.LaQueta.showError(studyError, "");
    try {
      const { response, body } = await window.LaQueta.api(`/api/cards/${card.id}/grade`, {
        method: "POST",
        body: JSON.stringify({ grade }),
      });
      if (!response.ok) {
        window.LaQueta.showError(studyError, body.error || "Could not save your answer");
        return;
      }
      countedThisSession.add(card.id);
      noteRetired(card, body);
      if (grade === "knew") {
        knewThisSession.add(card.id);
      } else {
        requeue(card);
      }
      index += 1;
      renderCard();
    } finally {
      advancing = false;
    }
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
      countedThisSession.add(card.id);
      noteRetired(card, body);
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
    if (!sessionUrl) {
      window.LaQueta.showError(studyError, "Missing study session");
      return;
    }
    const { response, body } = await window.LaQueta.api(sessionUrl);
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
    flip();
  });

  document.addEventListener("keydown", (event) => {
    if (dialogOpen()) return;
    const tag = event.target && event.target.tagName;
    if (tag && ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tag)) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      flip();
    } else if (event.key === "1" && !showingCatalan) {
      gradeCurrent("not_yet");
    } else if (event.key === "2" && !showingCatalan) {
      gradeCurrent("knew");
    }
  });

  studyFlip.addEventListener("click", flip);
  studyNotYet.addEventListener("click", () => gradeCurrent("not_yet"));
  studyKnew.addEventListener("click", () => gradeCurrent("knew"));
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
