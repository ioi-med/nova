//! Nova — navigateur web à onglets verticaux.
//!
//! Architecture :
//! - `tao` : fenêtre native et boucle d'événements ;
//! - `wry` : un `WebView2` (Chromium) par onglet, plus deux surfaces d'interface
//!   fixes (barre latérale, barre d'adresse) ;
//! - `native/` : accélérateur C pour le traitement des URL et la liste
//!   anti-traqueurs ;
//! - `assets/ui` : interface HTML/CSS/JS embarquée dans le binaire.
//!
//! Les vues Web ne modifient jamais l'état directement : elles envoient des
//! messages JSON (`window.ipc.postMessage`) qui sont traités sur le fil
//! principal de la boucle d'événements. Nova renvoie ensuite l'état complet aux
//! surfaces d'interface, qui le rejouent (`NovaUI.render`).

#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

mod accel;
mod blocker;
mod config;
mod engines;
mod import;
mod sqlread;
mod platform;
mod ui;
mod urls;

use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::{json, Map, Value};
use tao::dpi::{LogicalPosition, LogicalSize, PhysicalSize};
use tao::event::{Event, StartCause, WindowEvent};
use tao::event_loop::{ControlFlow, EventLoopBuilder, EventLoopProxy, EventLoopWindowTarget};
use tao::window::{Fullscreen, Window, WindowBuilder};
use wry::dpi as wdpi;
use wry::{NewWindowResponse, PageLoadEvent, Rect, WebContext, WebView, WebViewBuilder};

#[cfg(windows)]
use webview2_com::Microsoft::Web::WebView2::Win32::ICoreWebView2Environment;
#[cfg(windows)]
use wry::{Theme, WebViewBuilderExtWindows, WebViewExtWindows};

use config::{Config, History, Session, SessionTab};

/// Hauteur de la barre d'adresse, en pixels logiques.
const TOOLBAR_H: f64 = 46.0;
/// Largeur minimale conservée pour la zone de contenu.
const MIN_CONTENT_W: f64 = 360.0;

/// Délai de regroupement des mises à jour d'interface. Une page qui se charge
/// émet des dizaines d'événements (titres, iframes, progression) : sans ce
/// regroupement, l'interface était reconstruite à chaque événement et
/// monopolisait le fil de la boucle d'événements.
const UI_THROTTLE: Duration = Duration::from_millis(60);

/// Les sauvegardes (historique, session) sont différées : écrire sur disque
/// pendant un chargement ralentissait la navigation.
const SAVE_DELAY: Duration = Duration::from_secs(4);

/* ------------------------------------------------------------------ */
/* Événements                                                         */
/* ------------------------------------------------------------------ */

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Source {
    Sidebar,
    Toolbar,
    Page,
    Welcome,
}

#[derive(Debug)]
enum UserEvent {
    /// Message JSON envoyé par une vue.
    Ipc { source: Source, tab: u32, body: String },
    /// Le titre du document a changé.
    Title { tab: u32, title: String },
    /// Début / fin de chargement (URL de premier niveau fournie par le moteur).
    Load { tab: u32, started: bool, url: String },
    /// Une page demande l'ouverture d'une nouvelle fenêtre (`target=_blank`…).
    Popup { url: String },
    /// Navigation vers un protocole du système qu'aucun logiciel ne gère (ou
    /// vers l'overlay de jeu) : refusée **avant** que WebView2 ne la confie à
    /// Windows, qui afficherait « Obtenir une application pour ouvrir ce lien ».
    ProtocolRefused { tab: u32, url: String },
    /// La page est entrée ou sortie du plein écran (vidéo). Signalé soit par
    /// l'événement COM du moteur, soit par le script injecté.
    PageFullScreen { tab: u32, on: bool },
    /// Liste des navigateurs détectés, analyse faite hors du fil principal.
    ImportScan { list: Vec<import::Source>, auto: bool },
    /// Données lues depuis les sources choisies (fil de lecture).
    ImportLoaded {
        items: Vec<import::Loaded>,
        favorites: bool,
        history: bool,
        replace: bool,
        auto: bool,
    },
    /// Fichier désigné dans la boîte de dialogue système.
    ImportPicked(Option<PathBuf>),
}

/* ------------------------------------------------------------------ */
/* Onglets                                                            */
/* ------------------------------------------------------------------ */

struct Tab {
    id: u32,
    title: String,
    url: String,
    loading: bool,
    pinned: bool,
    /// L'onglet affiche une page interne de Nova (`nova://…`).
    internal: bool,
    engine: String,
    zoom: f64,
    can_back: bool,
    can_forward: bool,
    /// `None` tant que l'onglet restauré n'a pas été activé : aucun moteur
    /// n'est instancié, le démarrage reste instantané même avec 30 onglets.
    view: Option<WebView>,
}

impl Tab {
    fn display_title(&self) -> String {
        if self.internal {
            if let Some(t) = urls::display_title(&self.url) {
                return t.to_string();
            }
        }
        if !self.title.is_empty() {
            return accel::truncate(&self.title, 120).to_string();
        }
        let (host, _) = urls::split_display(&self.url);
        if host.is_empty() {
            "Nouvel onglet".to_string()
        } else {
            host
        }
    }
}

/* ------------------------------------------------------------------ */
/* Application                                                        */
/* ------------------------------------------------------------------ */

struct App {
    window: Window,
    sidebar: Option<WebView>,
    toolbar: Option<WebView>,
    welcome: Option<WebView>,
    /// Environnement WebView2 partagé : wry n'en crée qu'un par vue, ce qui
    /// faisait payer la création du moteur à chaque nouvel onglet.
    #[cfg(windows)]
    environment: Option<ICoreWebView2Environment>,

    tabs: Vec<Tab>,
    active: u32,
    next_id: u32,
    closed: Vec<SessionTab>,

    cfg: Config,
    cfg_dir: PathBuf,
    data_dir: PathBuf,
    history: History,
    blocker: Arc<blocker::Blocker>,
    browser_args: String,

    proxy: EventLoopProxy<UserEvent>,
    size: PhysicalSize<u32>,
    fullscreen: bool,
    /// Onglet dont la **page** est en plein écran (vidéo) : l'interface est
    /// alors masquée et la page occupe la fenêtre entière.
    page_fullscreen: Option<u32>,
    /// La fenêtre a-t-elle été mise en plein écran par Nova pour la vidéo ?
    /// (Ne pas confondre avec le plein écran `F11`, demandé par l'utilisateur.)
    page_fs_window: bool,
    history_open: bool,
    pending_quit: bool,
    /// Échéance de répaint de l'interface (regroupement).
    ui_deadline: Option<Instant>,
    /// Échéance d'écriture disque différée.
    save_deadline: Option<Instant>,
    /// Navigation bloquée comptabilisée depuis le démarrage.
    blocked: u32,
    /// Navigateurs détectés sur la machine (favoris / historique).
    import_sources: Vec<import::Source>,
    /// Compte rendu du dernier import, affiché par la page `nova://import`.
    import_result: Option<Value>,
    /// Une analyse ou une lecture est en cours.
    import_busy: bool,
    /// Options retenues pour l'import (favoris, historique, remplacement) :
    /// conservées ici car la boîte de dialogue système rend la main plus tard.
    import_opts: (bool, bool, bool),
    /// L'import automatique du démarrage a-t-il déjà été déclenché ?
    import_auto: bool,
    /// Liens refusés parce qu'aucun logiciel Windows ne gère leur protocole.
    protocols_refused: u32,
}

