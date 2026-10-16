//! Interprétation de ce que l'utilisateur tape dans la barre d'adresse.

use crate::accel;
use crate::engines::{self, Engine};

#[derive(Debug, Clone, PartialEq)]
pub enum Target {
    /// Une URL « réelle » à charger dans le moteur.
    Url(String),
    /// Une page interne de Nova (`nova://nouvelonglet`, `nova://parametres`, ...).
    Internal(String),
}

/// Transforme une saisie libre en cible de navigation.
///
/// * `github.com`            -> `https://github.com`
/// * `localhost:3000`        -> `http://localhost:3000`
/// * `intel i5 13600k`       -> recherche sur le moteur par défaut
/// * `!b clavier tkl`        -> recherche forcée sur Brave Search
/// * `nova://parametres`     -> page interne
pub fn resolve(input: &str, default_engine: &Engine) -> Option<Target> {
    let s = input.trim();
    if s.is_empty() {
        return None;
    }
    let lower = s.to_ascii_lowercase();

    // 1. Pages internes.
    if lower.starts_with("nova://") {
        return Some(Target::Internal(normalize_internal(&lower)));
    }

    // 2. Commande « !bang requête ».
    if let Some(rest) = s.strip_prefix('!') {
        if let Some(idx) = rest.find(char::is_whitespace) {
            let bang = format!("!{}", &rest[..idx]);
            let query = rest[idx..].trim();
            if !query.is_empty() {
                if let Some(engine) = engines::by_bang(&bang) {
                    return Some(Target::Url(engines::search_url(engine, query)));
                }
            }
        }
    }

    // 3. Début explicite d'une recherche.
    if let Some(query) = s.strip_prefix('?') {
        return Some(Target::Url(engines::search_url(default_engine, query.trim())));
    }

    // 4. Schéma déjà présent.
    if s.contains("://") {
        return Some(Target::Url(s.to_string()));
    }
    for scheme in ["about:", "data:", "file:", "view-source:", "mailto:", "edge:"] {
        if lower.starts_with(scheme) {
            return Some(Target::Url(s.to_string()));
        }
    }

    // 5. Hôte sans schéma : on tente le nom de domaine, puis on retombe sur la recherche.
    let host_part = s.split(['/', '?', '#']).next().unwrap_or(s);
    if is_local_host(host_part) {
        return Some(Target::Url(format!("http://{s}")));
    }
    // « github.com:8080 » doit être ouvert, pas recherché : le port est retiré
    // pour tester la forme du nom d'hôte, mais conservé dans l'URL finale.
    if accel::looks_like_host(strip_port(host_part)) {
        return Some(Target::Url(format!("https://{s}")));
    }

    Some(Target::Url(engines::search_url(default_engine, s)))
}

/// Retire un éventuel « :port » final (« github.com:8080 » -> « github.com »).
fn strip_port(host: &str) -> &str {
    match host.rsplit_once(':') {
        Some((head, port)) if !head.is_empty() && port.parse::<u16>().is_ok() => head,
        _ => host,
    }
}

/// `localhost`, `127.0.0.1`, `192.168.1.10`, `[::1]`, `mon-pc:8080`…
fn is_local_host(host: &str) -> bool {
    let bare = host.trim_start_matches('[').trim_end_matches(']');
    let hostname = bare.split(':').next().unwrap_or(bare);

    if hostname.eq_ignore_ascii_case("localhost") || hostname.is_empty() {
        return hostname.eq_ignore_ascii_case("localhost");
    }

    if hostname.parse::<std::net::Ipv6Addr>().is_ok() {
        return true;
    }

    let parts: Vec<&str> = hostname.split('.').collect();
    if parts.len() == 4 && parts.iter().all(|p| p.parse::<u8>().is_ok()) {
        return true;
    }

    // « machine:8080 » : un nom simple suivi d'un port.
    if let Some(port) = bare.split(':').nth(1) {
        if port.parse::<u16>().is_ok() && !hostname.contains('.') {
            return true;
        }
    }

    false
}

