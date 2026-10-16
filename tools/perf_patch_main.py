#!/usr/bin/env python3
"""Correctifs de performance pour src/main.rs (partie 2)."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "src" / "main.rs"
src = PATH.read_text(encoding="utf-8")


def sub(old, new, count=1):
    global src
    if old not in src:
        raise SystemExit("motif introuvable :\n" + old[:500])
    src = src.replace(old, new, count)


def replace_fn(signature, new_body):
    global src
    start = src.find(signature)
    if start < 0:
        raise SystemExit("fonction introuvable : " + signature.strip())
    i = start + len(signature)
    depth = 1
    while depth > 0:
        char = src[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        i += 1
    src = src[:start] + new_body + src[i:]


# ----------------------------------------------------------------------
# Imports et constantes
# ----------------------------------------------------------------------
sub("""use std::path::PathBuf;
use std::sync::Arc;""", """use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};""")

sub("""use tao::event::{Event, WindowEvent};""", """use tao::event::{Event, StartCause, WindowEvent};""")

sub("""#[cfg(windows)]
use wry::{Theme, WebViewBuilderExtWindows, WebViewExtWindows};""", """#[cfg(windows)]
use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Environment;
#[cfg(windows)]
use wry::{Theme, WebViewBuilderExtWindows, WebViewExtWindows};""")

sub("""/// Largeur minimale conservée pour la zone de contenu.
const MIN_CONTENT_W: f64 = 360.0;""", """/// Largeur minimale conservée pour la zone de contenu.
const MIN_CONTENT_W: f64 = 360.0;

/// Délai de regroupement des mises à jour d'interface. Une page qui se charge
/// émet des dizaines d'événements (titres, iframes, progression) : sans ce
/// regroupement, l'interface était reconstruite à chaque événement et
/// monopolisait le fil de la boucle d'événements.
const UI_THROTTLE: Duration = Duration::from_millis(60);

/// Les sauvegardes (historique, session) sont différées : écrire sur disque
/// pendant un chargement ralentissait la navigation.
const SAVE_DELAY: Duration = Duration::from_secs(4);""")

# ----------------------------------------------------------------------
# Onglets : la vue Web devient optionnelle (chargement paresseux)
# ----------------------------------------------------------------------
sub("""    can_back: bool,
    can_forward: bool,
    webview: WebView,
}""", """    can_back: bool,
    can_forward: bool,
    /// `None` tant que l'onglet restauré n'a pas été activé : aucun moteur
    /// n'est instancié, le démarrage reste instantané même avec 30 onglets.
    view: Option<WebView>,
}""")

# ----------------------------------------------------------------------
# Champs de l'application
# ----------------------------------------------------------------------
sub("""    sidebar: Option<WebView>,
    toolbar: Option<WebView>,
    welcome: Option<WebView>,
""", """    sidebar: Option<WebView>,
    toolbar: Option<WebView>,
    welcome: Option<WebView>,
    /// Environnement WebView2 partagé : wry n'en crée qu'un par vue, ce qui
    /// faisait payer la création du moteur à chaque nouvel onglet.
    #[cfg(windows)]
    environment: Option<ICoreWebView2Environment>,
