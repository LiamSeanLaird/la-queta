(() => {
  const registerForm = document.getElementById("register-form");
  const loginForm = document.getElementById("login-form");
  const tabRegister = document.getElementById("tab-register");
  const tabLogin = document.getElementById("tab-login");
  const gateTitle = document.getElementById("gate-title");
  const gateBlurb = document.getElementById("gate-blurb");
  const gateError = document.getElementById("gate-error");
  const loginError = document.getElementById("login-error");
  if (!registerForm || !loginForm) return;

  function showRegister() {
    registerForm.hidden = false;
    loginForm.hidden = true;
    tabRegister.classList.add("is-active");
    tabLogin.classList.remove("is-active");
    tabRegister.setAttribute("aria-selected", "true");
    tabLogin.setAttribute("aria-selected", "false");
    gateTitle.textContent = "Create a free account";
    gateBlurb.textContent = gateBlurb.dataset.signup;
    document.title = "Create a free account - La Queta";
    window.history.replaceState(null, "", "/signup");
    window.LaQueta.showError(gateError, "");
    window.LaQueta.showError(loginError, "");
  }

  function showLogin() {
    registerForm.hidden = true;
    loginForm.hidden = false;
    tabLogin.classList.add("is-active");
    tabRegister.classList.remove("is-active");
    tabLogin.setAttribute("aria-selected", "true");
    tabRegister.setAttribute("aria-selected", "false");
    gateTitle.textContent = "Sign in";
    gateBlurb.textContent = gateBlurb.dataset.signin;
    document.title = "Sign in - La Queta";
    window.history.replaceState(null, "", "/signin");
    window.LaQueta.showError(gateError, "");
    window.LaQueta.showError(loginError, "");
  }

  const PENDING_KEY = "laqueta.pendingCompletion";

  // After sign-up or sign-in, save a lesson the visitor finished logged out
  // (stored by practice.js), then land on that lesson. The server validates the
  // score exactly as it does for a logged-in learner. With nothing to save, a
  // new account goes to /continue (lesson 1) and a returning one to /levels.
  async function afterAuthHref(fallback) {
    let pending = null;
    try {
      pending = JSON.parse(window.sessionStorage.getItem(PENDING_KEY) || "null");
      window.sessionStorage.removeItem(PENDING_KEY);
    } catch (_err) {
      pending = null;
    }
    if (!pending || typeof pending.lesson_id !== "string" || !pending.lesson_id) {
      return fallback;
    }
    const lessonId = encodeURIComponent(pending.lesson_id);
    try {
      const before = await window.LaQueta.api(`/api/lessons/${lessonId}`);
      const wasCompleted = before.response.ok && before.body.completed === true;
      const { response } = await window.LaQueta.api(`/api/lessons/${lessonId}/complete`, {
        method: "POST",
        body: JSON.stringify({
          exercises_correct: pending.exercises_correct,
          exercises_total: pending.exercises_total,
          // Absent in payloads stored before scoring; the server then saves
          // the completion with no score (1 star).
          first_try_correct: pending.first_try_correct,
        }),
      });
      if (!response.ok) {
        return fallback;
      }
      return `/lessons/${lessonId}?saved=1${wasCompleted ? "" : "&finished=1"}`;
    } catch (_err) {
      return fallback;
    }
  }

  tabRegister.addEventListener("click", showRegister);
  tabLogin.addEventListener("click", showLogin);

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    window.LaQueta.showError(gateError, "");
    const handle = document.getElementById("handle-input").value.trim();
    const email = document.getElementById("reg-email-input").value.trim();
    const password = document.getElementById("reg-password-input").value;
    const { response, body } = await window.LaQueta.api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ handle, email, password }),
    });
    if (!response.ok) {
      window.LaQueta.showError(gateError, body.error || "Could not create account");
      return;
    }
    window.location.href = await afterAuthHref("/continue");
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    window.LaQueta.showError(loginError, "");
    const email = document.getElementById("login-email-input").value.trim();
    const password = document.getElementById("login-password-input").value;
    const { response, body } = await window.LaQueta.api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      window.LaQueta.showError(loginError, body.error || "Could not sign in");
      return;
    }
    window.location.href = await afterAuthHref("/levels");
  });
})();