impl App {
    fn new(
        target: &EventLoopWindowTarget<UserEvent>,
        proxy: EventLoopProxy<UserEvent>,
        cfg: Config,
        history: History,
        cfg_dir: PathBuf,
    ) -> Result<Self, String> {
        // Icône de la fenêtre (barre de titre et barre des tâches) : dessinée
        // par `tools/make_icon.py`, la même que celle du fichier .ico.
        let icone = tao::window::Icon::from_rgba(
            include_bytes!("../assets/nova-64.rgba").to_vec(),
            64,
            64,
        )
        .ok();

        let window = WindowBuilder::new()
            .with_title("Nova")
            .with_inner_size(LogicalSize::new(1320.0, 840.0))
            .with_min_inner_size(LogicalSize::new(760.0, 480.0))
            .with_window_icon(icone)
            .build(target)
            .map_err(|e| format!("Impossible de créer la fenêtre : {e}"))?;

        platform::style_window(&window, cfg.dark());

        let blocker = Arc::new(blocker::Blocker::new());
        let browser_args = browser_args(&cfg, &blocker);
        let session = Session::load(&cfg_dir);

        #[allow(unused_mut)]
        let mut app = App {
            size: window.inner_size(),
            window,
            sidebar: None,
            toolbar: None,
            welcome: None,
            #[cfg(windows)]
            environment: None,
            tabs: Vec::new(),
            active: 0,
            next_id: 1,
            closed: session.closed.clone(),
            cfg,
            cfg_dir,
            data_dir: config::profile_dir(),
            history,
            blocker,
            browser_args,
            proxy,
            fullscreen: false,
            page_fullscreen: None,
            page_fs_window: false,
            history_open: false,
            pending_quit: false,
            ui_deadline: None,
            save_deadline: None,
            blocked: 0,
            import_sources: Vec::new(),
            import_result: None,
            import_busy: false,
            import_opts: (true, true, false),
            import_auto: false,
            protocols_refused: 0,
        };

        if !app.cfg.onboarding_done {
            app.show_welcome()?;
        } else {
            app.build_chrome()?;
            app.restore_or_start(&session)?;
        }

        Ok(app)
    }

    /* ---------------- état / helpers ---------------- */

    fn tab(&self, id: u32) -> Option<&Tab> {
        self.tabs.iter().find(|t| t.id == id)
    }

    fn tab_mut(&mut self, id: u32) -> Option<&mut Tab> {
        self.tabs.iter_mut().find(|t| t.id == id)
    }

    fn active_tab(&self) -> Option<&Tab> {
        self.tab(self.active).or_else(|| self.tabs.first())
    }

    fn active_id(&self) -> u32 {
        self.active_tab().map(|t| t.id).unwrap_or(0)
    }

    fn index_of(&self, id: u32) -> Option<usize> {
        self.tabs.iter().position(|t| t.id == id)
    }

    /* ---------------- géométrie ---------------- */

    fn logical_size(&self) -> (f64, f64) {
        let logical = self.size.to_logical::<f64>(self.window.scale_factor());
        (logical.width, logical.height)
    }

    fn sidebar_width(&self) -> f64 {
        let (w, _) = self.logical_size();
        self.cfg
            .sidebar_width
            .min((w - MIN_CONTENT_W).max(180.0))
            .max(180.0)
    }

    fn rect(x: f64, y: f64, w: f64, h: f64) -> Rect {
        Rect {
            position: wdpi::Position::Logical(LogicalPosition::new(x, y)),
            size: wdpi::Size::Logical(LogicalSize::new(w.max(1.0), h.max(1.0))),
        }
    }

    fn content_rect(&self) -> Rect {
        // Plein écran demandé par la page : elle prend toute la fenêtre.
        if self.page_fullscreen.is_some() {
            return self.full_rect();
        }
        let (w, h) = self.logical_size();
        let x = self.sidebar_width();
        Self::rect(x, TOOLBAR_H, w - x, h - TOOLBAR_H)
    }

    fn sidebar_rect(&self) -> Rect {
        let (_, h) = self.logical_size();
        Self::rect(0.0, 0.0, self.sidebar_width(), h)
    }

    fn toolbar_rect(&self) -> Rect {
        let (w, _) = self.logical_size();
        let x = self.sidebar_width();
        Self::rect(x, 0.0, w - x, TOOLBAR_H)
    }

    fn full_rect(&self) -> Rect {
        let (w, h) = self.logical_size();
        Self::rect(0.0, 0.0, w, h)
    }

    /* ---------------- création des vues ---------------- */

