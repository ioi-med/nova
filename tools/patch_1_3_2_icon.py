#!/usr/bin/env python3
"""Nova 1.3.2 — icône de fenêtre et logos officiels des moteurs."""
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


# ================================================================== ui.rs ====
patch("src/ui.rs",
"""/// Prépare un document HTML en y injectant la peau puis l'état courant
/// (`window.NovaSkin` et `window.__NOVA__`).
pub fn with_state(html: &str, state: &Value) -> String {
    let script = format!(
        "<head>\\n<script>{}\\nwindow.__NOVA__ = {};</script>",
        SKIN,
        js_payload(state)
    );
    html.replacen("<head>", &script, 1)
}""",
"""/// Logos officiels des moteurs, embarqués dans le binaire et servis en `data:`.
/// Ils sont récupérés depuis les sites officiels (voir `assets/engines/` et le
/// fichier `LICENCES-TIERS.md` : ces marques appartiennent à leurs titulaires et
/// ne servent qu'à désigner le moteur).
const ENGINE_ICONS: &[(&str, &[u8])] = &[
    ("google", include_bytes!("../assets/engines/google.png")),
    ("brave", include_bytes!("../assets/engines/brave.png")),
    ("ecosia", include_bytes!("../assets/engines/ecosia.png")),
    ("duckduckgo", include_bytes!("../assets/engines/duckduckgo.png")),
    ("startpage", include_bytes!("../assets/engines/startpage.png")),
    ("qwant", include_bytes!("../assets/engines/qwant.png")),
];

/// Encodage base64 (aucune dépendance : 40 lignes de plus valent mieux qu'un
/// paquet supplémentaire pour un besoin aussi simple).
fn base64(data: &[u8]) -> String {
    const ALPHABET: &[u8; 64] =
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for bloc in data.chunks(3) {
        let b = [
            bloc[0],
            *bloc.get(1).unwrap_or(&0),
            *bloc.get(2).unwrap_or(&0),
        ];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(ALPHABET[(n >> 18) as usize & 63] as char);
        out.push(ALPHABET[(n >> 12) as usize & 63] as char);
        out.push(if bloc.len() > 1 {
            ALPHABET[(n >> 6) as usize & 63] as char
        } else {
            '='
        });
        out.push(if bloc.len() > 2 {
            ALPHABET[n as usize & 63] as char
        } else {
            '='
        });
    }
    out
}

/// Script `window.NovaEngineIcons` : identifiant de moteur -> image `data:`.
pub fn engine_icons_script() -> String {
    let mut js = String::from("window.NovaEngineIcons = {");
    for (id, png) in ENGINE_ICONS {
        js.push_str(&format!(
            "\\"{id}\\":\\"data:image/png;base64,{}\\",",
            base64(png)
        ));
    }
    js.push_str("};");
    js
}

/// Prépare un document HTML en y injectant la peau, les logos des moteurs puis
/// l'état courant (`window.NovaSkin`, `window.NovaEngineIcons` et
/// `window.__NOVA__`).
pub fn with_state(html: &str, state: &Value) -> String {
    let script = format!(
        "<head>\\n<script>{}\\n{}\\nwindow.__NOVA__ = {};</script>",
        SKIN,
        engine_icons_script(),
        js_payload(state)
    );
    html.replacen("<head>", &script, 1)
}""", label="ui.rs : logos des moteurs injectés")

# ================================================================ main.rs ====
patch("src/main.rs",
"""        let window = WindowBuilder::new()
            .with_title("Nova")
            .with_inner_size(LogicalSize::new(1320.0, 840.0))
            .with_min_inner_size(LogicalSize::new(760.0, 480.0))
            .build(target)""",
"""        // Icône de la fenêtre (barre de titre et barre des tâches) : dessinée
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
            .build(target)""", label="main.rs : icône de la fenêtre")

# Les sous-fenêtres qui portent la marque (page d'accueil, historique) gardent
# l'icône par défaut du système : la barre des tâches, elle, suit la fenêtre.
print("étape icône + logos : terminée")
