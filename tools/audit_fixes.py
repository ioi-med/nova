#!/usr/bin/env python3
"""Correctifs issus de l'audit de code (bugs confirmés par lecture et par tests)."""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def save(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def sub(text, old, new, rel="?"):
    if old not in text:
        raise SystemExit(f"motif introuvable dans {rel} :\n{old[:400]}")
    return text.replace(old, new, 1)


def swap(text, old, new, rel="?"):
    """Remplacement multiple (toutes les occurrences)."""
    if old not in text:
        raise SystemExit(f"motif introuvable dans {rel} :\n{old[:400]}")
    return text.replace(old, new)


# ======================================================================
# ui.rs : brancher la nouvelle page d'historique
# ======================================================================
ui = load("src/ui.rs")
ui = sub(ui, """pub const SETTINGS: &str = include_str!("../assets/ui/settings.html");""",
         """pub const SETTINGS: &str = include_str!("../assets/ui/settings.html");
pub const HISTORY: &str = include_str!("../assets/ui/history.html");""", "src/ui.rs")
ui = sub(ui, """pub fn internal_page(url: &str) -> &'static str {
    match url {
        "nova://settings" => SETTINGS,
        _ => NEWTAB,
    }
}""", """pub fn internal_page(url: &str) -> &'static str {
    match url {
        "nova://settings" => SETTINGS,
        "nova://history" => HISTORY,
        _ => NEWTAB,
    }
}""", "src/ui.rs")
save("src/ui.rs", ui)

# ======================================================================
# urls.rs : port dans la barre d'adresse, casse de l'hôte, alias
# ======================================================================
u = load("src/urls.rs")
u = sub(u, """    // 5. Hôte sans schéma : on tente le nom de domaine, puis on retombe sur la recherche.
    let host_part = s.split(['/', '?', '#']).next().unwrap_or(s);
    if is_local_host(host_part) {
        return Some(Target::Url(format!("http://{s}")));
    }
    if accel::looks_like_host(host_part) {
        return Some(Target::Url(format!("https://{s}")));
    }""",
"""    // 5. Hôte sans schéma : on tente le nom de domaine, puis on retombe sur la recherche.
    let host_part = s.split(['/', '?', '#']).next().unwrap_or(s);
    if is_local_host(host_part) {
        return Some(Target::Url(format!("http://{s}")));
    }
    // « github.com:8080 » doit être ouvert, pas recherché : le port est retiré
    // pour tester la forme du nom d'hôte, mais conservé dans l'URL finale.
    if accel::looks_like_host(strip_port(host_part)) {
        return Some(Target::Url(format!("https://{s}")));
    }""", "src/urls.rs")

u = sub(u, """/// `localhost`, `127.0.0.1`, `192.168.1.10`, `[::1]`, `mon-pc:8080`…""",
"""/// Retire un éventuel « :port » final (« github.com:8080 » -> « github.com »).
fn strip_port(host: &str) -> &str {
    match host.rsplit_once(':') {
        Some((head, port)) if !head.is_empty() && port.parse::<u16>().is_ok() => head,
        _ => host,
    }
}

/// `localhost`, `127.0.0.1`, `192.168.1.10`, `[::1]`, `mon-pc:8080`…""", "src/urls.rs")

u = sub(u, """fn normalize_internal(value: &str) -> String {
    match value {
        "nova://newtab" | "nova://nouvelonglet" | "nova://home" => "nova://newtab".into(),
        "nova://settings" | "nova://parametres" => "nova://settings".into(),
        "nova://history" | "nova://historique" => "nova://history".into(),
        "nova://about" | "nova://apropos" => "nova://about".into(),
        other => other.to_string(),
    }
}""", """fn normalize_internal(value: &str) -> String {
    match value {
        "nova://newtab" | "nova://nouvelonglet" | "nova://home" => "nova://newtab".into(),
        "nova://settings" | "nova://parametres" => "nova://settings".into(),
        "nova://history" | "nova://historique" => "nova://history".into(),
        // « À propos » vit dans la page Paramètres : on y renvoie directement
        // plutôt que d'annoncer une page qui n'existe pas.
        "nova://about" | "nova://apropos" => "nova://settings".into(),
        other => other.to_string(),
    }
}""", "src/urls.rs")

# split_display : l'hôte est comparé en ignorant la casse
u = sub(u, """    let host = accel::host_of(url);
    if host.is_empty() {
        return (url.to_string(), String::new());
    }
    match url.find(&host) {
        Some(idx) => {
            let rest = url[idx + host.len()..].to_string();
            let rest = if rest == "/" { String::new() } else { rest };
            (host, rest)
        }
        None => (host, String::new()),
    }
}""", """    let host = accel::host_of(url);
    if host.is_empty() {
        return (url.to_string(), String::new());
    }
    // `host_of` renvoie l'hôte en minuscules : on cherche donc sa position sur
    // une copie minusculée de l'URL (« https://GitHub.com/PaTh » ne perdait
    // auparavant tout son chemin). `to_ascii_lowercase` préserve les longueurs
    // et les frontières de caractères, l'index reste donc valide.
    match url.to_ascii_lowercase().find(&host) {
        Some(idx) => {
            let rest = url[idx + host.len()..].to_string();
            let rest = if rest == "/" { String::new() } else { rest };
            (host, rest)
        }
        None => (host, String::new()),
    }
}""", "src/urls.rs")

# tests supplémentaires
u = sub(u, """    #[test]
    fn secure_and_display() {""", """    #[test]
    fn resolve_hotes_avec_port() {
        let g = by_id("google");
        assert_eq!(
            resolve("github.com:8080", g),
            Some(Target::Url("https://github.com:8080".into()))
        );
        assert_eq!(
            resolve("gitlab.example.org:8443/wiki", g),
            Some(Target::Url("https://gitlab.example.org:8443/wiki".into()))
        );
        // Un domaine internationalisé (punycode) doit être ouvert, pas recherché.
        assert_eq!(
            resolve("exemple.xn--p1ai", g),
            Some(Target::Url("https://exemple.xn--p1ai".into()))
        );
        // Un texte libre reste une recherche.
        assert!(matches!(resolve("intel i5 13600k", g), Some(Target::Url(u)) if u.contains("search")));
    }

    #[test]
    fn display_garde_le_chemin() {
        assert_eq!(
            split_display("https://GitHub.com/PaTh/À-nouveau"),
            ("github.com".into(), "/PaTh/À-nouveau".into())
        );
        assert_eq!(
            split_display("http://EXAMPLE.COM"),
            ("example.com".into(), String::new())
        );
    }

    #[test]
    fn alias_internes() {
        let g = by_id("google");
        assert_eq!(
            resolve("nova://apropos", g),
            Some(Target::Internal("nova://settings".into()))
        );
        assert_eq!(
            resolve("nova://historique", g),
            Some(Target::Internal("nova://history".into()))
        );
    }

    #[test]
    fn secure_and_display() {""", "src/urls.rs")

u = sub(u, """    #[test]
    fn secure_and_display() {
        assert!(is_secure("https://example.com"));
        assert!(!is_secure("http://example.com"));
        assert_eq!(split_display("https://example.com/a/b"), ("example.com".into(), "/a/b".into()));
    }""", """    #[test]
    fn secure_and_display() {
        assert!(is_secure("https://example.com"));
        assert!(!is_secure("http://example.com"));
        assert_eq!(split_display("https://example.com/a/b"), ("example.com".into(), "/a/b".into()));
    }

    #[test]
    fn canonical_et_comparaison() {
        assert_eq!(canonical("https://a.fr/x#ancre"), "https://a.fr/x");
        assert_eq!(canonical("https://a.fr/x/"), "https://a.fr/x");
        assert!(canon_eq("https://a.fr/x#ancre", "https://a.fr/x"));
        assert!(canon_eq("https://a.fr/x/", "https://a.fr/x"));
        assert!(!canon_eq("https://a.fr/y", "https://a.fr/x"));
        // Une URL trop courte n'est pas rognée de travers.
        assert!(canon_eq("https://a/", "https://a/"));
    }""", "src/urls.rs")
save("src/urls.rs", u)

# ======================================================================
# config.rs : compteur de révision de l'historique
# ======================================================================
c = load("src/config.rs")
c = sub(c, """#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct History {
    pub entries: Vec<HistoryEntry>,
}""", """#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct History {
    pub entries: Vec<HistoryEntry>,
    /// Compteur incrémenté à chaque modification : l'interface s'en sert pour
    /// savoir si la liste affichée est encore valable. (L'ancienne signature
    /// était calculée à partir de la dernière entrée, ce qui ne changeait ni
    /// lors d'une revisite ni lors d'un renommage : le panneau restait figé.)
    #[serde(skip)]
    revision: u64,
}""", "src/config.rs")

c = swap(c, """                entry.visits = entry.visits.saturating_add(1);
                entry.ts = Self::now();
                if !title.is_empty() && entry.title != title {
                    entry.title = title.to_string();
                }
                return;""", """                entry.visits = entry.visits.saturating_add(1);
                entry.ts = Self::now();
                if !title.is_empty() && entry.title != title {
                    entry.title = title.to_string();
                }
                self.revision = self.revision.wrapping_add(1);
                return;""", "src/config.rs")

c = sub(c, """            entry.visits = entry.visits.saturating_add(1);
            entry.ts = Self::now();
            if !title.is_empty() {
                entry.title = title.to_string();
            }
            return;
        }""", """            entry.visits = entry.visits.saturating_add(1);
            entry.ts = Self::now();
            if !title.is_empty() {
                entry.title = title.to_string();
            }
            self.revision = self.revision.wrapping_add(1);
            return;
        }""", "src/config.rs")

c = sub(c, """        if self.entries.len() > 2000 {
            self.entries.sort_by(|a, b| b.ts.cmp(&a.ts));
            self.entries.truncate(1500);
        }
    }""", """        if self.entries.len() > 2000 {
            self.entries.sort_by(|a, b| b.ts.cmp(&a.ts));
            self.entries.truncate(1500);
        }
        self.revision = self.revision.wrapping_add(1);
    }""", "src/config.rs")

c = sub(c, """        if let Some(entry) = self.entries.iter_mut().find(|e| e.url == url) {
            if entry.title != title {
                entry.title = title.to_string();
            }
            return;
        }""", """        if let Some(entry) = self.entries.iter_mut().find(|e| e.url == url) {
            if entry.title != title {
                entry.title = title.to_string();
                self.revision = self.revision.wrapping_add(1);
            }
            return;
        }""", "src/config.rs")

c = sub(c, """        {
            entry.title = title.to_string();
        }
    }

    pub fn remove(&mut self, url: &str) {""", """        {
            if entry.title != title {
                entry.title = title.to_string();
                self.revision = self.revision.wrapping_add(1);
            }
        }
    }

    pub fn remove(&mut self, url: &str) {""", "src/config.rs")

c = sub(c, """        let direct = url.to_string();
        let key = crate::urls::canonical(url);
        self.entries
            .retain(|e| e.url != direct && !crate::urls::canon_eq(&e.url, &key));
    }""", """        let direct = url.to_string();
        let key = crate::urls::canonical(url);
        let before = self.entries.len();
        self.entries
            .retain(|e| e.url != direct && !crate::urls::canon_eq(&e.url, &key));
        if self.entries.len() != before {
            self.revision = self.revision.wrapping_add(1);
        }
    }""", "src/config.rs")

c = sub(c, """    pub fn clear(&mut self) {
        self.entries.clear();
    }""", """    pub fn clear(&mut self) {
        if !self.entries.is_empty() {
            self.entries.clear();
            self.revision = self.revision.wrapping_add(1);
        }
    }""", "src/config.rs")

c = sub(c, """    /// Signature bon marché de l'historique : l'interface ne reconstruit la
    /// liste que lorsque cette valeur change.
    #[allow(dead_code)]
    pub fn revision(&self) -> u64 {
        let last = self.entries.last().map(|e| e.ts).unwrap_or(0);
        (self.entries.len() as u64).wrapping_mul(0x100_0000_01b3) ^ last
    }""", """    /// Version courante de l'historique : l'interface ne reconstruit la liste
    /// que lorsque cette valeur change.
    pub fn revision(&self) -> u64 {
        self.revision
    }""", "src/config.rs")
save("src/config.rs", c)

# ======================================================================
# blocker.rs : toutes les règles sont utilisées (plus de limite implicite)
# ======================================================================
b = load("src/blocker.rs")
b = sub(b, """    pub fn resolver_rules(&self, max_hosts: usize) -> String {
        let mut arg = String::from("--host-resolver-rules=");
        let mut first = true;
        for (domain, _) in self.domains.iter().take(max_hosts) {""",
"""    pub fn resolver_rules(&self, max_hosts: usize) -> String {
        let mut arg = String::from("--host-resolver-rules=");
        let mut first = true;
        // `max_hosts` doit couvrir toute la liste : une limite trop basse
        // désactiverait silencieusement une partie du filtrage.
        for (domain, _) in self.domains.iter().take(max_hosts) {""", "src/blocker.rs")
save("src/blocker.rs", b)

# ======================================================================
# main.rs
# ======================================================================
m = load("src/main.rs")

# 1) toutes les règles de blocage sont transmises
m = sub(m, "args.push_str(&blocker.resolver_rules(160));",
        "args.push_str(&blocker.resolver_rules(blocker.len()));", "src/main.rs")

# 2) helper d'accès à la vue active (crée le moteur d'un onglet en veille)
m = sub(m, """    fn prefs(&self) -> platform::WebPrefs {""",
"""    /// Exécute une action sur la vue de l'onglet actif, en la créant au besoin :
    /// un onglet restauré n'a pas encore de moteur.
    fn with_active_view<T>(&mut self, action: impl FnOnce(&WebView) -> T) -> Option<T> {
        let id = self.active_id();
        if id == 0 || !self.ensure_view(id) {
            return None;
        }
        self.tab(id).and_then(|t| t.view.as_ref()).map(action)
    }

    fn prefs(&self) -> platform::WebPrefs {""", "src/main.rs")

# 3) raccourcis : ils agissent même sur un onglet en veille
m = sub(m, """    fn hotkey(&mut self, key: &str) {
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

        match key {""", """    fn hotkey(&mut self, key: &str) {
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

        match key {""", "src/main.rs")

# 4) Alt+Entrée : moteur utilisé pour cette recherche uniquement
m = sub(m, """        let engine_id = if alt { next_engine(&engine_id) } else { engine_id };
        let engine = engines::by_id(&engine_id);
        let Some(target) = urls::resolve(text, engine) else {
            return;
        };
        self.go(id, target, Some(engine_id));""",
"""        let base_engine = engine_id.clone();
        let engine_id = if alt { next_engine(&base_engine) } else { engine_id };
        let engine = engines::by_id(&engine_id);
        let Some(target) = urls::resolve(text, engine) else {
            return;
        };
        // Alt+Entrée est un choix ponctuel : le moteur de l'onglet ne change pas.
        let target_engine = if alt { None } else { Some(engine_id) };
        self.go(id, target, target_engine);""", "src/main.rs")

# 5) état « riche » aussi pour la page d'historique
m = sub(m, """    fn flush_ui(&mut self) {
        let state = self.state_json(self.history_open);""",
"""    fn flush_ui(&mut self) {
        // La page interne d'historique a besoin de la liste complète, même
        // lorsque le panneau latéral est fermé.
        let history_page = self
            .active_tab()
            .map(|t| t.internal && t.url == "nova://history")
            .unwrap_or(false);
        let state = self.state_json(self.history_open || history_page);""", "src/main.rs")

# 6) identifiant d'onglet fiable pour les messages venant des surfaces d'interface
m = sub(m, """        let tab_target = {
            let id = cmd.get("id").and_then(Value::as_u64).unwrap_or(0) as u32;
            if id == 0 {
                from_tab
            } else {
                id
            }
        };""",
"""        // Les vues d'interface (barre latérale, barre d'adresse) n'ont pas
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
        };""", "src/main.rs")

# 7) les commandes de navigation utilisent le helper
navigation_block = """            "back" => {
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
            }"""
new_navigation_block = """            "back" => {
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
                self.with_active_view(|view| platform::stop_webview(view));
                if let Some(tab) = self.tab_mut(id) {
                    tab.loading = false;
                }
                self.request_sync();
            }"""
m = sub(m, navigation_block, new_navigation_block, "src/main.rs")

m = sub(m, """            "devtools" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                }
            }
            "find" => self.find_in_page(),""",
"""            "devtools" => {
                self.with_active_view(|view| {
                    if view.is_devtools_open() {
                        view.close_devtools();
                    } else {
                        view.open_devtools();
                    }
                });
            }
            "find" => self.find_in_page(),""", "src/main.rs")

m = sub(m, """            "downloads" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.evaluate_script(""",
"""            "downloads" => {
                self.with_active_view(|view| {
                    let _ = view.evaluate_script(""", "src/main.rs")
m = sub(m, """                        "alert('Les téléchargements sont gérés par le moteur WebView2 : ils s\\\\'enregistrent dans votre dossier Téléchargements.');",
                    );
                }
            }""",
"""                        "alert('Les téléchargements sont gérés par le moteur WebView2 : ils s\\\\'enregistrent dans votre dossier Téléchargements.');",
                    );
                });
            }""", "src/main.rs")

m = sub(m, """            "clear_data" => {
                if let Some(view) = self.active_tab().and_then(|t| t.view.as_ref()) {
                    let _ = view.clear_all_browsing_data();
                }
                self.request_sync();
            }""",
"""            "clear_data" => {
                self.with_active_view(|view| {
                    let _ = view.clear_all_browsing_data();
                });
                self.request_sync();
            }""", "src/main.rs")

# 8) titre initial d'un onglet : l'hôte plutôt que « Nouvel onglet »
m = sub(m, """        let title = urls::display_title(&web_url).unwrap_or("Nouvel onglet").to_string();""",
"""        // Avant l'arrivée du vrai titre, afficher l'hôte est plus informatif
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
        };""", "src/main.rs")

# 9) find_in_page via le helper
m = sub(m, """    fn find_in_page(&mut self) {
        let id = self.active_id();
        if let Some(view) = self.tab(id).and_then(|t| t.view.as_ref()) {""",
"""    fn find_in_page(&mut self) {
        self.with_active_view(|view| {""", "src/main.rs")
m = sub(m, """                 if (!f) { window.getSelection().removeAllRanges(); window.find(q, true, true, true, false, false, false); } } })();",
            );
        }
    }""",
"""                 if (!f) { window.getSelection().removeAllRanges(); window.find(q, true, true, true, false, false, false); } } })();",
            );
        });
    }""", "src/main.rs")

save("src/main.rs", m)
print("correctifs Rust appliqués")
