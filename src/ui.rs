//! Ressources d'interface embarquées dans le binaire.
//!
//! L'interface de navigation de Nova (barre latérale, barre d'adresse, pages
//! internes) est écrite en HTML/CSS/JS et compilée *dans* l'exécutable : aucune
//! ressource externe, aucun serveur local, aucun fichier à installer à côté.

use serde_json::Value;

pub const SIDEBAR: &str = include_str!("../assets/ui/sidebar.html");
pub const TOOLBAR: &str = include_str!("../assets/ui/toolbar.html");
pub const NEWTAB: &str = include_str!("../assets/ui/newtab.html");
pub const SETTINGS: &str = include_str!("../assets/ui/settings.html");
pub const HISTORY: &str = include_str!("../assets/ui/history.html");
pub const WELCOME: &str = include_str!("../assets/ui/welcome.html");
pub const HOTKEYS: &str = include_str!("../assets/ui/inject.js");
pub const IMPORT: &str = include_str!("../assets/ui/import.html");

/// Page interne correspondant à une URL `nova://…`.
pub fn internal_page(url: &str) -> &'static str {
    match url {
        "nova://settings" => SETTINGS,
        "nova://history" => HISTORY,
        "nova://import" => IMPORT,
        _ => NEWTAB,
    }
}

/// Sérialise une valeur JSON pour l'injecter sans risque dans un `<script>`.
pub fn js_payload(value: &Value) -> String {
    let raw = serde_json::to_string(value).unwrap_or_else(|_| "{}".into());
    raw.replace('<', "\\u003c")
        .replace('>', "\\u003e")
        .replace('\u{2028}', "\\u2028")
        .replace('\u{2029}', "\\u2029")
}

/// Peau commune : recalcule la palette complète à partir de la couleur de fond
/// choisie par l'utilisateur. Définie **une seule fois**, ici : les six pages
/// d'interface l'appellent, aucune n'a de copie à maintenir.
pub const SKIN: &str = r##"(function () {
  function parse(hex) {
    if (typeof hex !== "string" || !/^#[0-9a-fA-F]{6}$/.test(hex)) return null;
    return [parseInt(hex.substr(1, 2), 16), parseInt(hex.substr(3, 2), 16),
            parseInt(hex.substr(5, 2), 16)];
  }
  var VARS = ["--bg", "--bg-2", "--bg-3", "--bg-hover", "--line", "--line-2", "--text",
              "--muted", "--card", "--card-hover", "--fav-plate", "--scroll",
              "--switch-off"];
  function apply(bg) {
    var root = document.documentElement, i;
    var base = parse(bg);
    if (!base) {                       /* valeur d'origine : thème standard */
      for (i = 0; i < VARS.length; i++) root.style.removeProperty(VARS[i]);
      return false;
    }
    /* Texte clair ou sombre selon la luminance perçue du fond choisi. */
    var lum = (0.2126 * base[0] + 0.7152 * base[1] + 0.0722 * base[2]) / 255;
    var dark = lum < 0.55;
    var fg = dark ? [255, 255, 255] : [12, 12, 16];
    var mix = function (t) {
      var out = [];
      for (var k = 0; k < 3; k++) out.push(Math.round(base[k] + (fg[k] - base[k]) * t));
      return "rgb(" + out.join(",") + ")";
    };
    var set = function (name, t) { root.style.setProperty(name, mix(t)); };
    root.style.setProperty("--bg", "rgb(" + base.join(",") + ")");
    set("--bg-2", 0.06); set("--bg-hover", 0.08); set("--bg-3", 0.12);
    set("--card", 0.05); set("--card-hover", 0.10); set("--line", 0.15); set("--line-2", 0.22);
    set("--text", 0.94); set("--muted", 0.62);
    set("--scroll", 0.25); set("--switch-off", 0.22);
    root.style.setProperty("--fav-plate", dark ? "#e9e9f2" : "#f2f2f7");
    return true;
  }
  window.NovaSkin = { apply: apply, isCustom: function (bg) { return !!parse(bg); } };
})();"##;

/// Logos officiels des moteurs, embarqués dans le binaire et servis en `data:`.
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
/// Petit utilitaire partagé par les pages : pose le logo officiel d'un moteur
/// dans un élément, et retombe sur la pastille de couleur si l'image manque.
const ICON_HELPER: &str = "window.NovaEngineIcon = function (el, eng) {\
  var src = window.NovaEngineIcons && window.NovaEngineIcons[eng && eng.id];\
  el.textContent = '';\
  if (src) {\
    var img = document.createElement('img');\
    img.src = src; img.alt = ''; img.draggable = false;\
    el.appendChild(img);\
    el.style.background = 'transparent';\
  } else {\
    el.style.background = (eng && eng.color) || 'var(--accent)';\
    el.textContent = ((eng && eng.name) || '?').charAt(0).toUpperCase();\
  }\
};";

pub fn engine_icons_script() -> String {
    let mut js = String::from("window.NovaEngineIcons = {");
    for (id, png) in ENGINE_ICONS {
        js.push_str(&format!(
            "\"{id}\":\"data:image/png;base64,{}\",",
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
        "<head>\n<script>{}\n{}\n{}\nwindow.__NOVA__ = {};</script>",
        SKIN,
        engine_icons_script(),
        ICON_HELPER,
        js_payload(state)
    );
    html.replacen("<head>", &script, 1)
}

/// Prépare un document dont l'état est poussé dynamiquement (`NovaPage.render`).
pub fn render_call(state: &Value) -> String {
    format!(
        "try{{ window.NovaPage && window.NovaPage.render({}); }}catch(e){{}}",
        js_payload(state)
    )
}
