#!/usr/bin/env python3
"""Correctifs issus de l'audit (partie 2) : interface, module C, robustesse de build."""

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


# ======================================================================
# 1. sidebar.html — fuite entre les deux listes d'onglets + favicons
# ======================================================================
s = load("assets/ui/sidebar.html")

s = sub(s, """  function syncTabs(list, container, isPinned){
    const seen = new Set();
    list.forEach((tab) => {
      seen.add(tab.id);""", """  /* `seen` est partagé entre les deux listes (épinglés / normaux) : le
     nettoyage avait lieu dans chaque appel, si bien qu'afficher les onglets
     épinglés détruisait tous les nœuds des onglets normaux — donc une
     reconstruction complète et un nouveau téléchargement des favicons à
     chaque rafraîchissement. */
  function syncTabs(list, container, isPinned, seen){
    list.forEach((tab) => {
      seen.add(tab.id);""", "sidebar.html")

s = sub(s, """      updateTab(el, tab, isPinned);
      container.appendChild(el);
    });
    Array.from(tabNodes.keys()).forEach((id) => {
      if (!seen.has(id)) {
        const el = tabNodes.get(id);
        if (el) el.remove();
        tabNodes.delete(id);
      }
    });
  }""", """      updateTab(el, tab, isPinned);
      container.appendChild(el);
    });
  }

  /* Supprime les nœuds des onglets réellement fermés (une seule fois,
     après avoir rempli les deux listes). */
  function pruneTabs(seen){
    Array.from(tabNodes.keys()).forEach((id) => {
      if (!seen.has(id)) {
        const el = tabNodes.get(id);
        if (el) el.remove();
        tabNodes.delete(id);
      }
    });
  }""", "sidebar.html")

s = sub(s, """      syncTabs(pinned, pinnedBar, true);
      syncTabs(plain, $("tabList"), false);""", """      const seen = new Set();
      syncTabs(pinned, pinnedBar, true, seen);
      syncTabs(plain, $("tabList"), false, seen);
      pruneTabs(seen);""", "sidebar.html")

s = sub(s, """  function applyFavicon(el, tab){
    const host = hostOf(tab.url);
    if (el._favHost === host && el._favTitle === tab.title) return;
    el._favHost = host;
    el._favTitle = tab.title;

    const box = el._favicon;
    if (!box) return;
    const letter = (tab.title || host || "?").trim().charAt(0).toUpperCase() || "?";
    box.style.background = tint(host || letter);

    if (el._img) { el._img.remove(); el._img = null; }
    box.textContent = letter;

    if (tab.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
      const img = document.createElement("img");
      img.alt = "";
      img.src = "https://" + host + "/favicon.ico";
      img.addEventListener("error", () => img.remove());
      box.appendChild(img);
      el._img = img;
    }
  }""", """  /* Le favicon ne dépend que de l'hôte : un changement de titre ne doit donc
     pas relancer de requête (l'ancienne version comparait aussi le titre, ce
     qui re-téléchargeait l'image à chaque « (1) », « • », etc.). */
  function applyFavicon(el, tab){
    const box = el._favicon;
    if (!box) return;
    const host = hostOf(tab.url);
    const letter = (tab.title || host || "?").trim().charAt(0).toUpperCase() || "?";

    if (el._favHost !== host) {
      el._favHost = host;
      if (el._img) { el._img.remove(); el._img = null; }
      box.style.background = tint(host || letter);
      box.textContent = letter;

      if (tab.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
        const img = document.createElement("img");
        img.alt = "";
        img.src = "https://" + host + "/favicon.ico";
        img.addEventListener("error", () => { img.remove(); el._img = null; });
        box.appendChild(img);
        el._img = img;
      }
    } else if (!el._img && box.textContent !== letter) {
      box.textContent = letter;
    }
  }""", "sidebar.html")

s = sub(s, """    const el = document.createElement("div");
    el.dataset.id = tab.id;
    el.dataset.pinned = isPinned ? "1" : "0";
    el.draggable = true;
    el._favHost = null;""", """    const el = document.createElement("div");
    el.dataset.id = tab.id;
    el.dataset.pinned = isPinned ? "1" : "0";
    el.draggable = true;
    el._favHost = null;
    el._img = null;""", "sidebar.html")
save("assets/ui/sidebar.html", s)

# ======================================================================
# 2. Textes obsolètes (« 0.0.0.0 » alors que le blocage utilise ~NOTFOUND)
# ======================================================================
t = load("assets/trackers.txt")
t = sub(t, """# Ces domaines sont résolus vers 0.0.0.0 dans le moteur de rendu (blocage réseau,
# sous-requêtes comprises) et toute navigation de premier niveau vers eux est refusée.""",
"""# Ces domaines sont résolus en « ~NOTFOUND » (échec de résolution immédiat) dans le
# moteur de rendu : blocage réseau, sous-requêtes comprises, sans aucune connexion
# sortante. Toute navigation de premier niveau vers eux est également refusée.""", "trackers.txt")
save("assets/trackers.txt", t)

