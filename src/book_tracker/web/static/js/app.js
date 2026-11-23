// Small progressive enhancements. Every page also works without JavaScript.
(function () {
  "use strict";

  // Recent profiles on the sign-in page fill in the login field (FR-007).
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-fill-login]");
    if (!button) return;
    var login = document.getElementById("login");
    if (!login) return;
    login.value = button.getAttribute("data-fill-login");
    var password = document.getElementById("password");
    if (password) password.focus();
  });

  // ------------------------------------------------------------------ comboboxes
  // ARIA 1.2 combobox with a listbox popup (FR-010, FR-030). HTMX fills the listbox.

  function listboxFor(input) {
    return document.getElementById(input.getAttribute("aria-controls"));
  }

  function options(input) {
    var list = listboxFor(input);
    return list ? Array.prototype.slice.call(list.querySelectorAll('[role="option"]')) : [];
  }

  function close(input) {
    var list = listboxFor(input);
    if (list) list.innerHTML = "";
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function highlight(input, index) {
    var items = options(input);
    items.forEach(function (item, i) {
      item.setAttribute("aria-selected", i === index ? "true" : "false");
    });
    if (items[index]) {
      input.setAttribute("aria-activedescendant", items[index].id);
      items[index].scrollIntoView({ block: "nearest" });
    }
  }

  function activeIndex(input) {
    var id = input.getAttribute("aria-activedescendant");
    return options(input).findIndex(function (item) { return item.id === id; });
  }

  function choose(input, option) {
    input.value = option.getAttribute("data-value");
    var hidden = document.getElementById(input.getAttribute("data-id-field"));
    if (hidden) hidden.value = option.getAttribute("data-id");
    close(input);
    input.focus();
  }

  document.addEventListener("keydown", function (event) {
    var input = event.target;
    if (!input.matches || !input.matches('[role="combobox"]')) return;
    var items = options(input);
    var index = activeIndex(input);
    if (event.key === "ArrowDown" && items.length) {
      event.preventDefault();
      input.setAttribute("aria-expanded", "true");
      highlight(input, index < items.length - 1 ? index + 1 : 0);
    } else if (event.key === "ArrowUp" && items.length) {
      event.preventDefault();
      highlight(input, index > 0 ? index - 1 : items.length - 1);
    } else if (event.key === "Enter" && index >= 0) {
      event.preventDefault();
      choose(input, items[index]);
    } else if (event.key === "Escape") {
      close(input);
    }
  });

  document.addEventListener("input", function (event) {
    var input = event.target;
    if (!input.matches || !input.matches('[role="combobox"]')) return;
    // Typing replaces any earlier choice.
    var hidden = document.getElementById(input.getAttribute("data-id-field"));
    if (hidden) hidden.value = "";
  });

  document.addEventListener("click", function (event) {
    var option = event.target.closest('[role="option"]');
    if (!option) return;
    var list = option.closest('[role="listbox"]');
    var input = list && document.querySelector('[aria-controls="' + list.id + '"]');
    if (input) choose(input, option);
  });

  document.addEventListener("htmx:afterSwap", function (event) {
    var list = event.target.querySelector && event.target.querySelector('[role="listbox"]');
    if (!list) return;
    var input = document.querySelector('[aria-controls="' + list.id + '"]');
    if (!input) return;
    var count = list.querySelectorAll('[role="option"]').length;
    input.setAttribute("aria-expanded", count ? "true" : "false");
    input.removeAttribute("aria-activedescendant");
  });

  // ------------------------------------------------------------------ toggles
  // A checkbox with data-enables="<id>" enables or disables that field (pen name → real name).
  function syncToggle(box) {
    var target = document.getElementById(box.getAttribute("data-enables"));
    if (target) target.disabled = !box.checked;
  }
  // Spec 013: "This book is an anthology or collection" shows or hides the story rows.
  // Without JavaScript the rows are always shown; hidden rows are kept, never cleared.
  function syncAnthology(box) {
    var section = document.getElementById("stories");
    if (section) section.hidden = !box.checked;
  }
  document.querySelectorAll("[data-anthology-toggle]").forEach(syncAnthology);
  document.addEventListener("change", function (event) {
    if (!event.target.matches) return;
    if (event.target.matches("[data-enables]")) syncToggle(event.target);
    if (event.target.matches("[data-anthology-toggle]")) syncAnthology(event.target);
  });
})();
