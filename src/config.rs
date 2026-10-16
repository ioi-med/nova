//! Configuration persistante, historique et session de Nova.
//!
//! Tout est stocké dans `%APPDATA%\Nova\` (Windows) ou l'équivalent XDG :
//!   * `config.json`    — réglages
//!   * `history.json`   — historique de navigation
//!   * `session.json`   — onglets ouverts / onglets fermés

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Horodatage lisible (« 2026-10-16 14:32:07 ») à partir d'un temps Unix.
///
/// Volontairement sans dépendance : quelques divisions suffisent, et le calcul
/// est ensuite vérifié par un test sur des dates connues.
pub fn iso_time(ts: u64) -> String {
    let days = (ts / 86_400) as i64;
    let secs = ts % 86_400;
    // Algorithme « civil_from_days » (prolepse grégorienne).
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02} {:02}:{:02}:{:02}",
        secs / 3600,
        (secs % 3600) / 60,
        secs % 60
    )
}

/// Nombre maximal de favoris (apps) conservés. Un import en apporte facilement
/// plusieurs dizaines : la limite n'est là que pour éviter une liste
/// inutilisable.
pub const MAX_FAVORITES: usize = 240;

/// Nombre de favoris affichés dans la barre latérale, sous les onglets.
/// Au-delà, la liste des onglets deviendrait trop courte ; les autres favoris
/// restent visibles dans la page Nouvel onglet.
pub const SIDEBAR_APPS: usize = 24;

/// Une application / un site mis en favori, affiché dans la barre latérale.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Favorite {
    pub title: String,
    pub url: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Moteur de recherche par défaut (`google`, `brave`, `ecosia`, …).
    pub engine: String,
    /// `dark`, `light` ou `system`.
    pub theme: String,
    /// L'assistant de premier lancement a-t-il déjà été joué ?
    pub onboarding_done: bool,
    /// Bloque les navigations vers les régisseurs publicitaires connus et
    /// active le blocage DNS de la liste locale.
    pub block_trackers: bool,
    /// Restaure les onglets à l'ouverture suivante.
    pub restore_session: bool,
    /// Largeur de la barre latérale (px logiques).
    pub sidebar_width: f64,
    /// Page ouverte au démarrage / pour un nouvel onglet.
    pub homepage: String,
    /// Ouvre uniquement les favoris épinglés au démarrage.
    pub start_with_pinned: bool,
    /// Affiche le menu contextuel natif du moteur de rendu.
    pub native_context_menus: bool,
    /// Zoom par défaut des pages (1.0 = 100 %).
    pub zoom: f64,
    /// Mémorisation des mots de passe et des formulaires (profil local).
    pub passwords: bool,
    /// Couleur de fond de l'interface (`#rrggbb`), vide = thème standard.
    pub ui_bg: String,
    /// Applications / sites favoris, affichés dans la barre latérale.
    pub favorites: Vec<Favorite>,
    /// Relit les navigateurs installés au démarrage et importe les données
    /// nouvelles (favoris et historique). Sans effet une fois tout importé :
    /// un import ne crée jamais de doublon.
    pub auto_import: bool,
    /// Valeurs (captures, Game DVR) relevées avant que Nova ne les coupe, pour
    /// pouvoir les remettre exactement à l'identique si l'utilisateur décoche.
    #[serde(default)]
    pub dvr_prev: Option<[u32; 2]>,

    /// Coupe le message de Windows qui réclame l'overlay de jeu (Game Bar).
    /// lien » : Nova accepte les protocoles de la Xbox Game Bar pour le compte
    /// courant (`HKCU\Software\Classes`) et les ignore. Sans effet si la
    /// Game Bar est réellement installée.
    pub silence_game_overlay: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            engine: "google".into(),
            theme: "dark".into(),
            onboarding_done: false,
            block_trackers: true,
            restore_session: true,
            sidebar_width: 272.0,
            homepage: "nova://newtab".into(),
            start_with_pinned: false,
            native_context_menus: false,
            zoom: 1.0,
            passwords: true,
            ui_bg: String::new(),
            favorites: Vec::new(),
            auto_import: true,
            silence_game_overlay: true,
            dvr_prev: None,
        }
    }
}

impl Config {
    /// Applique un correctif JSON partiel (utilisé par la page Paramètres).
    pub fn patch(&mut self, patch: serde_json::Value) {
        if let Ok(mut value) = serde_json::to_value(self.clone()) {
            if let (Some(dst), Some(src)) = (value.as_object_mut(), patch.as_object()) {
                for (k, v) in src {
                    dst.insert(k.clone(), v.clone());
                }
            }
            if let Ok(updated) = serde_json::from_value::<Config>(value) {
                *self = updated;
            }
        }
        self.sanitize();
    }