    /// Construit une vue Web partageant le profil (cookies, stockage) de Nova.
    // Constructeur interne : les paramètres sont explicites à dessein (chaque
    // appel passe une combinaison différente de vue et de cible).
    #[allow(clippy::too_many_arguments)]
    fn make_view(&mut self, html: Option<&str>, url: Option<&str>, bounds: Rect, source: Source, tab: u32, visible: bool, internal: bool) -> Result<WebView, String> {
        let mut context = WebContext::new(Some(self.data_dir.clone()));
        let proxy = self.proxy.clone();
        let proxy_title = self.proxy.clone();
        let proxy_nav = self.proxy.clone();
        let proxy_load = self.proxy.clone();
        let proxy_popup = self.proxy.clone();
        let blocker = Arc::clone(&self.blocker);
        let block_ads = self.cfg.block_trackers;
        let dark = self.cfg.dark();

        let mut builder = WebViewBuilder::new_with_web_context(&mut context)
            .with_bounds(bounds)
            .with_visible(visible)
            .with_transparent(false)
            .with_background_color(if dark {
                (26, 26, 31, 255)
            } else {
                (255, 255, 255, 255)
            })
            .with_hotkeys_zoom(false)
            .with_devtools(true)
            .with_initialization_script(ui::HOTKEYS)
            .with_ipc_handler(move |req: wry::http::Request<String>| {
                let body = req.body().clone();
                let _ = proxy.send_event(UserEvent::Ipc { source, tab, body });
            })
            .with_document_title_changed_handler(move |title| {
                let _ = proxy_title.send_event(UserEvent::Title { tab, title });
            })
            .with_on_page_load_handler(move |event, url| {
                let _ = proxy_load.send_event(UserEvent::Load {
                    tab,
                    started: matches!(event, PageLoadEvent::Started),
                    url,
                });
            })
            .with_new_window_req_handler(move |url, _features| {
                // Une page veut ouvrir une fenêtre : Nova en fait un nouvel onglet.
                let _ = proxy_popup.send_event(UserEvent::Popup { url });
                NewWindowResponse::Deny
            })
            .with_navigation_handler(move |url| {
                if url.starts_with("nova://") && !internal {
                    // Une page web ne peut pas déclencher les pages internes.
                    return false;
                }
                // Protocoles du système (`mailto:`, `ms-settings:`, `steam:`…).
                //
                // WebView2 confie ces adresses à Windows, qui affiche « Obtenir
                // une application pour ouvrir ce lien » quand aucun logiciel ne
                // les gère — c'est exactement ce qui arrivait avec
                // `ms-gamingoverlay:` (Xbox Game Bar absente de la machine).
                // Nova vérifie donc **avant** de laisser passer : si le registre
                // ne connaît pas le protocole, la navigation est refusée et
                // l'événement est journalisé.
                if let Some(scheme) = urls::scheme_of(&url) {
                    if !urls::is_engine_scheme(&scheme)
                        && (urls::is_blocked_scheme(&scheme)
                            || !platform::scheme_handler_exists(&scheme))
                    {
                        let _ = proxy_nav.send_event(UserEvent::ProtocolRefused {
                            tab,
                            url: url.clone(),
                        });
                        return false;
                    }
                }
                // Ce rappel est appelé pour **chaque** trame, iframes comprises :
                // il ne fait donc plus que décider du blocage, sans toucher à
                // l'interface (qui serait sinon reconstruite des dizaines de fois
                // par page).
                if block_ads && url.len() > 8 {
                    let host = accel::host_of(&url);
                    if host.len() >= 4 && blocker.is_blocked(&host) {
                        let _ = proxy_nav.send_event(UserEvent::Ipc {
                            source: Source::Page,
                            tab,
                            body: json!({"cmd":"blocked", "url":url}).to_string(),
                        });
                        return false;
                    }
                }
                true
            });

        builder = if let Some(html) = html {
            builder.with_html(html)
        } else {
            builder.with_url(url.unwrap_or("nova://newtab"))
        };

        // Réglages spécifiques à Windows (thème, raccourcis, arguments du moteur).
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

        // Plein écran demandé par la page : l'événement COM du moteur, puis le
        // signal du script injecté (les deux arrivent au même endroit).
        if matches!(source, Source::Page) {
            let proxy_fs = self.proxy.clone();
            platform::watch_fullscreen(&view, move |on| {
                let _ = proxy_fs.send_event(UserEvent::PageFullScreen { tab, on });
            });
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
    }

    /// État injecté dans les pages internes, avec le moteur de l'onglet courant.
    fn internal_state(&self, engine_id: &str) -> Value {
        let mut state = self.state_json(true);
        if let Some(config) = state.get_mut("config").and_then(Value::as_object_mut) {
            config.insert("engine".into(), json!(engine_id));
        }
        state
    }

    /// Exécute une action sur la vue de l'onglet actif, en la créant au besoin :
    /// un onglet restauré n'a pas encore de moteur.
    fn with_active_view<T>(&mut self, action: impl FnOnce(&WebView) -> T) -> Option<T> {
        let id = self.active_id();
        if id == 0 || !self.ensure_view(id) {
            return None;
        }
        self.tab(id).and_then(|t| t.view.as_ref()).map(action)
    }

    fn prefs(&self) -> platform::WebPrefs {
        platform::WebPrefs {
            context_menus: self.cfg.native_context_menus,
            devtools: true,
            passwords: self.cfg.passwords,
        }
    }

    /// Crée la barre latérale et la barre d'adresse.
    fn build_chrome(&mut self) -> Result<(), String> {
        let state = self.state_json(true);
        let dark = self.cfg.dark();

        let sidebar_html = ui::with_state(ui::SIDEBAR, &state);
        let sidebar = self.make_view(
            Some(&sidebar_html),
            None,
            self.sidebar_rect(),
            Source::Sidebar,
            0,
            true,
            true,
        )?;

        let toolbar_html = ui::with_state(ui::TOOLBAR, &state);
        let toolbar = self.make_view(
            Some(&toolbar_html),
            None,
            self.toolbar_rect(),
            Source::Toolbar,
            0,
            true,
            true,
        )?;

        platform::tune_webview(&sidebar, platform::WebPrefs { context_menus: false, devtools: false, passwords: false }, dark);
        platform::tune_webview(&toolbar, platform::WebPrefs { context_menus: false, devtools: false, passwords: false }, dark);

        self.sidebar = Some(sidebar);
        self.toolbar = Some(toolbar);
        Ok(())
    }

    /// Affiche l'assistant de premier lancement (plein écran, au-dessus de tout).
    fn show_welcome(&mut self) -> Result<(), String> {
        // L'assistant propose de reprendre les données d'un autre navigateur :
        // la liste doit être prête dès l'affichage.
        self.start_import_scan(false);
        let state = self.state_json(true);
        let html = ui::with_state(ui::WELCOME, &state);
        let view = self.make_view(Some(&html), None, self.full_rect(), Source::Welcome, 0, true, true)?;
        platform::tune_webview(&view, platform::WebPrefs { context_menus: false, devtools: false, passwords: false }, self.cfg.dark());
        self.welcome = Some(view);
        Ok(())
    }

    /* ---------------- session ---------------- */

    fn restore_or_start(&mut self, session: &Session) -> Result<(), String> {
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


    fn session_snapshot(&self) -> Session {
        Session {
            tabs: self
                .tabs
                .iter()
                .map(|t| SessionTab {
                    url: t.url.clone(),
                    title: t.display_title(),
                    pinned: t.pinned,
                })
                .collect(),
            closed: self.closed.clone(),
        }
    }

    fn save_all(&self) {
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


    /* ---------------- onglets ---------------- */

    fn new_tab(&mut self, url: Option<String>, background: bool, pinned: bool) -> Result<u32, String> {
        let id = self.next_id;
        self.next_id += 1;

        let requested = url.unwrap_or_else(|| self.cfg.homepage.clone());
        let engine_id = self.cfg.engine.clone();
        let engine = engines::by_id(&engine_id);
        let target = urls::resolve(&requested, engine);
        let (web_url, internal, html) = match &target {
            Some(urls::Target::Internal(page)) => (
                page.clone(),
                true,
                Some(ui::with_state(ui::internal_page(page), &self.internal_state(&engine_id))),
            ),
            Some(urls::Target::Url(u)) => (u.clone(), false, None),
            None => ("nova://newtab".to_string(), true, Some(ui::with_state(ui::NEWTAB, &self.state_json(true)))),
        };

        let view = self.make_view(
            html.as_deref(),
            Some(&web_url),
            self.content_rect(),
            Source::Page,
            id,
            !background,
            internal,
        )?;

        let zoom = self.cfg.zoom;
        let _ = view.zoom(zoom);
        platform::tune_webview(&view, self.prefs(), self.cfg.dark());

        // Avant l'arrivée du vrai titre, afficher l'hôte est plus informatif
        // qu'un « Nouvel onglet » générique.
        let title = match urls::display_title(&web_url) {
            Some(name) => name.to_string(),
            None if internal => "Nouvel onglet".to_string(),
            None => {
                let host = urls::split_display(&web_url).0;
                if host.is_empty() {
                    "Nouvel onglet".to_string()
                } else {
                    host
                }
            }
        };
        self.tabs.push(Tab {
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
        Ok(id)
    }

    fn set_active(&mut self, id: u32) {
        if self.index_of(id).is_none() {
            return;
        }
        // Changer d'onglet pendant une vidéo en plein écran rend l'interface.
        if self.page_fullscreen.is_some() && self.page_fullscreen != Some(id) {
            self.leave_page_fullscreen();
        }
        // L'onglet devient actif : on instancie son moteur seulement maintenant.
        self.active = id;
        if !self.ensure_view(id) {
            return;
        }

        let content = self.content_rect();
        for tab in self.tabs.iter_mut() {
            if let Some(view) = &tab.view {
                if tab.id == id {
                    let _ = view.set_bounds(content);
                    let _ = view.set_visible(true);
                    let _ = view.focus();
                } else {
                    let _ = view.set_visible(false);
                }
            }
        }

        self.refresh_nav_state(id);
        self.update_window_title();

        // Une page interne (paramètres, nouvel onglet) affichée tardivement doit
        // recevoir l'état courant : les repaints groupés ne visent que l'onglet actif.
        let internal = self.tab(id).map(|t| t.internal).unwrap_or(false);
        if internal {
            let state = self.state_json(true);
            if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
                let _ = view.evaluate_script(&ui::render_call(&state));
            }
        }

        self.request_sync();
    }


    fn close_tab(&mut self, id: u32, remember: bool) -> Result<(), String> {
        let Some(index) = self.index_of(id) else {
            return Ok(());
        };
        let tab = self.tabs.remove(index);
        if self.page_fullscreen == Some(id) {
            self.page_fullscreen = None;
            self.apply_page_layout();
        }
        if remember {
            self.closed.push(SessionTab {
                url: tab.url.clone(),
                title: tab.display_title(),
                pinned: tab.pinned,
            });
            if self.closed.len() > 40 {
                self.closed.remove(0);
            }
        }

        if self.tabs.is_empty() {
            let home = self.cfg.homepage.clone();
            self.new_tab(Some(home), false, false)?;
            return Ok(());
        }

        if self.active == id {
            let next = self
                .tabs
                .get(index.min(self.tabs.len().saturating_sub(1)))
                .map(|t| t.id)
                .unwrap_or(0);
            self.set_active(next);
        } else {
            self.request_sync();
        }
        Ok(())
    }

    fn reopen_closed(&mut self) {
        if let Some(entry) = self.closed.pop() {
            let _ = self.new_tab(Some(entry.url), false, entry.pinned);
        }
    }

    fn move_tab(&mut self, id: u32, target: u32, after: bool) {
        let Some(from) = self.index_of(id) else { return };
        let Some(to) = self.index_of(target) else { return };
        if from == to {
            return;
        }
        let tab = self.tabs.remove(from);
        let mut insert_at = self.index_of(target).unwrap_or(to);
        if after {
            insert_at += 1;
        }
        self.tabs.insert(insert_at.min(self.tabs.len()), tab);
        self.persist();
        self.request_sync();
    }

    fn refresh_nav_state(&mut self, id: u32) {
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


    fn update_window_title(&mut self) {
        let title = self
            .active_tab()
            .map(|t| t.display_title())
            .unwrap_or_else(|| "Nova".into());
        self.window.set_title(&format!("{title} — Nova"));
    }

    /* ---------------- navigation ---------------- */

    fn navigate(&mut self, text: &str, engine_override: Option<String>, alt: bool) {
        let id = self.active_id();
        if id == 0 {
            return;
        }
        let engine_id = engine_override.unwrap_or_else(|| {
            self.tab(id).map(|t| t.engine.clone()).unwrap_or_else(|| self.cfg.engine.clone())
        });
        let base_engine = engine_id.clone();
        let engine_id = if alt { next_engine(&base_engine) } else { engine_id };
        // Adresse d'un protocole du système (`mailto:`, `ms-settings:`…) :
        // Nova l'ouvre lui-même, et **seulement** si Windows a un logiciel pour
        // la gérer. Sinon, elle est traitée comme une recherche par le moteur,
        // plutôt que de faire surgir la boîte de dialogue « Obtenir une
        // application pour ouvrir ce lien ».
        if let Some(scheme) = urls::scheme_of(text) {
            if !urls::is_engine_scheme(&scheme) {
                let blocked = urls::is_blocked_scheme(&scheme);
                if !blocked && platform::scheme_handler_exists(&scheme)
                    && platform::open_external(text)
                {
                    return;
                }
                if blocked || platform::scheme_handler_exists(&scheme) {
                    // Protocole connu mais ouverture impossible : on le signale
                    // au lieu de lancer une recherche trompeuse.
                    self.protocols_refused = self.protocols_refused.saturating_add(1);
                    self.log_protocol_refused(id, text);
                    self.request_sync();
                    return;
                }
            }
        }
        let engine = engines::by_id(&engine_id);
        let Some(target) = urls::resolve(text, engine) else {
            return;
        };
        // Alt+Entrée est un choix ponctuel : le moteur de l'onglet ne change pas.
        let target_engine = if alt { None } else { Some(engine_id) };
        self.go(id, target, target_engine);
    }

    fn go(&mut self, id: u32, target: urls::Target, engine_id: Option<String>) {
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


    /* ---------------- raccourcis ---------------- */

    fn hotkey(&mut self, key: &str) {
        let active_id = self.active_id();

        match key {
            "reload" => {
                self.with_active_view(|view| {
                    let _ = view.reload();
                });
            }
            "back" => {
                self.with_active_view(|view| {
                    let _ = view.go_back();
                });
            }
            "forward" => {
                self.with_active_view(|view| {
                    let _ = view.go_forward();
                });
            }
            "devtools" => {
                self.with_active_view(|view| {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                });
            }
            _ => {}
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
                } else if other == "toggle_favorite" {
                    self.toggle_favorite();
                    self.request_save();
                    self.request_sync();
                } else if other == "next_tab" {
                    self.cycle_tab(1);
                } else if other == "prev_tab" {
                    self.cycle_tab(-1);
                }
            }
        }
    }


    fn cycle_tab(&mut self, delta: i32) {
        if self.tabs.len() < 2 {
            return;
        }
        let index = self.index_of(self.active_id()).unwrap_or(0) as i32;
        let len = self.tabs.len() as i32;
        let next = ((index + delta).rem_euclid(len)) as usize;
        let id = self.tabs[next].id;
        self.set_active(id);
    }

    fn home_target(&self) -> urls::Target {
        let engine = engines::by_id(&self.cfg.engine);
        urls::resolve(&self.cfg.homepage, engine)
            .unwrap_or(urls::Target::Internal("nova://newtab".into()))
    }

    fn zoom_by(&mut self, delta: f64) {
        let current = self.active_tab().map(|t| t.zoom).unwrap_or(1.0);
        self.set_zoom((current + delta).clamp(0.25, 5.0));
    }

    fn set_zoom(&mut self, value: f64) {
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


    fn toggle_fullscreen(&mut self) {
        self.fullscreen = !self.fullscreen;
        if self.fullscreen {
            self.window.set_fullscreen(Some(Fullscreen::Borderless(None)));
        } else {
            self.window.set_fullscreen(None);
        }
    }

    fn find_in_page(&mut self) {
        self.with_active_view(|view| {
            let _ = view.evaluate_script(
                "(function(){ var q = window.prompt('Rechercher dans la page :'); \
                 if (q) { var f = window.find(q, false, false, true, false, false, false); \
                 if (!f) { window.getSelection().removeAllRanges(); window.find(q, true, true, true, false, false, false); } } })();",
            );
        });
    }


    fn focus_omnibox(&mut self) {
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.focus();
            let _ = toolbar.evaluate_script("window.NovaUI && window.NovaUI.focusOmnibox();");
        }
    }

    /* ---------------- mise à jour des vues ---------------- */

    fn state_json(&self, rich: bool) -> Value {
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
                    "is_favorite": self.is_favorite(&t.url),
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
            counts.sort_by_key(|c| std::cmp::Reverse(c.3));
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
            // Thème réellement appliqué, « Système » déjà résolu par Windows :
            // les pages d'interface ne peuvent pas interroger le système, elles
            // lisaient donc `config.theme` et ignoraient le mode clair du bureau.
            "dark": self.cfg.dark(),
            "config": self.cfg,
            "engines": engines::ENGINES,
            "tabs": tabs,
            "active": active,
            "closed_count": self.closed.len(),
            "favorites": self.cfg.favorites,
            "ui_bg": self.cfg.ui_bg,
            "history": history,
            "history_rev": self.history.revision(),
            "history_open": self.history_open,
            "topsites": topsites,
            "limits": {
                "sidebar_apps": config::SIDEBAR_APPS,
                "favorites": config::MAX_FAVORITES,
            },
            "import_sources": self
                .import_sources
                .iter()
                .map(|s| {
                    json!({
                        "id": s.id,
                        "app": s.app,
                        "app_id": s.app_id(),
                        "name": s.name,
                        "kind": s.kind.label(),
                        "path": s.path.display().to_string(),
                    })
                })
                .collect::<Vec<_>>(),
            "import_result": self.import_result,
            "import_busy": self.import_busy,
            "version": config::VERSION,
            "backend": accel::backend(),
            "data_dir": self.cfg_dir.display().to_string(),
            "overlay": {
                "silenced": self.cfg.silence_game_overlay,
                "dvr_off": platform::game_dvr_disabled(),
                "stub": platform::game_overlay_stub_installed(),
                "game_bar": platform::game_bar_installed(),
                "refused": self.protocols_refused,
                "log": self.cfg_dir.join("protocoles-refuses.log").display().to_string(),
            },
            "stats": {
                "tabs": self.tabs.len(),
                "history": self.history.entries.len(),
                "trackers": self.blocker.len(),
                "blocked": self.blocked,
                "schemes_refused": self.protocols_refused,
                "log_path": self.cfg_dir.join("protocoles-refuses.log").display().to_string(),
            },
        })
    }


    /// Renvoie l'état complet aux surfaces d'interface.
    /// Envoie l'état courant aux surfaces d'interface.
    fn flush_ui(&mut self) {
        // La page interne d'historique a besoin de la liste complète, même
        // lorsque le panneau latéral est fermé.
        let history_page = self
            .active_tab()
            .map(|t| t.internal && t.url == "nova://history")
            .unwrap_or(false);
        let state = self.state_json(self.history_open || history_page);
        let payload = ui::js_payload(&state);
        let js = format!("window.NovaUI && window.NovaUI.render({payload});");
        if let Some(sidebar) = &self.sidebar {
            let _ = sidebar.evaluate_script(&js);
        }
        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.evaluate_script(&js);
        }
        // L'assistant de premier lancement suit aussi l'état : liste des
        // navigateurs dès la fin de l'analyse, résultat de l'import ensuite.
        if let Some(welcome) = &self.welcome {
            let _ = welcome.evaluate_script(&ui::render_call(&state));
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


    /* ---------------- favoris (apps) ---------------- */

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
        // La liste accepte désormais beaucoup plus de favoris (import) : on
        // n'évince l'ancien que lorsqu'elle est réellement pleine, sinon un
        // favori ajouté à la main supprimait le premier de la liste.
        if self.cfg.favorites.len() >= config::MAX_FAVORITES {
            self.cfg.favorites.remove(0);
        }
        self.cfg.favorites.push(config::Favorite { title, url });
        true
    }

    fn remove_favorite(&mut self, url: &str) {
        self.cfg.favorites.retain(|f| !urls::canon_eq(url, &f.url));
    }

    /// Masque (ou remontre) l'interface et redimensionne la page en
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
        if self.page_fs_window {
            self.page_fs_window = false;
            self.window.set_fullscreen(None);
        }
        self.apply_page_layout();
    }

    fn resize(&mut self, size: PhysicalSize<u32>) {
        if size.width == 0 || size.height == 0 {
            return;
        }
        self.size = size;
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
    }

    fn set_theme(&mut self) {
        let dark = self.cfg.dark();
        platform::style_window(&self.window, dark);
        #[cfg(windows)]
        if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
            let _ = view.set_theme(if dark { Theme::Dark } else { Theme::Light });
        }
        let _ = dark;
        // Les surfaces d'interface appliquent le thème via `NovaUI.render`.
        self.flush_ui();
    }

