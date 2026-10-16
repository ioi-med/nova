//! Import des données d'un autre navigateur : favoris et historique.
//!
//! Formats pris en charge, tous lus **sans dépendance externe** :
//!
//! | Source | Fichier | Contenu |
//! |---|---|---|
//! | Chrome, Edge, Brave, Vivaldi, Chromium, Opera, Ecosia… | `Bookmarks` (JSON) | favoris |
//! | idem | `History` (SQLite) | historique (URL, titre, date) |
//! | Firefox | `places.sqlite` (SQLite) | historique |
//! | tout navigateur | export HTML des favoris (`bookmarks.html`) | favoris |
//!
//! Les mots de passe et les cookies ne sont **pas** importables : ils sont
//! chiffrés avec la clé du système liée au compte utilisateur d'origine, et le
//! moteur de rendu de Nova (WebView2) possède son propre stockage. C'est dit
//! clairement dans l'interface plutôt que de proposer un import qui échouerait.

use std::path::{Path, PathBuf};

use crate::sqlread::{Db, Value};

/// Une visite à importer dans l'historique.
#[derive(Debug, Clone)]
pub struct Visit {
    pub url: String,
    pub title: String,
    /// Horodatage Unix (secondes).
    pub ts: u64,
}

/// Ce qu'un import a produit.
#[derive(Debug, Default)]
pub struct Data {
    /// Favoris (titre, URL).
    pub favorites: Vec<(String, String)>,
    pub visits: Vec<Visit>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    ChromiumBookmarks,
    ChromiumHistory,
    FirefoxPlaces,
}

impl Kind {
    pub fn label(self) -> &'static str {
        match self {
            Kind::ChromiumBookmarks => "favoris",
            Kind::ChromiumHistory => "historique",
            Kind::FirefoxPlaces => "historique",
        }
    }
}

/// Devine la catégorie d'un fichier d'après son nom (utilisé quand
/// l'utilisateur désigne lui-même le fichier à importer).
pub fn kind_of_path(path: &Path) -> Kind {
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_ascii_lowercase())
        .unwrap_or_default();
    if name.starts_with("places") {
        Kind::FirefoxPlaces
    } else if name == "history" || name.ends_with(".sqlite") || name.ends_with(".db") {
        Kind::ChromiumHistory
    } else {
        Kind::ChromiumBookmarks
    }
}

/// Une source détectée sur la machine.
#[derive(Debug, Clone)]
pub struct Source {
    /// Identifiant unique de la source (« google-chrome-default-hist »).
    pub id: String,
    /// Navigateur concerné (« Google Chrome »), pour le regroupement dans
    /// l'interface : c'est **l'application** que l'utilisateur choisit.
    pub app: String,
    /// Libellé précis, profil compris (« Google Chrome (Profile 1) »).
    pub name: String,
    pub kind: Kind,
    pub path: PathBuf,
}

impl Source {
    /// Clé de regroupement (identifiant stable du navigateur).
    pub fn app_id(&self) -> String {
        self.app.to_lowercase().replace(' ', "-")
    }
}

/// Nombre maximal d'entrées d'historique importées.
pub const MAX_VISITS: usize = 4000;
/// Nombre maximal de favoris importés d'un coup.
pub const MAX_FAVORITES: usize = 500;

/* ------------------------------------------------------------------ */
/* Favoris : export HTML (format Netscape, tous les navigateurs)       */
/* ------------------------------------------------------------------ */