fn normalize_internal(value: &str) -> String {
    match value {
        "nova://newtab" | "nova://nouvelonglet" | "nova://home" => "nova://newtab".into(),
        "nova://settings" | "nova://parametres" => "nova://settings".into(),
        "nova://history" | "nova://historique" => "nova://history".into(),
        "nova://import" | "nova://importer" | "nova://import-externe" => "nova://import".into(),
        // « À propos » vit dans la page Paramètres : on y renvoie directement
        // plutôt que d'annoncer une page qui n'existe pas.
        "nova://about" | "nova://apropos" => "nova://settings".into(),
        other => other.to_string(),
    }
}

/// Schéma d'une URL (« https », « mailto », « ms-gamingoverlay »…), en
/// minuscules. `None` pour une URL relative ou vide.
pub fn scheme_of(url: &str) -> Option<String> {
    let before = url.split(['/', '?', '#']).next().unwrap_or("");
    let (scheme, _) = before.split_once(':')?;
    if scheme.is_empty() || !scheme.chars().next()?.is_ascii_alphabetic() {
        return None;
    }
    if !scheme
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '-' | '.'))
    {
        return None;
    }
    Some(scheme.to_ascii_lowercase())
}

/// Schémas que le moteur de rendu charge lui-même, sans passer par Windows.
///
/// Tout ce qui n'est pas dans cette liste est un protocole **du système** :
/// Nova demande alors au registre si un logiciel sait l'ouvrir avant de laisser
/// faire, sinon Windows affiche « Obtenir une application pour ouvrir ce lien »
/// (c'est le cas du célèbre `ms-gamingoverlay` de la Xbox Game Bar).
pub fn is_engine_scheme(scheme: &str) -> bool {
    matches!(
        scheme,
        "http"
            | "https"
            | "nova"
            | "about"
            | "data"
            | "blob"
            | "file"
            | "filesystem"
            | "view-source"
            | "chrome"
            | "chrome-extension"
            | "chrome-error"
            | "chrome-untrusted"
            | "devtools"
            | "edge"
    )
}

/// Protocoles du système que Nova refuse **toujours**, même si un logiciel les
/// gère : l'overlay de jeu n'a rien à faire dans une fenêtre de navigateur, et
/// c'est ce protocole qui faisait apparaître la boîte de dialogue de Windows au
/// lancement.
pub fn is_blocked_scheme(scheme: &str) -> bool {
    matches!(
        scheme,
        "ms-gamingoverlay" | "ms-gamebar" | "ms-gamebarservices" | "ms-xbl-3d8b372c"
    )
}

/// `true` si la page est interne à Nova.
#[allow(dead_code)]
pub fn is_internal(url: &str) -> bool {
    url.starts_with("nova://")
}

/// Connexion chiffrée (ou page interne) : affiche le cadenas fermé.
pub fn is_secure(url: &str) -> bool {
    let lower = url.to_ascii_lowercase();
    lower.starts_with("https://") || lower.starts_with("nova://") || lower.starts_with("about:")
}

/// Découpe une URL en (hôte, reste) pour l'affichage compact de la barre d'adresse.
pub fn split_display(url: &str) -> (String, String) {
    if let Some(rest) = url.strip_prefix("nova://") {
        return ("nova".to_string(), rest.to_string());
    }
    let host = accel::host_of(url);
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
}

/// Libellé lisible d'une page interne.
pub fn display_title(url: &str) -> Option<&'static str> {
    match url {
        "nova://newtab" => Some("Nouvel onglet"),
        "nova://settings" => Some("Paramètres"),
        "nova://history" => Some("Historique"),
        "nova://import" => Some("Importer des données"),
        "nova://about" => Some("À propos de Nova"),
        _ => None,
    }
}

/// Longueur minimale pour qu'un « / » final soit considéré comme la racine
/// d'un chemin. « https:// » (8 caractères) ne doit jamais être rogné.
const MIN_LEN_ROOT_SLASH: usize = 9;

/// Compare une URL à une clé canonique **sans allouer** (chemin chaud de
/// l'historique : appelé pour chaque entrée à chaque changement de titre).
///
/// Doit appliquer exactement la même normalisation que [`canonical`] : les
/// deux seuils différaient d'un octet, ce qui faisait diverger les
/// comparaisons sur les URL très courtes.
pub fn canon_eq(url: &str, key: &str) -> bool {
    let base = match url.split_once('#') {
        Some((head, _)) => head,
        None => url,
    };
    let trimmed = if base.ends_with('/') && base.len() >= MIN_LEN_ROOT_SLASH {
        &base[..base.len() - 1]
    } else {
        base
    };
    trimmed == key
}