    /* ---------------- messages de l'interface ---------------- */

    fn on_user_event(&mut self, event: UserEvent, control_flow: &mut ControlFlow) {
        match event {
            UserEvent::Ipc { source, tab, body } => {
                self.handle_ipc(source, tab, &body);
                if self.pending_quit {
                    self.save_all();
                    *control_flow = ControlFlow::Exit;
                }
            }
            UserEvent::Title { tab, title } => {
                let clean = accel::truncate(&title, 200).to_string();
                // Les sites changent souvent leur titre : on ignore les répétitions.
                if self.tab(tab).map(|t| t.title == clean).unwrap_or(true) {
                    return;
                }
                let url = self.tab(tab).map(|t| t.url.clone()).unwrap_or_default();
                if let Some(t) = self.tab_mut(tab) {
                    t.title = clean.clone();
                }
                if !url.is_empty() && !url.starts_with("nova://") {
                    self.history.rename(&url, &clean);
                    self.request_save();
                }
                if tab == self.active_id() {
                    self.update_window_title();
                }
                self.request_sync();
            }
            UserEvent::Load { tab, started, url } => {
                let ignorable = url.is_empty() || url == "about:blank" || url.starts_with("nova://");
                if let Some(t) = self.tab_mut(tab) {
                    if !ignorable && t.url != url {
                        t.url = url;
                    }
                    if t.loading != started {
                        t.loading = started;
                    }
                }

                if !started {
                    self.refresh_nav_state(tab);
                    let (final_url, title) = self
                        .tab(tab)
                        .map(|t| (t.url.clone(), t.display_title()))
                        .unwrap_or_default();
                    if !final_url.starts_with("nova://") {
                        self.history.visit(&final_url, &title);
                        self.request_save();
                    }
                }
                self.request_sync();
            }
            UserEvent::PageFullScreen { tab, on } => {
                self.set_page_fullscreen(tab, on);
            }
            UserEvent::ProtocolRefused { tab, url } => {
                self.protocols_refused = self.protocols_refused.saturating_add(1);
                self.log_protocol_refused(tab, &url);
                self.request_sync();
            }
            UserEvent::ImportScan { list, auto } => {
                self.import_sources = list;
                self.import_busy = false;
                if auto {
                    let jobs: Vec<(String, import::Kind, PathBuf)> = self
                        .import_sources
                        .iter()
                        .map(|s| (s.name.clone(), s.kind, s.path.clone()))
                        .collect();
                    if jobs.is_empty() {
                        self.request_sync();
                    } else {
                        self.start_import_load(jobs, true, true, false, true);
                    }
                } else {
                    self.request_sync();
                }
            }
            UserEvent::ImportLoaded {
                items,
                favorites,
                history,
                replace,
                auto,
            } => {
                self.apply_import(items, favorites, history, replace, auto);
            }
            UserEvent::ImportPicked(picked) => {
                let (favorites, history, replace) = self.import_opts;
                match picked {
                    Some(path) => {
                        let name = path
                            .file_name()
                            .map(|n| n.to_string_lossy().to_string())
                            .unwrap_or_else(|| path.display().to_string());
                        let kind = import::kind_of_path(&path);
                        self.start_import_load(vec![(name, kind, path)], favorites, history, replace, false);
                    }
                    // Boîte de dialogue fermée sans choisir : rien à signaler.
                    None => self.import_busy = false,
                }
            }
            UserEvent::Popup { url } => {
                // Une page ne peut pas non plus ouvrir de force un protocole du
                // système dans un nouvel onglet.
                let refuse = urls::scheme_of(&url).is_some_and(|scheme| {
                    !urls::is_engine_scheme(&scheme)
                        && (urls::is_blocked_scheme(&scheme)
                            || !platform::scheme_handler_exists(&scheme))
                });
                if refuse {
                    self.protocols_refused = self.protocols_refused.saturating_add(1);
                    self.log_protocol_refused(0, &url);
                    self.request_sync();
                } else if !url.is_empty() {
                    let _ = self.new_tab(Some(url), false, false);
                }
            }
        }
    }