/// Lit un export HTML de favoris. Analyse volontairement tolérante : on cherche
/// les balises `<A HREF="…">titre</A>` et on ignore le reste.
pub fn html_bookmarks(src: &str) -> Vec<(String, String)> {
    let lower = src.to_ascii_lowercase();
    let mut out: Vec<(String, String)> = Vec::new();

    let mut pos = 0;
    while let Some(found) = lower[pos..].find("<a ") {
        let start = pos + found;
        let Some(gt) = lower[start..].find('>') else { break };
        let tag = &src[start..start + gt];
        let tag_lower = &lower[start..start + gt];
        let end = lower[start..].find("</a>").map(|e| start + e);
        let title_raw = match end {
            Some(e) => &src[start + gt + 1..e],
            None => "",
        };
        pos = end.map(|e| e + 4).unwrap_or(start + gt + 1);

        let Some(href_at) = tag_lower.find("href=") else { continue };
        let after = tag[href_at + 5..].trim_start();
        let (quote, rest) = match after.chars().next() {
            Some(q @ ('"' | '\'')) => (Some(q), &after[1..]),
            _ => (None, after),
        };
        let value = match quote {
            Some(q) => rest.split(q).next().unwrap_or(""),
            None => rest
                .split(|c: char| c.is_whitespace() || c == '>')
                .next()
                .unwrap_or(""),
        };
        let url = decode_entities(value.trim());
        if !usable_url(&url) {
            continue;
        }
        let title = strip_tags(&decode_entities(title_raw)).trim().to_string();
        out.push((title, url));
    }
    dedupe(out, MAX_FAVORITES)
}

/* ------------------------------------------------------------------ */
/* Favoris : `Bookmarks` de la famille Chromium (JSON)                 */
/* ------------------------------------------------------------------ */

pub fn chromium_bookmarks(json: &str) -> Result<Vec<(String, String)>, String> {
    let root: serde_json::Value =
        serde_json::from_str(json).map_err(|e| format!("fichier illisible : {e}"))?;
    let mut out = Vec::new();
    if let Some(roots) = root.get("roots") {
        for key in ["bookmark_bar", "other", "synced", "mobile"] {
            if let Some(node) = roots.get(key) {
                walk_chromium(node, &mut out);
            }
        }
        // Certains profils n'ont que des dossiers nommés : on prend tout.
        if out.is_empty() {
            if let Some(map) = roots.as_object() {
                for (_, node) in map {
                    walk_chromium(node, &mut out);
                }
            }
        }
    }
    if out.is_empty() {
        return Err("aucun favori trouvé dans ce fichier".into());
    }
    Ok(dedupe(out, MAX_FAVORITES))
}

fn walk_chromium(node: &serde_json::Value, out: &mut Vec<(String, String)>) {
    let kind = node.get("type").and_then(|v| v.as_str()).unwrap_or("");
    if kind == "url" {
        let url = node.get("url").and_then(|v| v.as_str()).unwrap_or("");
        if usable_url(url) {
            let name = node.get("name").and_then(|v| v.as_str()).unwrap_or("");
            out.push((name.to_string(), url.to_string()));
        }
    }
    if let Some(children) = node.get("children").and_then(|v| v.as_array()) {
        for child in children {
            walk_chromium(child, out);
        }
    }
}

/* ------------------------------------------------------------------ */
/* Historique : `History` (Chromium) et `places.sqlite` (Firefox)      */
/* ------------------------------------------------------------------ */

/// Historique d'un profil Chromium.
///
/// Deux colonnes comptent : `url`, `title` et la date de dernière visite
/// (`last_visit_time`, en microsecondes depuis le 1er janvier 1601).
pub fn chromium_history(db: &Db) -> Result<Vec<Visit>, String> {
    let table = db
        .table_schema("urls")
        .ok_or("ce fichier n'est pas un historique Chromium (table « urls » absente)")?;
    let (Some(url_col), Some(date_col)) = (table.index_of("url"), table.index_of("last_visit_time"))
    else {
        return Err("colonnes attendues absentes de la table « urls »".into());
    };
    let title_col = table.index_of("title");

    let mut out = Vec::new();
    for row in db.rows(table.root) {
        let url = row.get(url_col).map(Value::text).unwrap_or_default();
        if !usable_url(&url) {
            continue;
        }
        let title = title_col
            .and_then(|c| row.get(c))
            .map(Value::text)
            .unwrap_or_default();
        let ts = chromium_time(row.get(date_col).map(Value::int).unwrap_or(0));
        out.push(Visit { url, title, ts });
    }
    Ok(keep_most_recent(out, MAX_VISITS))
}

