(() => {
  const registerForm = document.getElementById("register-form");
  const loginForm = document.getElementById("login-form");
  const tabRegister = document.getElementById("tab-register");
  const tabLogin = document.getElementById("tab-login");
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
    gateBlurb.textContent =
      "Create an account to save progress and sign in on any device.";
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
    gateBlurb.textContent = "Sign in with your email and password.";
    window.LaQueta.showError(gateError, "");
    window.LaQueta.showError(loginError, "");
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
    window.location.href = "/levels";
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
    window.location.href = "/levels";
  });
})();
