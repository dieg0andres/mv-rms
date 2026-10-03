(() => {
  const summary = document.querySelector("[data-error-summary]");
  if (summary) summary.focus();
  document.addEventListener("click", event => {
    const link = event.target.closest("[data-focus-target]");
    if (!link) return;
    const target = document.getElementById(link.dataset.focusTarget);
    if (target) target.focus();
  });
  document.addEventListener("submit", event => {
    if (!event.target.matches("[data-draft-preview]")) return;
    event.preventDefault();
    const status = event.target.querySelector(".status");
    if (status) status.textContent = "Not saved. This repository-only preview is not connected.";
  });
})();
