#!/usr/bin/env python3
"""Cinquième lot : plein écran vidéo, couleur de fond, favoris (apps).

1. **Plein écran vidéo** — quand une page passe en plein écran (lecteur vidéo),
   Nova masque sa propre interface et donne toute la fenêtre à la page. La barre
   latérale était une vue séparée : elle restait affichée par-dessus la vidéo.
2. **Couleur de fond** — réglage « Couleur du fond » dans les paramètres :
   palette de teintes prêtes + sélecteur libre, appliquée à la barre latérale,
   à la barre d'adresse et à toutes les pages internes.
3. **Favoris / apps** — l'étoile de la barre d'adresse ajoute la page courante
   aux favoris ; les favoris apparaissent dans la barre latérale et sur la page
   « nouvel onglet ».

Toutes les modifications d'interface sont vérifiées par `tools/ui_probe.py`.
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
        sys.exit(f"motif introuvable dans {rel} :\n{old[:400]}")
    return text.replace(old, new, n)


# ======================================================================
# 1. config.rs — couleur de fond + favoris
# ======================================================================
c = load("src/config.rs")

c = sub(
    c,
    """pub const VERSION: &str = env!("CARGO_PKG_VERSION");""",
    """pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Nombre maximal de favoris (apps) conservés.
pub const MAX_FAVORITES: usize = 24;

/// Une application / un site mis en favori, affiché dans la barre latérale.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Favorite {
    pub title: String,
    pub url: String,
}

impl Default for Favorite {
    fn default() -> Self {
        Self { title: String::new(), url: String::new() }
    }
}""",
    "src/config.rs",
)

c = sub(
    c,
    """    /// Mémorisation des mots de passe et des formulaires (profil local).
    pub passwords: bool,
}""",
    """    /// Mémorisation des mots de passe et des formulaires (profil local).
    pub passwords: bool,
    /// Couleur de fond de l'interface (`#rrggbb`), vide = thème standard.
    pub ui_bg: String,
    /// Applications / sites favoris, affichés dans la barre latérale.
    pub favorites: Vec<Favorite>,
}""",
    "src/config.rs",
)

c = sub(
    c,
    """    pub fn sanitize(&mut self) {""",
    """    /// Vrai si la couleur de fond fournie est exploitable (`#rrggbb`).
    pub fn ui_bg_ok(bg: &str) -> bool {
        let b = bg.as_bytes();
        b.len() == 7
            && b[0] == b'#'
            && b[1..].iter().all(|c| c.is_ascii_hexdigit())
    }

    pub fn sanitize(&mut self) {
        // Une couleur invalide est ignorée plutôt que recopiée telle quelle
        // dans la feuille de style des pages d'interface.
        if !self.ui_bg.is_empty() && !Self::ui_bg_ok(&self.ui_bg) {
            self.ui_bg.clear();
        }
        self.favorites.retain(|f| !f.url.trim().is_empty());
        if self.favorites.len() > MAX_FAVORITES {
            self.favorites.truncate(MAX_FAVORITES);
        }""",
    "src/config.rs",
)

c = sub(
    c,
    """            native_context_menus: true,
            zoom: 1.0,
            passwords: true,
        }""",
    """            native_context_menus: false,
            zoom: 1.0,
            passwords: true,
            ui_bg: String::new(),
            favorites: Vec::new(),
        }""",
    "src/config.rs",
)
save("src/config.rs", c)

# ======================================================================
# 2. uuid → ui.rs : feuille de style partagée (« NovaSkin »)
# ======================================================================
u = load("src/ui.rs")
u = sub(
    u,
    """/// Prépare un document HTML en y injectant l'état courant (`window.__NOVA__`).
pub fn with_state(html: &str, state: &Value) -> String {
    let script = format!(
        "<head>\\n<script>window.__NOVA__ = {};</script>",
        js_payload(state)
    );
    html.replacen("<head>", &script, 1)
}""",
    """/// Peau commune : recalcule la palette complète à partir de la couleur de fond