w = load("assets/ui/welcome.html")
w = sub(w, """          <small>Liste locale de régies publicitaires résolues vers 0.0.0.0 dans le moteur de rendu.
          Désactivez cette option si un site se comporte mal.</small>""",
"""          <small>Liste locale de régies publicitaires : leur résolution est neutralisée
          dans le moteur de rendu, sans aucune connexion sortante.
          Désactivez cette option si un site se comporte mal.</small>""", "welcome.html")
save("assets/ui/welcome.html", w)

# ======================================================================
# 3. Module C : accepter les domaines internationalisés (punycode)
# ======================================================================
c = load("native/nova_core.c")
c = sub(c, """    /* Le dernier label (TLD) doit contenir au moins deux lettres. */
    size_t label = 0;
    for (size_t i = len; i > 0; i--) {
        if (s[i - 1] == '.') {
            break;
        }
        label++;
    }
    if (label < 2 || label > 24) {
        return 0;
    }
    for (size_t i = len - label; i < len; i++) {
        if (!((s[i] >= 'a' && s[i] <= 'z') || (s[i] >= 'A' && s[i] <= 'Z'))) {
            return 0;
        }
    }
    return 1;""",
"""    /* Le dernier label (TLD) doit être plausible : 2 à 63 caractères
     * alphanumériques ou tirets, avec au moins une lettre. Accepter les
     * chiffres et les tirets est indispensable pour les domaines
     * internationalisés, qui s'écrivent en punycode (« xn--p1ai » pour .рф) :
     * les refuser faisait passer l'adresse pour une recherche. */
    size_t label = 0;
    for (size_t i = len; i > 0; i--) {
        if (s[i - 1] == '.') {
            break;
        }
        label++;
    }
    if (label < 2 || label > 63) {
        return 0;
    }
    int has_letter = 0;
    for (size_t i = len - label; i < len; i++) {
        const unsigned char c = (unsigned char)s[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
            has_letter = 1;
        } else if ((c >= '0' && c <= '9') || c == '-') {
            /* autorisé (punycode) */
        } else {
            return 0;
        }
    }
    return has_letter;""", "nova_core.c")
save("native/nova_core.c", c)

h = load("native/nova_core.h")
h = sub(h, """/*
 * Vrai (1) si la chaîne ressemble à un nom de domaine (« example.com ») :
 * uniquement [a-z0-9.-] + au moins un point + pas de point en début/fin.
 */""", """/*
 * Vrai (1) si la chaîne ressemble à un nom de domaine (« example.com ») :
 * uniquement [a-z0-9.-], au moins un point, pas de point en début/fin, et un
 * dernier label plausible (2 à 63 caractères alphanumériques ou tirets avec au
 * moins une lettre — ce qui couvre le punycode des domaines internationalisés).
 */""", "nova_core.h")
save("native/nova_core.h", h)

# ======================================================================
# 4. accel.rs : parité du repli Rust + bascule automatique si le C échoue
# ======================================================================
a = load("src/accel.rs")
a = a.replace('#[cfg(feature = "native-accel")]', '#[cfg(nova_c_accel)]')
a = a.replace('#[cfg(not(feature = "native-accel"))]', '#[cfg(not(nova_c_accel))]')
a = sub(a, """//! Passerelle vers l'accélérateur natif écrit en C (`native/nova_core.c`).""",
"""//! Passerelle vers l'accélérateur natif écrit en C (`native/nova_core.c`).
//!
//! La configuration `nova_c_accel` est posée par `build.rs` **uniquement**
//! lorsque le module C a été compilé avec succès. Elle est donc fausse si la
//! fonctionnalité est désactivée *ou* si aucun compilateur C n'est disponible :
//! dans les deux cas, c'est l'implémentation Rust ci-dessous qui prend le
//! relais, sans que la compilation échoue.""", "accel.rs")

