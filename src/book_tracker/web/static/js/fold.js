// Spec 003 FR-007: on a phone, "Sort and filter" folds My books' filters away.
// Loaded without defer in <head>, so html.js is set before the first paint and the
// filters never show and then jump shut. The CSS folds only under html.js, so without
// JavaScript every filter stays visible. Kept apart from app.js so the fold still works
// if app.js fails to load.
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".filters-toggle").forEach(function (toggle) {
      toggle.hidden = false;
    });
  });
  document.addEventListener("click", function (event) {
    var toggle = event.target.closest && event.target.closest(".filters-toggle");
    if (!toggle) return;
    var form = toggle.closest("[data-fold]");
    var open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (form) form.setAttribute("data-fold", open ? "open" : "closed");
  });
})();
