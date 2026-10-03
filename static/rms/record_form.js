(() => {
  const summary = document.querySelector("[data-error-summary]");
  if (summary) summary.focus();
  document.addEventListener("click", event => {
    const link = event.target.closest("[data-focus-target]");
    if (!link) return;
    const target = document.getElementById(link.dataset.focusTarget);
    if (target) target.focus();
  });
  document.querySelectorAll("[data-record-form]").forEach(form => {
    form.addEventListener("submit", event => {
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = "true";
      // Keep the named submitter enabled so native POST includes its operation.
      // The original transport key stays in the form for lost-response replay.
      const status = form.querySelector(".status");
      if (status) status.textContent = "Submitting… awaiting server confirmation.";
    });
  });
  window.addEventListener("pageshow", () => {
    document.querySelectorAll("[data-record-form]").forEach(form => {
      delete form.dataset.submitting;
      const status = form.querySelector(".status");
      if (status) status.textContent = "No new save confirmed.";
    });
  });
})();
