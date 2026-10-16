/* Nova — script injecté dans chaque page au démarrage du document.
 *
 * Rôle : relayer les raccourcis clavier et les boutons latéraux de la souris
 * vers l'interface Rust. Le moteur de rendu ne voit donc jamais Ctrl+T,
 * Ctrl+W ou Alt+← : Nova les intercepte en capture, avant le site.
 */
(function () {
  "use strict";
  if (window.__novaInjected) return;
  window.__novaInjected = true;

  var post = function (obj) {
    var payload = JSON.stringify(obj);
    try { window.ipc.postMessage(payload); }
    catch (e) { try { window.chrome.webview.postMessage(payload); } catch (e2) {} }
  };
  var send = function (combo) {
    post({ cmd: "hotkey", key: combo });
  };

  /* Plein écran demandé par la page (lecteur vidéo, diaporama…).
     La barre latérale et la barre d'adresse sont des vues séparées : sans ce
     signal, elles restaient affichées par-dessus la vidéo en plein écran. */
  var fsState = null;
  var reportFullscreen = function () {
    var on = !!(document.fullscreenElement || document.webkitFullscreenElement);
    if (on === fsState) return;          /* rien de neuf : aucun message */
    fsState = on;
    post({ cmd: "page_fullscreen", on: on });
  };
  document.addEventListener("fullscreenchange", reportFullscreen, true);
  document.addEventListener("webkitfullscreenchange", reportFullscreen, true);
  window.addEventListener("pageshow", reportFullscreen, true);

  /* Filet de sécurité : tous les moteurs de rendu ne déclenchent pas
     `fullscreenchange`. Relire une propriété deux fois par seconde ne coûte
     rien et garantit que Nova est prévenu quoi qu'il arrive. La minuterie est
     suspendue quand l'onglet est masqué. */
  setInterval(function () {
    if (!document.hidden) reportFullscreen();
  }, 500);

  document.addEventListener("keydown", function (e) {
    var k = e.key;
    var lower = (typeof k === "string") ? k.toLowerCase() : "";
    var combo = null;

    if (e.ctrlKey && e.shiftKey) {
      if (lower === "t") combo = "reopen_closed";
      else if (k === "Tab") combo = "prev_tab";
      else if (lower === "i" || lower === "j" || k === "F12") combo = "devtools";
      else if (lower === "h") combo = "home";
    } else if (e.ctrlKey && !e.altKey) {
      if (lower === "t") combo = "new_tab";
      else if (lower === "w") combo = "close_tab";
      else if (lower === "l") combo = "focus_url";
      else if (lower === "r") combo = "reload";
      else if (lower === "h") combo = "history";
      else if (lower === "d") combo = "toggle_favorite";
      else if (lower === "f") combo = "find";
      else if (k === ",") combo = "settings";
      else if (k === "Tab") combo = "next_tab";
      else if (k === "=" || k === "+") combo = "zoom_in";
      else if (k === "-") combo = "zoom_out";
      else if (k === "0") combo = "zoom_reset";
      else if (k >= "1" && k <= "9") combo = "tab_" + k;
    } else if (e.altKey && !e.ctrlKey) {
      if (k === "ArrowLeft") combo = "back";
      else if (k === "ArrowRight") combo = "forward";
      else if (k === "Home") combo = "home";
    } else if (!e.ctrlKey && !e.altKey) {
      if (k === "F5") combo = "reload";
      else if (k === "F11") combo = "fullscreen";
      else if (k === "F12") combo = "devtools";
      else if (k === "F6") combo = "focus_url";
    }

    if (combo) {
      e.preventDefault();
      e.stopPropagation();
      send(combo);
    }
  }, true);

  /* Boutons latéraux de la souris : retour / avance, comme dans un vrai navigateur. */
  document.addEventListener("mousedown", function (e) {
    if (e.button === 3) { e.preventDefault(); send("back"); }
    else if (e.button === 4) { e.preventDefault(); send("forward"); }
  }, true);
  document.addEventListener("mouseup", function (e) {
    if (e.button === 3 || e.button === 4) e.preventDefault();
  }, true);

  /* La molette horizontale + Alt : navigation (confort trackpad). */
  document.addEventListener("wheel", function (e) {
    if (e.altKey && Math.abs(e.deltaX) > 40) {
      send(e.deltaX > 0 ? "forward" : "back");
    }
  }, { capture: true, passive: true });
})();
