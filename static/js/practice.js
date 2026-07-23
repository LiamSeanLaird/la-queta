(() => {
  const page = document.getElementById("lesson-page");
  if (!page || page.dataset.tab !== "practice") return;

  const dataEl = document.getElementById("practice-data");
  const practiceItem = document.getElementById("practice-item");
  const practiceProgressText = document.getElementById("practice-progress-text");
  const practiceProgressBar = document.getElementById("practice-progress-bar");
  const practiceEmpty = document.getElementById("practice-empty");
  const practiceDone = document.getElementById("practice-done");
  const practiceError = document.getElementById("practice-error");
  const lessonsUrl = page.dataset.lessonsUrl;
  const alreadyCompleted = page.dataset.completed === "true";

  let items = [];
  try {
    items = JSON.parse(dataEl.textContent || "[]");
  } catch (_err) {
    items = [];
  }

  let index = 0;
  let finishing = false;

  function normalizeAnswer(value) {
    return String(value || "")
      .trim()
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
    const done = Math.min(index, total);
    practiceProgressText.textContent = total
      ? `Item ${Math.min(index + 1, total)} of ${total}`
      : "No items";
    practiceProgressBar.style.width = total ? `${(done / total) * 100}%` : "0%";
  }

  function showExplain(container, text, ok) {
    let el = container.querySelector(".exercise__explain");
    if (!el) {
      el = document.createElement("p");
      el.className = "text-small exercise__explain";
      container.appendChild(el);
    }
    el.hidden = false;
    el.textContent = text || (ok ? "Correct." : "Try again.");
  }

  function renderMultipleChoice(item, root) {
    const question = document.createElement("p");
    question.className = "heading-3";
    question.textContent = item.question || "";
    root.appendChild(question);

    const list = document.createElement("div");
    list.className = "option-list";
    (item.options || []).forEach((option) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "option";
      btn.dataset.option = option;
      btn.textContent = option;
      btn.addEventListener("click", () => {
        if (finishing) return;
        const ok = answersMatch(option, acceptedAnswers(item));
        list.querySelectorAll(".option").forEach((child) => {
          child.classList.remove("is-selected", "is-correct", "is-wrong");
          const label = child.dataset.option;
          if (label === option) {
            child.classList.add("is-selected");
            child.classList.add(ok ? "is-correct" : "is-wrong");
          } else if (answersMatch(label, acceptedAnswers(item))) {
            child.classList.add("is-correct");
          }
        });
        showExplain(root, item.explanation || "", ok);
        if (ok) {
          window.setTimeout(() => advance(), 350);
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
    input.setAttribute("aria-label", "Your answer");

    const submit = document.createElement("button");
    submit.type = "button";
    submit.className = "btn btn--primary";
    submit.textContent = "Check";

    function check() {
      if (finishing) return;
      const ok = answersMatch(input.value, acceptedAnswers(item));
      input.classList.toggle("input--error", !ok);
      showExplain(root, item.explanation || "", ok);
      if (ok) {
        input.disabled = true;
        submit.disabled = true;
        window.setTimeout(() => advance(), 350);
      } else {
        input.focus();
        input.select();
      }
    }

    submit.addEventListener("click", check);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        check();
      }
    });

    row.appendChild(input);
    row.appendChild(submit);
    root.appendChild(row);
    window.setTimeout(() => input.focus(), 0);
  }

  function renderItem() {
    const item = items[index];
    practiceItem.innerHTML = "";
    practiceItem.hidden = !item;
    practiceDone.hidden = true;
    setProgress();
    if (!item) return;

    if (item.kind === "multiple_choice") {
      renderMultipleChoice(item, practiceItem);
    } else {
      renderTyped(item, practiceItem);
    }
  }

  async function finish() {
    if (finishing) return;
    finishing = true;
    practiceItem.hidden = true;
    practiceDone.hidden = false;
    practiceProgressText.textContent = "Done";
    practiceProgressBar.style.width = "100%";

    if (alreadyCompleted) {
      if (lessonsUrl) window.location.assign(lessonsUrl);
      return;
    }

    window.LaQueta.showError(practiceError, "");
    const total = items.length;
    const { response, body } = await window.LaQueta.api(
      `/api/lessons/${page.dataset.lessonId}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          exercises_correct: total,
          exercises_total: total,
        }),
      }
    );
    if (!response.ok) {
      window.LaQueta.showError(practiceError, body.error || "Could not save progress");
      finishing = false;
      return;
    }
    if (lessonsUrl) {
      window.location.assign(lessonsUrl);
    }
  }

  function advance() {
    index += 1;
    if (index >= items.length) {
      finish();
      return;
    }
    renderItem();
  }

  if (!items.length) {
    practiceEmpty.hidden = false;
    practiceProgressText.textContent = "No items";
    return;
  }

  renderItem();
})();
