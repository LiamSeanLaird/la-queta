(() => {
  document.querySelectorAll("[data-can-dos-open]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const id = btn.getAttribute("data-can-dos-dialog") || btn.getAttribute("aria-controls");
      const dialog = id ? document.getElementById(id) : document.getElementById("can-dos-dialog");
      if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
      }
    });
  });
})();
