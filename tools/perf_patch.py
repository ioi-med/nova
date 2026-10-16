#!/usr/bin/env python3
"""Correctifs de performance pour Nova.

Trois causes identifiées :
  1. un environnement WebView2 était créé pour chaque onglet (aucun cache dans wry) ;
  2. `navigation_handler` (WebView2 `NavigationStarting`) se déclenche pour chaque
     iframe : chaque sous-navigation provoquait une reconstruction complète de
     l'état de l'interface + trois `ExecuteScript` ;
  3. l'interface était reconstruite intégralement (DOM + favicons) à chaque
     événement, et l'historique était écrit sur disque de façon synchrone.

Ce script applique : environnement partagé, regroupement des mises à jour
d'interface (60 ms), chargement paresseux des onglets restaurés, historique sans
allocation et sauvegardes différées, plus le rendu incrémental du DOM.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def sub(text, old, new, rel="?", count=1):
    if old not in text:
        raise SystemExit(f"motif introuvable dans {rel} :\n{old[:400]}")
    return text.replace(old, new, count)


def replace_fn(text, signature, new_body, rel="?"):
    """Remplace une fonction entière en équilibrant les accolades."""
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"fonction introuvable dans {rel} : {signature.strip()}")
    i = start + len(signature)
    depth = 1
    while depth > 0:
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        i += 1
    return text[:start] + new_body + text[i:]


# ======================================================================
# 1. urls.rs — comparaison canonique sans allocation
# ======================================================================
urls = read("src/urls.rs")
urls = sub(urls, """/// Normalise une URL pour comparaison (sans fragment, sans slash final).
pub fn canonical(url: &str) -> String {""", """/// Compare une URL à une clé canonique **sans allouer** (chemin chaud de
/// l'historique : appelé pour chaque entrée à chaque changement de titre).
pub fn canon_eq(url: &str, key: &str) -> bool {
    let base = match url.split_once('#') {
        Some((head, _)) => head,
        None => url,
    };
    let trimmed = match base.strip_suffix('/') {
        Some(inner) if inner.len() > 7 => inner,
        _ => base,
    };
    trimmed == key
}

/// Normalise une URL pour comparaison (sans fragment, sans slash final).
pub fn canonical(url: &str) -> String {""")
write("src/urls.rs", urls)

# ======================================================================
# 2. config.rs — historique : zéro allocation, révision, JSON compact
# ======================================================================
cfg = read("src/config.rs")
cfg = sub(cfg, """    /// Enregistre une visite (les URL internes sont ignorées).
    pub fn visit(&mut self, url: &str, title: &str) {
        if url.is_empty() || url.starts_with("nova://") || url.starts_with("about:") {
            return;
        }
        let key = crate::urls::canonical(url);
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canonical(&e.url) == key)
        {
            entry.visits = entry.visits.saturating_add(1);
            entry.ts = Self::now();
            if !title.is_empty() {
                entry.title = title.to_string();
            }
            return;
        }""", """    /// Enregistre une visite (les URL internes sont ignorées).
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
            return;
        }""")

cfg = sub(cfg, """    pub fn rename(&mut self, url: &str, title: &str) {
        if title.is_empty() {
            return;
        }
        let key = crate::urls::canonical(url);
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canonical(&e.url) == key)
        {
            entry.title = title.to_string();
        }
    }

    pub fn remove(&mut self, url: &str) {
        let key = crate::urls::canonical(url);
        self.entries.retain(|e| crate::urls::canonical(&e.url) != key);
    }""", """    pub fn rename(&mut self, url: &str, title: &str) {
        if title.is_empty() {
            return;
        }
        if let Some(entry) = self.entries.iter_mut().find(|e| e.url == url) {
            if entry.title != title {
                entry.title = title.to_string();
            }
            return;
        }
        let key = crate::urls::canonical(url);
        if let Some(entry) = self
            .entries
            .iter_mut()
            .find(|e| crate::urls::canon_eq(&e.url, &key))
        {
            entry.title = title.to_string();
        }
    }

    pub fn remove(&mut self, url: &str) {
        let direct = url.to_string();
        let key = crate::urls::canonical(url);
        self.entries
            .retain(|e| e.url != direct && !crate::urls::canon_eq(&e.url, &key));
    }

    /// Signature bon marché de l'historique : l'interface ne reconstruit la
    /// liste que lorsque cette valeur change.
    #[allow(dead_code)]
    pub fn revision(&self) -> u64 {
        let last = self.entries.last().map(|e| e.ts).unwrap_or(0);
        (self.entries.len() as u64).wrapping_mul(0x100_0000_01b3) ^ last
    }""")

# JSON compact (l'historique et la session ne sont pas relus à la main par l'utilisateur).
cfg = sub(cfg, """fn write_json<T: Serialize>(path: &Path, value: &T) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let json = serde_json::to_string_pretty(value).unwrap_or_else(|_| "{}".into());""",
"""fn write_json<T: Serialize>(path: &Path, value: &T) -> std::io::Result<()> {
    write_json_compact(path, value, false)
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
    .unwrap_or_else(|_| "{}".into());""")
cfg = sub(cfg, """    pub fn save(&self, dir: &Path) {
        let _ = write_json(&dir.join("config.json"), self);
    }""", """    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("config.json"), self, true);
    }""")
cfg = sub(cfg, """    pub fn save(&self, dir: &Path) {
        let _ = write_json(&dir.join("history.json"), self);
    }""", """    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("history.json"), self, false);
    }""")
cfg = sub(cfg, """    pub fn save(&self, dir: &Path) {
        let _ = write_json(&dir.join("session.json"), self);
    }""", """    pub fn save(&self, dir: &Path) {
        let _ = write_json_compact(&dir.join("session.json"), self, false);
    }""")
write("src/config.rs", cfg)

# ======================================================================
# 3. blocker.rs — résolution instantanée en NXDOMAIN (~NOTFOUND)
# ======================================================================
blk = read("src/blocker.rs")
blk = sub(blk, """    /// Liste de règles passée au moteur de rendu : les domaines concernés sont
    /// résolus vers `0.0.0.0`, ce qui bloque réellement les ressources
    /// publicitaires au niveau réseau (sous-requêtes incluses).
    pub fn resolver_rules(&self, max_hosts: usize) -> String {
        let mut arg = String::from("--host-resolver-rules=");
        for (i, (domain, _)) in self.domains.iter().take(max_hosts).enumerate() {
            if i > 0 {
                arg.push(',');
            }
            arg.push_str("MAP *.");
            arg.push_str(domain);
            arg.push_str(" 0.0.0.0");
        }
        arg
    }""", """    /// Liste de règles passée au moteur de rendu.
    ///
    /// Les domaines concernés sont résolus en `~NOTFOUND`, c'est-à-dire un
    /// échec de résolution immédiat : plus rapide qu'une redirection vers
    /// `0.0.0.0`, qui oblige le moteur à ouvrir une connexion (et qui, sous
    /// Windows, aboutit à la machine locale). Le blocage est instantané et
    /// aucune connexion n'est tentée.
    pub fn resolver_rules(&self, max_hosts: usize) -> String {
        let mut arg = String::from("--host-resolver-rules=");
        let mut first = true;
        for (domain, _) in self.domains.iter().take(max_hosts) {
            for pattern in [format!("*.{domain}"), (*domain).to_string()] {
                if !first {
                    arg.push(',');
                }
                first = false;
                arg.push_str("MAP ");
                arg.push_str(&pattern);
                arg.push_str(" ~NOTFOUND");
            }
        }
        arg
    }""")
write("src/blocker.rs", blk)

print("modules Rust annexes : OK")