/// choisie par l'utilisateur. Définie **une seule fois**, ici : les six pages
/// d'interface l'appellent, aucune n'a de copie à maintenir.
pub const SKIN: &str = r#"(function () {
  function parse(hex) {
    if (typeof hex !== "string" || !/^#[0-9a-fA-F]{6}$/.test(hex)) return null;
    return [parseInt(hex.substr(1, 2), 16), parseInt(hex.substr(3, 2), 16),
            parseInt(hex.substr(5, 2), 16)];
  }
  var VARS = ["--bg", "--bg-2", "--bg-3", "--bg-hover", "--line", "--text",
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
    set("--card", 0.05); set("--card-hover", 0.10); set("--line", 0.17);
    set("--text", 0.94); set("--muted", 0.62);
    set("--scroll", 0.25); set("--switch-off", 0.22);
    root.style.setProperty("--fav-plate", dark ? "#e9e9f2" : "#f2f2f7");
    return true;
  }
  window.NovaSkin = { apply: apply, isCustom: function (bg) { return !!parse(bg); } };
})();"#;

/// Prépare un document HTML en y injectant la peau puis l'état courant
/// (`window.NovaSkin` et `window.__NOVA__`).
pub fn with_state(html: &str, state: &Value) -> String {
    let script = format!(
        "<head>\\n<script>{}\\nwindow.__NOVA__ = {};</script>",
        SKIN,
        js_payload(state)
    );
    html.replacen("<head>", &script, 1)
}""",
    "src/ui.rs",
)
save("src/ui.rs", u)

# ======================================================================
# 3. inject.js — signaler le plein écran demandé par la page (vidéo)
# ======================================================================
j = load("assets/ui/inject.js")
j = sub(
    j,
    """  var send = function (combo) {
    var payload = JSON.stringify({ cmd: "hotkey", key: combo });
    try { window.ipc.postMessage(payload); }
    catch (e) { try { window.chrome.webview.postMessage(payload); } catch (e2) {} }
  };""",
    """  var post = function (obj) {
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
  var reportFullscreen = function () {
    post({ cmd: "page_fullscreen",
           on: !!(document.fullscreenElement || document.webkitFullscreenElement) });
  };
  document.addEventListener("fullscreenchange", reportFullscreen, true);
  document.addEventListener("webkitfullscreenchange", reportFullscreen, true);
  /* Une page restaurée peut déjà être en plein écran (rechargement). */
  window.addEventListener("pageshow", reportFullscreen, true);""",
    "assets/ui/inject.js",
)
save("assets/ui/inject.js", j)

# ======================================================================
# 4. main.rs — état, disposition, IPC
# ======================================================================
m = load("src/main.rs")

# --- champs d'état
m = sub(
    m,
    """    size: PhysicalSize<u32>,
    fullscreen: bool,
    history_open: bool,""",
    """    size: PhysicalSize<u32>,
    fullscreen: bool,
    /// Onglet dont la **page** est en plein écran (vidéo) : l'interface est
    /// alors masquée et la page occupe la fenêtre entière.
    page_fullscreen: Option<u32>,
    history_open: bool,""",
    "src/main.rs",
)
m = sub(
    m,
    """            fullscreen: false,
            history_open: false,""",
    """            fullscreen: false,
            page_fullscreen: None,
            history_open: false,""",
    "src/main.rs",
)

# --- disposition : rects qui tiennent compte du plein écran de page
m = sub(
    m,
    """    fn content_rect(&self) -> Rect {
        let (w, h) = self.logical_size();
        let x = self.sidebar_width();
        Self::rect(x, TOOLBAR_H, w - x, h - TOOLBAR_H)
    }""",
    """    fn content_rect(&self) -> Rect {
        // Plein écran demandé par la page : elle prend toute la fenêtre.
        if self.page_fullscreen.is_some() {
            return self.full_rect();
        }
        let (w, h) = self.logical_size();
        let x = self.sidebar_width();
        Self::rect(x, TOOLBAR_H, w - x, h - TOOLBAR_H)
    }""",
    "src/main.rs",
)

# --- appliquer / quitter le plein écran de page
m = sub(
    m,
    """    fn resize(&mut self, size: PhysicalSize<u32>) {""",
    """    /// Masque (ou remontre) l'interface et redimensionne la page en
    /// conséquence. Appelé quand une page entre ou sort du plein écran.
    fn apply_page_layout(&mut self) {
        let fs = self.page_fullscreen.is_some();
        if let Some(sidebar) = &self.sidebar {
            let _ = sidebar.set_bounds(self.sidebar_rect());
            let _ = sidebar.set_visible(!fs);
        }
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.set_bounds(self.toolbar_rect());
            let _ = toolbar.set_visible(!fs);
        }
        let content = self.content_rect();
        let active = self.active_id();
        for tab in self.tabs.iter() {
            if tab.id == active {
                if let Some(view) = &tab.view {
                    let _ = view.set_bounds(content);
                }
            }
        }
        if !fs {
            self.flush_ui();
        }
    }

    /// Entrée / sortie du plein écran demandé par la page (vidéo).
    fn set_page_fullscreen(&mut self, tab: u32, on: bool) {
        if on {
            let active = self.active_id();
            // Seule la page affichée peut masquer l'interface.
            if tab != active {
                return;
            }
            if self.page_fullscreen == Some(tab) {
                return;
            }
            self.page_fullscreen = Some(tab);
            self.apply_page_layout();
        } else {
            let concerned = self.page_fullscreen == Some(tab) || self.page_fullscreen == Some(0);
            if !concerned {
                return;
            }
            self.page_fullscreen = None;
            self.apply_page_layout();
        }
    }

    /// Quitte le plein écran de page, en le disant à la page concernée.
    /// (Changer d'onglet pendant une vidéo en plein écran doit rendre
    /// l'interface — c'est aussi ce que fait Chrome.)
    fn leave_page_fullscreen(&mut self) {
        let Some(tab) = self.page_fullscreen.take() else {
            return;
        };
        if let Some(view) = self.tab(tab).and_then(|t| t.view.as_ref()) {
            let _ = view.evaluate_script("document.exitFullscreen && document.exitFullscreen();");
        }
        self.apply_page_layout();
    }

    fn resize(&mut self, size: PhysicalSize<u32>) {""",
    "src/main.rs",
)

# --- resize : ne pas réafficher l'interface si une page est en plein écran
m = sub(
    m,
    """        self.size = size;
        if let Some(sidebar) = &self.sidebar {
            let _ = sidebar.set_bounds(self.sidebar_rect());
        }
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.set_bounds(self.toolbar_rect());
        }
        if let Some(welcome) = &self.welcome {
            let _ = welcome.set_bounds(self.full_rect());
        }""",
    """        self.size = size;
        let fs = self.page_fullscreen.is_some();
        if let Some(sidebar) = &self.sidebar {
            let _ = sidebar.set_bounds(self.sidebar_rect());
            let _ = sidebar.set_visible(!fs);
        }
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.set_bounds(self.toolbar_rect());
            let _ = toolbar.set_visible(!fs);
        }
        if let Some(welcome) = &self.welcome {
            let _ = welcome.set_bounds(self.full_rect());
        }""",
    "src/main.rs",
)

# --- changer d'onglet quitte le plein écran de page
m = sub(
    m,
    """    fn set_active(&mut self, id: u32) {
        if self.index_of(id).is_none() {
            return;
        }""",
    """    fn set_active(&mut self, id: u32) {
        if self.index_of(id).is_none() {
            return;
        }
        // Changer d'onglet pendant une vidéo en plein écran rend l'interface.
        if self.page_fullscreen.is_some() && self.page_fullscreen != Some(id) {
            self.leave_page_fullscreen();
        }""",
    "src/main.rs",
)

# --- fermer l'onglet concerné quitte le plein écran de page
m = sub(
    m,
    """        let tab = self.tabs.remove(index);
        if remember {""",
    """        let tab = self.tabs.remove(index);
        if self.page_fullscreen == Some(id) {
            self.page_fullscreen = None;
            self.apply_page_layout();
        }
        if remember {""",
    "src/main.rs",
)

# --- état : couleur de fond, favoris, étoile
m = sub(
    m,
    """                    "internal": t.internal,
                    "engine": t.engine,
                    "zoom": t.zoom,
                    "search_mode": false,""",
    """                    "internal": t.internal,
                    "engine": t.engine,
                    "zoom": t.zoom,
                    "search_mode": false,
                    "is_favorite": self.is_favorite(&t.url),""",
    "src/main.rs",
)
m = sub(
    m,
    """            "closed_count": self.closed.len(),""",
    """            "closed_count": self.closed.len(),
            "favorites": self.cfg.favorites,
            "ui_bg": self.cfg.ui_bg,""",
    "src/main.rs",
)

# --- helpers favoris
m = sub(
    m,
    """    /// Masque (ou remontre) l'interface et redimensionne la page en""",
    """    /* ---------------- favoris (apps) ---------------- */

    fn is_favorite(&self, url: &str) -> bool {
        !url.is_empty()
            && !url.starts_with("nova://")
            && self.cfg.favorites.iter().any(|f| urls::canon_eq(url, &f.url))
    }

    /// Ajoute la page courante aux favoris, ou l'en retire si elle y est déjà.
    fn toggle_favorite(&mut self) -> bool {
        let Some(tab) = self.active_tab() else {
            return false;
        };
        let url = tab.url.clone();
        if url.is_empty() || url.starts_with("nova://") {
            return false;
        }
        if let Some(pos) = self.cfg.favorites.iter().position(|f| urls::canon_eq(&url, &f.url)) {
            self.cfg.favorites.remove(pos);
            return false;
        }
        let title = {
            let t = tab.display_title();
            if t.is_empty() || t == "Nouvel onglet" {
                accel::host_of(&url).to_string()
            } else {
                t
            }
        };
        if self.cfg.favorites.len() >= config::MAX_FAVORITES {
            self.cfg.favorites.remove(0);
        }
        self.cfg.favorites.push(config::Favorite { title, url });
        true
    }

    fn remove_favorite(&mut self, url: &str) {
        self.cfg.favorites.retain(|f| !urls::canon_eq(url, &f.url));
    }

    /// Masque (ou remontre) l'interface et redimensionne la page en""",
    "src/main.rs",
)

# --- IPC : plein écran de page + favoris
m = sub(
    m,
    """            "hotkey" => {""",
    """            /* --- plein écran demandé par la page (vidéo) --- */
            "page_fullscreen" => {
                let on = cmd.get("on").and_then(Value::as_bool).unwrap_or(false);
                // Les vues d'interface n'ont pas de plein écran : sans
                // `from_tab`, la commande viserait l'onglet actif.
                let tab = if from_tab != 0 { from_tab } else { self.active_id() };
                self.set_page_fullscreen(tab, on);
            }
            /* --- favoris (apps) --- */
            "toggle_favorite" => {
                self.toggle_favorite();
                self.request_save();
                self.request_sync();
            }
            "remove_favorite" => {
                if let Some(url) = cmd.get("url").and_then(Value::as_str) {
                    let url = url.to_string();
                    self.remove_favorite(&url);
                    self.request_save();
                    self.request_sync();
                }
            }
            "hotkey" => {""",
    "src/main.rs",
)
save("src/main.rs", m)

print("Rust et inject.js mis à jour : plein écran, couleur de fond, favoris.")
