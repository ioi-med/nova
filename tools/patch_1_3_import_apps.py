#!/usr/bin/env python3
"""Correctif 1.3.0 — étape 2 : un seul style (pas de variante), et choix de
l'application à importer côté cœur (regroupement des sources par navigateur)."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def patch(path, old, new, label=""):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    if old not in s:
        sys.exit(f"MOTIF INTROUVABLE [{label}] dans {path}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print(f"  ok {label}")


# ---- 1. Retrait de la variante d'habillage (un seul style, sobre) ------------
patch("src/config.rs",
      """    /// Apparence de l'interface : `arc` (sobre, par défaut) ou `classique`.
    pub skin: String,
}""", "}", label="retrait du champ skin")
patch("src/config.rs",
      """            silence_game_overlay: true,
            skin: "arc".into(),
        }""",
      """            silence_game_overlay: true,
        }""", label="retrait du skin par défaut")
patch("src/config.rs",
      """        if !matches!(self.skin.as_str(), "arc" | "classique") {
            self.skin = "arc".into();
        }
""", "", label="retrait de la validation skin")
patch("src/main.rs",
      """                    let skin_changed = patch.get("skin").is_some()
                        && patch.get("skin").and_then(Value::as_str) != Some(self.cfg.skin.as_str());
""", "", label="retrait de skin_changed")
patch("src/main.rs",
      """                    if skin_changed {
                        self.reload_internal_pages();
                    }
""", "", label="retrait de reload_internal_pages")

# ---- 2. Regroupement par navigateur ----------------------------------------
patch("src/import.rs",
      """/// Une source détectée sur la machine.
#[derive(Debug, Clone)]
pub struct Source {
    pub id: String,
    pub name: String,
    pub kind: Kind,
    pub path: PathBuf,
}""",
      """/// Une source détectée sur la machine.
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
}""", label="import : Source.app")

patch("src/import.rs",
      """            let bookmarks = dir.join("Bookmarks");
            if bookmarks.is_file() {
                out.push(Source {
                    id: format!("{}-{}", slug(cand.name), slug(profile)),
                    name: label.clone(),
                    kind: Kind::ChromiumBookmarks,
                    path: bookmarks,
                });
            }
            let history = dir.join("History");
            if history.is_file() {
                out.push(Source {
                    id: format!("{}-{}-hist", slug(cand.name), slug(profile)),
                    name: label,
                    kind: Kind::ChromiumHistory,
                    path: history,
                });
            }""",
      """            let bookmarks = dir.join("Bookmarks");
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
            }""", label="import : sources Chromium avec app")

patch("src/import.rs",
      """                out.push(Source {
                    id: format!("firefox-{}", slug(&label)),
                    name: format!("Firefox ({label})"),
                    kind: Kind::FirefoxPlaces,
                    path: places,
                });""",
      """                out.push(Source {
                    id: format!("firefox-{}", slug(&label)),
                    app: "Firefox".to_string(),
                    name: format!("Firefox ({label})"),
                    kind: Kind::FirefoxPlaces,
                    path: places,
                });""", label="import : sources Firefox avec app")

# ---- 3. État transmis à l'interface : `app` et groupes d'applications -------
patch("src/main.rs",
      """            "import_sources": self
                .import_sources
                .iter()
                .map(|s| {
                    json!({
                        "id": s.id,
                        "name": s.name,
                        "kind": s.kind.label(),
                        "path": s.path.display().to_string(),
                    })
                })
                .collect::<Vec<_>>(),""",
      """            "import_sources": self
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
                .collect::<Vec<_>>(),""", label="état : sources enrichies")

print("étape 2 (cœur) : terminée")