    /// Garde les valeurs dans des bornes raisonnables.
    /// Vrai si la couleur de fond fournie est exploitable (`#rrggbb`).
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
        }
        self.sidebar_width = self.sidebar_width.clamp(220.0, 420.0);
        if !(0.25..=5.0).contains(&self.zoom) {
            self.zoom = 1.0;
        }
        if !matches!(self.theme.as_str(), "dark" | "light" | "system") {
            self.theme = "dark".into();
        }
        // Une page d'accueil que le moteur ne peut pas charger (protocole du
        // système, adresse corrompue) est remplacée : sinon chaque nouvel
        // onglet demanderait l'ouverture du protocole à Windows.
        if !loadable_url(&self.homepage) {
            self.homepage = "nova://newtab".into();
        }
    }

    pub fn dark(&self) -> bool {
        match self.theme.as_str() {
            "light" => false,
            "system" => !crate::platform::system_prefers_dark(),
            _ => true,
        }
    }
}

/// Répertoire de données de Nova, créé si nécessaire.
pub fn data_dir() -> PathBuf {
    let dir = dirs::config_dir()
        .or_else(dirs::data_dir)
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Nova");
    let _ = std::fs::create_dir_all(&dir);
    dir
}

/// Répertoire de profil du moteur de rendu (cookies, cache, stockage).
pub fn profile_dir() -> PathBuf {
    let dir = dirs::data_local_dir()
        .unwrap_or_else(data_dir)
        .join("Nova")
        .join("WebView2");
    let _ = std::fs::create_dir_all(&dir);
    dir
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Option<T> {
    let raw = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&raw).ok()
}

/// `pretty = true` pour les fichiers que l'utilisateur peut ouvrir à la main
/// (config.json), `false` pour les fichiers volumineux et écrits souvent.
fn write_json_compact<T: Serialize>(path: &Path, value: &T, pretty: bool) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let json = if pretty {
        serde_json::to_string_pretty(value)
    } else {
        serde_json::to_string(value)
    }
    .unwrap_or_else(|_| "{}".into());
    // Écriture atomique : fichier temporaire puis renommage.
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, json.as_bytes())?;
    std::fs::rename(&tmp, path)
}

impl Config {
    pub fn load(dir: &Path) -> Self {
        let mut cfg: Self = read_json(&dir.join("config.json")).unwrap_or_default();
        cfg.sanitize();
        cfg
    }

    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("config.json"), self, true);
    }
}

