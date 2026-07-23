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