/// Historique Firefox (`places.sqlite`, table `moz_places`,
/// `last_visit_date` en microsecondes depuis 1970).
pub fn firefox_places(db: &Db) -> Result<Vec<Visit>, String> {
    let table = db
        .table_schema("moz_places")
        .ok_or("ce fichier n'est pas un profil Firefox (table « moz_places » absente)")?;
    let (Some(url_col), Some(date_col)) = (table.index_of("url"), table.index_of("last_visit_date"))
    else {
        return Err("colonnes attendues absentes de la table « moz_places »".into());
    };
    let title_col = table.index_of("title");

    let mut out = Vec::new();
    for row in db.rows(table.root) {
        let url = row.get(url_col).map(Value::text).unwrap_or_default();
        if !usable_url(&url) {
            continue;
        }
        let title = title_col
            .and_then(|c| row.get(c))
            .map(Value::text)
            .unwrap_or_default();
        let ts = firefox_time(row.get(date_col).map(Value::int).unwrap_or(0));
        out.push(Visit { url, title, ts });
    }
    Ok(keep_most_recent(out, MAX_VISITS))
}

/// Microsecondes depuis 1601 -> secondes Unix.
pub fn chromium_time(us: i64) -> u64 {
    if us <= 0 {
        return 0;
    }
    let secs = us / 1_000_000 - 11_644_473_600;
    secs.max(0) as u64
}

/// Microsecondes depuis 1970 -> secondes Unix.
pub fn firefox_time(us: i64) -> u64 {
    if us <= 0 {
        return 0;
    }
    (us / 1_000_000).max(0) as u64
}

/* ------------------------------------------------------------------ */
/* Chargement                                                          */
/* ------------------------------------------------------------------ */

/// Charge un fichier choisi par l'utilisateur, en reconnaissant son format.
pub fn load_file(path: &Path) -> Result<Data, String> {
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();

    // Base SQLite ? (on ne lit que l'en-tête pour le savoir : un fichier de
    // favoris HTML peut peser plusieurs mégaoctets.)
    let mut magic = [0u8; 16];
    let is_sqlite = std::fs::File::open(path)
        .and_then(|mut file| std::io::Read::read_exact(&mut file, &mut magic))
        .map(|()| &magic == b"SQLite format 3\0")
        .unwrap_or(false);

    if is_sqlite {
        let db = Db::open(path)?;
        if let Ok(visits) = chromium_history(&db) {
            if !visits.is_empty() {
                return Ok(Data { favorites: Vec::new(), visits, notes: Vec::new() });
            }
        }
        let visits = firefox_places(&db)?;
        if visits.is_empty() {
            return Err("aucune visite lisible dans cette base".into());
        }
        return Ok(Data { favorites: Vec::new(), visits, notes: Vec::new() });
    }

    // JSON (Bookmarks de Chromium) ? Export HTML sinon.
    let bytes = std::fs::read(path).map_err(|e| format!("lecture impossible : {e}"))?;
    let text = String::from_utf8_lossy(&bytes).into_owned();
    if text.trim_start().starts_with('{') {
        if let Ok(favorites) = chromium_bookmarks(&text) {
            return Ok(Data { favorites, visits: Vec::new(), notes: Vec::new() });
        }
    }

    // Sinon : export HTML de favoris.
    let favorites = html_bookmarks(&text);
    if favorites.is_empty() {
        return Err(format!(
            "aucun favori reconnu dans « {name} » (export HTML attendu)"
        ));
    }
    Ok(Data { favorites, visits: Vec::new(), notes: Vec::new() })
}

/* ------------------------------------------------------------------ */
/* Détection des navigateurs installés                                 */
/* ------------------------------------------------------------------ */

/// Emplacement de la famille Chromium, exprimé en « dossier local » ou
/// « dossier itinérant » (les deux racines sont fournies à l'appel).
struct Candidate {
    name: &'static str,
    roaming: bool,
    root: &'static str,
    profiles: &'static [&'static str],
}