a = sub(a, """    #[cfg(not(nova_c_accel))]
    {
        let mut dots = 0;
        let bytes = s.as_bytes();
        for (i, c) in bytes.iter().enumerate() {
            match c {
                b'.' => {
                    if i == 0 || i + 1 == bytes.len() || bytes[i - 1] == b'.' {
                        return false;
                    }
                    dots += 1;
                }
                b'-' => {
                    if i == 0 || i + 1 == bytes.len() {
                        return false;
                    }
                }
                b'a'..=b'z' | b'A'..=b'Z' | b'0'..=b'9' => {}
                _ => return false,
            }
        }
        dots > 0
    }""", """    #[cfg(not(nova_c_accel))]
    {
        // Doit rester strictement équivalent à `nova_looks_like_host` en C.
        let bytes = s.as_bytes();
        let mut dots = 0usize;
        for (i, c) in bytes.iter().enumerate() {
            match c {
                b'.' => {
                    if i == 0 || i + 1 == bytes.len() || bytes[i - 1] == b'.' {
                        return false;
                    }
                    dots += 1;
                }
                b'-' => {
                    if i == 0 || i + 1 == bytes.len() {
                        return false;
                    }
                }
                b'a'..=b'z' | b'A'..=b'Z' | b'0'..=b'9' => {}
                _ => return false,
            }
        }
        if dots == 0 {
            return false;
        }

        let label_start = bytes.iter().rposition(|c| *c == b'.').map(|p| p + 1).unwrap_or(0);
        let label = &bytes[label_start..];
        if label.len() < 2 || label.len() > 63 {
            return false;
        }
        let mut has_letter = false;
        for c in label {
            match c {
                b'a'..=b'z' | b'A'..=b'Z' => has_letter = true,
                b'0'..=b'9' | b'-' => {}
                _ => return false,
            }
        }
        has_letter
    }""", "accel.rs")

a = sub(a, """/// Nom du moteur de calcul utilisé, affiché dans la page « À propos ».
pub fn backend() -> &'static str {
    #[cfg(nova_c_accel)]
    {
        "C natif (nova_core.c)"
    }
    #[cfg(not(nova_c_accel))]
    {
        "Rust (repli, sans module C)"
    }
}""", """/// Nom du moteur de calcul utilisé, affiché dans la page « À propos ».
pub fn backend() -> &'static str {
    #[cfg(nova_c_accel)]
    {
        "C natif (nova_core.c)"
    }
    #[cfg(not(nova_c_accel))]
    {
        "Rust (repli, module C indisponible)"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hotes_reconnus() {
        for host in [
            "example.com",
            "sub.example.travel",
            "my-site.co.uk",
            "exemple.xn--p1ai", // domaine internationalisé en punycode
            "a1.b2.example",
        ] {
            assert!(looks_like_host(host), "{host} devrait être un nom d'hôte");
        }
        for text in ["bonjour le monde", "localhost", "a.b", "test.123", "-x.com", "x.com-", ".com", "x."] {
            assert!(!looks_like_host(text), "{text} ne devrait pas être un nom d'hôte");
        }
    }

    #[test]
    fn hotes_et_encodage() {
        assert_eq!(host_of("https://Utilisateur@Exemple.FR:8443/a/b"), "exemple.fr");
        assert_eq!(host_of("localhost:3000"), "localhost");
        assert_eq!(host_of("http://[::1]:8080/x"), "::1");
        assert_eq!(host_of(""), "");
    }

    #[test]
    fn recherche_et_troncature() {
        assert!(find_ci("https://ADS.DoubleClick.net/x", "doubleclick.net"));
        assert!(!find_ci("https://example.com", "doubleclick.net"));
        assert!(ends_with_ci("ads.example.com", ".example.com"));
        assert!(!ends_with_ci("notexample.com", ".example.com"));
        let accent = "Prévisions détaillées";
        let cut = truncate(accent, 12);
        assert!(cut.len() <= 12 && accent.starts_with(cut));
        assert!(accent.is_char_boundary(cut.len()));
        assert_ne!(hash64("a"), hash64("b"));
    }
}""", "accel.rs")
save("src/accel.rs", a)

# ======================================================================
# 5. build.rs : ne jamais faire échouer la compilation si le C manque
# ======================================================================
b = load("build.rs")
b = sub(b, """fn main() {
    println!("cargo:rerun-if-changed=native/nova_core.c");""",
"""fn main() {
    // Configuration posée par ce script si (et seulement si) le module C a
    // réellement été compilé : `src/accel.rs` s'en sert pour choisir entre
    // l'appel natif et l'implémentation Rust équivalente.
    println!("cargo:rustc-check-cfg=cfg(nova_c_accel)");
    println!("cargo:rerun-if-changed=native/nova_core.c");""", "build.rs")

b = sub(b, """    build.compile("nova_core");
}""", """    // `try_compile` plutôt que `compile` : sans compilateur C (ou si la chaîne
    // est incomplète), on prévient et on continue avec le repli Rust au lieu
    // d'échouer sur un message obscur du type « lib.exe not found ».
    match build.try_compile("nova_core") {
        Ok(()) => println!("cargo:rustc-cfg=nova_c_accel"),
        Err(err) => println!(
            "cargo:warning=accélérateur C non compilé ({err}) : repli sur l'implémentation Rust"
        ),
    }
}""", "build.rs")
save("build.rs", b)

print("correctifs interface / C / build appliqués")