""")

sub("""    fullscreen: bool,
    history_open: bool,
    pending_quit: bool,
}""", """    fullscreen: bool,
    history_open: bool,
    pending_quit: bool,
    /// Échéance de répaint de l'interface (regroupement).
    ui_deadline: Option<Instant>,
    /// Échéance d'écriture disque différée.
    save_deadline: Option<Instant>,
    /// Navigation bloquée comptabilisée depuis le démarrage.
    blocked: u32,
}""")

sub("""            fullscreen: false,
            history_open: false,
            pending_quit: false,
        };""", """            fullscreen: false,
            history_open: false,
            pending_quit: false,
            ui_deadline: None,
            save_deadline: None,
            blocked: 0,
        };""")

sub("""        let session = Session::load(&cfg_dir);

        let mut app = App {""", """        let session = Session::load(&cfg_dir);

        #[allow(unused_mut)]
        let mut app = App {""")

sub("""            welcome: None,
            tabs: Vec::new(),""", """            welcome: None,
            #[cfg(windows)]
            environment: None,
            tabs: Vec::new(),""")

# ----------------------------------------------------------------------
# make_view : environnements partagés
# ----------------------------------------------------------------------
sub("""    fn make_view(&self, html: Option<&str>, url: Option<&str>, bounds: Rect, source: Source, tab: u32, visible: bool, internal: bool) -> Result<WebView, String> {""",
    """    fn make_view(&mut self, html: Option<&str>, url: Option<&str>, bounds: Rect, source: Source, tab: u32, visible: bool, internal: bool) -> Result<WebView, String> {""")

sub("""        // Réglages spécifiques à Windows (barre d'état, menus, zoom logiciel…).
        #[cfg(windows)]
        {
            builder = builder
                .with_theme(if dark { Theme::Dark } else { Theme::Light })
                .with_browser_accelerator_keys(false)
                .with_additional_browser_args(self.browser_args.clone());
        }
        #[cfg(not(windows))]
        {
            let _ = &self.browser_args;
        }

        builder
            .build_as_child(&self.window)
            .map_err(|e| format!("Création de la vue Web impossible : {e}"))
    }""", """        // Réglages spécifiques à Windows (thème, raccourcis, arguments du moteur).
        #[cfg(windows)]
        {
            builder = builder
                .with_theme(if dark { Theme::Dark } else { Theme::Light })
                .with_browser_accelerator_keys(false);

            // Le premier environnement est créé par wry avec les arguments du
            // moteur ; toutes les vues suivantes le réutilisent (un seul
            // processus de navigateur, pas de création d'environnement par onglet).
            match &self.environment {
                Some(environment) => {
                    builder = builder.with_environment(environment.clone());
                }
                None => {
                    builder = builder.with_additional_browser_args(self.browser_args.clone());
                }
            }
        }
        #[cfg(not(windows))]
        {
            let _ = &self.browser_args;
        }

        let view = builder
            .build_as_child(&self.window)
            .map_err(|e| format!("Création de la vue Web impossible : {e}"))?;

        #[cfg(windows)]
        if self.environment.is_none() {
            self.environment = Some(view.environment());
        }

        Ok(view)
    }

    /// Crée la vue d'un onglet en veille. Retourne `false` si la création échoue.
    fn ensure_view(&mut self, id: u32) -> bool {
        let Some(index) = self.index_of(id) else {
            return false;
        };
        if self.tabs[index].view.is_some() {
            return true;
        }

        let (url, internal, engine) = {
            let tab = &self.tabs[index];
            (tab.url.clone(), tab.internal, tab.engine.clone())
        };
        let visible = id == self.active;
        let bounds = self.content_rect();
        let (html, web_url) = if internal {
            let state = self.internal_state(&engine);
            (
                Some(ui::with_state(ui::internal_page(&url), &state)),
                url.clone(),
            )
        } else {
            (None, url.clone())
        };

        match self.make_view(
            html.as_deref(),
            Some(&web_url),
            bounds,
            Source::Page,
            id,
            visible,
            internal,
        ) {
            Ok(view) => {
                let zoom = self.cfg.zoom;
                let _ = view.zoom(zoom);
                platform::tune_webview(&view, self.prefs(), self.cfg.dark());
                if let Some(tab) = self.tab_mut(id) {
                    tab.loading = !internal;
                    tab.view = Some(view);
                }
                true
            }
            Err(_) => false,
        }
    }""")

# ----------------------------------------------------------------------
# Repaint regroupé, sauvegardes différées
# ----------------------------------------------------------------------
sub("""    fn internal_state(&self, engine_id: &str) -> Value {
        let mut state = self.state_json();""", """    fn internal_state(&self, engine_id: &str) -> Value {
        let mut state = self.state_json(true);""")

replace_fn("    fn save_all(&self) {", """    fn save_all(&self) {
        self.persist();
        self.cfg.save(&self.cfg_dir);
    }

    /// Écrit sur disque l'historique et la session.
    fn persist(&self) {
        self.history.save(&self.cfg_dir);
        self.session_snapshot().save(&self.cfg_dir);
    }

    /// Demande une sauvegarde différée (au plus une écriture toutes les 4 s).
    fn request_save(&mut self) {
        if self.save_deadline.is_none() {
            self.save_deadline = Some(Instant::now() + SAVE_DELAY);
        }
    }

    /// Demande un repaint de l'interface, regroupé sur 60 ms.
    fn request_sync(&mut self) {
        if self.ui_deadline.is_none() {
            self.ui_deadline = Some(Instant::now() + UI_THROTTLE);
        }
    }

    /// Prochaine échéance à honorer (repaint ou sauvegarde).
    fn next_deadline(&self) -> Option<Instant> {
        match (self.ui_deadline, self.save_deadline) {
            (Some(a), Some(b)) => Some(a.min(b)),
            (Some(a), None) | (None, Some(a)) => Some(a),
            (None, None) => None,
        }
    }

    /// Appelé par la boucle d'événements quand une échéance est atteinte.
    fn on_tick(&mut self) {
        let now = Instant::now();
        if self.save_deadline.map(|d| d <= now).unwrap_or(false) {
            self.save_deadline = None;
            self.persist();
        }
        if self.ui_deadline.map(|d| d <= now).unwrap_or(false) {
            self.ui_deadline = None;
            self.flush_ui();
        }
    }
""")

replace_fn("    fn sync(&self) {", """    /// Envoie l'état courant aux surfaces d'interface.
    fn flush_ui(&mut self) {
        let state = self.state_json(self.history_open);
        let payload = ui::js_payload(&state);
        let js = format!("window.NovaUI && window.NovaUI.render({payload});");
        if let Some(sidebar) = &self.sidebar {
            let _ = sidebar.evaluate_script(&js);
        }
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.evaluate_script(&js);
        }
        let active = self.active_id();
        if let Some(tab) = self.tab(active) {
            if tab.internal {
                let render = ui::render_call(&state);
                if let Some(view) = &tab.view {
                    let _ = view.evaluate_script(&render);
                }
            }
        }
    }
""")

# ----------------------------------------------------------------------
# Restauration de session : un seul onglet chargé, les autres en veille
# ----------------------------------------------------------------------
replace_fn("    fn restore_or_start(&mut self, session: &Session) -> Result<(), String> {", """    fn restore_or_start(&mut self, session: &Session) -> Result<(), String> {
        let mut pending = 0usize;

        if self.cfg.restore_session {
            let candidates: Vec<&SessionTab> = session
                .tabs
                .iter()
                .filter(|t| !t.url.is_empty())
                .filter(|t| !self.cfg.start_with_pinned || t.pinned)
                .collect();

            for (index, saved) in candidates.iter().enumerate() {
                if index == 0 {
                    // Le premier onglet est chargé tout de suite : la fenêtre
                    // n'est jamais vide.
                    if self
                        .new_tab(Some(saved.url.clone()), true, saved.pinned)
                        .is_ok()
                    {
                        pending += 1;
                    }
                } else {
                    self.restore_tab(saved.url.clone(), saved.title.clone(), saved.pinned);
                    pending += 1;
                }
            }
        }

        if pending == 0 {
            let home = self.cfg.homepage.clone();
            self.new_tab(Some(home), false, false)?;
        } else if let Some(first) = self.tabs.first().map(|t| t.id) {
            self.set_active(first);
        }
        Ok(())
    }

    /// Ouvre un onglet en veille : aucun moteur n'est instancié avant la
    /// première activation de l'onglet.
    fn restore_tab(&mut self, url: String, title: String, pinned: bool) {
        let id = self.next_id;
        self.next_id += 1;
        let internal = url.starts_with("nova://");
        let title = if title.is_empty() {
            urls::display_title(&url).unwrap_or("Nouvel onglet").to_string()
        } else {
            title
        };
        self.tabs.push(Tab {
            id,
            title,
            url,
            loading: false,
            pinned,
            internal,
            engine: self.cfg.engine.clone(),
            zoom: self.cfg.zoom,
            can_back: false,
            can_forward: false,
            view: None,
        });
    }
""")

# ----------------------------------------------------------------------
# new_tab / set_active / close_tab / move_tab
# ----------------------------------------------------------------------
sub("""        self.tabs.push(Tab {
            id,
            title,
            url: web_url,
            loading: true,
            pinned,
            internal,
            engine: engine_id,
            zoom,
            can_back: false,
            can_forward: false,
            webview: view,
        });

        if !background {
            self.set_active(id);
        } else {
            self.sync();
        }
        Ok(id)""", """        self.tabs.push(Tab {
            id,
            title,
            url: web_url,
            loading: true,
            pinned,
            internal,
            engine: engine_id,
            zoom,
            can_back: false,
            can_forward: false,
            view: Some(view),
        });

        if !background {
            self.set_active(id);
        } else {
            self.request_sync();
        }
        Ok(id)""")

replace_fn("    fn set_active(&mut self, id: u32) {", """    fn set_active(&mut self, id: u32) {
        if self.index_of(id).is_none() {
            return;
        }
        // L'onglet devient actif : on instancie son moteur seulement maintenant.
        self.active = id;
        if !self.ensure_view(id) {
            return;
        }

        let content = self.content_rect();
        for tab in self.tabs.iter_mut() {
            match &tab.view {
                Some(view) => {
                    if tab.id == id {
                        let _ = view.set_bounds(content);
                        let _ = view.set_visible(true);
                        let _ = view.focus();
                    } else {
                        let _ = view.set_visible(false);
                    }
                }
                None => {}
            }
        }

        self.refresh_nav_state(id);
        self.update_window_title();
        self.request_sync();
    }
""")

sub("""        if self.active == id {
            let next = self.tabs.get(index.min(self.tabs.len().saturating_sub(1))).map(|t| t.id).unwrap_or(0);
            self.set_active(next);
        } else {
            self.sync();
        }
        Ok(())""", """        if self.active == id {
            let next = self
                .tabs
                .get(index.min(self.tabs.len().saturating_sub(1)))
                .map(|t| t.id)
                .unwrap_or(0);
            self.set_active(next);
        } else {
            self.request_sync();
        }
        Ok(())""")

sub("""        self.tabs.insert(insert_at.min(self.tabs.len()), tab);
        self.save_all();
        self.sync();""", """        self.tabs.insert(insert_at.min(self.tabs.len()), tab);
        self.persist();
        self.request_sync();""")

replace_fn("    fn refresh_nav_state(&mut self, id: u32) {", """    fn refresh_nav_state(&mut self, id: u32) {
        let Some(tab) = self.tab(id) else { return };
        let Some(view) = &tab.view else {
            if let Some(tab) = self.tab_mut(id) {
                tab.can_back = false;
                tab.can_forward = false;
            }
            return;
        };
        let back = view.can_go_back().unwrap_or(false);
        let forward = view.can_go_forward().unwrap_or(false);
        if let Some(tab) = self.tab_mut(id) {
            tab.can_back = back;
            tab.can_forward = forward;
        }
    }
""")

# ----------------------------------------------------------------------
# go() : la vue peut ne pas exister encore
# ----------------------------------------------------------------------
replace_fn("    fn go(&mut self, id: u32, target: urls::Target, engine_id: Option<String>) {", """    fn go(&mut self, id: u32, target: urls::Target, engine_id: Option<String>) {
        if self.tab(id).is_none() {
            return;
        }
        match target {
            urls::Target::Url(url) => {
                if let Some(tab) = self.tab_mut(id) {
                    tab.internal = false;
                    tab.loading = true;
                    tab.url = url.clone();
                    if let Some(engine) = engine_id {
                        tab.engine = engine;
                    }
                }
                if self.ensure_view(id) {
                    if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
                        let _ = view.load_url(&url);
                    }
                }
            }
            urls::Target::Internal(page) => {
                let engine = engine_id.unwrap_or_else(|| self.cfg.engine.clone());
                let html = ui::with_state(ui::internal_page(&page), &self.internal_state(&engine));
                let title = urls::display_title(&page).unwrap_or("Nova").to_string();
                if let Some(tab) = self.tab_mut(id) {
                    tab.internal = true;
                    tab.loading = false;
                    tab.url = page.clone();
                    tab.title = title;
                }
                if self.ensure_view(id) {
                    if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
                        let _ = view.load_html(&html);
                    }
                }
            }
        }
        self.update_window_title();
        self.request_sync();
    }
""")

# ----------------------------------------------------------------------
# Raccourcis : accès à la vue optionnelle
# ----------------------------------------------------------------------
replace_fn("    fn hotkey(&mut self, key: &str) {", """    fn hotkey(&mut self, key: &str) {
        let active_id = self.active_id();
        if let Some(view) = self.tab(active_id).and_then(|t| t.view.as_ref()) {
            match key {
                "reload" => {
                    let _ = view.reload();
                }
                "back" => {
                    let _ = view.go_back();
                }
                "forward" => {
                    let _ = view.go_forward();
                }
                "devtools" => {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                }
                _ => {}
            }
        }

        match key {
            "new_tab" => {
                let _ = self.new_tab(None, false, false);
            }
            "close_tab" => {
                let _ = self.close_tab(active_id, true);
                self.request_save();
            }
            "reopen_closed" => self.reopen_closed(),
            "focus_url" => self.focus_omnibox(),
            "history" => {
                self.history_open = !self.history_open;
                self.request_sync();
            }
            "settings" => {
                self.go(active_id, urls::Target::Internal("nova://settings".into()), None);
            }
            "home" => {
                let target = self.home_target();
                self.go(active_id, target, None);
            }
            "zoom_in" => self.zoom_by(0.1),
            "zoom_out" => self.zoom_by(-0.1),
            "zoom_reset" => self.set_zoom(1.0),
            "fullscreen" => self.toggle_fullscreen(),
            "find" => self.find_in_page(),
            "copy_url" => {
                if let Some(tab) = self.tab(active_id) {
                    let url = tab.url.clone();
                    platform::set_clipboard_text(&url);
                }
            }
            other => {
                if let Some(rest) = other.strip_prefix("tab_") {
                    if let Ok(n) = rest.parse::<usize>() {
                        if let Some(tab) = self.tabs.get(n.saturating_sub(1)) {
                            let id = tab.id;
                            self.set_active(id);
                        }
                    }
                } else if other == "next_tab" {
                    self.cycle_tab(1);
                } else if other == "prev_tab" {
                    self.cycle_tab(-1);
                }
            }
        }
    }
""")

replace_fn("    fn set_zoom(&mut self, value: f64) {", """    fn set_zoom(&mut self, value: f64) {
        let value = (value * 100.0).round() / 100.0;
        let id = self.active_id();
        if let Some(tab) = self.tab_mut(id) {
            tab.zoom = value;
        }
        if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
            let _ = view.zoom(value);
        }
        self.request_sync();
    }
