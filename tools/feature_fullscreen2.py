#!/usr/bin/env python3
"""Plein écran vidéo : deuxième tentative, trois couches indépendantes.

Le premier correctif ne reposait que sur l'événement JavaScript
`fullscreenchange`. S'il ne se déclenche pas dans le moteur de rendu de
l'utilisateur, rien n'est signalé à Nova et le menu de gauche reste affiché.
Ce lot ajoute :

1. **l'événement COM officiel** `ContainsFullScreenElementChanged` du moteur
   WebView2, branché directement sur la vue — il ne dépend pas de la page ;
2. **un repli par interrogation** dans le script injecté : l'état
   `document.fullscreenElement` est relu 2 fois par seconde et tout changement
   est signalé (utile si l'événement n'est pas dispatché) ;
3. la fenêtre elle-même passe en plein écran (comportement de Chrome pour une
   vidéo), et revient à l'état antérieur à la sortie.
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
# 1. platform.rs — surveiller le plein écran demandé par la page
# ======================================================================
p = load("src/platform.rs")

p = sub(
    p,
    """/// Réglages appliqués au moteur de rendu au moment de la création.
#[derive(Clone, Copy, Debug)]
#[cfg_attr(not(windows), allow(dead_code))]
pub struct WebPrefs {""",
    """/// Surveille le plein écran demandé **par la page** (lecteur vidéo, diaporama).
///
/// `ICoreWebView2::ContainsFullScreenElementChanged` est l'événement officiel du
/// moteur : il est levé dès qu'un élément du document passe en plein écran, sans
/// dépendre du JavaScript de la page (certains moteurs ne dispatchant pas
/// `fullscreenchange`, un simple écouteur JS ne suffisait pas).
///
/// Le rappel est invoqué sur le fil de la boucle d'événements : il doit donc se
/// contenter d'envoyer un message, jamais de manipuler l'interface.
#[cfg(windows)]
pub fn watch_fullscreen<F>(webview: &WebView, notify: F)
where
    F: Fn(bool) + 'static,
{
    use webview2_com::ContainsFullScreenElementChangedEventHandler;
    use wry::WebViewExtWindows;

    let core = webview.webview();
    // Le gestionnaire est conservé par COM (AddRef) : on peut le laisser ici
    // sans le retirer, l'événement devant vivre aussi longtemps que la vue.
    let handler = ContainsFullScreenElementChangedEventHandler::create(Box::new(
        move |sender, _args| {
            if let Some(core) = sender {
                let mut value = 0i32;
                unsafe {
                    if core.get_ContainsFullScreenElement(&mut value).is_ok() {
                        notify(value != 0);
                    }
                }
            }
            Ok(())
        },
    ));
    let mut token = 0i64;
    unsafe {
        let _ = core.add_ContainsFullScreenElementChanged(&handler, &mut token);
    }
}

/// Sans Windows, la fonction existe mais ne fait rien (tests sur l'hôte).
#[cfg(not(windows))]
pub fn watch_fullscreen<F>(_webview: &WebView, _notify: F)
where
    F: Fn(bool) + 'static,
{
}

/// Réglages appliqués au moteur de rendu au moment de la création.
#[derive(Clone, Copy, Debug)]
#[cfg_attr(not(windows), allow(dead_code))]
pub struct WebPrefs {""",
    "src/platform.rs",
)
save("src/platform.rs", p)

# ======================================================================
# 2. main.rs — événement, branchement, fenêtre en plein écran
# ======================================================================
m = load("src/main.rs")

m = sub(
    m,
    """    /// Une page demande l'ouverture d'une nouvelle fenêtre (`target=_blank`…).
    Popup { url: String },
}""",
    """    /// Une page demande l'ouverture d'une nouvelle fenêtre (`target=_blank`…).
    Popup { url: String },
    /// La page est entrée ou sortie du plein écran (vidéo). Signalé soit par
    /// l'événement COM du moteur, soit par le script injecté.
    PageFullScreen { tab: u32, on: bool },
}""",
    "src/main.rs",
)

m = sub(
    m,
    """    /// Onglet dont la **page** est en plein écran (vidéo) : l'interface est
    /// alors masquée et la page occupe la fenêtre entière.
    page_fullscreen: Option<u32>,""",
    """    /// Onglet dont la **page** est en plein écran (vidéo) : l'interface est
    /// alors masquée et la page occupe la fenêtre entière.
    page_fullscreen: Option<u32>,
    /// La fenêtre a-t-elle été mise en plein écran par Nova pour la vidéo ?
    /// (Ne pas confondre avec le plein écran `F11`, demandé par l'utilisateur.)
    page_fs_window: bool,""",
    "src/main.rs",
)

m = sub(
    m,
    """            page_fullscreen: None,
            history_open: false,""",
    """            page_fullscreen: None,
            page_fs_window: false,
            history_open: false,""",
    "src/main.rs",
)

# --- branchement de la surveillance à la création de la vue
m = sub(
    m,
    """        #[cfg(windows)]
        if self.environment.is_none() {
            self.environment = Some(view.environment());
        }

        Ok(view)
    }""",
    """        #[cfg(windows)]
        if self.environment.is_none() {
            self.environment = Some(view.environment());
        }

        // Plein écran demandé par la page : l'événement COM du moteur, puis le
        // signal du script injecté (les deux arrivent au même endroit).
        if matches!(source, Source::Page) {
            let proxy_fs = self.proxy.clone();
            platform::watch_fullscreen(&view, move |on| {
                let _ = proxy_fs.send_event(UserEvent::PageFullScreen { tab, on });
            });
        }

        Ok(view)
    }""",
    "src/main.rs",
)

# --- traitement de l'événement
m = sub(
    m,
    """            UserEvent::Popup { url } => {""",
    """            UserEvent::PageFullScreen { tab, on } => {
                self.set_page_fullscreen(tab, on);
            }
            UserEvent::Popup { url } => {""",
    "src/main.rs",
)

# --- entrée / sortie : masquer l'interface et mettre la fenêtre en plein écran
m = sub(
    m,
    """    /// Entrée / sortie du plein écran demandé par la page (vidéo).
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
    }""",
    """    /// Entrée / sortie du plein écran demandé par la page (vidéo).
    fn set_page_fullscreen(&mut self, tab: u32, on: bool) {
        if on {
            let active = self.active_id();
            // Seule la page affichée peut masquer l'interface. (L'onglet est
            // identifié par l'événement ; à défaut, c'est l'onglet actif.)
            if tab != 0 && tab != active {
                return;
            }
            if self.page_fullscreen.is_some() {
                return;
            }
            self.page_fullscreen = Some(if tab == 0 { active } else { tab });
            // Comme Chrome : la fenêtre entière passe en plein écran. Si
            // l'utilisateur l'a déjà demandé avec F11, on n'y touche pas.
            if !self.fullscreen {
                self.window.set_fullscreen(Some(Fullscreen::Borderless(None)));
                self.page_fs_window = true;
            }
            self.apply_page_layout();
            // La barre latérale disparaît : l'image de fond de fenêtre doit
            // suivre le thème pour éviter une bande blanche fugace.
            let dark = self.cfg.dark();
            platform::style_window(&self.window, dark);
        } else {
            let concerned = self.page_fullscreen.is_some();
            if !concerned {
                return;
            }
            self.page_fullscreen = None;
            if self.page_fs_window {
                self.page_fs_window = false;
                self.window.set_fullscreen(None);
            }
            self.apply_page_layout();
        }
    }""",
    "src/main.rs",
)

# --- sortie par changement d'onglet / fermeture : restaurer aussi la fenêtre
m = sub(
    m,
    """    fn leave_page_fullscreen(&mut self) {
        let Some(tab) = self.page_fullscreen.take() else {
            return;
        };
        if let Some(view) = self.tab(tab).and_then(|t| t.view.as_ref()) {
            let _ = view.evaluate_script("document.exitFullscreen && document.exitFullscreen();");
        }
        self.apply_page_layout();
    }""",
    """    fn leave_page_fullscreen(&mut self) {
        let Some(tab) = self.page_fullscreen.take() else {
            return;
        };
        if let Some(view) = self.tab(tab).and_then(|t| t.view.as_ref()) {
            let _ = view.evaluate_script("document.exitFullscreen && document.exitFullscreen();");
        }
        if self.page_fs_window {
            self.page_fs_window = false;
            self.window.set_fullscreen(None);
        }
        self.apply_page_layout();
    }""",
    "src/main.rs",
)
save("src/main.rs", m)

# ======================================================================
# 3. inject.js — repli par interrogation de l'état
# ======================================================================
j = load("assets/ui/inject.js")
j = sub(
    j,
    """  var reportFullscreen = function () {
    post({ cmd: "page_fullscreen",
           on: !!(document.fullscreenElement || document.webkitFullscreenElement) });
  };
  document.addEventListener("fullscreenchange", reportFullscreen, true);
  document.addEventListener("webkitfullscreenchange", reportFullscreen, true);
  /* Une page restaurée peut déjà être en plein écran (rechargement). */
  window.addEventListener("pageshow", reportFullscreen, true);""",
    """  var fsState = null;
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
  }, 500);""",
    "assets/ui/inject.js",
)
save("assets/ui/inject.js", j)

print("Trois couches en place : COM (moteur), événement JS, interrogation JS.")
