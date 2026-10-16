#!/usr/bin/env python3
"""Banc d'essai visuel de l'interface de Nova.

Chaque page d'interface est placée dans une **iframe à sa taille réelle**
(248×900 pour la barre latérale, etc.), ce qui reproduit exactement ce que voit
l'utilisateur dans la WebView correspondante : c'est la taille de la coquille
qui pilote la mise en page, pas celle de la fenêtre de capture.

L'état injecté est le même que celui produit par `src/main.rs` :
* pages internes : `window.__NOVA__` puis `window.NovaPage.render(state)` ;
* barre latérale / barre d'adresse : `window.NovaUI.render(state)`.

    python3 tools/ui_shot.py [dark|light]
"""
import base64
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UI = ROOT / "assets" / "ui"
OUT = ROOT / "audit_ui"
CHROME = "chromium"

ENGINES = [
    {"id": "google", "name": "Google", "color": "#4285f4", "bang": "!g",
     "note": "Le plus complet"},
    {"id": "brave", "name": "Brave Search", "color": "#fb542b", "bang": "!b",
     "note": "Index indépendant, sans traqueurs"},
    {"id": "ecosia", "name": "Ecosia", "color": "#22b24c", "bang": "!e",
     "note": "Finance la plantation d'arbres"},
    {"id": "duckduckgo", "name": "DuckDuckGo", "color": "#de5833", "bang": "!d",
     "note": "Recherche privée"},
    {"id": "startpage", "name": "Startpage", "color": "#6573ff", "bang": "!s",
     "note": "Résultats Google, sans profilage"},
    {"id": "qwant", "name": "Qwant", "color": "#5c97ff", "bang": "!q",
     "note": "Moteur européen"},
]

CONFIG = {
    "engine": "ecosia", "theme": "dark", "onboarding_done": True,
    "block_trackers": True, "restore_session": True, "sidebar_width": 248.0,
    "homepage": "nova://newtab", "start_with_pinned": False,
    "native_context_menus": False, "zoom": 1.0, "passwords": True,
    "ui_bg": "", "auto_import": True, "favorites": [],
    "silence_game_overlay": True,
    "dvr_prev": None,
}

TABS = [
    {"id": 1, "title": "Le Monde.fr — Actualités et Infos en France",
     "url": "https://www.lemonde.fr/", "pinned": True, "loading": False,
     "internal": False, "active": False},
    {"id": 2, "title": "GitHub · Where software is built",
     "url": "https://github.com/", "pinned": True, "loading": False,
     "internal": False, "active": False},
    {"id": 3, "title": "Ecosia — le moteur de recherche qui plante des arbres",
     "url": "https://www.ecosia.org/", "pinned": False, "loading": False,
     "internal": False, "active": True},
    {"id": 4, "title": "Rust Programming Language",
     "url": "https://www.rust-lang.org/", "pinned": False, "loading": True,
     "internal": False, "active": False},
    {"id": 5, "title": "Nouvel onglet", "url": "nova://newtab", "pinned": False,
     "loading": False, "internal": True, "active": False},
    {"id": 6, "title": "Météo Troyes — prévisions à 14 jours, Grand Est",
     "url": "https://www.meteoblue.com/fr/meteo/semaine/troyes_france_2971547",
     "pinned": False, "loading": False, "internal": False, "active": False},
    {"id": 7, "title": "Wikipédia, l'encyclopédie libre",
     "url": "https://fr.wikipedia.org/wiki/Navigateur_web", "pinned": False,
     "loading": False, "internal": False, "active": False},
]

HISTORY = [
    {"title": "Ecosia — le moteur de recherche qui plante des arbres",
     "url": "https://www.ecosia.org/", "ts": 1760000000},
    {"title": "Wikipédia, l'encyclopédie libre",
     "url": "https://fr.wikipedia.org/wiki/Navigateur_web", "ts": 1759990000},
    {"title": "Rust Programming Language", "url": "https://www.rust-lang.org/",
     "ts": 1759980000},
    {"title": "Le Monde.fr — Actualités et Infos en France",
     "url": "https://www.lemonde.fr/", "ts": 1759900000},
    {"title": "Météo Troyes — prévisions à 14 jours, Grand Est",
     "url": "https://www.meteoblue.com/fr/meteo/semaine/troyes_france_2971547",
     "ts": 1759800000},
]