const CHROMIUM_CANDIDATES: &[Candidate] = &[
    Candidate { name: "Google Chrome", roaming: false, root: "Google\\Chrome\\User Data", profiles: &["Default", "Profile 1", "Profile 2", "Profile 3"] },
    Candidate { name: "Microsoft Edge", roaming: false, root: "Microsoft\\Edge\\User Data", profiles: &["Default", "Profile 1", "Profile 2"] },
    Candidate { name: "Brave", roaming: false, root: "BraveSoftware\\Brave-Browser\\User Data", profiles: &["Default", "Profile 1"] },
    Candidate { name: "Vivaldi", roaming: false, root: "Vivaldi\\User Data", profiles: &["Default", "Profile 1"] },
    Candidate { name: "Chromium", roaming: false, root: "Chromium\\User Data", profiles: &["Default"] },
    Candidate { name: "Ecosia", roaming: false, root: "Ecosia\\User Data", profiles: &["Default"] },
    Candidate { name: "Opera", roaming: true, root: "Opera Software\\Opera Stable", profiles: &[""] },
    Candidate { name: "Opera GX", roaming: true, root: "Opera Software\\Opera GX Stable", profiles: &[""] },
];

/// Liste les navigateurs trouvés sur cette machine (favoris et historique).
pub fn detect() -> Vec<Source> {
    let local = dirs::data_local_dir().unwrap_or_default();
    let roaming = dirs::config_dir().unwrap_or_default();
    detect_in(&local, &roaming)
}

/// Variante utilisée par les tests : les racines sont fournies.
pub fn detect_in(local: &Path, roaming: &Path) -> Vec<Source> {
    let mut out = Vec::new();
    for cand in CHROMIUM_CANDIDATES {
        let base = if cand.roaming { roaming } else { local };
        for profile in cand.profiles {
            let dir = if profile.is_empty() {
                base.join(cand.root)
            } else {
                base.join(cand.root).join(profile)
            };
            let label = if profile.is_empty() || *profile == "Default" {
                cand.name.to_string()
            } else {
                format!("{} ({})", cand.name, profile)
            };
            let bookmarks = dir.join("Bookmarks");
            if bookmarks.is_file() {
                out.push(Source {
                    id: format!("{}-{}", slug(cand.name), slug(profile)),
                    app: cand.name.to_string(),
                    name: label.clone(),
                    kind: Kind::ChromiumBookmarks,
                    path: bookmarks,
                });
            }
            let history = dir.join("History");
            if history.is_file() {
                out.push(Source {
                    id: format!("{}-{}-hist", slug(cand.name), slug(profile)),
                    app: cand.name.to_string(),
                    name: label,
                    kind: Kind::ChromiumHistory,
                    path: history,
                });
            }
        }
    }

    // Firefox : un dossier par profil, sous « Profils ».
    let profiles = roaming.join("Mozilla\\Firefox\\Profiles");
    if let Ok(entries) = std::fs::read_dir(&profiles) {
        for entry in entries.flatten() {
            let dir = entry.path();
            let places = dir.join("places.sqlite");
            if places.is_file() {
                let label = dir
                    .file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default();
                out.push(Source {
                    id: format!("firefox-{}", slug(&label)),
                    app: "Firefox".to_string(),
                    name: format!("Firefox ({label})"),
                    kind: Kind::FirefoxPlaces,
                    path: places,
                });
            }
        }
    }
    out
}

fn slug(text: &str) -> String {
    text.chars()
        .map(|c| if c.is_ascii_alphanumeric() { c.to_ascii_lowercase() } else { '-' })
        .collect::<String>()
        .trim_matches('-')
        .to_string()
}

/* ------------------------------------------------------------------ */
/* Utilitaires                                                         */
/* ------------------------------------------------------------------ */

/// Une URL acceptable pour un favori ou une visite.
pub fn usable_url(url: &str) -> bool {
    let u = url.trim();
    (u.starts_with("http://") || u.starts_with("https://")) && u.len() > 11
}

fn dedupe(items: Vec<(String, String)>, max: usize) -> Vec<(String, String)> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();
    for (title, url) in items {
        let key = crate::urls::canonical(&url);
        if seen.insert(key) {
            out.push((title, url));
            if out.len() >= max {
                break;
            }
        }
    }
    out
}

fn keep_most_recent(mut visits: Vec<Visit>, max: usize) -> Vec<Visit> {
    // Les visites les plus récentes d'abord (l'historique de Nova est
    // chronologique), puis une seule entrée par URL : le tri fait remonter la
    // visite la plus récente de chaque adresse.
    visits.sort_by_key(|v| std::cmp::Reverse(v.ts));
    let mut seen = std::collections::HashSet::new();
    visits.retain(|v| seen.insert(crate::urls::canonical(&v.url)));
    visits.truncate(max);
    visits
}

