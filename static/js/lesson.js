(() => {
  const page = document.getElementById("lesson-page");
  if (!page) return;

  const completeBtn = document.getElementById("complete-lesson");
  const lessonScore = document.getElementById("lesson-score");
  const lessonError = document.getElementById("lesson-error");
  const exercises = [...page.querySelectorAll(".exercise")];
  const answers = exercises.map(() => null);
  let completed = page.dataset.completed === "true";

  function updateCompleteButton() {
    const answered = answers.filter((value) => value != null).length;
    const allDone = exercises.length === 0 || answered === exercises.length;
    completeBtn.disabled = !allDone || completed;
    completeBtn.textContent = completed ? "Completed" : "Mark complete";

    if (exercises.length && answered === exercises.length) {
      const correct = answers.filter((value, index) => {
        return value === exercises[index].dataset.answer;
      }).length;
      lessonScore.hidden = false;
      lessonScore.textContent = `Score: ${correct} / ${exercises.length}`;
    } else {
      lessonScore.hidden = true;
    }
  }

  exercises.forEach((exercise, exerciseIndex) => {
    const list = exercise.querySelector(".option-list");
    const explain = exercise.querySelector(".exercise__explain");
    const answer = exercise.dataset.answer;

    list.querySelectorAll(".option").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (completed) return;
        const option = btn.dataset.option;
        answers[exerciseIndex] = option;
        list.querySelectorAll(".option").forEach((child) => {
          child.classList.remove("is-selected", "is-correct", "is-wrong");
          const label = child.dataset.option;
          if (label === option) {
            child.classList.add("is-selected");
            child.classList.add(option === answer ? "is-correct" : "is-wrong");
          } else if (label === answer) {
            child.classList.add("is-correct");
          }
        });
        if (explain) explain.hidden = false;
        updateCompleteButton();
      });
    });
  });

  completeBtn.addEventListener("click", async () => {
    if (completeBtn.disabled) return;
    window.LaQueta.showError(lessonError, "");
    const correct = answers.filter((value, index) => {
      return value === exercises[index].dataset.answer;
    }).length;
    const { response, body } = await window.LaQueta.api(
      `/api/lessons/${page.dataset.lessonId}/complete`,
      {
        method: "POST",
        body: JSON.stringify({
          exercises_correct: correct,
          exercises_total: exercises.length,
        }),
      }
    );
    if (!response.ok) {
      window.LaQueta.showError(lessonError, body.error || "Could not save progress");
      return;
    }
    completed = true;
    updateCompleteButton();
    // Reload so the server can render the Next CTA for the following lesson/deck.
    window.location.reload();
  });

  updateCompleteButton();
})();
