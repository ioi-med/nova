#!/usr/bin/env python3
"""Vérifie la détection du plein écran de page (vidéo), les trois couches.

Cas testés dans un vrai moteur (Chromium, comme WebView2) :

1. l'événement `fullscreenchange` est bien relayé ;
2. **le repli par interrogation** fonctionne même si l'événement n'est jamais
   dispatché (cas des moteurs qui ne l'émettent pas) — on remplace
   `dispatchEvent` par l'inverse : seul l'état change ;
3. aucun message parasite : un état stable n'envoie rien.

    python3 tools/ui_fullscreen_test.py
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "audit_ui" / "build"

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>lecteur</title>
<style>body{margin:0;background:#111}</style>
<script>window.__SENT__ = []; window.ipc = { postMessage(m){ window.__SENT__.push(m); } };</script>
</head><body><video id="v" width="320" height="180"></video></body></html>"""

CHECK = """<script>
/* --- 1. événement classique --------------------------------------------- */
function setFs(value, dispatch) {
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true, get: function () { return value; }
  });
  if (dispatch) document.dispatchEvent(new Event("fullscreenchange"));
}
var out = [];
setFs(document.getElementById("v"), true);
out.push("evenement : entree -> " +
  window.__SENT__[window.__SENT__.length - 1]);
setFs(null, true);
out.push("evenement : sortie -> " +
  window.__SENT__[window.__SENT__.length - 1]);
var apresEvenement = window.__SENT__.length;

/* --- 2. repli par interrogation (aucun evenement dispatché) ------------- */
setFs(document.getElementById("v"), false);     /* etat change, sans evenement */
out.push("etat stable, aucun message supplementaire : " +
  (window.__SENT__.length === apresEvenement));

setTimeout(function () {
  out.push("interrogation : entree -> " +
    window.__SENT__[window.__SENT__.length - 1]);
  setFs(null, false);
  setTimeout(function () {
    out.push("interrogation : sortie -> " +
      window.__SENT__[window.__SENT__.length - 1]);
    out.push("total de messages : " + window.__SENT__.length);
    document.body.innerHTML = '<pre id="zzprobe">' + out.join("\\n") + "</pre>";
  }, 900);
}, 900);
</script>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inject = (ROOT / "assets" / "ui" / "inject.js").read_text(encoding="utf-8")
    html = PAGE.replace("</head>", f"<script>\n{inject}\n</script>\n</head>", 1)
    html = html.replace("</body>", CHECK + "\n</body>", 1)
    path = OUT / "test-plein-ecran.html"
    path.write_text(html, encoding="utf-8")

    dom = subprocess.run(
        ["chromium", "--headless=new", "--no-sandbox", "--disable-gpu",
         "--virtual-time-budget=6000", "--dump-dom", f"file://{path}"],
        capture_output=True, text=True, timeout=180).stdout
    i = dom.rfind('id="zzprobe"')
    if i == -1:
        sys.exit("script non exécuté")
    report = dom[dom.find(">", i) + 1:dom.find("</pre>", i)]
    for a, b in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        report = report.replace(a, b)
    report = report.replace('\\\\"', '"').replace('\\"', '"')
    print(report)

    ok = True
    if report.count('"on":true') < 2:
        ok = False
        print("!! entrée en plein écran non signalée dans les deux cas")
    if report.count('"on":false') < 2:
        ok = False
        print("!! sortie du plein écran non signalée dans les deux cas")
    if "aucun message supplementaire : true" not in report:
        ok = False
        print("!! des messages sont envoyés alors que l'état n'a pas changé")
    print("\nDétection du plein écran (événement + interrogation) : "
          + ("OK" if ok else "ÉCHEC"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
