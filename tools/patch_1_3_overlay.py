#!/usr/bin/env python3
"""Correctif 1.3.0 — étape 1 : gestionnaire inerte des protocoles de la Game Bar.

Windows ouvre `ms-gamingoverlay:` de lui-même (touche Win+G, manette branchée).
Sans application pour l'accepter, il affiche « Obtenir une application pour
ouvrir ce lien ». Nova déclare donc ces protocoles pour le compte courant, et
se contente de quitter immédiatement quand il est appelé ainsi.
"""
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


BLOCK = r'''/// Les trois protocoles de la Xbox Game Bar : c'est leur ouverture qui
/// déclenche la boîte de dialogue « Obtenir une application pour ouvrir ce
/// lien » quand aucun logiciel ne les gère.
const GAME_OVERLAY_SCHEMES: [&str; 3] = ["ms-gamingoverlay", "ms-gamebar", "ms-gamebarservices"];

/// Marqueur de la commande enregistrée par Nova : il permet de reconnaître la
/// clé créée ici (et de ne supprimer qu'elle).
pub const OVERLAY_STUB_ARG: &str = "--ignore-protocol";

/// Lit la commande d'ouverture d'un protocole (`shell\open\command`).
#[cfg(windows)]
fn protocol_command(scheme: &str) -> Option<String> {
    use windows::core::PCWSTR;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegOpenKeyExW, RegQueryValueExW, HKEY, HKEY_CLASSES_ROOT, KEY_READ, REG_SZ,
    };

    let path = format!("{scheme}\\shell\\open\\command");
    let wide: Vec<u16> = path.encode_utf16().chain(std::iter::once(0)).collect();
    let mut key = HKEY::default();
    let mut buffer = vec![0u16; 1024];
    let mut size = (buffer.len() * 2) as u32;
    unsafe {
        if RegOpenKeyExW(HKEY_CLASSES_ROOT, PCWSTR(wide.as_ptr()), Some(0), KEY_READ, &mut key)
            .is_err()
        {
            return None;
        }
        let name: Vec<u16> = std::iter::once(0).collect();
        let mut kind = REG_SZ;
        let read = RegQueryValueExW(
            key,
            PCWSTR(name.as_ptr()),
            None,
            Some(&mut kind),
            Some(buffer.as_mut_ptr() as *mut u8),
            Some(&mut size),
        );
        let _ = RegCloseKey(key);
        if read.is_err() {
            return None;
        }
        let len = (size as usize / 2).saturating_sub(1);
        Some(String::from_utf16_lossy(&buffer[..len.min(buffer.len())]))
    }
}

/// La clé enregistrée pour ce protocole est-elle celle de Nova ?
#[cfg(windows)]
pub fn game_overlay_stub_is_ours(scheme: &str) -> bool {
    protocol_command(scheme).is_some_and(|cmd| cmd.contains(OVERLAY_STUB_ARG))
}

#[cfg(not(windows))]
pub fn game_overlay_stub_is_ours(_scheme: &str) -> bool {
    false
}

/// Enregistre (ou retire) pour le compte courant un gestionnaire inerte des
/// protocoles de la Game Bar.
///
/// Windows ouvre `ms-gamingoverlay:` **de lui-même** — touche `Win+G`, ou
/// manette de jeu branchée (Windows tente l'ouverture dès la connexion). Quand
/// aucune application ne l'accepte, il affiche « Obtenir une application pour
/// ouvrir ce lien ». En déclarant ces protocoles dans `HKCU\Software\Classes`,
/// Nova remplit le vide : l'ouverture aboutit sur lui, et il quitte aussitôt.
///
/// Rien n'est écrit dans `HKEY_LOCAL_MACHINE`, aucun droit administrateur n'est
/// requis, et l'opération est réversible : la désactivation supprime exactement
/// la clé créée ici — et rien n'est écrit du tout si un vrai gestionnaire
/// existe déjà (Game Bar installée).
#[cfg(windows)]
pub fn set_game_overlay_stub(enable: bool) -> bool {
    use windows::core::PCWSTR;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegCreateKeyExW, RegDeleteTreeW, RegSetValueExW, HKEY, HKEY_CURRENT_USER,
        KEY_WRITE, REG_OPTION_NON_VOLATILE, REG_SZ,
    };

    fn wide(text: &str) -> Vec<u16> {
        text.encode_utf16().chain(std::iter::once(0)).collect()
    }

    fn write_string(subkey: &str, name: &str, value: &str) -> bool {
        let sub = wide(subkey);
        let mut key = HKEY::default();
        let created = unsafe {
            RegCreateKeyExW(
                HKEY_CURRENT_USER,
                PCWSTR(sub.as_ptr()),
                Some(0),
                PCWSTR::null(),
                REG_OPTION_NON_VOLATILE,
                KEY_WRITE,
                None,
                &mut key,
                None,
            )
        };
        if created.is_err() {
            return false;
        }
        let value_name = wide(name);
        let data = wide(value);
        let written = unsafe {
            RegSetValueExW(
                key,
                PCWSTR(value_name.as_ptr()),
                Some(0),
                REG_SZ,
                Some(data.as_ptr() as *const u8),
                (data.len() * 2) as u32,
            )
        };
        let _ = unsafe { RegCloseKey(key) };
        written.is_ok()
    }

    let exe = std::env::current_exe()
        .map(|p| p.display().to_string())
        .unwrap_or_default();
    let mut ok = true;
    for scheme in GAME_OVERLAY_SCHEMES {
        let root = format!("Software\\Classes\\{scheme}");
        if enable {
            ok &= write_string(&root, "", "URL:Nova")
                && write_string(&root, "URL Protocol", "")
                && write_string(&format!("{root}\\shell\\open\\command"), "", &format!("\"{exe}\" {OVERLAY_STUB_ARG}"));
        } else if game_overlay_stub_is_ours(scheme) {
            let sub = wide(&root);
            ok &= unsafe { RegDeleteTreeW(HKEY_CURRENT_USER, PCWSTR(sub.as_ptr())) }.is_ok();
        }
    }
    ok
}

#[cfg(not(windows))]
pub fn set_game_overlay_stub(_enable: bool) -> bool {
    false
}

/// Installe le gestionnaire inerte **uniquement** là où il manque : si un vrai
/// gestionnaire existe (Game Bar installée), Nova ne touche à rien.
#[cfg(windows)]
pub fn ensure_game_overlay_stub() -> bool {
    let manquant = GAME_OVERLAY_SCHEMES
        .iter()
        .any(|s| !game_overlay_stub_is_ours(s) && !scheme_handler_exists(s));
    if manquant {
        set_game_overlay_stub(true)
    } else {
        true
    }
}

#[cfg(not(windows))]
pub fn ensure_game_overlay_stub() -> bool {
    false
}

'''

