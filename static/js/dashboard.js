// Dashboard: filters, delete confirmation, image lightbox, toasts.
(() => {
  // Filters: dropdowns and the checkbox apply straight away; the search box uses its button or Enter
  const filters = document.getElementById("filters");
  if (filters) {
    filters.querySelectorAll("select, input[type=checkbox]").forEach((el) =>
      el.addEventListener("change", () => filters.requestSubmit()));
  }

  // Delete confirmation
  const dlg = document.getElementById("delete-dialog");
  if (dlg) {
    const form = dlg.querySelector("form");
    const who = dlg.querySelector("[data-who]");
    const confirmBtn = dlg.querySelector("button[type=submit]");
    document.querySelectorAll("[data-delete-url]").forEach((b) =>
      b.addEventListener("click", () => {
        form.action = b.dataset.deleteUrl;
        if (form.elements.next) form.elements.next.value = location.pathname + location.search;
        who.textContent = b.dataset.name;
        dlg.showModal();
      }));
    dlg.querySelector("[data-cancel]").addEventListener("click", () => dlg.close());
    form.addEventListener("submit", () => { confirmBtn.disabled = true; confirmBtn.textContent = "Deleting…"; });
  }

  // Lightbox
  const box = document.getElementById("lightbox");
  if (box) {
    const img = box.querySelector("img");
    document.querySelectorAll("[data-full]").forEach((b) =>
      b.addEventListener("click", () => { img.src = b.dataset.full; box.showModal(); }));
    box.addEventListener("click", () => box.close());
  }

  // Auto-dismiss toasts
  document.querySelectorAll(".toast").forEach((el) => setTimeout(() => el.remove(), 4500));
})();
