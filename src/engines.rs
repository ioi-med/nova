//! Définition des moteurs de recherche accessibles depuis Nova.

use serde::Serialize;

#[derive(Clone, Copy, Debug, Serialize)]
pub struct Engine {
    pub id: &'static str,
    pub name: &'static str,
    /// Modèle d'URL de recherche, `{q}` est remplacé par la requête encodée.
    pub query: &'static str,
    pub home: &'static str,
    /// Couleur d'accent utilisée par l'interface (logo, puces).
    pub color: &'static str,
    /// Raccourci de commande : `!b requete` cherche avec Brave.
    pub bang: &'static str,
    pub note: &'static str,
}

pub const ENGINES: &[Engine] = &[
    Engine {
        id: "google",
        name: "Google",
        query: "https://www.google.com/search?q={q}",
        home: "https://www.google.com/",
        color: "#4285f4",
        bang: "!g",
        note: "Le plus complet",
    },
    Engine {
        id: "brave",
        name: "Brave Search",
        query: "https://search.brave.com/search?q={q}",
        home: "https://search.brave.com/",
        color: "#fb542b",
        bang: "!b",
        note: "Index indépendant, sans traqueurs",
    },
    Engine {
        id: "ecosia",
        name: "Ecosia",
        query: "https://www.ecosia.org/search?q={q}",
        home: "https://www.ecosia.org/",
        color: "#22b24c",
        bang: "!e",
        note: "Finance la plantation d'arbres",
    },
    Engine {
        id: "duckduckgo",
        name: "DuckDuckGo",
        query: "https://duckduckgo.com/?q={q}",
        home: "https://duckduckgo.com/",
        color: "#de5833",
        bang: "!d",
        note: "Recherche privée",
    },
    Engine {
        id: "startpage",
        name: "Startpage",
        query: "https://www.startpage.com/sp/search?query={q}",
        home: "https://www.startpage.com/",
        color: "#6578ea",
        bang: "!s",
        note: "Résultats Google anonymisés",
    },
    Engine {
        id: "qwant",
        name: "Qwant",
        query: "https://www.qwant.com/?q={q}",
        home: "https://www.qwant.com/",
        color: "#5c97ff",
        bang: "!q",
        note: "Moteur européen",
    },
];

pub fn by_id(id: &str) -> &'static Engine {
    ENGINES
        .iter()
        .find(|e| e.id.eq_ignore_ascii_case(id))
        .unwrap_or(&ENGINES[0])
}

pub fn by_bang(bang: &str) -> Option<&'static Engine> {
    ENGINES.iter().find(|e| e.bang.eq_ignore_ascii_case(bang))
}

/// Construit l'URL de recherche d'un moteur pour une requête donnée.
pub fn search_url(engine: &Engine, query: &str) -> String {
    let encoded = encode_query(query);
    engine.query.replace("{q}", &encoded)
}

/// Encodage `application/x-www-form-urlencoded` des requêtes (espace -> `%20`).
pub fn encode_query(query: &str) -> String {
    use percent_encoding::{utf8_percent_encode, AsciiSet, CONTROLS};
    const QUERY: &AsciiSet = &CONTROLS
        .add(b' ')
        .add(b'"')
        .add(b'#')
        .add(b'<')
        .add(b'>')
        .add(b'`')
        .add(b'?')
        .add(b'{')
        .add(b'}')
        .add(b'&')
        .add(b'=')
        .add(b'+')
        .add(b'%');
    utf8_percent_encode(query, QUERY).to_string()
}