TOPSITES = [
    {"host": "github.com", "url": "https://github.com/", "title": "GitHub"},
    {"host": "lemonde.fr", "url": "https://www.lemonde.fr/", "title": "Le Monde"},
    {"host": "fr.wikipedia.org", "url": "https://fr.wikipedia.org/", "title": "Wikipédia"},
    {"host": "rust-lang.org", "url": "https://www.rust-lang.org/", "title": "Rust"},
    {"host": "ecosia.org", "url": "https://www.ecosia.org/", "title": "Ecosia"},
    {"host": "youtube.com", "url": "https://www.youtube.com/", "title": "YouTube"},
]

SIZES = {"sidebar": (248, 900), "toolbar": (1200, 52), "newtab": (1200, 820),
         "settings": (1200, 820), "history": (1200, 820), "welcome": (900, 640),
         "import": (1200, 900)}


FAVORITES = [
    {"title": "YouTube", "url": "https://www.youtube.com/"},
    {"title": "Gmail", "url": "https://mail.google.com/"},
    {"title": "Spotify", "url": "https://open.spotify.com/"},
    {"title": "Figma", "url": "https://www.figma.com/"},
    {"title": "Notion", "url": "https://www.notion.so/"},
]


# Peau commune, reprise **telle quelle** de `src/ui.rs` : le banc d'essai
# injecte exactement ce que fait `ui::with_state`.
# Sources détectées, telles que `import::detect` les renvoie sous Windows.
HELPER_ICONE = """window.NovaEngineIcon = function (el, eng) {
  var src = window.NovaEngineIcons && window.NovaEngineIcons[eng && eng.id];
  el.textContent = "";
  if (src) {
    var img = document.createElement("img");
    img.src = src; img.alt = ""; img.draggable = false;
    el.appendChild(img);
    el.style.background = "transparent";
  } else {
    el.style.background = (eng && eng.color) || "var(--accent)";
    el.textContent = ((eng && eng.name) || "?").charAt(0).toUpperCase();
  }
};"""


IMPORT_SOURCES = [
    {"id": "google-chrome-default", "app": "Google Chrome", "app_id": "google-chrome",
     "name": "Google Chrome", "kind": "favoris",
     "path": r"C:\Users\Vous\AppData\Local\Google\Chrome\User Data\Default\Bookmarks"},
    {"id": "google-chrome-default-hist", "app": "Google Chrome", "app_id": "google-chrome",
     "name": "Google Chrome", "kind": "historique",
     "path": r"C:\Users\Vous\AppData\Local\Google\Chrome\User Data\Default\History"},
    {"id": "microsoft-edge-default", "app": "Microsoft Edge", "app_id": "microsoft-edge",
     "name": "Microsoft Edge", "kind": "favoris",
     "path": r"C:\Users\Vous\AppData\Local\Microsoft\Edge\User Data\Default\Bookmarks"},
    {"id": "brave-default", "app": "Brave", "app_id": "brave",
     "name": "Brave", "kind": "favoris",
     "path": r"C:\Users\Vous\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Bookmarks"},
    {"id": "brave-default-hist", "app": "Brave", "app_id": "brave",
     "name": "Brave", "kind": "historique",
     "path": r"C:\Users\Vous\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\History"},
    {"id": "firefox-abc", "app": "Firefox", "app_id": "firefox",
     "name": "Firefox (abc1234.default-release)", "kind": "historique",
     "path": r"C:\Users\Vous\AppData\Roaming\Mozilla\Firefox\Profiles\abc1234.default-release\places.sqlite"},
]

IMPORT_RESULT = {
    "favorites": 37, "visits": 1842, "sources": 5, "skipped": 116,
    "notes": ["Google Chrome : 24 favoris ajoutés, 116 déjà connus",
              "Brave : 9 favoris ajoutés",
              "Firefox (abc1234.default-release) : import automatique au démarrage"],
    "errors": [],
    "when_ts": 1760000000,
}