/// Retire les balises d'une chaîne HTML.
fn strip_tags(src: &str) -> String {
    let mut out = String::with_capacity(src.len());
    let mut inside = false;
    for c in src.chars() {
        match c {
            '<' => inside = true,
            '>' => inside = false,
            _ if !inside => out.push(c),
            _ => {}
        }
    }
    out
}

/// Décode les entités HTML les plus courantes (y compris numériques).
pub fn decode_entities(src: &str) -> String {
    if !src.contains('&') {
        return src.to_string();
    }
    let mut out = String::with_capacity(src.len());
    let mut rest = src;
    while let Some(at) = rest.find('&') {
        out.push_str(&rest[..at]);
        rest = &rest[at..];
        let Some(end) = rest[..rest.len().min(12)].find(';') else {
            out.push_str(rest);
            return out;
        };
        let entity = &rest[1..end];
        let decoded = match entity.to_ascii_lowercase().as_str() {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" | "#39" => Some('\''),
            "nbsp" => Some(' '),
            _ => None,
        };
        let decoded = decoded.or_else(|| {
            let code = entity.strip_prefix('#')?;
            let value = if let Some(hex) = code.strip_prefix(['x', 'X']) {
                u32::from_str_radix(hex, 16).ok()?
            } else {
                code.parse::<u32>().ok()?
            };
            char::from_u32(value)
        });
        match decoded {
            Some(c) => {
                out.push(c);
                rest = &rest[end + 1..];
            }
            None => {
                out.push('&');
                rest = &rest[1..];
            }
        }
    }
    out.push_str(rest);
    out
}

/// Données d'une source, lues hors du fil principal (l'analyse d'une base de
/// plusieurs mégaoctets ne doit pas figer l'interface).
#[derive(Debug)]
pub struct Loaded {
    /// Nom affiché de la source (« Google Chrome », « fichier choisi »…).
    pub name: String,
    /// Catégorie de la source, pour l'affichage.
    pub kind: Kind,
    pub data: Result<Data, String>,
}

/// Compte rendu d'un import, tel que l'interface le présente.
#[derive(Debug, Default, Clone)]
pub struct Outcome {
    pub favorites: usize,
    pub visits: usize,
    pub sources: usize,
    pub skipped: usize,
    pub notes: Vec<String>,
    pub errors: Vec<String>,
    /// Horodatage Unix de fin d'import.
    pub when: u64,
}

impl Outcome {
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "favorites": self.favorites,
            "visits": self.visits,
            "sources": self.sources,
            "skipped": self.skipped,
            "notes": self.notes,
            "errors": self.errors,
            "when_ts": self.when,
        })
    }
}

/// Résultat d'une fusion, pour le compte rendu.
#[derive(Debug, Default)]
pub struct Merge {
    pub favorites: usize,
    pub visits: usize,
    pub skipped: usize,
    /// Favoris refusés parce que la liste est pleine.
    pub overflow: usize,
}

/// Fusionne les données lues avec celles de Nova.
///
/// * les favoris existants ne sont jamais dupliqués ([`crate::urls::canon_eq`]) ;
/// * une visite déjà connue n'est pas recomptée ([`crate::config::History::import_visit`]) :
///   lancer l'import deux fois ne change rien ;
/// * `replace` vide d'abord la liste concernée.
pub fn merge(
    cfg: &mut crate::config::Config,
    history: &mut crate::config::History,
    data: &Data,
    want_favorites: bool,
    want_history: bool,
    replace: bool,
) -> Merge {
    let mut out = Merge::default();

    if want_favorites {
        if replace {
            cfg.favorites.clear();
        }
        for (title, url) in &data.favorites {
            if cfg
                .favorites
                .iter()
                .any(|f| crate::urls::canon_eq(url, &f.url))
            {
                out.skipped += 1;
                continue;
            }
            if cfg.favorites.len() >= crate::config::MAX_FAVORITES {
                out.overflow += 1;
                continue;
            }
            let title = title.trim();
            let title = if title.is_empty() {
                // Un favori sans nom (dossier « Autres favoris » de Chrome) est
                // nommé d'après son hôte plutôt que de rester vide.
                crate::accel::host_of(url).to_string()
            } else {
                title.to_string()
            };
            cfg.favorites
                .push(crate::config::Favorite { title, url: url.clone() });
            out.favorites += 1;
        }
    }

    if want_history {
        if replace {
            history.clear();
        }
        for visit in &data.visits {
            if history.import_visit(&visit.url, &visit.title, visit.ts) {
                out.visits += 1;
            } else {
                out.skipped += 1;
            }
        }
        history.trim();
    }

    out
}

