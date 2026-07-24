window.LaQueta = window.LaQueta || {};

window.LaQueta.api = async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  return { response, body };
};

window.LaQueta.showError = function showError(el, message) {
  if (!el) return;
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
};

/** Close a modal `<dialog>` when the backdrop (outside the panel) is clicked. */
window.LaQueta.bindDialogBackdropClose = function bindDialogBackdropClose(dialog) {
  if (!dialog || dialog.dataset.backdropClose === "1") return;
  dialog.dataset.backdropClose = "1";
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
};

window.LaQueta.bindAllDialogBackdropClose = function bindAllDialogBackdropClose(
  root = document,
) {
  root.querySelectorAll("dialog.dialog").forEach(window.LaQueta.bindDialogBackdropClose);
};

(function initDialogBackdropClose() {
  const run = () => window.LaQueta.bindAllDialogBackdropClose();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