# Un import volumineux : la barre latérale n'affiche que les premiers favoris.
MANY_FAVORITES = FAVORITES + [
    {"title": f"Site importé {i}", "url": f"https://import{i}.example.org/"} for i in range(1, 26)
]


SKIN = r"""(function () {
  function parse(hex) {
    if (typeof hex !== "string" || !/^#[0-9a-fA-F]{6}$/.test(hex)) return null;
    return [parseInt(hex.substr(1, 2), 16), parseInt(hex.substr(3, 2), 16),
            parseInt(hex.substr(5, 2), 16)];
  }
  var VARS = ["--bg", "--bg-2", "--bg-3", "--bg-hover", "--line", "--line-2", "--text",
              "--muted", "--card", "--card-hover", "--fav-plate", "--scroll",
              "--switch-off"];
  function apply(bg) {
    var root = document.documentElement, i;
    var base = parse(bg);
    if (!base) {                       /* valeur d'origine : thème standard */
      for (i = 0; i < VARS.length; i++) root.style.removeProperty(VARS[i]);
      return false;
    }
    /* Texte clair ou sombre selon la luminance perçue du fond choisi. */
    var lum = (0.2126 * base[0] + 0.7152 * base[1] + 0.0722 * base[2]) / 255;
    var dark = lum < 0.55;
    var fg = dark ? [255, 255, 255] : [12, 12, 16];
    var mix = function (t) {
      var out = [];
      for (var k = 0; k < 3; k++) out.push(Math.round(base[k] + (fg[k] - base[k]) * t));
      return "rgb(" + out.join(",") + ")";
    };
    var set = function (name, t) { root.style.setProperty(name, mix(t)); };
    root.style.setProperty("--bg", "rgb(" + base.join(",") + ")");
    set("--bg-2", 0.06); set("--bg-hover", 0.08); set("--bg-3", 0.12);
    set("--card", 0.05); set("--card-hover", 0.10); set("--line", 0.15); set("--line-2", 0.22);
    set("--text", 0.94); set("--muted", 0.62);
    set("--scroll", 0.25); set("--switch-off", 0.22);
    root.style.setProperty("--fav-plate", dark ? "#e9e9f2" : "#f2f2f7");
    return true;
  }
  window.NovaSkin = { apply: apply, isCustom: function (bg) { return !!parse(bg); } };
})();"""


def state(theme="dark", cfg_theme=None, dark=None, ui_bg="", favorites=None,
          is_favorite=False, import_result=None, import_busy=False,
          import_sources=None, schemes_refused=0):
    """État complet, comme celui produit par `state_json` dans main.rs."""
    cfg = dict(CONFIG, theme=cfg_theme or theme)
    active = dict(TABS[2])
    active.update({"can_back": True, "can_forward": False, "secure": True,
                   "engine": cfg["engine"], "zoom": 1.0, "search_mode": False})
    return {
        "theme": theme, "dark": (theme != "light") if dark is None else dark,
        "config": cfg, "engines": ENGINES, "tabs": TABS,
        "active": active, "closed_count": 3, "history": HISTORY,
        "history_rev": 42, "history_open": False, "topsites": TOPSITES,
        "favorites": FAVORITES if favorites is None else favorites,
        "ui_bg": ui_bg,
        "limits": {"sidebar_apps": 24, "favorites": 240},
        "import_sources": IMPORT_SOURCES if import_sources is None else import_sources,
        "import_result": IMPORT_RESULT if import_result is None else import_result,
        "import_busy": import_busy,
        "active": dict(active, is_favorite=is_favorite),
        "version": "1.3.2", "backend": "C (nova_core)",
        "data_dir": r"C:\Users\Vous\AppData\Roaming\Nova",
        "overlay": {
            "silenced": True,
            "dvr_off": True,
            "stub": True,
            "game_bar": False,
            "refused": schemes_refused,
            "log": r"C:\Users\Vous\AppData\Roaming\Nova\protocoles-refuses.log",
        },
        "stats": {"tabs": len(TABS), "history": len(HISTORY),
                  "trackers": 146, "blocked": 23,
                  "schemes_refused": schemes_refused,
                  "log_path": r"C:\Users\Vous\AppData\Roaming\Nova\protocoles-refuses.log"},
    }


