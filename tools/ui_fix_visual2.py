#!/usr/bin/env python3
"""Correctifs visuels, 2e partie (settings, newtab, toolbar, welcome).

Voir `tools/ui_fix_visual.py` pour la 1re partie (main.rs, sidebar, history).
Les motifs sont vérifiés : le script refuse de continuer plutôt que de
corriger à l'aveugle.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def save(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def sub(text, old, new, rel, n=1):
    if old not in text:
        sys.exit(f"motif introuvable dans {rel} :\n{old[:300]}")
    return text.replace(old, new, n)


# ======================================================================
# settings.html — interrupteurs éteints lisibles en thème clair
# ======================================================================
t = load("assets/ui/settings.html")
t = sub(
    t,
    """    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;""",
    """    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;
    --switch-off:#3a3a45;""",
    "settings.html",
)
t = sub(
    t,
    """    --bg:#fbfbfd; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;""",
    """    --bg:#fbfbfd; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;
    --switch-off:#c9c9d2;""",
    "settings.html",
)
t = sub(
    t,
    """  .switch{width:42px;height:24px;border-radius:99px;background:#3a3a45;border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    """  /* Couleur codée en dur : l'interrupteur éteint était presque invisible sur
     fond clair (gris foncé sur carte blanche). */
  .switch{width:42px;height:24px;border-radius:99px;background:var(--switch-off);border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    "settings.html",
)
t = sub(
    t,
    """      document.documentElement.dataset.theme = state.config.theme === "light" ? "light" : "dark";""",
    """      const dark = (typeof state.dark === "boolean") ? state.dark : state.config.theme !== "light";
      document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "settings.html",
)
save("assets/ui/settings.html", t)

# ======================================================================
# newtab.html — « Système » ignoré
# ======================================================================
n = load("assets/ui/newtab.html")
n = sub(
    n,
    """  document.documentElement.dataset.theme = N.config.theme === "light" ? "light" : "dark";""",
    """  /* `dark` est résolu par Rust (« Système » -> clair ou sombre). */
  const dark = (typeof N.dark === "boolean") ? N.dark : N.config.theme !== "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "newtab.html",
)
save("assets/ui/newtab.html", n)

# ======================================================================
# toolbar.html — « Système » ignoré
# ======================================================================
b = load("assets/ui/toolbar.html")
b = sub(
    b,
    """      document.documentElement.dataset.theme = next.theme === "light" ? "light" : "dark";""",
    """      /* `dark` est résolu par Rust (« Système » -> clair ou sombre). */
      const dark = (typeof next.dark === "boolean") ? next.dark : next.theme !== "light";
      document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "toolbar.html",
)
save("assets/ui/toolbar.html", b)

# ======================================================================
# welcome.html — aucune palette claire, thème jamais appliqué
# ======================================================================
w = load("assets/ui/welcome.html")
w = sub(
    w,
    """    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  *{box-sizing:border-box}""",
    """    --switch-off:#3a3a45;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  /* L'assistant de premier lancement n'avait aucune palette claire : il restait
     sombre même après avoir choisi le thème clair. */
  html[data-theme="light"]{
    --bg:#f7f7fb; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76;
    --line:#e6e6ec; --switch-off:#c9c9d2;
  }
  html[data-theme="light"] .glow{opacity:.20}
  *{box-sizing:border-box}""",
    "welcome.html",
)
w = sub(
    w,
    """  .switch{width:42px;height:24px;border-radius:99px;background:#3a3a45;border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    """  .switch{width:42px;height:24px;border-radius:99px;background:var(--switch-off);border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    "welcome.html",
)
w = sub(
    w,
    """  .chip:hover{background:var(--card-hover);color:#fff}
  .chip.on{border-color:var(--accent);color:#fff}""",
    """  /* Texte blanc codé en dur : illisible sur fond clair. */
  .chip:hover{background:var(--card-hover);color:var(--text)}
  .chip.on{border-color:var(--accent);color:var(--text)}""",
    "welcome.html",
)
w = sub(
    w,
    """  const MAIN = ["google","brave","ecosia"];""",
    """  /* Thème appliqué dès l'affichage, « Système » déjà résolu par Rust. */
  function applyTheme(){
    const dark = (typeof N.dark === "boolean") ? N.dark : (N.config && N.config.theme !== "light");
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }
  applyTheme();

  const MAIN = ["google","brave","ecosia"];""",
    "welcome.html",
)
w = sub(
    w,
    """  const swDark = bindSwitch("swDark");""",
    """  const swDark = bindSwitch("swDark");
  /* Le réglage « thème sombre » se voit immédiatement : il ne faisait rien. */
  swDark.addEventListener("click", () => {
    N.dark = swDark.classList.contains("on");
    applyTheme();
  });""",
    "welcome.html",
)
save("assets/ui/welcome.html", w)

print("2e partie appliquée : settings.html, newtab.html, toolbar.html, welcome.html")
