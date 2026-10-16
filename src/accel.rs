//! Passerelle vers l'accélérateur natif écrit en C (`native/nova_core.c`).
//!
//! La configuration `nova_c_accel` est posée par `build.rs` **uniquement**
//! lorsque le module C a été compilé avec succès. Elle est donc fausse si la
//! fonctionnalité est désactivée *ou* si aucun compilateur C n'est disponible :
//! dans les deux cas, c'est l'implémentation Rust ci-dessous qui prend le
//! relais, sans que la compilation échoue.
//!
//! Toutes les fonctions sont appelées sur des tranches Rust bornées (`&str`),
//! jamais sur des chaînes non terminées : l'ABI est donc sûre. Si le module C
//! n'est pas disponible (compilation avec `--no-default-features`), des
//! implémentations Rust équivalentes prennent le relais.

#[cfg(nova_c_accel)]
#[allow(dead_code)] // Certaines fonctions exposées par le module C ne sont pas encore utilisées.
mod ffi {
    use std::os::raw::{c_char, c_int};

    extern "C" {
        pub fn nova_abi_version() -> u32;
        pub fn nova_find_ci(hay: *const c_char, hay_len: usize, needle: *const c_char, needle_len: usize) -> isize;
        pub fn nova_host_of(url: *const c_char, url_len: usize, out: *mut c_char, out_len: usize) -> usize;
        pub fn nova_ends_with_ci(s: *const c_char, s_len: usize, suffix: *const c_char, suffix_len: usize) -> c_int;
        pub fn nova_fnv1a64(data: *const c_char, len: usize) -> u64;
        pub fn nova_utf8_prefix(s: *const c_char, len: usize, max: usize) -> usize;
        pub fn nova_looks_like_host(s: *const c_char, len: usize) -> c_int;
    }
}

/// Nom du moteur de calcul utilisé, affiché dans la page « À propos ».
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

#[cfg(not(nova_c_accel))]
pub fn check_abi() -> bool {
    true
}

/// Recherche insensible à la casse (`needle` dans `hay`).
#[inline]
pub fn find_ci(hay: &str, needle: &str) -> bool {
    if needle.is_empty() || hay.len() < needle.len() {
        return false;
    }
    #[cfg(nova_c_accel)]
    {
        unsafe {
            ffi::nova_find_ci(
                hay.as_ptr() as *const std::os::raw::c_char,
                hay.len(),
                needle.as_ptr() as *const std::os::raw::c_char,
                needle.len(),
            ) >= 0
        }
    }
    #[cfg(not(nova_c_accel))]
    {
        let h = hay.as_bytes();
        let n = needle.as_bytes();
        h.windows(n.len())
            .any(|w| w.eq_ignore_ascii_case(n))
    }
}

/// Extrait l'hôte (minuscules) d'une URL.
#[inline]
pub fn host_of(url: &str) -> String {
    let mut buf = [0u8; 256];
    #[cfg(nova_c_accel)]
    let n = unsafe {
        ffi::nova_host_of(
            url.as_ptr() as *const std::os::raw::c_char,
            url.len(),
            buf.as_mut_ptr() as *mut std::os::raw::c_char,
            buf.len(),
        )
    };
    #[cfg(not(nova_c_accel))]
    let n = {
        let fallback = fallback_host_of(url);
        let bytes = fallback.as_bytes();
        let len = bytes.len().min(buf.len() - 1);
        buf[..len].copy_from_slice(&bytes[..len]);
        len
    };
    String::from_utf8_lossy(&buf[..n]).into_owned()
}

#[cfg(not(nova_c_accel))]
fn fallback_host_of(url: &str) -> String {
    let mut s = url;
    if let Some(pos) = s.find("://") {
        s = &s[pos + 3..];
    }
    let end = s.find(['/', '?', '#']).unwrap_or(s.len());
    s = &s[..end];
    if let Some(at) = s.rfind('@') {
        s = &s[at + 1..];
    }
    if s.starts_with('[') {
        if let Some(close) = s.find(']') {
            s = &s[1..close];
        }
    } else if let Some(colon) = s.find(':') {
        s = &s[..colon];
    }
    s.to_ascii_lowercase()
}

/// `true` si `s` se termine par `suffix` (insensible à la casse).
#[inline]
pub fn ends_with_ci(s: &str, suffix: &str) -> bool {
    if suffix.len() > s.len() || suffix.is_empty() {
        return false;
    }
    #[cfg(nova_c_accel)]
    {
        unsafe {
            ffi::nova_ends_with_ci(
                s.as_ptr() as *const std::os::raw::c_char,
                s.len(),
                suffix.as_ptr() as *const std::os::raw::c_char,
                suffix.len(),
            ) == 1
        }
    }
    #[cfg(not(nova_c_accel))]
    {
        s.as_bytes()[s.len() - suffix.len()..].eq_ignore_ascii_case(suffix.as_bytes())
    }
}

/// Hachage FNV-1a 64 bits (indexation de la liste anti-traqueurs).
#[inline]
pub fn hash64(s: &str) -> u64 {
    #[cfg(nova_c_accel)]
    {
        unsafe { ffi::nova_fnv1a64(s.as_ptr() as *const std::os::raw::c_char, s.len()) }
    }
    #[cfg(not(nova_c_accel))]
    {
        let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
        for b in s.as_bytes() {
            hash ^= *b as u64;
            hash = hash.wrapping_mul(0x100_0000_01b3);
        }
        hash
    }
}

/// Tronque une chaîne sur une frontière de caractère UTF-8.
#[inline]
pub fn truncate(s: &str, max_bytes: usize) -> &str {
    if s.len() <= max_bytes {
        return s;
    }
    #[cfg(nova_c_accel)]
    let n = unsafe { ffi::nova_utf8_prefix(s.as_ptr() as *const std::os::raw::c_char, s.len(), max_bytes) };
    #[cfg(not(nova_c_accel))]
    let n = {
        let mut i = max_bytes;
        while i > 0 && !s.is_char_boundary(i) {
            i -= 1;
        }
        i
    };
    &s[..n]
}

/// `true` si la chaîne ressemble à un nom de domaine.
#[inline]
pub fn looks_like_host(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    #[cfg(nova_c_accel)]
    {
        unsafe { ffi::nova_looks_like_host(s.as_ptr() as *const std::os::raw::c_char, s.len()) == 1 }
    }
    #[cfg(not(nova_c_accel))]
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
        let mut all_letters = true;
        let mut has_letter = false;
        for c in label {
            match c {
                b'a'..=b'z' | b'A'..=b'Z' => has_letter = true,
                b'0'..=b'9' | b'-' => all_letters = false,
                _ => return false,
            }
        }
        if all_letters && has_letter {
            return true;
        }
        // Sinon, seul le punycode est admis (« xn--p1ai » pour .рф).
        label.len() >= 5
            && has_letter
            && label[0].eq_ignore_ascii_case(&b'x')
            && label[1].eq_ignore_ascii_case(&b'n')
            && label[2] == b'-'
            && label[3] == b'-'
    }
}



/// Vérifie que le module C chargé est bien celui attendu.
#[cfg(nova_c_accel)]
pub fn check_abi() -> bool {
    unsafe { ffi::nova_abi_version() == 3 }
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
        for text in ["bonjour le monde", "localhost", "a.b", "test.c0m", "test.123", "-x.com", "x.com-", ".com", "x."] {
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
}