STUB = """<script>
/* Trace IPC : la coquille webview est remplacée par un tableau. */
window.__SENT__ = [];
window.ipc = { postMessage(m){ window.__SENT__.push(m); } };
</script>"""


def page(name, theme, tail, cfg_theme=None, dark=None, ui_bg="", favorites=None,
         is_favorite=False, import_result=None, import_busy=False,
         import_sources=None, schemes_refused=0):
    """Document d'interface prêt à être placé dans l'iframe (+ état injecté).

    L'injection reproduit exactement `ui::with_state` : la peau commune
    (`NovaSkin`, extraite de `src/ui.rs`) puis l'état.
    """
    html = (UI / f"{name}.html").read_text(encoding="utf-8")
    payload = json.dumps(
        state(theme, cfg_theme, dark, ui_bg, favorites, is_favorite,
              import_result, import_busy, import_sources, schemes_refused),
        ensure_ascii=False,
    )
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    icones = "window.NovaEngineIcons = {" + ",".join(
        '"%s":"data:image/png;base64,%s"' % (f.stem, base64.b64encode(f.read_bytes()).decode())
        for f in sorted((ROOT / "assets" / "engines").glob("*.png"))
    ) + "};"
    html = html.replace("<head>", f"<head>\n{STUB}\n<script>{icones}</script>\n<script>{HELPER_ICONE}</script>\n"
                                 f"<script>{SKIN}\nwindow.__NOVA__ = {payload};</script>", 1)
    if tail:
        html = html.replace("</body>", f"<script>{tail}</script>\n</body>", 1)
    return html


def host(inner, w, h, theme):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{{margin:0;background:{'#0b0b0e' if theme == 'dark' else '#cfcfd6'}}}
  iframe{{width:{w}px;height:{h}px;border:0;display:block}}