/* ------------------------------------------------------------------ */
/* Historique                                                         */
/* ------------------------------------------------------------------ */

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HistoryEntry {
    pub url: String,
    pub title: String,
    /// Horodatage Unix (secondes).
    pub ts: u64,
    pub visits: u32,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct History {
    pub entries: Vec<HistoryEntry>,
    /// Compteur incrémenté à chaque modification : l'interface s'en sert pour
    /// savoir si la liste affichée est encore valable. (L'ancienne signature
    /// était calculée à partir de la dernière entrée, ce qui ne changeait ni
    /// lors d'une revisite ni lors d'un renommage : le panneau restait figé.)
    #[serde(skip)]
    revision: u64,
}

impl History {
    pub fn load(dir: &Path) -> Self {
        read_json(&dir.join("history.json")).unwrap_or_default()
    }

    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("history.json"), self, false);
    }

    pub fn now() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }

    /// Enregistre une visite (les URL internes sont ignorées).
    ///
    /// La comparaison se fait sans allocation : c'est le chemin chaud de la
    /// navigation, appelé à chaque fin de chargement.
    pub fn visit(&mut self, url: &str, title: &str) {
        if url.is_empty() || url.starts_with("nova://") || url.starts_with("about:") {
            return;
        }
        if !url.ends_with('/') && url.find('#').is_none() {
            if let Some(entry) = self.entries.iter_mut().find(|e| e.url == url) {
                entry.visits = entry.visits.saturating_add(1);
                entry.ts = Self::now();
                if !title.is_empty() && entry.title != title {
                    entry.title = title.to_string();
                }
                self.revision = self.revision.wrapping_add(1);
                return;
            }
        }
        let key = crate::urls::canonical(url);
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canon_eq(&e.url, &key))
        {
            entry.visits = entry.visits.saturating_add(1);
            entry.ts = Self::now();
            if !title.is_empty() {
                entry.title = title.to_string();
            }
            self.revision = self.revision.wrapping_add(1);
            return;
        }
        self.entries.push(HistoryEntry {
            url: url.to_string(),
            title: title.to_string(),
            ts: Self::now(),
            visits: 1,
        });
        if self.entries.len() > 2000 {
            self.entries.sort_by_key(|e| std::cmp::Reverse(e.ts));
            self.entries.truncate(1500);
        }
        self.revision = self.revision.wrapping_add(1);
    }

    /// Dernières visites, plus récentes d'abord.
    /// Insère une visite venue d'un autre navigateur.
    ///
    /// Contrairement à [`History::visit`], une URL déjà connue **ne voit pas**
    /// son compteur grimper : un import répété (import automatique au
    /// démarrage) doit donner exactement le même résultat. Retourne `true`
    /// quand l'entrée est nouvelle.
    pub fn import_visit(&mut self, url: &str, title: &str, ts: u64) -> bool {
        if url.is_empty() {
            return false;
        }
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canon_eq(url, &e.url))
        {
            // Un titre manquant côté Nova peut être complété par la source.
            if entry.title.is_empty() && !title.is_empty() {
                entry.title = title.to_string();
                self.revision = self.revision.wrapping_add(1);
            }
            return false;
        }
        self.entries.push(HistoryEntry {
            url: url.to_string(),
            title: title.to_string(),
            ts,
            visits: 1,
        });
        self.revision = self.revision.wrapping_add(1);
        true
    }

    /// Borne la liste après un import massif (même règle que [`History::visit`]).
    pub fn trim(&mut self) {
        if self.entries.len() > 2000 {
            self.entries.sort_by_key(|e| std::cmp::Reverse(e.ts));
            self.entries.truncate(1500);
            self.revision = self.revision.wrapping_add(1);
        }
    }

    pub fn recent(&self, count: usize) -> Vec<&HistoryEntry> {
        let mut list: Vec<&HistoryEntry> = self.entries.iter().collect();
        list.sort_by_key(|e| std::cmp::Reverse(e.ts));
        list.truncate(count);
        list
    }

    /// Met à jour le titre d'une entrée sans compter une nouvelle visite
    /// (le titre d'une page arrive souvent après la fin du chargement).
    pub fn rename(&mut self, url: &str, title: &str) {
        if title.is_empty() {
            return;
        }
        if let Some(entry) = self.entries.iter_mut().find(|e| e.url == url) {
            if entry.title != title {
                entry.title = title.to_string();
                self.revision = self.revision.wrapping_add(1);
            }
            return;
        }
        let key = crate::urls::canonical(url);
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canon_eq(&e.url, &key))
        {
            if entry.title != title {
                entry.title = title.to_string();
                self.revision = self.revision.wrapping_add(1);
            }
        }
    }

    pub fn remove(&mut self, url: &str) {
        let direct = url.to_string();
        let key = crate::urls::canonical(url);
        let before = self.entries.len();
        self.entries
            .retain(|e| e.url != direct && !crate::urls::canon_eq(&e.url, &key));
        if self.entries.len() != before {
            self.revision = self.revision.wrapping_add(1);
        }
    }

    /// Version courante de l'historique : l'interface ne reconstruit la liste
    /// que lorsque cette valeur change.
    pub fn revision(&self) -> u64 {
        self.revision
    }

    pub fn clear(&mut self) {
        if !self.entries.is_empty() {
            self.entries.clear();
            self.revision = self.revision.wrapping_add(1);
        }
    }
}

