#!/usr/bin/env python3
"""Correctifs de performance pour src/main.rs (partie 3 : événements et boucle)."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH = ROOT / "src" / "main.rs"
src = PATH.read_text(encoding="utf-8")


def sub(old, new, count=1):
    global src
    if old not in src:
        raise SystemExit("motif introuvable :\n" + old[:400])
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
# 1. L'événement « navigation » disparaît : `NavigationStarting` se déclenche
#    aussi pour les iframes, ce qui polluait la barre d'adresse et l'interface.
#    L'URL de référence vient désormais de `ContentLoading`/`NavigationCompleted`
#    (wry y fournit toujours l'URL de premier niveau).
# ----------------------------------------------------------------------
sub("""    /// Le titre du document a changé.
    Title { tab: u32, title: String },
    /// Une navigation de premier niveau démarre.
    Nav { tab: u32, url: String },
    /// Début / fin de chargement.
    Load { tab: u32, started: bool },""", """    /// Le titre du document a changé.
    Title { tab: u32, title: String },
    /// Début / fin de chargement (URL de premier niveau fournie par le moteur).
    Load { tab: u32, started: bool, url: String },""")

sub("""            .with_on_page_load_handler(move |event, url| {
                let _ = proxy_load.send_event(UserEvent::Load {
                    tab,
                    started: matches!(event, PageLoadEvent::Started),
                });
                if matches!(event, PageLoadEvent::Finished) && !url.is_empty() && url != "about:blank" {
                    let _ = proxy_load.send_event(UserEvent::Nav { tab, url });
                }
            })""", """            .with_on_page_load_handler(move |event, url| {
                let _ = proxy_load.send_event(UserEvent::Load {
                    tab,
                    started: matches!(event, PageLoadEvent::Started),
                    url,
                });
            })""")

sub("""                if block_ads {
                    let host = accel::host_of(&url);
                    if !host.is_empty() && blocker.is_blocked(&host) {
                        // Redirection publicitaire : on l'annonce et on bloque.
                        let _ = proxy_nav.send_event(UserEvent::Ipc {
                            source: Source::Page,
                            tab,
                            body: json!({"cmd":"blocked", "url":url}).to_string(),
                        });
                        return false;
                    }
                }
                let _ = proxy_nav.send_event(UserEvent::Nav { tab, url });
                true""", """                // Ce rappel est appelé pour **chaque** trame, iframes comprises :
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
                true""")

# ----------------------------------------------------------------------
# 2. Traitement des événements : plus de travail inutile, repaint regroupé
# ----------------------------------------------------------------------
replace_fn("    fn on_user_event(&mut self, event: UserEvent, control_flow: &mut ControlFlow) {", """    fn on_user_event(&mut self, event: UserEvent, control_flow: &mut ControlFlow) {
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
            UserEvent::Popup { url } => {
                if !url.is_empty() {
                    let _ = self.new_tab(Some(url), false, false);
                }
            }
        }
    }