    /* ---------- protocoles refusés ---------- */

    /// Écrit la raison d'un refus dans `protocoles-refuses.log` (dossier de
    /// profil). Sert de preuve : si la boîte de dialogue de Windows réapparaît,
    /// le journal dit si c'est Nova qui a tenté la navigation — et depuis
    /// quelle page.
    fn log_protocol_refused(&self, tab: u32, url: &str) {
        let path = self.cfg_dir.join("protocoles-refuses.log");
        // Rotation simple : au-delà de 256 Ko, le journal est remis à zéro.
        if std::fs::metadata(&path).map(|m| m.len() > 256 * 1024).unwrap_or(false) {
            let _ = std::fs::write(&path, b"");
        }
        let line = format!(
            "{} | onglet {} | refusé : {} | motif : aucun logiciel Windows ne gère ce protocole\n",
            config::iso_time(config::History::now()),
            tab,
            url
        );
        use std::io::Write;
        if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(&path) {
            let _ = file.write_all(line.as_bytes());
        }
    }

    /* ---------- import des données d'un autre navigateur ---------- */

    /// Déclenche l'analyse de la machine si l'import automatique est actif.
    /// Appelé une seule fois, juste après la construction de la fenêtre.
    fn start_auto_import(&mut self) {
        // Avant la fin de l'assistant, c'est lui qui demande ce qu'il faut
        // reprendre : l'import silencieux attendrait le prochain démarrage.
        if self.cfg.onboarding_done
            && self.cfg.auto_import
            && !self.import_auto
            && self.import_sources.is_empty()
        {
            self.import_auto = true;
            self.start_import_scan(true);
        }
    }