/// Normalise une URL pour comparaison (sans fragment, sans slash final).
pub fn canonical(url: &str) -> String {
    let mut u = url.split('#').next().unwrap_or(url).to_string();
    if u.ends_with('/') && u.len() >= MIN_LEN_ROOT_SLASH {
        u.pop();
    }
    u
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engines::by_id;

    #[test]
    fn resolve_cases() {
        let g = by_id("google");
        assert_eq!(
            resolve("github.com", g),
            Some(Target::Url("https://github.com".into()))
        );
        assert_eq!(
            resolve("localhost:3000", g),
            Some(Target::Url("http://localhost:3000".into()))
        );
        assert!(matches!(resolve("bonjour le monde", g), Some(Target::Url(u)) if u.contains("google.com/search")));
        assert!(matches!(resolve("!b test", g), Some(Target::Url(u)) if u.contains("brave.com")));
        assert_eq!(resolve("nova://parametres", g), Some(Target::Internal("nova://settings".into())));
        assert_eq!(resolve("   ", g), None);
    }

    #[test]
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
    fn secure_and_display() {
        assert!(is_secure("https://example.com"));
        assert!(!is_secure("http://example.com"));
        assert_eq!(split_display("https://example.com/a/b"), ("example.com".into(), "/a/b".into()));
    }

    #[test]
    fn schemas_du_systeme() {
        assert_eq!(scheme_of("https://exemple.fr/"), Some("https".into()));
        assert_eq!(scheme_of("mailto:contact@exemple.fr"), Some("mailto".into()));
        assert_eq!(scheme_of("ms-gamingoverlay:"), Some("ms-gamingoverlay".into()));
        assert_eq!(scheme_of("MS-Settings:display"), Some("ms-settings".into()));
        assert_eq!(scheme_of("about:blank"), Some("about".into()));
        assert_eq!(scheme_of("exemple.fr/page"), None, "pas de schéma");
        assert_eq!(scheme_of("/chemin/local"), None);
        assert_eq!(scheme_of("12:30"), None, "un nombre n'est pas un schéma");

        // Le moteur charge ces schémas lui-même.
        for bon in ["http", "https", "nova", "about", "data", "blob", "file", "edge",
                    "chrome-extension", "view-source"] {
            assert!(is_engine_scheme(bon), "{bon} doit être chargé par le moteur");
        }
        // Les protocoles du système passent par le registre.
        for systeme in ["mailto", "tel", "ms-settings", "steam", "zoommtg"] {
            assert!(!is_engine_scheme(systeme), "{systeme} est un protocole Windows");
        }
        // Et l'overlay de jeu est refusé dans tous les cas.
        for jeu in ["ms-gamingoverlay", "ms-gamebar", "ms-gamebarservices"] {
            assert!(is_blocked_scheme(jeu), "{jeu} doit être refusé");
        }
        assert!(!is_blocked_scheme("mailto"));
    }

    #[test]
    fn canonical_et_comparaison() {
        // Cas d'usage réel : la clé stockée est le résultat de `canonical`.
        for (raw, want) in [
            ("https://a.fr/x#ancre", "https://a.fr/x"),
            ("https://a.fr/x/", "https://a.fr/x"),
            ("https://a.fr/", "https://a.fr"),
            ("https://a.fr", "https://a.fr"),
        ] {
            assert_eq!(canonical(raw), want, "canonical({raw})");
            let key = canonical(raw);
            assert!(canon_eq(raw, &key), "canon_eq({raw}) doit reconnaître sa forme canonique");
            assert!(canon_eq(want, &key), "canon_eq({want})");
        }

        assert!(!canon_eq("https://a.fr/y", &canonical("https://a.fr/x")));

        // Formes dégénérées : ni l'une ni l'autre ne doit rogner le schéma.
        assert_eq!(canonical("https://a/"), "https://a");
        assert_eq!(canonical("https://"), "https://");
        assert!(canon_eq("https://", "https://"));
    }
}
