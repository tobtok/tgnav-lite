/* tgnav-lite client-side search — vanilla JS, chunked static index, no backend */
(function () {
  "use strict";

  var base = (window.TGLITE && window.TGLITE.siteBase) || "";
  var searchBase = (window.TGLITE && window.TGLITE.searchBase) || "/search";

  var input = document.getElementById("search-input");
  var status = document.getElementById("search-status");
  var results = document.getElementById("search-results");
  var buttons = document.querySelectorAll(".filter-btn");

  if (!input || !results) return;

  var entries = [];      // loaded rows: [name, username, type, category, desc, tags, path]
  var loaded = false;
  var loading = false;
  var typeFilter = "all";
  var MAX_RESULTS = 50;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function score(row, q) {
    var name = row[0].toLowerCase();
    var uname = row[1].toLowerCase();
    var desc = row[4].toLowerCase();
    var tags = row[5].toLowerCase();
    var s = 0;
    if (name.indexOf(q) !== -1) s += 3;
    if (uname.indexOf(q) !== -1) s += 2;
    if (tags.indexOf(q) !== -1) s += 2;
    if (desc.indexOf(q) !== -1) s += 1;
    return s;
  }

  function render(q) {
    var trimmed = q.trim().toLowerCase();
    results.innerHTML = "";
    if (!trimmed) {
      status.textContent = "";
      return;
    }
    var hits = [];
    for (var i = 0; i < entries.length && hits.length < MAX_RESULTS * 3; i++) {
      var row = entries[i];
      if (typeFilter !== "all" && row[2] !== typeFilter) continue;
      var s = score(row, trimmed);
      if (s > 0) hits.push({ row: row, s: s });
    }
    hits.sort(function (a, b) { return b.s - a.s; });
    hits = hits.slice(0, MAX_RESULTS);

    if (!hits.length) {
      status.textContent = "No results for “" + trimmed + "”.";
      return;
    }
    var html = "";
    for (var j = 0; j < hits.length; j++) {
      var r = hits[j].row;
      html +=
        '<a class="row" href="' + esc(base + "/" + r[6]) + '">' +
        '<span class="avatar">' + esc(r[0].charAt(0)) + "</span>" +
        '<div class="fm"><div class="fn">' + esc(r[0]) + "</div>" +
        '<div class="fd">' + esc(r[4]) + "</div></div>" +
        '<span class="badge">' + esc(r[2] === "channel" ? "Channel" : "Group") + "</span></a>";
    }
    results.innerHTML = html;
    status.textContent = hits.length + " result" + (hits.length === 1 ? "" : "s") + " for “" + trimmed + "”";
  }

  function loadIndex(cb) {
    if (loaded) return cb();
    if (loading) return;
    loading = true;
    status.textContent = "Loading search index…";
    fetch(base + searchBase + "/index.json")
      .then(function (res) { return res.json(); })
      .then(function (manifest) {
        var done = 0;
        manifest.chunks.forEach(function (f) {
          fetch(base + searchBase + "/" + f)
            .then(function (res) { return res.json(); })
            .then(function (rows) {
              entries = entries.concat(rows);
              done += 1;
              if (done === manifest.chunks.length) {
                loaded = true;
                loading = false;
                cb();
              } else if (input.value.trim()) {
                render(input.value); // progressive results while chunks arrive
              }
            });
        });
      })
      .catch(function () {
        loading = false;
        status.textContent = "Failed to load the search index.";
      });
  }

  var debounceTimer = null;
  input.addEventListener("input", function () {
    if (!loaded && !loading) loadIndex(function () { render(input.value); });
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      if (loaded) render(input.value);
    }, 120);
  });

  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      buttons.forEach(function (b) {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      typeFilter = btn.getAttribute("data-type");
      if (loaded) render(input.value);
    });
  });

  // prefill from ?q=
  var q = new URLSearchParams(window.location.search).get("q");
  if (q) {
    input.value = q;
    loadIndex(function () { render(q); });
  }
})();