    /// Liste les navigateurs installés. La lecture disque (profils, bases) part
    /// sur un fil dédié : l'interface ne doit jamais attendre.
    fn start_import_scan(&mut self, auto: bool) {
        self.import_busy = true;
        let proxy = self.proxy.clone();
        let spawned = std::thread::Builder::new()
            .name("nova-import-scan".into())
            .spawn(move || {
                let list = import::detect();
                let _ = proxy.send_event(UserEvent::ImportScan { list, auto });
            });
        if spawned.is_err() {
            self.import_busy = false;
            self.import_result = Some(json!({
                "favorites": 0, "visits": 0, "sources": 0, "skipped": 0,
                "notes": [], "errors": ["Impossible de lancer l'analyse des navigateurs."],
                "when_ts": config::History::now(),
            }));
            self.request_sync();
        }
    }

    /// Lit les sources demandées, puis renvoie les données au fil principal.
    fn start_import_load(
        &mut self,
        jobs: Vec<(String, import::Kind, PathBuf)>,
        favorites: bool,
        history: bool,
        replace: bool,
        auto: bool,
    ) {
        if jobs.is_empty() {
            self.import_busy = false;
            self.import_result = Some(json!({
                "favorites": 0, "visits": 0, "sources": 0, "skipped": 0,
                "notes": ["Aucune source sélectionnée."], "errors": [],
                "when_ts": config::History::now(),
            }));
            self.request_sync();
            return;
        }
        self.import_busy = true;
        self.import_opts = (favorites, history, replace);
        let proxy = self.proxy.clone();
        let spawned = std::thread::Builder::new()
            .name("nova-import-load".into())
            .spawn(move || {
                let items: Vec<import::Loaded> = jobs
                    .into_iter()
                    .map(|(name, kind, path)| {
                        let data = import::load_file(&path);
                        import::Loaded { name, kind, data }
                    })
                    .collect();
                let _ = proxy.send_event(UserEvent::ImportLoaded {
                    items,
                    favorites,
                    history,
                    replace,
                    auto,
                });
            });
        if spawned.is_err() {
            self.import_busy = false;
            self.request_sync();
        }
    }

    /// Ouvre la boîte de dialogue système (favoris HTML, `Bookmarks`, base
    /// SQLite…) sur un fil dédié : la fenêtre reste réactive pendant ce temps.
    fn pick_import_file(&mut self) {
        let proxy = self.proxy.clone();
        let spawned = std::thread::Builder::new()
            .name("nova-import-pick".into())
            .spawn(move || {
                let picked = platform::pick_file();
                let _ = proxy.send_event(UserEvent::ImportPicked(picked));
            });
        if spawned.is_err() {
            self.import_result = Some(json!({
                "favorites": 0, "visits": 0, "sources": 0, "skipped": 0,
                "notes": [], "errors": ["Impossible d'ouvrir la boîte de dialogue."],
                "when_ts": config::History::now(),
            }));
            self.request_sync();
        }
    }

    /// Fusionne les données lues avec celles de Nova, enregistre et publie le
    /// compte rendu. Point d'entrée unique : import manuel, choix d'un fichier
    /// et import automatique du démarrage passent tous par ici.
    fn apply_import(
        &mut self,
        items: Vec<import::Loaded>,
        favorites: bool,
        history: bool,
        replace: bool,
        auto: bool,
    ) {
        let mut outcome = import::Outcome::default();
        if auto {
            outcome
                .notes
                .push("Import automatique au démarrage".to_string());
        }
        for item in items {
            let merged = match &item.data {
                Ok(data) => Some(import::merge(
                    &mut self.cfg,
                    &mut self.history,
                    data,
                    favorites,
                    history,
                    replace,
                )),
                Err(_) => None,
            };
            if let Some(m) = &merged {
                outcome.favorites += m.favorites;
                outcome.visits += m.visits;
                outcome.skipped += m.skipped;
            }
            import::summarize(&mut outcome, &item.name, item.kind, &item.data, merged.as_ref());
        }
        outcome.when = config::History::now();

        if outcome.favorites > 0 || outcome.visits > 0 {
            self.cfg.save(&self.cfg_dir);
            self.history.save(&self.cfg_dir);
        }
        if auto && outcome.favorites == 0 && outcome.visits == 0 && outcome.errors.is_empty() {
            // Rien de neuf : on ne remplit pas la page d'un compte rendu vide.
            self.import_busy = false;
            self.request_sync();
            return;
        }
        self.import_result = Some(outcome.to_json());
        self.import_busy = false;
        self.request_sync();
    }

