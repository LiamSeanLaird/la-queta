(() => {
  const page = document.getElementById("lesson-page");
  if (!page || page.dataset.tab !== "test") return;

  const dataEl = document.getElementById("practice-data");
  const practiceItem = document.getElementById("practice-item");
  const practiceProgressText = document.getElementById("practice-progress-text");
  const practiceProgressBar = document.getElementById("practice-progress-bar");
  const practiceEmpty = document.getElementById("practice-empty");
  const practiceDone = document.getElementById("practice-done");
  const practiceError = document.getElementById("practice-error");
  const practiceProgress = document.getElementById("practice-progress");
  const testIntro = document.getElementById("test-intro");
  const testStart = document.getElementById("test-start");
  const loggedIn = page.dataset.loggedIn === "true";
  const Speech = window.LaQueta && window.LaQueta.Speech;

  let items = [];
  try {
    items = JSON.parse(dataEl.textContent || "[]");
  } catch (_err) {
    items = [];
  }

  // The test is a queue of item indexes. A question answered right leaves the
  // queue; one answered wrong goes to the back and comes back once the others
  // are done, until it is answered right. The score is how many were right on
  // the first try.
  let queue = [];
  let seen = new Set();
  let missed = new Set();
  let current = -1;
  // True once the current question is answered, so later clicks are ignored.
  let answered = false;
  let finishing = false;

  function normalizeAnswer(value) {
    return String(value || "")
      .trim()
      // Phone keyboards type a curly apostrophe (l’estació); treat it as '.
      .replace(/[\u2018\u2019\u02bc`\u00b4]/g, "'")
      .replace(/[^\p{L}\p{N}\s'-]+/gu, "")
      .replace(/\s+/g, " ")
      .toLocaleLowerCase();
  }

  function acceptedAnswers(item) {
    if (Array.isArray(item.answers) && item.answers.length) {
      return item.answers.map(String);
    }
    if (item.answer != null) return [String(item.answer)];
    return [];
  }

  function answersMatch(userValue, accepted) {
    const needle = normalizeAnswer(userValue);
    return accepted.some((entry) => normalizeAnswer(entry) === needle);
  }

  function setProgress() {
    const total = items.length;
    const done = total - queue.length;
    if (!seen.has(current)) {
      practiceProgressText.textContent = `Question ${seen.size + 1} of ${total}`;
    } else {
      const left = queue.length;
      practiceProgressText.textContent = `Missed question - ${left} left`;
    }
    practiceProgressBar.style.width = total ? `${(done / total) * 100}%` : "0%";
  }

  // Stars from the first-try score; app/services/lessons.py lesson_stars uses
  // the same thresholds for the best score it stores.
  function starsFor(firstTry, total) {
    if (firstTry >= total) return 3;
    if (firstTry * 4 >= total * 3) return 2;
    return 1;
  }

  // Answered right: the question leaves the queue and the test moves on.
  function answerRight(delay) {
    if (answered) return false;
    answered = true;
    queue.shift();
    window.setTimeout(() => advance(), delay);
    return true;
  }

  // Answered wrong: show the answer, send the question to the back of the
  // queue, and wait for the learner to read it before moving on.
  function answerWrong(root, message) {
    if (answered) return false;
    answered = true;
    missed.add(current);
    queue.push(queue.shift());
    showExplain(root, message, false);
    const note = document.createElement("p");
    note.className = "text-small text-muted";
    note.textContent = "This question comes back at the end.";
    root.appendChild(note);
    const row = document.createElement("div");
    row.className = "study-actions__end";
    const next = document.createElement("button");
    next.type = "button";
    next.className = "btn btn--primary";
    next.textContent = "Continue";
    next.addEventListener("click", () => advance());
    row.appendChild(next);
    root.appendChild(row);
    window.setTimeout(() => next.focus(), 0);
    return true;
  }

  function answerMessage(answer, explanation) {
    const parts = [];
    if (answer) parts.push(`Answer: ${answer}`);
    if (explanation) parts.push(explanation);
    return parts.join(" - ") || "Not quite.";
  }

  function showExplain(container, text, ok) {
    let el = container.querySelector(".exercise__explain");
    if (!el) {
      el = document.createElement("p");
      el.className = "text-small exercise__explain";
      container.appendChild(el);
    }
    el.hidden = false;
    el.textContent = text || (ok ? "Correct." : "Not quite.");
  }

  function playButton(speakText) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn--secondary";
    btn.textContent = "Play";
    btn.addEventListener("click", async () => {
      if (!Speech) {
        window.LaQueta.showError(practiceError, "Audio not supported in this browser");
        return;
      }
      btn.disabled = true;
      try {
        await Speech.speak(speakText);
      } catch (_err) {
        window.LaQueta.showError(
          practiceError,
          "Could not play audio - try Chrome/Safari, or check system voices"
        );
      } finally {
        btn.disabled = false;
      }
    });
    return btn;
  }

  function renderMultipleChoice(item, root, opts = {}) {
    if (!opts.skipQuestion) {
      const question = document.createElement("p");
      question.className = "heading-3";
      question.textContent = item.question || "";
      root.appendChild(question);
    }

    const list = document.createElement("div");
    list.className = "option-list";
    (item.options || []).forEach((option) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option";
      btn.dataset.option = option;
      btn.textContent = option;
      btn.addEventListener("click", () => {
        if (finishing || answered) return;
        const accepted = acceptedAnswers(item);
        const ok = answersMatch(option, accepted);
        let rightLabel = "";
        list.querySelectorAll(".option").forEach((child) => {
          child.classList.remove("is-selected", "is-correct", "is-wrong");
          child.disabled = true;
          const label = child.dataset.option;
          if (label === option) {
            child.classList.add("is-selected");
            child.classList.add(ok ? "is-correct" : "is-wrong");
          } else if (answersMatch(label, accepted)) {
            child.classList.add("is-correct");
          }
          if (answersMatch(label, accepted)) rightLabel = label;
        });
        if (ok) {
          showExplain(root, item.explanation || "", true);
          answerRight(350);
        } else {
          answerWrong(root, answerMessage(rightLabel, item.explanation));
        }
      });
      list.appendChild(btn);
    });
    root.appendChild(list);
  }

  function renderTyped(item, root) {
    const prompt = document.createElement("p");
    prompt.className = "heading-3";
    prompt.textContent = item.prompt || item.question || "";
    root.appendChild(prompt);

    if (item.hint) {
      const hint = document.createElement("p");
      hint.className = "text-muted";
      hint.textContent = item.hint;
      root.appendChild(hint);
    }

    const isCloze =
      item.kind === "cloze" || String(item.prompt || "").includes("___");
    if (isCloze) {
      const guide = document.createElement("p");
      guide.className = "text-small text-muted";
      guide.textContent = "Fill the blank only - not the whole sentence.";
      root.appendChild(guide);
    }

    if (Array.isArray(item.options) && item.options.length) {
      renderMultipleChoice(
        {
          ...item,
          question: item.prompt || item.question,
        },
        root
      );
      return;
    }

    const row = document.createElement("div");
    row.className = "stack";

    const input = document.createElement("input");
    input.className = "input";
    input.type = "text";
    input.autocomplete = "off";
    input.autocapitalize = "off";
    input.spellcheck = false;
    input.setAttribute("aria-label", isCloze ? "Fill the blank" : "Your answer");
    if (isCloze) input.placeholder = "Blank only";

    const actions = document.createElement("div");
    actions.className = "study-actions__end";

    const submit = document.createElement("button");
    submit.type = "button";
    submit.className = "btn btn--primary";
    submit.textContent = "Check";

    function check() {
      if (finishing || answered) return;
      const accepted = acceptedAnswers(item);
      const ok = answersMatch(input.value, accepted);
      input.classList.toggle("input--error", !ok);
      input.disabled = true;
      submit.disabled = true;
      actions.hidden = true;
      if (ok) {
        showExplain(root, item.explanation || "Correct.", true);
        answerRight(450);
      } else {
        answerWrong(root, answerMessage(accepted[0] || "", item.explanation));
      }
    }

    submit.addEventListener("click", check);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        check();
      }
    });

    actions.appendChild(submit);
    row.appendChild(input);
    row.appendChild(actions);
    root.appendChild(row);
    window.setTimeout(() => input.focus(), 0);
  }

  function renderListenChoice(item, root) {
    const title = document.createElement("p");
    title.className = "heading-3";
    title.textContent = item.question || "What did you hear?";
    root.appendChild(title);
    root.appendChild(playButton(item.speak));
    renderMultipleChoice(item, root, { skipQuestion: true });
  }

  function renderListenType(item, root) {
    root.appendChild(playButton(item.speak));
    renderTyped(
      {
        ...item,
        prompt: item.prompt || "Type the Catalan you hear",
      },
      root
    );
  }

  function renderSpeak(item, root) {
    const title = document.createElement("p");
    title.className = "heading-3";
    title.textContent = item.prompt || "Say this aloud";
    root.appendChild(title);

    const target = document.createElement("p");
    target.className = "flashcard__word";
    target.lang = "ca";
    target.textContent = item.speak || "";
    root.appendChild(target);

    if (item.hint) {
      const hint = document.createElement("p");
      hint.className = "text-muted";
      hint.textContent = item.hint;
      root.appendChild(hint);
    }

    const row = document.createElement("div");
    row.className = "study-actions__end";
    row.appendChild(playButton(item.speak));

    const said = document.createElement("button");
    said.type = "button";
    said.className = "btn btn--primary";
    said.textContent = "I said it";
    said.addEventListener("click", () => {
      if (finishing || answered) return;
      said.disabled = true;
      showExplain(root, item.explanation || "Nice - keep practising aloud.", true);
      answerRight(350);
    });
    row.appendChild(said);
    root.appendChild(row);

    const status = document.createElement("p");
    status.className = "text-small";
    status.hidden = true;
    root.appendChild(status);

    if (Speech && Speech.recognitionAvailable()) {
      const listenBtn = document.createElement("button");
      listenBtn.type = "button";
      listenBtn.className = "btn btn--ghost";
      listenBtn.textContent = "Check with mic (optional)";
      listenBtn.addEventListener("click", async () => {
        status.hidden = false;
        status.textContent = "Listening…";
        try {
          const transcript = await Speech.listenOnce({ lang: "ca-ES" });
          const ok = answersMatch(transcript, [item.speak, ...(item.answers || [])]);
          status.textContent = ok
            ? `Heard: “${transcript}” - close enough.`
            : `Heard: “${transcript}” - model is “${item.speak}”. You can still tap I said it.`;
        } catch (_err) {
          status.textContent = "Mic check unavailable - use I said it.";
        }
      });
      root.appendChild(listenBtn);
    }
  }

  function renderItem() {
    current = queue[0];
    answered = false;
    const item = items[current];
    practiceItem.innerHTML = "";
    practiceItem.hidden = !item;
    practiceDone.hidden = true;
    window.LaQueta.showError(practiceError, "");
    setProgress();
    seen.add(current);
    if (!item) return;

    if (item.kind === "multiple_choice") {
      renderMultipleChoice(item, practiceItem);
    } else if (item.kind === "listen_choice") {
      renderListenChoice(item, practiceItem);
    } else if (item.kind === "listen_type") {
      renderListenType(item, practiceItem);
    } else if (item.kind === "speak") {
      renderSpeak(item, practiceItem);
    } else {
      renderTyped(item, practiceItem);
    }
  }

  function showScore(firstTry, total) {
    const stars = starsFor(firstTry, total);
    const starsEl = document.getElementById("test-score-stars");
    const textEl = document.getElementById("test-score-text");
    const retry = document.getElementById("test-retry");
    if (starsEl) {
      starsEl.querySelectorAll(".test-score__star").forEach((star, i) => {
        star.classList.toggle("is-earned", i < stars);
      });
      starsEl.setAttribute("aria-label", `${stars} of 3 stars`);
    }
    if (textEl) textEl.textContent = `${firstTry} of ${total} right first time`;
    if (retry) retry.hidden = stars >= 3;
  }

  function showDonePanel() {
    practiceDone.hidden = false;
    practiceDone.querySelector("a:not([hidden])")?.focus();
  }

  // A logged-out visitor who signs up or signs in from the done panel gets this
  // lesson saved: gate.js re-posts it to the normal, validated completion API.
  // sessionStorage keeps it to this tab, so a shared computer does not carry it
  // over to someone else's account later.
  // A retake in the same tab keeps the better score, as the server would.
  function rememberPendingCompletion(total, firstTry) {
    const key = "laqueta.pendingCompletion";
    try {
      let best = firstTry;
      const previous = JSON.parse(window.sessionStorage.getItem(key) || "null");
      if (
        previous &&
        previous.lesson_id === page.dataset.lessonId &&
        previous.exercises_total === total &&
        Number.isInteger(previous.first_try_correct)
      ) {
        best = Math.max(best, previous.first_try_correct);
      }
      window.sessionStorage.setItem(
        key,
        JSON.stringify({
          lesson_id: page.dataset.lessonId,
          exercises_correct: total,
          exercises_total: total,
          first_try_correct: best,
        })
      );
    } catch (_err) {
      // Storage blocked (private mode): the visitor can still sign up, the
      // lesson just is not saved for them.
    }
  }

  async function finish() {
    if (finishing) return;
    finishing = true;
    practiceItem.hidden = true;
    practiceProgressText.textContent = "Done";
    practiceProgressBar.style.width = "100%";
    const total = items.length;
    const firstTry = total - missed.size;
    showScore(firstTry, total);

    // The done panel (rendered by the server) offers the matching vocab deck
    // and the next lesson, so the learner stays here instead of being redirected.
    // A logged-out visitor has nothing to save: the panel asks them to sign up.
    if (!loggedIn) {
      rememberPendingCompletion(total, firstTry);
      showDonePanel();
      return;
    }

    // A retake posts too: the server keeps the best score and the first
    // completion date.
    window.LaQueta.showError(practiceError, "");
    const { response, body } = await window.LaQueta.api(
      `/api/lessons/${page.dataset.lessonId}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          exercises_correct: total,
          exercises_total: total,
          first_try_correct: firstTry,
        }),
      }
    );
    if (!response.ok) {
      window.LaQueta.showError(practiceError, body.error || "Could not save progress");
      finishing = false;
      return;
    }

    showDonePanel();
    const unlocked = Array.isArray(body.goals_unlocked) ? body.goals_unlocked : [];
    const dialog = document.getElementById("goal-unlock-dialog");
    const labelEl = document.getElementById("goal-unlock-label");
    if (unlocked.length && dialog && labelEl) {
      labelEl.textContent = unlocked.map((g) => g.label).join(" · ");
      dialog.showModal();
    }
  }

  function advance() {
    if (!queue.length) {
      finish();
      return;
    }
    renderItem();
  }

  if (!items.length) {
    practiceEmpty.hidden = false;
    return;
  }

  // The intro card (question count, words, rule) stays up until the learner
  // chooses to start, so they can review the words right before the test.
  function start() {
    queue = items.map((_item, i) => i);
    seen = new Set();
    missed = new Set();
    if (testIntro) testIntro.hidden = true;
    practiceProgress.hidden = false;
    renderItem();
    // The Start button is gone: keep keyboard focus in the first question.
    window.setTimeout(() => {
      if (!practiceItem.contains(document.activeElement)) {
        practiceItem.querySelector("input, button")?.focus();
      }
    }, 0);
  }

  if (testStart) {
    testStart.addEventListener("click", start);
  } else {
    start();
  }
})();
