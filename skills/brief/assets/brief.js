/* brief — the only behaviour on the page.
 *
 * Two jobs: open/close every group at once, and mark a sticky group
 * header as stuck so it can grow a hairline without changing height.
 * No content is produced here; everything visible is already in the DOM
 * when this runs, so the page stays readable with scripting disabled. */
(function () {
  var button = document.getElementById("toggleAll");
  var cards = document.querySelectorAll("details.card");
  if (!button) { return; }

  button.addEventListener("click", function () {
    var shouldOpen = button.getAttribute("data-state") === "closed";
    for (var i = 0; i < cards.length; i++) { cards[i].open = shouldOpen; }
    sync();
  });

  function sync() {
    var openCount = document.querySelectorAll("details.card[open]").length;
    var closed = openCount === 0;
    button.setAttribute("data-state", closed ? "closed" : "open");
    button.textContent = closed ? "すべて開く" : "すべて閉じる";
  }
  for (var i = 0; i < cards.length; i++) { cards[i].addEventListener("toggle", sync); }
  sync();

  var bar = document.querySelector(".bar");
  if (!bar || !("IntersectionObserver" in window)) { return; }
  var sentinelMargin = "-" + (bar.offsetHeight + 1) + "px 0px 0px 0px";
  var stickWatch = new IntersectionObserver(function (entries) {
    for (var i = 0; i < entries.length; i++) {
      entries[i].target.classList.toggle("stuck", entries[i].intersectionRatio < 1);
    }
  }, { rootMargin: sentinelMargin, threshold: [1] });
  var heads = document.querySelectorAll("details.card > summary");
  for (var j = 0; j < heads.length; j++) { stickWatch.observe(heads[j]); }
})();
