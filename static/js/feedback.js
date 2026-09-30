// Feedback form: live validation, image preview, loading and error states.
(() => {
  const MAX_BYTES = 2 * 1024 * 1024;
  const TYPES = ["image/jpeg", "image/png", "image/webp"];

  const form = document.getElementById("fb-form");
  if (!form) return;

  const nameEl = form.elements["name"];
  const msgEl = form.elements["message"];
  const imgEl = form.elements["image"];
  const btn = document.getElementById("submit-btn");
  const btnLabel = btn.querySelector(".label-text");
  const spinner = btn.querySelector(".spinner");
  const banner = document.getElementById("form-error");
  const counter = document.getElementById("msg-counter");
  const dropzone = document.getElementById("dropzone");
  const previewWrap = document.getElementById("preview-wrap");
  const previewImg = document.getElementById("preview");
  const previewMeta = document.getElementById("preview-meta");
  const removeBtn = document.getElementById("preview-remove");

  let previewUrl = null;

  const setError = (field, message) => {
    const el = form.elements[field];
    const out = form.querySelector(`[data-for="${field}"]`);
    if (out) out.textContent = message || "";
    if (el) el.setAttribute("aria-invalid", message ? "true" : "false");
  };

  const validators = {
    name() {
      const v = nameEl.value.trim();
      if (!v) return "Enter your name.";
      if (!/^[\p{L}\s]+$/u.test(v)) return "Name can only contain letters and spaces (no numbers or symbols).";
      return "";
    },
    message() {
      const v = msgEl.value.trim();
      if (!v) return "Write your feedback.";
      return "";
    },
    image() {
      const f = imgEl.files[0];
      if (!f) return "";
      if (!TYPES.includes(f.type)) return "Use a JPG, PNG or WEBP image.";
      if (f.size > MAX_BYTES) return `Image is ${(f.size / 1048576).toFixed(1)} MB. The limit is 2 MB.`;
      return "";
    },
  };

  const showBanner = (text) => {
    banner.textContent = text;
    banner.classList.toggle("hidden", !text);
  };

  const setLoading = (on) => {
    btn.disabled = on;
    spinner.classList.toggle("hidden", !on);
    btnLabel.textContent = on ? "Sending…" : "Send feedback";
  };

  // Character counter
  const updateCounter = () => {
    const n = msgEl.value.length;
    counter.textContent = `${n} character${n === 1 ? "" : "s"}`;
  };
  msgEl.addEventListener("input", updateCounter);
  updateCounter();

  // Validate on blur, clear on input
  ["name", "message"].forEach((f) => {
    const el = form.elements[f];
    el.addEventListener("blur", () => setError(f, validators[f]()));
    el.addEventListener("input", () => {
      if (el.getAttribute("aria-invalid") === "true") setError(f, validators[f]());
    });
  });

  // Image preview
  const clearImage = () => {
    imgEl.value = "";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    previewWrap.classList.add("hidden");
    previewImg.removeAttribute("src");
  };

  const handleFile = () => {
    const err = validators.image();
    setError("image", err);
    if (err) { clearImage(); return; }
    const f = imgEl.files[0];
    if (!f) { clearImage(); return; }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(f);
    previewImg.src = previewUrl;
    previewMeta.textContent = `${f.name} · ${(f.size / 1024).toFixed(0)} KB`;
    previewWrap.classList.remove("hidden");
  };

  imgEl.addEventListener("change", handleFile);
  removeBtn.addEventListener("click", () => { clearImage(); setError("image", ""); });

  // Drag and drop
  ["dragenter", "dragover"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); }));
  dropzone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) {
      imgEl.files = e.dataTransfer.files;
      handleFile();
    }
  });

  // Submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showBanner("");

    const results = { name: validators.name(), message: validators.message(), image: validators.image() };
    let firstBad = null;
    for (const [field, msg] of Object.entries(results)) {
      setError(field, msg);
      if (msg && !firstBad) firstBad = form.elements[field];
    }
    if (firstBad) { firstBad.focus(); return; }

    setLoading(true);
    try {
      const res = await fetch(form.getAttribute("action") || window.location.href, {
        method: "POST",
        body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });

      let data = null;
      try { data = await res.json(); } catch { /* non-JSON response */ }

      if (res.ok && data && data.ok) {
        window.location.href = form.dataset.successUrl;
        return;
      }
      if (data && data.errors) {
        for (const [field, errs] of Object.entries(data.errors)) {
          if (field === "__all__") showBanner(errs[0].message);
          else setError(field, errs[0].message);
        }
        showBanner(banner.textContent || "Fix the highlighted fields and try again.");
      } else {
        showBanner("The server had a problem saving your feedback. Try again in a moment.");
      }
    } catch {
      showBanner("Couldn't reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  });
})();