</style></head><body>
<iframe id="f" srcdoc="{inner.replace('&', '&amp;').replace(chr(34), '&quot;')}"></iframe>
</body></html>"""


def shot(name, inner, w, h, theme, delay=1):
    OUT.mkdir(exist_ok=True)
    path = OUT / "build" / f"{name}-{theme}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(host(inner, w, h, theme), encoding="utf-8")
    png = OUT / f"{name}-{theme}.png"
    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
         "--allow-file-access-from-files", "--force-color-profile=srgb",
         f"--window-size={w},{h}", "--virtual-time-budget=4000",
         f"--screenshot={png}", f"file://{path}"],
        capture_output=True, timeout=120)
    print(f"  {png.name}  ({w}×{h})")


def main():
    theme = sys.argv[1] if len(sys.argv) > 1 else "dark"
    print(f"Captures (thème {theme}) — iframe à la taille réelle de la WebView :")
    w, h = SIZES["sidebar"]
    sidebar_tails = {
        "sidebar": "window.NovaUI.render(window.__NOVA__);",
        "sidebar-historique": "window.__NOVA__.history_open = true;"
                              "window.NovaUI.render(window.__NOVA__);",
        "sidebar-menu": "window.NovaUI.render(window.__NOVA__);"
                        "document.getElementById('menuBtn').click();",
        "sidebar-moteurs": "window.NovaUI.render(window.__NOVA__);"
                           "document.getElementById('engineBtn').click();",
        "sidebar-menu-onglet": "window.NovaUI.render(window.__NOVA__);"
                               "const t=document.querySelector('.tab');"
                               "t.dispatchEvent(new MouseEvent('contextmenu',"
                               "{bubbles:true,clientX:60,clientY:120}));",
    }
    for name, tail in sidebar_tails.items():
        shot(name, page("sidebar", theme, tail), w, h, theme)

    shot("toolbar", page("toolbar", theme,
                         "window.NovaUI.render(window.__NOVA__);"),
         *SIZES["toolbar"], theme)

    page_tail = "window.NovaPage && window.NovaPage.render(window.__NOVA__);"
    for name in ("newtab", "settings", "history", "welcome", "import"):
        shot(name, page(name, theme, page_tail), *SIZES[name], theme)

    # --- import des données (onglet 1.2.0) --------------------------------
    shot("import-resultat", page("import", theme, page_tail), *SIZES["import"], theme)
    shot("import-analysant", page("import", theme, page_tail, import_result={},
                                  import_busy=True), *SIZES["import"], theme)
    shot("import-vide", page("import", theme, page_tail, import_sources=[],
                             import_result=None), *SIZES["import"], theme)
    # Le compte rendu et l'aide vivent en bas de page : on y défile dans l'iframe.
    bottom = page_tail + "window.scrollTo(0, 99999);"
    shot("import-resultat-bas", page("import", theme, bottom), *SIZES["import"], theme)
    shot("import-analysant-bas", page("import", theme, bottom, import_result={},
                                      import_busy=True), *SIZES["import"], theme)

    # --- paramètres : section « Importer depuis un autre navigateur » -----
    # (une vue défilée en bas, une autre centrée sur le bouton d'import)
    shot("settings-import", page("settings", theme,
                                 page_tail + "window.scrollTo(0, 99999);"),
         *SIZES["settings"], theme)
    shot("settings-import-haut", page("settings", theme, page_tail +
                                       "document.getElementById('openImport')"
                                       ".scrollIntoView({block:'center'});"),
         *SIZES["settings"], theme)
    # --- assistant, étape 2 : quels navigateurs reprendre (1.3.1) ---------
    shot("welcome-import", page("welcome", theme, page_tail +
                                "document.body.dataset.step='2';"), *SIZES["welcome"], theme)
    shot("welcome-reglages", page("welcome", theme, page_tail +
                                  "document.body.dataset.step='3';"), *SIZES["welcome"], theme)
    # --- réglage du message de Windows (1.3.0) ----------------------------
    shot("settings-overlay", page("settings", theme, page_tail +
                                  "document.getElementById('swOverlay')"
                                  ".scrollIntoView({block:'center'});"),
         *SIZES["settings"], theme)
    # --- protocoles refusés (1.2.1) : la ligne d'information des Paramètres --
    shot("settings-protocoles", page("settings", theme, page_tail +
                                     "document.getElementById('schemeCount')"
                                     ".scrollIntoView({block:'center'});",
                                     schemes_refused=3),
         *SIZES["settings"], theme)

    # --- couleur de fond personnalisée (violet nuit) ---------------------
    for name in ("sidebar", "toolbar", "settings", "newtab"):
        tail = ("window.NovaUI.render(window.__NOVA__);"
                if name in ("sidebar", "toolbar") else page_tail)
        shot(f"{name}-fond", page(name, theme, tail, ui_bg="#2a2035"),
             *SIZES[name], theme)

    # --- favoris (apps) : avec et sans ----------------------------------
    shot("sidebar-favoris", page("sidebar", theme,
                                 "window.NovaUI.render(window.__NOVA__);"),
         *SIZES["sidebar"], theme)
    shot("newtab-favoris", page("newtab", theme, page_tail),
         *SIZES["newtab"], theme)
    shot("sidebar-sans-favoris", page("sidebar", theme,
                                      "window.NovaUI.render(window.__NOVA__);",
                                      favorites=[]),
         *SIZES["sidebar"], theme)
    shot("newtab-sans-favoris", page("newtab", theme, page_tail, favorites=[]),
         *SIZES["newtab"], theme)

    # --- import volumineux : plafond de la barre latérale ------------------
    shot("sidebar-favoris-import", page("sidebar", theme,
                                        "window.NovaUI.render(window.__NOVA__);",
                                        favorites=MANY_FAVORITES),
         *SIZES["sidebar"], theme)
    shot("newtab-favoris-import", page("newtab", theme, page_tail,
                                       favorites=MANY_FAVORITES),
         *SIZES["newtab"], theme)


if __name__ == "__main__":
    main()