/* ------------------------------------------------------------------ */
/* Session                                                            */
/* ------------------------------------------------------------------ */

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SessionTab {
    pub url: String,
    #[serde(default)]
    pub title: String,
    #[serde(default)]
    pub pinned: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Session {
    pub tabs: Vec<SessionTab>,
    pub closed: Vec<SessionTab>,
}

/// Une URL qu'un onglet restauré peut réellement charger.
///
/// Sans ce filtre, une adresse comme `ms-gamingoverlay:` (protocole du système,
/// jamais ouvrable par un navigateur) resterait dans la session et **provoquerait
/// une demande à Windows à chaque démarrage** — c'est précisément la boîte de
/// dialogue « Obtenir une application pour ouvrir ce lien ».
pub fn loadable_url(url: &str) -> bool {
    match crate::urls::scheme_of(url) {
        Some(scheme) => matches!(scheme.as_str(), "http" | "https" | "nova" | "about" | "file"),
        None => false,
    }
}

impl Session {
    pub fn load(dir: &Path) -> Self {
        let mut session: Self = read_json(&dir.join("session.json")).unwrap_or_default();
        session.tabs.retain(|t| loadable_url(&t.url));
        session.closed.retain(|t| loadable_url(&t.url));
        session
    }

    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("session.json"), self, false);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// La couleur de fond part dans la feuille de style des pages : une valeur
    /// fantaisiste doit être refusée, jamais recopiée telle quelle.
    #[test]
    fn couleur_de_fond_validee() {
        assert!(Config::ui_bg_ok("#1b1b1f"));
        assert!(Config::ui_bg_ok("#FFFFFF"));
        assert!(!Config::ui_bg_ok("1b1b1f"));
        assert!(!Config::ui_bg_ok("#1b1b1"));
        assert!(!Config::ui_bg_ok("#1b1b1f;"));
        assert!(!Config::ui_bg_ok("#zzzzzz"));
        assert!(!Config::ui_bg_ok(""));

        let mut cfg = Config { ui_bg: "javascript:alert(1)".into(), ..Config::default() };
        cfg.sanitize();
        assert!(cfg.ui_bg.is_empty(), "une couleur invalide est effacée");
    }

    #[test]
    fn horodatage_lisible() {
        assert_eq!(iso_time(0), "1970-01-01 00:00:00");
        assert_eq!(iso_time(1_700_000_000), "2023-11-14 22:13:20");
        // Année bissextile et fin d'année.
        assert_eq!(iso_time(1_704_067_199), "2023-12-31 23:59:59");
        assert_eq!(iso_time(951_782_400), "2000-02-29 00:00:00");
    }

    #[test]
    fn session_sans_url_inchargeable() {
        let dir = std::env::temp_dir().join(format!("nova-session-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let cells = vec![
            SessionTab { url: "https://exemple.fr/".into(), title: "Bon".into(), pinned: false },
            SessionTab { url: "ms-gamingoverlay:".into(), title: "Overlay".into(), pinned: false },
            SessionTab { url: "nova://newtab".into(), title: "".into(), pinned: false },
            SessionTab { url: "n'importe quoi".into(), title: "".into(), pinned: false },
        ];
        let session = Session { tabs: cells.clone(), closed: cells };
        session.save(&dir);
        let relu = Session::load(&dir);
        let urls: Vec<&str> = relu.tabs.iter().map(|t| t.url.as_str()).collect();
        assert_eq!(urls, vec!["https://exemple.fr/", "nova://newtab"]);
        assert_eq!(relu.closed.len(), 2, "la liste des onglets fermés est filtrée aussi");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn favoris_nettoyes_et_relus() {
        let mut cfg = Config {
            favorites: vec![
                Favorite { title: "A".into(), url: "https://a.fr/".into() },
                Favorite { title: "vide".into(), url: "   ".into() },
            ],
            ..Config::default()
        };
        cfg.sanitize();
        assert_eq!(cfg.favorites.len(), 1, "une adresse vide est retirée");

        // Aller-retour JSON : c'est ce que fait `config.json`.
        let raw = serde_json::to_string(&cfg).unwrap();
        let back: Config = serde_json::from_str(&raw).unwrap();
        assert_eq!(back.favorites.len(), 1);
        assert_eq!(back.favorites[0].url, "https://a.fr/");
        assert_eq!(back.ui_bg, "");
    }

    #[test]
    fn liste_de_favoris_bornee() {
        let mut cfg = Config::default();
        for i in 0..(MAX_FAVORITES + 5) {
            cfg.favorites.push(Favorite {
                title: format!("site {i}"),
                url: format!("https://site{i}.fr/"),
            });
        }
        cfg.sanitize();
        assert_eq!(cfg.favorites.len(), MAX_FAVORITES);
    }

    /// Un `config.json` écrit par une version antérieure (sans ces champs)
    /// doit continuer à se charger.
    #[test]
    fn config_ancienne_relue() {
        let old = r#"{"engine":"brave","theme":"light","zoom":1.0}"#;
        let cfg: Config = serde_json::from_str(old).unwrap();
        assert_eq!(cfg.engine, "brave");
        assert!(cfg.ui_bg.is_empty());
        assert!(cfg.favorites.is_empty());
        assert_eq!(cfg.sidebar_width, 272.0);
    }
}