""")

replace_fn("    fn find_in_page(&mut self) {", """    fn find_in_page(&mut self) {
        let id = self.active_id();
        if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
            let _ = view.evaluate_script(
                "(function(){ var q = window.prompt('Rechercher dans la page :'); \\
                 if (q) { var f = window.find(q, false, false, true, false, false, false); \\
                 if (!f) { window.getSelection().removeAllRanges(); window.find(q, true, true, true, false, false, false); } } })();",
            );
        }
    }
""")

# ----------------------------------------------------------------------
# État : charge utile allégée (historique seulement si le panneau est ouvert)
# ----------------------------------------------------------------------
replace_fn("    fn state_json(&self) -> Value {", """    fn state_json(&self, rich: bool) -> Value {
        let active_id = self.active_id();

        let tabs: Vec<Value> = self
            .tabs
            .iter()
            .map(|t| {
                json!({
                    "id": t.id,
                    "title": t.display_title(),
                    "url": t.url,
                    "pinned": t.pinned,
                    "loading": t.loading,
                    "internal": t.internal,
                    "active": t.id == active_id,
                })
            })
            .collect();

        let active = self
            .active_tab()
            .map(|t| {
                json!({
                    "id": t.id,
                    "url": t.url,
                    "title": t.display_title(),
                    "loading": t.loading,
                    "can_back": t.can_back,
                    "can_forward": t.can_forward,
                    "secure": urls::is_secure(&t.url),
                    "internal": t.internal,
                    "engine": t.engine,
                    "zoom": t.zoom,
                    "search_mode": false,
                })
            })
            .unwrap_or_else(|| json!({"id":0,"url":"","loading":false,"can_back":false,"can_forward":false,"secure":true,"engine":self.cfg.engine,"zoom":1.0}));

        // L'historique et les sites fréquents ne sont envoyés que lorsqu'ils
        // sont affichés : c'est ce qui coûtait le plus cher à chaque repaint.
        let history: Vec<Value> = if rich {
            self.history
                .recent(80)
                .into_iter()
                .map(|h| json!({"title": h.title, "url": h.url, "ts": h.ts}))
                .collect()
        } else {
            Vec::new()
        };

        let topsites: Vec<Value> = if rich {
            let mut index: std::collections::HashMap<u64, usize> = std::collections::HashMap::new();
            let mut counts: Vec<(String, String, String, u32)> = Vec::new();
            for entry in self.history.entries.iter().rev().take(400) {
                let host = accel::host_of(&entry.url);
                if host.is_empty() {
                    continue;
                }
                match index.get(&accel::hash64(&host)) {
                    Some(slot) => counts[*slot].3 += entry.visits.max(1),
                    None => {
                        index.insert(accel::hash64(&host), counts.len());
                        counts.push((host, entry.url.clone(), entry.title.clone(), entry.visits.max(1)));
                    }
                }
            }
            counts.sort_by(|a, b| b.3.cmp(&a.3));
            counts
                .iter()
                .take(10)
                .map(|(host, url, title, _)| json!({"host": host, "url": url, "title": title}))
                .collect()
        } else {
            Vec::new()
        };

        json!({
            "theme": if self.cfg.dark() { "dark" } else { "light" },
            "config": self.cfg,
            "engines": engines::ENGINES,
            "tabs": tabs,
            "active": active,
            "closed_count": self.closed.len(),
            "history": history,
            "history_rev": self.history.revision(),
            "history_open": self.history_open,
            "topsites": topsites,
            "version": config::VERSION,
            "backend": accel::backend(),
            "data_dir": self.cfg_dir.display().to_string(),
            "stats": {
                "tabs": self.tabs.len(),
                "history": self.history.entries.len(),
                "trackers": self.blocker.len(),
                "blocked": self.blocked,
            },
        })
    }
""")

# ----------------------------------------------------------------------
# resize / set_theme
# ----------------------------------------------------------------------
sub("""        let content = self.content_rect();
        let active = self.active_id();
        for tab in self.tabs.iter() {
            if tab.id == active {
                let _ = tab.webview.set_bounds(content);
            }
        }
    }""", """        let content = self.content_rect();
        let active = self.active_id();
        for tab in self.tabs.iter() {
            if tab.id == active {
                if let Some(view) = &tab.view {
                    let _ = view.set_bounds(content);
                }
            }
        }
    }""")

sub("""        #[cfg(windows)]
        if let Some(tab) = self.active_tab() {
            let _ = tab.webview.set_theme(if dark { Theme::Dark } else { Theme::Light });
        }
        let _ = dark;
        // Les surfaces d'interface appliquent le thème via `NovaUI.render`.
        self.sync();""", """        #[cfg(windows)]
        if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
            let _ = view.set_theme(if dark { Theme::Dark } else { Theme::Light });
        }
        let _ = dark;
        // Les surfaces d'interface appliquent le thème via `NovaUI.render`.
        self.flush_ui();""")

print("main.rs : première série de correctifs appliquée")
PATH.write_text(src, encoding="utf-8")
