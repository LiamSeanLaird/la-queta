(() => {
  const btn = document.getElementById("logout-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    await window.LaQueta.api("/api/auth/logout", { method: "POST", body: "{}" });
    window.location.href = "/";
  });
})();
