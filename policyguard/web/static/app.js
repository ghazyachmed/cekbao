// CEKBAO PolicyGuard progressive enhancement. Every page works without this file.
// No storage of form contents: drafts stay in the page only.
(function () {
  "use strict";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  // Focus the first error summary, or the result heading after a completed check.
  document.addEventListener("DOMContentLoaded", function () {
    var summary = $("#error-summary");
    if (summary) { summary.focus(); return; }
    if (location.hash === "#result") { var h = $("#result"); if (h) { h.focus(); } }
  });

  // Institution filter (the radio list works without it).
  function initInstitutions() {
    var filterBox = $(".filter[data-js-only]");
    var input = $("#institution_filter");
    var options = $all(".inst-option");
    if (!filterBox || !input || options.length < 2) { return; }
    filterBox.hidden = false;
    var count = $("#institution_count");
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var q = input.value.trim().toLowerCase();
        var shown = 0;
        options.forEach(function (o) {
          var match = !q || o.getAttribute("data-name").indexOf(q) !== -1;
          o.hidden = !match;
          if (match) { shown += 1; }
        });
        if (count) { count.textContent = shown + " institutions shown"; }
      }, 200);
    });
  }

  // Reveal the institution name field only when "not listed" is chosen.
  function initReveal() {
    var wrap = $("[data-reveal-for]");
    if (!wrap) { return; }
    var trigger = document.getElementById(wrap.getAttribute("data-reveal-for"));
    function sync() { wrap.hidden = !(trigger && trigger.checked) && !wrap.querySelector("[aria-invalid]"); }
    $all('input[name="institution_choice"]').forEach(function (r) { r.addEventListener("change", sync); });
    sync();
  }

  // Uploads: keyboard via the native file input, drag and drop on the zone, real byte progress.
  function initUpload() {
    var form = $("#check-form");
    var input = $("#document_input");
    var zone = $("[data-dropzone]");
    var list = $("#upload-list");
    if (!form || !input || !zone || !list || !window.XMLHttpRequest || !window.FormData) { return; }
    var csrf = form.querySelector('input[name="csrf_token"]').value;

    function send(file, item) {
      item.className = "upload-item";
      item.innerHTML = "";
      var name = document.createElement("strong"); name.textContent = file.name; item.appendChild(name);
      var bar = document.createElement("progress"); bar.max = 100; bar.value = 0; item.appendChild(bar);
      var status = document.createElement("span"); status.textContent = "Uploading and scanning…"; item.appendChild(status);
      var xhr = new XMLHttpRequest();
      xhr.open("POST", form.getAttribute("data-upload-url"));
      xhr.setRequestHeader("X-CSRF-Token", csrf);
      xhr.upload.addEventListener("progress", function (e) { if (e.lengthComputable) { bar.value = Math.round(e.loaded / e.total * 100); } });
      xhr.addEventListener("load", function () {
        bar.remove();
        var body = {};
        try { body = JSON.parse(xhr.responseText); } catch (err) { body = {}; }
        if (xhr.status === 200 && body.status === "CLEAN") {
          item.classList.add("is-clean");
          status.textContent = "Scanned. Ready to attach.";
          var hidden = document.createElement("input");
          hidden.type = "hidden"; hidden.name = "upload_ids"; hidden.value = body.upload_id;
          item.appendChild(hidden);
        } else {
          item.classList.add("is-rejected");
          status.textContent = "Not attached: " + (body.reject_reason || body.detail || "the upload failed.");
          addButton(item, "Try again", function () { send(file, item); });
        }
        addButton(item, "Remove", function () { item.remove(); input.focus(); });
      });
      xhr.addEventListener("error", function () {
        bar.remove();
        item.classList.add("is-rejected");
        status.textContent = "The upload did not finish. Check your connection and try again.";
        addButton(item, "Try again", function () { send(file, item); });
        addButton(item, "Remove", function () { item.remove(); input.focus(); });
      });
      var data = new FormData(); data.append("file", file);
      xhr.send(data);
    }
    function addButton(item, label, onClick) {
      var actions = item.querySelector(".upload-actions");
      if (!actions) { actions = document.createElement("div"); actions.className = "upload-actions"; item.appendChild(actions); }
      var b = document.createElement("button"); b.type = "button"; b.className = "btn btn-quiet"; b.textContent = label;
      b.addEventListener("click", onClick); actions.appendChild(b);
    }
    function handle(files) {
      Array.prototype.forEach.call(files, function (file) {
        var item = document.createElement("li"); list.appendChild(item); send(file, item);
      });
      input.value = "";   // the file travels by XHR, not with the main form
    }
    input.addEventListener("change", function () { handle(input.files); });
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("is-over"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("is-over"); });
    });
    zone.addEventListener("drop", function (e) { if (e.dataTransfer && e.dataTransfer.files) { handle(e.dataTransfer.files); } });
  }

  // Submit: show progress text. The server's idempotency key prevents duplicates, not this.
  function initSubmit() {
    var form = $("#check-form");
    if (!form) { return; }
    form.addEventListener("submit", function () {
      var btn = form.querySelector('button[type="submit"]');
      if (btn) { btn.setAttribute("aria-disabled", "true"); btn.textContent = btn.getAttribute("data-busy-text") || btn.textContent; }
    });
  }

  // Status polling: bounded, exponential backoff with jitter; announce only state changes.
  function initPolling() {
    var box = $("[data-status-url]");
    if (!box || !window.fetch) { return; }
    var url = box.getAttribute("data-status-url");
    var state = box.getAttribute("data-state");
    var delay = 1000, polls = 0, maxPolls = 40;
    var live = $("#status-live"), label = $("#status-label"), text = $("#status-text"), slow = $("#status-slow");
    function next() {
      if (polls >= maxPolls) { if (slow) { slow.hidden = false; } return; }
      var jitter = delay * (0.8 + Math.random() * 0.4);
      setTimeout(poll, jitter);
      delay = Math.min(delay * 1.5, 8000);
    }
    function poll() {
      polls += 1;
      fetch(url, { headers: { "Accept": "application/json" }, credentials: "same-origin", cache: "no-store" })
        .then(function (r) { if (r.status === 401) { location.reload(); throw new Error("signed out"); } return r.json(); })
        .then(function (s) {
          if (s.done) { location.replace(location.pathname + "#result"); location.reload(); return; }
          if (s.state !== state) {
            state = s.state;
            if (label) { label.textContent = s.label; }
            if (text) { text.textContent = s.description; }
            if (live) { live.textContent = s.label + ". " + s.description; }
          }
          next();
        })
        .catch(function () { next(); });
    }
    if (box.getAttribute("data-state") && ["COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"].indexOf(state) === -1) { next(); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initInstitutions(); initReveal(); initUpload(); initSubmit(); initPolling();
  });
})();
