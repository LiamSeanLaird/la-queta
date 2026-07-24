(() => {
  const openBtn = document.getElementById("profile-open");
  const dialog = document.getElementById("profile-dialog");
  const form = document.getElementById("profile-form");
  const handleInput = document.getElementById("profile-handle");
  const emailInput = document.getElementById("profile-email");
  const errorEl = document.getElementById("profile-error");
  const cancelBtn = document.getElementById("profile-cancel");
  const logoutBtn = document.getElementById("profile-logout");
  if (!openBtn || !dialog || !form) return;

  openBtn.addEventListener("click", () => {
    window.LaQueta.showError(errorEl, "");
    dialog.showModal();
  });

  cancelBtn?.addEventListener("click", () => dialog.close());

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    window.LaQueta.showError(errorEl, "");
    const { response, body } = await window.LaQueta.api("/api/me", {
      method: "PATCH",
      body: JSON.stringify({
        handle: handleInput.value.trim(),
        email: emailInput.value.trim(),
      }),
    });
    if (!response.ok) {
      window.LaQueta.showError(errorEl, body.error || "Could not save profile");
      return;
    }
    dialog.close();
  });

  logoutBtn?.addEventListener("click", async () => {
    await window.LaQueta.api("/api/auth/logout", { method: "POST", body: "{}" });
    window.location.assign("/");
  });
})();