patch("src/platform.rs",
      "/// Ouvre la boîte de dialogue système « ouvrir un fichier » et renvoie le",
      BLOCK + "/// Ouvre la boîte de dialogue système « ouvrir un fichier » et renvoie le",
      label="platform : gestionnaire inerte")

# ---- config : réglage persisté -------------------------------------------------
patch("src/config.rs",
      """    /// Relit les navigateurs installés au démarrage et importe les données
    /// nouvelles (favoris et historique). Sans effet une fois tout importé :
    /// un import ne crée jamais de doublon.
    pub auto_import: bool,
}""",
      """    /// Relit les navigateurs installés au démarrage et importe les données
    /// nouvelles (favoris et historique). Sans effet une fois tout importé :
    /// un import ne crée jamais de doublon.
    pub auto_import: bool,
    /// Empêche le message de Windows « Obtenir une application pour ouvrir ce
    /// lien » : Nova accepte les protocoles de la Xbox Game Bar pour le compte
    /// courant (`HKCU\\Software\\Classes`) et les ignore. Sans effet si la
    /// Game Bar est réellement installée.
    pub silence_game_overlay: bool,
    /// Apparence de l'interface : `arc` (sobre, par défaut) ou `classique`.
    pub skin: String,
}""", label="config : silence_game_overlay + skin")

patch("src/config.rs",
      """            auto_import: true,
        }""",
      """            auto_import: true,
            silence_game_overlay: true,
            skin: "arc".into(),
        }""", label="config : valeurs par défaut")

patch("src/config.rs",
      """        if !matches!(self.theme.as_str(), "dark" | "light" | "system") {""",
      """        if !matches!(self.skin.as_str(), "arc" | "classique") {
            self.skin = "arc".into();
        }
        if !matches!(self.theme.as_str(), "dark" | "light" | "system") {""",
      label="config : skin validé")

# ---- main : argument, réglage appliqué au démarrage, IPC ----------------------
patch("src/main.rs",
      """fn main() {
    platform::init();
""",
      """fn main() {
    // Appelé par Windows pour un protocole que Nova a accepté de « couvrir »
    // (overlay de jeu) : il n'y a rien à faire, et surtout rien à afficher.
    if std::env::args().any(|a| a == platform::OVERLAY_STUB_ARG) {
        return;
    }

    platform::init();
""", label="main : argument --ignore-protocol")

patch("src/main.rs",
      """    let cfg_dir = config::data_dir();
    let cfg = Config::load(&cfg_dir);
    let history = History::load(&cfg_dir);
""",
      """    let cfg_dir = config::data_dir();
    let cfg = Config::load(&cfg_dir);
    let history = History::load(&cfg_dir);

    // Message de Windows « Obtenir une application pour ouvrir ce lien » :
    // Nova couvre les protocoles de la Game Bar si aucun logiciel ne les gère.
    #[cfg(windows)]
    if cfg.silence_game_overlay {
        let _ = platform::ensure_game_overlay_stub();
    }
""", label="main : installe le gestionnaire inerte")

patch("src/main.rs",
      """            "set_config" => {
                if let Some(patch) = cmd.get("patch") {
                    let theme_changed = patch.get("theme").is_some();""",
      """            "set_config" => {
                if let Some(patch) = cmd.get("patch") {
                    let theme_changed = patch.get("theme").is_some();
                    let skin_changed = patch.get("skin").is_some()
                        && patch.get("skin").and_then(Value::as_str) != Some(self.cfg.skin.as_str());
                    // Interrupteur du message de Windows : appliqué tout de suite.
                    let overlay_changed = patch
                        .get("silence_game_overlay")
                        .and_then(Value::as_bool);""",
      label="set_config : détection")

patch("src/main.rs",
      """                    if theme_changed {
                        self.set_theme();
                    } else if width_changed {""",
      """                    if let Some(on) = overlay_changed {
                        let _ = platform::set_game_overlay_stub(on);
                    }
                    if skin_changed {
                        self.reload_internal_pages();
                    }
                    if theme_changed {
                        self.set_theme();
                    } else if width_changed {""", label="set_config : application")

print("étape 1 : code posé")