/// Traduit une liste d'erreurs et de remarques en compte rendu lisible.
pub fn summarize(
    outcome: &mut Outcome,
    name: &str,
    kind: Kind,
    data: &Result<Data, String>,
    merged: Option<&Merge>,
) {
    match data {
        Ok(d) => {
            outcome.sources += 1;
            let n = d.favorites.len() + d.visits.len();
            if n == 0 {
                outcome
                    .notes
                    .push(format!("{name} : rien à importer ({})", kind.label()));
            }
            for note in &d.notes {
                outcome.notes.push(format!("{name} : {note}"));
            }
            if let Some(m) = merged {
                if m.overflow > 0 {
                    outcome.notes.push(format!(
                        "{name} : {} favoris ignorés, la liste de Nova est pleine ({} au maximum)",
                        m.overflow,
                        crate::config::MAX_FAVORITES
                    ));
                }
            }
        }
        Err(err) => outcome.errors.push(format!("{name} : {err}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn export_html_de_favoris() {
        let html = r#"<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><A HREF="https://www.rust-lang.org/" ADD_DATE="1700000000">Rust &amp; Cie</A>
    <DT><A HREF='https://fr.wikipedia.org/wiki/Rust'>Wikip&#233;dia</A>
    <DT><A HREF="javascript:alert(1)">Mauvais</A>
    <DT><A HREF="https://www.rust-lang.org/">Doublon</A>
</DL><p>"#;
        let favs = html_bookmarks(html);
        assert_eq!(favs.len(), 2, "doublon et javascript: écartés");
        assert_eq!(favs[0].0, "Rust & Cie");
        assert_eq!(favs[0].1, "https://www.rust-lang.org/");
        assert_eq!(favs[1].0, "Wikipédia");
    }

    #[test]
    fn bookmarks_json_chromium() {
        let json = r#"{"roots":{
            "bookmark_bar":{"type":"folder","children":[
                {"type":"url","name":"Ecosia","url":"https://www.ecosia.org/"},
                {"type":"folder","name":"Dev","children":[
                    {"type":"url","name":"Docs","url":"https://doc.rust-lang.org/"}]}]},
            "other":{"type":"folder","children":[
                {"type":"url","name":"","url":"https://example.com/"}]}}}"#;
        let favs = chromium_bookmarks(json).expect("analyse");
        assert_eq!(favs.len(), 3);
        assert!(favs.iter().any(|(_, u)| u == "https://doc.rust-lang.org/"));
    }

    #[test]
    fn dates_converties() {
        // 2023-11-14 22:13:20 UTC, tel que Chromium l'écrit.
        assert_eq!(chromium_time(13_344_473_600_000_000), 1_700_000_000);
        assert_eq!(firefox_time(1_700_000_000_000_000), 1_700_000_000);
        assert_eq!(chromium_time(0), 0);
        assert_eq!(firefox_time(-5), 0);
    }

    fn fixture(name: &str) -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("tools/fixtures").join(name)
    }

    /// Le cas qui compte : une vraie base Chromium, avec beaucoup de lignes
    /// (pages intérieures), un titre de 7,6 ko (pages de débordement) et des
    /// lignes supprimées (pages libres).
    #[test]
    fn historique_chromium_complet() {
        let db = Db::open(&fixture("chrome-history.sqlite")).expect("ouverture");
        let visits = chromium_history(&db).expect("analyse");
        assert_eq!(visits.len(), 397, "toutes les lignes valides sont lues");
        let long = visits
            .iter()
            .find(|v| v.url == "https://tres-long.example.org/")
            .expect("ligne au titre très long (débordement)");
        assert_eq!(long.title.len(), 7600, "titre reconstitué depuis les pages de débordement");
        assert!(visits.iter().any(|v| v.url.contains("long-url.example.org/segment")));
        // Les dates doivent être converties, pas recopiées.
        assert!(visits.iter().all(|v| (1_600_000_000..1_800_000_000).contains(&v.ts)));
        assert!(visits.iter().all(|v| usable_url(&v.url)));
    }

    /// Les colonnes sont résolues par leur **nom** : un schéma dans un autre
    /// ordre doit donner exactement le même résultat.
    #[test]
    fn historique_chromium_colonnes_melangees() {
        let db = Db::open(&fixture("chrome-history-colonnes-melangees.sqlite")).expect("ouverture");
        let visits = chromium_history(&db).expect("analyse");
        assert_eq!(visits.len(), 2);
        assert_eq!(visits[0].url, "https://beta.fr/");
        assert_eq!(visits[0].title, "Beta");
        assert_eq!(visits[0].ts, 1_700_000_100);
    }

    #[test]
    fn historique_firefox() {
        let db = Db::open(&fixture("firefox-places.sqlite")).expect("ouverture");
        let visits = firefox_places(&db).expect("analyse");
        // « place:… » est une URL interne à Firefox : elle est écartée.
        assert_eq!(visits.len(), 2);
        let mozilla = visits
            .iter()
            .find(|v| v.url == "https://www.mozilla.org/fr/")
            .expect("mozilla");
        assert_eq!(mozilla.title, "Mozilla France");
        assert_eq!(mozilla.ts, 1_700_000_000);
        // Les visites arrivent de la plus récente à la plus ancienne.
        assert_eq!(visits[0].title, "Modules Firefox");
    }

    #[test]
    fn fichier_reconnu_automatiquement() {
        let html = load_file(&fixture("favoris-export.html")).expect("export HTML");
        assert_eq!(html.favorites.len(), 5, "les 3 favoris du dossier + 2 hors dossier");

        let json = load_file(&fixture("Bookmarks")).expect("Bookmarks JSON");
        assert_eq!(json.favorites.len(), 4);
        assert!(json.favorites.iter().any(|(_, u)| u == "https://www.figma.com/"));

        let visits = load_file(&fixture("chrome-history.sqlite")).expect("base Chromium");
        assert_eq!(visits.visits.len(), 397);

        let ff = load_file(&fixture("firefox-places.sqlite")).expect("base Firefox");
        assert_eq!(ff.visits.len(), 2);

        // Un fichier quelconque est refusé avec un message clair.
        let tmp = std::env::temp_dir().join("nova-import-inconnu.txt");
        std::fs::write(&tmp, b"bonjour").unwrap();
        assert!(load_file(&tmp).is_err());
        let _ = std::fs::remove_file(&tmp);
    }

    #[test]
    fn detection_dans_une_arborescence() {
        let base = std::env::temp_dir().join("nova-detect-test");
        let local = base.join("Local");
        let roaming = base.join("Roaming");
        // La détection assemble « racine \ profil » : le test doit créer
        // exactement la même arborescence (sous Linux, la barre oblique
        // inverse reste un caractère du nom de dossier).
        let chrome = local.join("Google\\Chrome\\User Data").join("Default");
        std::fs::create_dir_all(&chrome).unwrap();
        std::fs::write(chrome.join("Bookmarks"), b"{}").unwrap();
        std::fs::write(chrome.join("History"), b"SQLite format 3\0").unwrap();
        let ff = roaming
            .join("Mozilla\\Firefox\\Profiles")
            .join("abc.default-release");
        std::fs::create_dir_all(&ff).unwrap();
        std::fs::write(ff.join("places.sqlite"), b"SQLite format 3\0").unwrap();

        let found = detect_in(&local, &roaming);
        let names: Vec<&str> = found.iter().map(|s| s.name.as_str()).collect();
        assert!(names.iter().any(|n| n.starts_with("Google Chrome")), "{names:?}");
        assert!(found.iter().any(|s| s.kind == Kind::ChromiumHistory));
        assert!(found.iter().any(|s| s.kind == Kind::FirefoxPlaces));
        let _ = std::fs::remove_dir_all(&base);
    }
}
