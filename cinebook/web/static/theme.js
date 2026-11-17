// Runs before first paint so the page never flashes the wrong theme.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) { /* storage unavailable */ }
  var dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = saved || (dark === false && window.matchMedia ? "light" : "dark");
})();