    fn handle_ipc(&mut self, _source: Source, from_tab: u32, body: &str) {
        let Ok(cmd) = serde_json::from_str::<Value>(body) else {
            return;
        };
        let name = cmd.get("cmd").and_then(Value::as_str).unwrap_or("");
        // Les vues d'interface (barre latérale, barre d'adresse) n'ont pas
        // d'onglet : sans identifiant explicite, la commande vise l'onglet actif.
        // (Auparavant le bouton « copier l'adresse » de la barre d'adresse ne
        // faisait rien : il visait l'onglet 0, qui n'existe pas.)
        let tab_target = {
            let id = cmd.get("id").and_then(Value::as_u64).unwrap_or(0) as u32;
            if id != 0 {
                id
            } else if from_tab != 0 {
                from_tab
            } else {
                self.active_id()
            }
        };

        match name {
            /* --- onglets --- */
            "new_tab" => {
                let url = cmd.get("url").and_then(Value::as_str).map(str::to_string);
                let _ = self.new_tab(url, false, false);
                self.request_save();
            }
            "close_tab" => {
                let _ = self.close_tab(tab_target, true);
                self.request_save();
            }
            "close_active" => {
                let id = self.active_id();
                let _ = self.close_tab(id, true);
                self.request_save();
            }
            "close_others" => {
                let keep = tab_target;
                let others: Vec<u32> = self.tabs.iter().map(|t| t.id).filter(|id| *id != keep).collect();
                for id in others {
                    let _ = self.close_tab(id, false);
                }
                self.set_active(keep);
                self.request_save();
            }
            "select_tab" => self.set_active(tab_target),
            "reload_tab" => {
                if let Some(view) = self.tab(tab_target).and_then(|t| t.view.as_ref()) {
                    let _ = view.reload();
                }
            }
            "duplicate_tab" => {
                if let Some(url) = self.tab(tab_target).map(|t| t.url.clone()) {
                    let _ = self.new_tab(Some(url), false, false);
                }
            }
            "pin_tab" | "unpin_tab" => {
                let pinned = name == "pin_tab";
                if let Some(t) = self.tab_mut(tab_target) {
                    t.pinned = pinned;
                }
                self.save_all();
                self.request_sync();
            }
            "move_tab" => {
                let target = cmd.get("target").and_then(Value::as_u64).unwrap_or(0) as u32;
                let after = cmd.get("after").and_then(Value::as_bool).unwrap_or(false);
                self.move_tab(tab_target, target, after);
            }
            "copy_url" => {
                let url = self
                    .tab(tab_target)
                    .map(|t| t.url.clone())
                    .unwrap_or_default();
                if !url.is_empty() {
                    platform::set_clipboard_text(&url);
                }
                self.request_sync();
            }
            "reopen" => self.reopen_closed(),
            "blocked" => {
                // Une redirection publicitaire a été bloquée : simple compteur,
                // affiché dans les paramètres.
                self.blocked = self.blocked.saturating_add(1);
            }

            /* --- navigation --- */
            "navigate" => {
                let text = cmd.get("text").and_then(Value::as_str).unwrap_or("");
                let engine = cmd.get("engine").and_then(Value::as_str).map(str::to_string);
                let alt = cmd.get("alt").and_then(Value::as_bool).unwrap_or(false);
                self.navigate(text, engine, alt);
            }
            "open_url" => {
                let url = cmd.get("url").and_then(Value::as_str).unwrap_or("").to_string();
                let new_tab = cmd.get("new_tab").and_then(Value::as_bool).unwrap_or(false);
                if url.is_empty() {
                    return;
                }
                if new_tab {
                    let _ = self.new_tab(Some(url), false, false);
                } else {
                    let engine = engines::by_id(&self.cfg.engine);
                    if let Some(target) = urls::resolve(&url, engine) {
                        let id = self.active_id();
                        self.go(id, target, None);
                    }
                }
            }
            "back" => {
                self.with_active_view(|view| {
                    let _ = view.go_back();
                });
            }
            "forward" => {
                self.with_active_view(|view| {
                    let _ = view.go_forward();
                });
            }
            "reload" => {
                self.with_active_view(|view| {
                    let _ = view.reload();
                });
            }
            "stop" => {
                let id = self.active_id();
                self.with_active_view(platform::stop_webview);
                if let Some(tab) = self.tab_mut(id) {
                    tab.loading = false;
                }
                self.request_sync();
            }
            "home" => {
                let target = self.home_target();
                let id = self.active_id();
                self.go(id, target, None);
            }
            "forget_url" => {
                if let Some(url) = cmd.get("url").and_then(Value::as_str) {
                    let url = url.to_string();
                    self.history.remove(&url);
                    self.history.save(&self.cfg_dir);
                    self.request_sync();
                }
            }

            /* --- vue --- */
            "zoom_in" => self.zoom_by(0.1),
            "zoom_out" => self.zoom_by(-0.1),
            "zoom_reset" => self.set_zoom(1.0),
            "fullscreen" => self.toggle_fullscreen(),
            "devtools" => {
                self.with_active_view(|view| {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                });
            }
            "find" => self.find_in_page(),
            "downloads" => {
                self.with_active_view(|view| {
                    let _ = view.evaluate_script(
                        "alert('Les téléchargements sont gérés par le moteur WebView2 : ils s\\'enregistrent dans votre dossier Téléchargements.');",
                    );
                });
            }

            /* --- pages internes / barre latérale --- */
            "settings" => {
                let id = self.active_id();
                self.go(id, urls::Target::Internal("nova://settings".into()), None);
            }
            "toggle_history" => {
                let explicit = cmd.get("open").and_then(Value::as_bool);
                self.history_open = explicit.unwrap_or(!self.history_open);
                self.request_sync();
            }
            "import" => {
                let id = self.active_id();
                self.go(id, urls::Target::Internal("nova://import".into()), None);
            }
            "import_scan" => self.start_import_scan(false),
            "import_pick" => self.pick_import_file(),
            "import_run" => {
                let ids: Vec<String> = cmd
                    .get("ids")
                    .and_then(Value::as_array)
                    .map(|list| {
                        list.iter()
                            .filter_map(Value::as_str)
                            .map(str::to_string)
                            .collect()
                    })
                    .unwrap_or_default();
                let favorites = cmd
                    .get("favorites")
                    .and_then(Value::as_bool)
                    .unwrap_or(true);
                let history = cmd.get("history").and_then(Value::as_bool).unwrap_or(true);
                let replace = cmd.get("replace").and_then(Value::as_bool).unwrap_or(false);
                let jobs: Vec<(String, import::Kind, PathBuf)> = self
                    .import_sources
                    .iter()
                    .filter(|s| ids.is_empty() || ids.iter().any(|id| id == &s.id))
                    .map(|s| (s.name.clone(), s.kind, s.path.clone()))
                    .collect();
                self.start_import_load(jobs, favorites, history, replace, false);
            }
            "clear_history" => {
                self.history.clear();
                self.history.save(&self.cfg_dir);
                self.request_sync();
            }
            "clear_data" => {
                self.with_active_view(|view| {
                    let _ = view.clear_all_browsing_data();
                });
                self.request_sync();
            }
            "open_profile" => {
                let dir = self.data_dir.display().to_string();
                platform::open_in_explorer(&dir);
            }
            "set_engine" => {
                if let Some(engine) = cmd.get("engine").and_then(Value::as_str) {
                    let engine = engine.to_string();
                    self.cfg.engine = engine.clone();
                    let id = self.active_id();
                    if let Some(tab) = self.tab_mut(id) {
                        tab.engine = engine;
                    }
                    self.cfg.save(&self.cfg_dir);
                    self.request_sync();
                }
            }

            /* --- réglages --- */
            "set_config" => {
                if let Some(patch) = cmd.get("patch") {
                    let theme_changed = patch.get("theme").is_some();
                    // Interrupteur du message de Windows : appliqué tout de suite.
                    let overlay_changed = patch
                        .get("silence_game_overlay")
                        .and_then(Value::as_bool);
                    let width_changed = patch.get("sidebar_width").is_some()
                        && patch.get("sidebar_width").and_then(Value::as_f64) != Some(self.cfg.sidebar_width);
                    self.cfg.patch(patch.clone());
                    self.cfg.save(&self.cfg_dir);
                    if let Some(on) = overlay_changed {
                        regler_overlay(&mut self.cfg, &self.cfg_dir, on);
                        self.request_sync();
                    }
                    if theme_changed {
                        self.set_theme();
                    } else if width_changed {
                        self.resize(self.size);
                        self.request_sync();
                    } else {
                        self.request_sync();
                    }
                }
            }
            "reset_config" => {
                let onboarding = self.cfg.onboarding_done;
                self.cfg = Config::default();
                self.cfg.onboarding_done = onboarding;
                self.cfg.save(&self.cfg_dir);
                self.set_theme();
                self.resize(self.size);
            }
            "replay_onboarding" => {
                self.cfg.onboarding_done = false;
                self.cfg.save(&self.cfg_dir);
                let _ = self.show_welcome();
            }
            "finish_onboarding" => {
                let engine = cmd
                    .get("engine")
                    .and_then(Value::as_str)
                    .unwrap_or(&self.cfg.engine)
                    .to_string();
                let mut patch = Map::new();
                patch.insert("engine".into(), json!(engine));
                patch.insert("onboarding_done".into(), json!(true));
                for key in ["block_trackers", "restore_session", "silence_game_overlay"] {
                    if let Some(v) = cmd.get(key) {
                        patch.insert(key.into(), v.clone());
                    }
                }
                if let Some(theme) = cmd.get("theme") {
                    patch.insert("theme".into(), theme.clone());
                }
                self.cfg.patch(Value::Object(patch));
                self.cfg.save(&self.cfg_dir);
                let silencieux = self.cfg.silence_game_overlay;
                regler_overlay(&mut self.cfg, &self.cfg_dir, silencieux);

                self.welcome = None;
                if self.sidebar.is_none() {
                    let _ = self.build_chrome();
                    let home = self.cfg.homepage.clone();
                    let _ = self.new_tab(Some(home), false, false);
                }
                self.set_theme();
                self.resize(self.size);
                self.request_sync();
            }

            /* --- plein écran demandé par la page (vidéo) --- */
            "page_fullscreen" => {
                let on = cmd.get("on").and_then(Value::as_bool).unwrap_or(false);
                // Les vues d'interface n'ont pas de plein écran : sans
                // `from_tab`, la commande viserait l'onglet actif.
                let tab = if from_tab != 0 { from_tab } else { self.active_id() };
                self.set_page_fullscreen(tab, on);
            }
            "copy_text" => {
                if let Some(text) = cmd.get("text").and_then(Value::as_str) {
                    let text = text.to_string();
                    platform::set_clipboard_text(&text);
                }
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
            "hotkey" => {
                if let Some(key) = cmd.get("key").and_then(Value::as_str) {
                    let key = key.to_string();
                    self.hotkey(&key);
                }
            }
            "quit" => self.pending_quit = true,
            _ => {}
        }
    }
}

/* ------------------------------------------------------------------ */
/* Utilitaires                                                        */
/* ------------------------------------------------------------------ */

fn next_engine(current: &str) -> String {
    let list = engines::ENGINES;
    let index = list.iter().position(|e| e.id == current).unwrap_or(0);
    list[(index + 1) % list.len()].id.to_string()
}

/// Applique le réglage « supprimer le message de Windows » : gestionnaire de
/// secours pour ces adresses, et Game Bar / captures coupées pour le compte
/// courant — sans quoi Windows redemande l'overlay de lui-même. Les valeurs
/// trouvées avant l'intervention sont mémorisées pour être reposées à
/// l'identique si l'utilisateur décoche le réglage.
fn regler_overlay(cfg: &mut Config, cfg_dir: &std::path::Path, actif: bool) {
    if actif {
        let _ = platform::ensure_game_overlay_stub();
        if !platform::game_dvr_disabled() {
            if let Some((captures, dvr)) = platform::game_dvr_values() {
                cfg.dvr_prev = Some([captures, dvr]);
                cfg.save(cfg_dir);
            }
            let _ = platform::set_game_dvr_disabled(true);
        }
    } else {
        let _ = platform::set_game_overlay_stub(false);
        if let Some([captures, dvr]) = cfg.dvr_prev.take() {
            let _ = platform::set_game_dvr_values(captures, dvr);
            cfg.save(cfg_dir);
        }
    }
}

/// Arguments passés au moteur de rendu (identiques pour toutes les vues : c'est
/// une exigence de WebView2 lorsqu'un même dossier de profil est partagé).
fn browser_args(cfg: &Config, blocker: &blocker::Blocker) -> String {
    let mut args = String::from(
        "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection,msEdgeSidebarV2 \
         --no-default-browser-check",
    );
    if cfg.block_trackers {
        args.push(' ');
        args.push_str(&blocker.resolver_rules(blocker.len()));
    }
    args
}

fn main() {
    // Appelé par Windows pour un protocole que Nova a accepté de « couvrir »
    // (overlay de jeu) : il n'y a rien à faire, et surtout rien à afficher.
    if std::env::args().any(|a| a == platform::OVERLAY_STUB_ARG) {
        return;
    }

    platform::init();

    if !accel::check_abi() {
        platform::fatal(
            "Nova",
            "Le module d'accélération natif est incompatible (ABI).\nRéinstallez Nova depuis une archive officielle.",
        );
    }

    let cfg_dir = config::data_dir();
    let mut cfg = Config::load(&cfg_dir);
    let history = History::load(&cfg_dir);

    // Message de Windows « Obtenir une application pour ouvrir ce lien » :
    // Nova couvre les protocoles de la Game Bar si aucun logiciel ne les gère,
    // et coupe la demande à la source (Game Bar et captures du compte courant),
    // sinon Windows la réclame de lui-même (Win+G, manette, jeu lancé).
    if cfg.silence_game_overlay {
        regler_overlay(&mut cfg, &cfg_dir, true);
    }

    let event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();

    let mut app: Option<App> = None;
    let mut fatal_reported = false;

    event_loop.run(move |event, target, control_flow| {
        if app.is_none() {
            match App::new(target, proxy.clone(), cfg.clone(), history.clone(), cfg_dir.clone()) {
                Ok(instance) => {
                    let mut instance = instance;
                    // Import automatique : les navigateurs de la machine sont
                    // relus en tâche de fond (sans bloquer l'affichage).
                    instance.start_auto_import();
                    app = Some(instance);
                }
                Err(message) => {
                    if !fatal_reported {
                        fatal_reported = true;
                        platform::fatal("Nova — démarrage impossible", &message);
                    }
                    *control_flow = ControlFlow::Exit;
                    return;
                }
            }
        }

        let Some(state) = app.as_mut() else { return };

        match event {
            Event::WindowEvent { event, .. } => match event {
                WindowEvent::CloseRequested => {
                    state.save_all();
                    *control_flow = ControlFlow::Exit;
                }
                WindowEvent::Resized(size) => state.resize(size),
                WindowEvent::ScaleFactorChanged { .. } => {
                    let size = state.window.inner_size();
                    state.resize(size);
                }
                WindowEvent::Focused(true) => state.request_sync(),
                _ => {}
            },
            Event::NewEvents(StartCause::ResumeTimeReached { .. }) => state.on_tick(),
            Event::UserEvent(user_event) => state.on_user_event(user_event, control_flow),
            Event::LoopDestroyed => state.save_all(),
            _ => {}
        }

        // Tao réinitialise `ControlFlow` à chaque itération : on reprogramme
        // l'échéance de repaint / de sauvegarde si elle existe — sauf si une
        // fermeture a déjà été demandée, auquel cas on laisse `Exit` en place.
        if !matches!(*control_flow, ControlFlow::Exit) {
            match state.next_deadline() {
                Some(deadline) => *control_flow = ControlFlow::WaitUntil(deadline),
                None => *control_flow = ControlFlow::Wait,
            }
        }
    });
}
