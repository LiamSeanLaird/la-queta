(() => {
  const form = document.getElementById("register-form");
  const handleInput = document.getElementById("handle-input");
  const gateError = document.getElementById("gate-error");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    window.LaQueta.showError(gateError, "");
    const handle = handleInput.value.trim();
    const { response, body } = await window.LaQueta.api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ handle }),
    });
    if (!response.ok) {
      window.LaQueta.showError(gateError, body.error || "Could not register");
      return;
    }
    window.location.href = "/levels";
  });
})();