""")

# ----------------------------------------------------------------------
# 3. Messages de l'interface : vues optionnelles + sauvegardes différées
# ----------------------------------------------------------------------
sub("""            "close_tab" => {
                let _ = self.close_tab(tab_target, true);
                self.save_all();
            }
            "close_active" => {
                let id = self.active_id();
                let _ = self.close_tab(id, true);
                self.save_all();
            }""", """            "close_tab" => {
                let _ = self.close_tab(tab_target, true);
                self.request_save();
            }
            "close_active" => {
                let id = self.active_id();
                let _ = self.close_tab(id, true);
                self.request_save();
            }""")

sub("""                for id in others {
                    let _ = self.close_tab(id, false);
                }
                self.set_active(keep);
                self.save_all();""", """                for id in others {
                    let _ = self.close_tab(id, false);
                }
                self.set_active(keep);
                self.request_save();""")

sub("""            "reload_tab" => {
                if let Some(t) = self.tab(tab_target) {
                    let _ = t.webview.reload();
                }
            }""", """            "reload_tab" => {
                if let Some(view) = self.tab(tab_target).and_then(|t| t.view.as_ref()) {
                    let _ = view.reload();
                }
            }""")

sub("""                let url = self
                    .tab(tab_target)
                    .map(|t| t.url.clone())
                    .unwrap_or_default();
                if !url.is_empty() {
                    platform::set_clipboard_text(&url);
                }""", """                let url = self
                    .tab(tab_target)
                    .map(|t| t.url.clone())
                    .unwrap_or_default();
                if !url.is_empty() {
                    platform::set_clipboard_text(&url);
                }
                self.request_sync();""")

sub("""            "blocked" => {
                // Une redirection publicitaire a été bloquée : on le signale brièvement.
                if let Some(tab) = self.active_tab() {
                    let _ = tab.webview.evaluate_script(
                        "try{console.debug('[Nova] redirection publicitaire bloquée');}catch(e){}",
                    );
                }
            }""", """            "blocked" => {
                // Une redirection publicitaire a été bloquée : simple compteur,
                // affiché dans les paramètres.
                self.blocked = self.blocked.saturating_add(1);
            }""")

sub("""            "back" => {
                if let Some(t) = self.active_tab() {
                    let _ = t.webview.go_back();
                }
            }
            "forward" => {
                if let Some(t) = self.active_tab() {
                    let _ = t.webview.go_forward();
                }
            }
            "reload" => {
                if let Some(t) = self.active_tab() {
                    let _ = t.webview.reload();
                }
            }
            "stop" => {
                if let Some(t) = self.active_tab() {
                    platform::stop_webview(&t.webview);
                    let id = t.id;
                    if let Some(tab) = self.tab_mut(id) {
                        tab.loading = false;
                    }
                    self.sync();
                }
            }""", """            "back" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.go_back();
                }
            }
            "forward" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.go_forward();
                }
            }
            "reload" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.reload();
                }
            }
            "stop" => {
                let id = self.active_id();
                if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {
                    platform::stop_webview(view);
                }
                if let Some(tab) = self.tab_mut(id) {
                    tab.loading = false;
                }
                self.request_sync();
            }""")

sub("""            "devtools" => {
                if let Some(t) = self.active_tab() {
                    if t.webview.is_devtools_open() {
                        t.webview.close_devtools();
                    } else {
                        t.webview.open_devtools();
                    }
                }
            }
            "find" => self.find_in_page(),
            "downloads" => {
                if let Some(t) = self.active_tab() {
                    let _ = t.webview.evaluate_script(""", """            "devtools" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                }
            }
            "find" => self.find_in_page(),
            "downloads" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.evaluate_script(""")

# ----------------------------------------------------------------------
# 4. Les autres appels `self.sync()` deviennent des demandes regroupées
# ----------------------------------------------------------------------
src = src.replace("self.sync()", "self.request_sync()")
# `save_all` ponctuel -> sauvegarde différée
src = src.replace("""            "pin_tab" | "unpin_tab" => {
                let pinned = name == "pin_tab";
                if let Some(t) = self.tab_mut(tab_target) {
                    t.pinned = pinned;
                }
                self.request_save();
                self.request_sync();
            }""", """            "pin_tab" | "unpin_tab" => {
                let pinned = name == "pin_tab";
                if let Some(t) = self.tab_mut(tab_target) {
                    t.pinned = pinned;
                }
                self.request_save();
                self.request_sync();
            }""")
src = src.replace("""            "new_tab" => {
                let url = cmd.get("url").and_then(Value::as_str).map(str::to_string);
                let _ = self.new_tab(url, false, false);
                self.save_all();
            }""", """            "new_tab" => {
                let url = cmd.get("url").and_then(Value::as_str).map(str::to_string);
                let _ = self.new_tab(url, false, false);
                self.request_save();
            }""")

# ----------------------------------------------------------------------
# 5. Boucle d'événements : échéances de repaint et d'écriture disque
# ----------------------------------------------------------------------
sub("""            Event::UserEvent(user_event) => state.on_user_event(user_event, control_flow),
            Event::LoopDestroyed => state.save_all(),
            _ => {}
        }
    });""", """            Event::NewEvents(StartCause::ResumeTimeReached { .. }) => state.on_tick(),
            Event::UserEvent(user_event) => state.on_user_event(user_event, control_flow),
            Event::LoopDestroyed => state.save_all(),
            _ => {}
        }

        // Tao réinitialise `ControlFlow` à chaque itération : on reprogramme
        // l'échéance de repaint / de sauvegarde si elle existe.
        match state.next_deadline() {
            Some(deadline) => *control_flow = ControlFlow::WaitUntil(deadline),
            None => *control_flow = ControlFlow::Wait,
        }
    });""")

sub("""                WindowEvent::Focused(true) => state.sync(),""",
    """                WindowEvent::Focused(true) => state.request_sync(),""")

PATH.write_text(src, encoding="utf-8")
print("main.rs : seconde série de correctifs appliquée")
