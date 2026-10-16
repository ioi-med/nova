//! Code spécifique à la plateforme.
//!
//! Sous Windows : icône et thème de la barre de titre (API DWM), détection du
//! thème système (Registre), réglages fins du contrôleur WebView2 (COM) et
//! boîtes de dialogue d'erreur natives. Ailleurs : équivalents inertes, ce qui
//! permet de compiler et tester la même base de code sous Linux/macOS.

#![allow(unused_variables)]
// La compilation hôte (tests, Linux) n'utilise qu'une partie des aides Windows.
#![cfg_attr(not(windows), allow(dead_code))]

use tao::window::Window;
use wry::WebView;

/// Surveille le plein écran demandé **par la page** (lecteur vidéo, diaporama).
///
/// `ICoreWebView2::ContainsFullScreenElementChanged` est l'événement officiel du
/// moteur : il est levé dès qu'un élément du document passe en plein écran, sans
/// dépendre du JavaScript de la page (certains moteurs ne dispatchant pas
/// `fullscreenchange`, un simple écouteur JS ne suffisait pas).
///
/// Le rappel est invoqué sur le fil de la boucle d'événements : il doit donc se
/// contenter d'envoyer un message, jamais de manipuler l'interface.
#[cfg(windows)]
pub fn watch_fullscreen<F>(webview: &WebView, notify: F)
where
    F: Fn(bool) + 'static,
{
    use webview2_com::ContainsFullScreenElementChangedEventHandler;
    use wry::WebViewExtWindows;

    let core = webview.webview();
    // Le gestionnaire est conservé par COM (AddRef) : on peut le laisser ici
    // sans le retirer, l'événement devant vivre aussi longtemps que la vue.
    let handler = ContainsFullScreenElementChangedEventHandler::create(Box::new(
        move |sender, _args| {
            if let Some(core) = sender {
                // `ContainsFullScreenElement` lit la propriété du moteur :
                // écrite en `BOOL` (entier 32 bits), pas en `bool`.
                let mut value = windows::core::BOOL(0);
                unsafe {
                    if core.ContainsFullScreenElement(&mut value).is_ok() {
                        notify(value.as_bool());
                    }
                }
            }
            Ok(())
        },
    ));
    let mut token = 0i64;
    unsafe {
        let _ = core.add_ContainsFullScreenElementChanged(&handler, &mut token);
    }
}

/// Sans Windows, la fonction existe mais ne fait rien (tests sur l'hôte).
#[cfg(not(windows))]
pub fn watch_fullscreen<F>(_webview: &WebView, _notify: F)
where
    F: Fn(bool) + 'static,
{
}

/// Windows sait-il ouvrir ce protocole ? (autrement dit : existe-t-il un
/// logiciel associé à `mailto:`, `ms-settings:`, `steam:`…)
///
/// Lecture du registre dans la vue fusionnée `HKEY_CLASSES_ROOT` : un protocole
/// est ouvrable s'il déclare `URL Protocol` **et** une commande
/// `shell\open\command`. Ailleurs qu'à Windows, la réponse est toujours non.
#[cfg(windows)]
pub fn scheme_handler_exists(scheme: &str) -> bool {
    use windows::core::PCWSTR;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegOpenKeyExW, RegQueryValueExW, HKEY, HKEY_CLASSES_ROOT, KEY_READ, REG_NONE,
    };

    fn key_exists(parent: HKEY, path: &str) -> Option<HKEY> {
        let wide: Vec<u16> = path.encode_utf16().chain(std::iter::once(0)).collect();
        let mut key = HKEY::default();
        let status = unsafe { RegOpenKeyExW(parent, PCWSTR(wide.as_ptr()), Some(0), KEY_READ, &mut key) };
        status.is_ok().then_some(key)
    }

    /// Le protocole doit déclarer `URL Protocol` (valeur présente, même vide).
    fn declares_url_protocol(key: &HKEY) -> bool {
        let name: Vec<u16> = "URL Protocol".encode_utf16().chain(std::iter::once(0)).collect();
        // Interroger sans tampon de données (`lpData` et `lpcbData` nuls) suffit
        // à savoir si la valeur existe : c'est la marque d'un vrai protocole.
        let mut kind = REG_NONE;
        let status = unsafe {
            RegQueryValueExW(*key, PCWSTR(name.as_ptr()), None, Some(&mut kind), None, None)
        };
        status.is_ok()
    }

    let Some(root) = key_exists(HKEY_CLASSES_ROOT, scheme) else {
        return false;
    };
    let declared = declares_url_protocol(&root);
    let command = key_exists(root, "shell\\open\\command");
    unsafe {
        if let Some(key) = command {
            let _ = RegCloseKey(key);
        }
        let _ = RegCloseKey(root);
    }
    declared && command.is_some()
}

#[cfg(not(windows))]
pub fn scheme_handler_exists(_scheme: &str) -> bool {
    false
}

/// Confie une adresse à Windows (protocole du système : `mailto:`,
/// `ms-settings:`, `steam:`…). Retourne `false` si Windows n'a rien pu ouvrir —
/// auquel cas rien ne doit être tenté : c'est ce cas qui déclenchait la boîte de
/// dialogue « Obtenir une application pour ouvrir ce lien ».
#[cfg(windows)]
pub fn open_external(url: &str) -> bool {
    use windows::core::HSTRING;
    use windows::Win32::UI::Shell::ShellExecuteW;
    use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;

    let wide = HSTRING::from(url);
    let verb = HSTRING::from("open");
    let result = unsafe {
        ShellExecuteW(None, &verb, &wide, None, None, SW_SHOWNORMAL)
    };
    // ShellExecute renvoie une valeur <= 32 en cas d'échec.
    result.0 as usize > 32
}

#[cfg(not(windows))]
pub fn open_external(_url: &str) -> bool {
    false
}

/// Les trois protocoles de la Xbox Game Bar : c'est leur ouverture qui
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
        // La vue `windows` veut les données en octets (chaîne UTF-16 terminée
        // par un zéro, la longueur se déduit de la tranche).
        let data: Vec<u8> = wide(value).iter().flat_map(|u| u.to_ne_bytes()).collect();
        let written = unsafe {
            RegSetValueExW(key, PCWSTR(value_name.as_ptr()), Some(0), REG_SZ, Some(&data))
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

/// Clés du compte courant où Windows range les réglages de la Game Bar.
/// C'est Windows lui-même qui réclame l'overlay (touche `Win+G`, manette
/// branchée, démarrage d'un jeu) : tant que ces deux valeurs autorisent la
/// capture, il redemande l'ouverture et la boîte revient. Les couper pour le
/// seul compte de l'utilisateur supprime la demande à la source.
pub const GAME_DVR_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\GameDVR";
pub const GAME_CONFIG_STORE_KEY: &str = r"System\GameConfigStore";

/// Chaîne large terminée par un zéro.
#[cfg(windows)]
fn wide_z(text: &str) -> Vec<u16> {
    text.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Lit une valeur DWORD du compte courant (`None` si absente).
#[cfg(windows)]
fn read_dword(subkey: &str, value: &str) -> Option<u32> {
    use windows::core::PCWSTR;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegOpenKeyExW, RegQueryValueExW, HKEY, HKEY_CURRENT_USER, KEY_READ,
        REG_DWORD, REG_NONE,
    };

    let sub = wide_z(subkey);
    let name = wide_z(value);
    let mut key = HKEY::default();
    let opened = unsafe {
        RegOpenKeyExW(HKEY_CURRENT_USER, PCWSTR(sub.as_ptr()), Some(0), KEY_READ, &mut key)
    };
    if opened.is_err() {
        return None;
    }
    let mut kind = REG_NONE;
    let mut data = [0u8; 4];
    let mut size = data.len() as u32;
    let got = unsafe {
        RegQueryValueExW(
            key,
            PCWSTR(name.as_ptr()),
            None,
            Some(&mut kind),
            Some(data.as_mut_ptr()),
            Some(&mut size),
        )
    };
    let _ = unsafe { RegCloseKey(key) };
    if got.is_err() || size < 4 || kind != REG_DWORD {
        return None;
    }
    Some(u32::from_ne_bytes(data))
}

/// Écrit une valeur DWORD du compte courant (crée la clé au besoin).
#[cfg(windows)]
fn write_dword(subkey: &str, value: &str, data: u32) -> bool {
    use windows::core::PCWSTR;
    use windows::Win32::System::Registry::{
        RegCloseKey, RegCreateKeyExW, RegSetValueExW, HKEY, HKEY_CURRENT_USER, KEY_WRITE,
        REG_DWORD, REG_OPTION_NON_VOLATILE,
    };

    let sub = wide_z(subkey);
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
    let name = wide_z(value);
    let bytes = data.to_ne_bytes();
    let written =
        unsafe { RegSetValueExW(key, PCWSTR(name.as_ptr()), Some(0), REG_DWORD, Some(&bytes)) };
    let _ = unsafe { RegCloseKey(key) };
    written.is_ok()
}

/// Couple (captures, Game DVR) tel que Windows le voit aujourd'hui.
#[cfg(windows)]
pub fn game_dvr_values() -> Option<(u32, u32)> {
    let captures = read_dword(GAME_DVR_KEY, "AppCaptureEnabled")?;
    let dvr = read_dword(GAME_CONFIG_STORE_KEY, "GameDVR_Enabled")?;
    Some((captures, dvr))
}

#[cfg(not(windows))]
pub fn game_dvr_values() -> Option<(u32, u32)> {
    None
}

/// `true` si les captures et la Game Bar sont déjà coupées pour ce compte.
#[cfg(windows)]
pub fn game_dvr_disabled() -> bool {
    read_dword(GAME_DVR_KEY, "AppCaptureEnabled") == Some(0)
        && read_dword(GAME_CONFIG_STORE_KEY, "GameDVR_Enabled") == Some(0)
}

#[cfg(not(windows))]
pub fn game_dvr_disabled() -> bool {
    false
}

/// Coupe (ou rétablit) captures et Game Bar pour le compte courant.
#[cfg(windows)]
pub fn set_game_dvr_disabled(disable: bool) -> bool {
    let actif = u32::from(!disable);
    let a = write_dword(GAME_DVR_KEY, "AppCaptureEnabled", actif);
    let b = write_dword(GAME_CONFIG_STORE_KEY, "GameDVR_Enabled", actif);
    a && b
}

#[cfg(not(windows))]
pub fn set_game_dvr_disabled(_disable: bool) -> bool {
    false
}

/// Repose exactement les valeurs mémorisées avant l'intervention de Nova.
#[cfg(windows)]
pub fn set_game_dvr_values(captures: u32, dvr: u32) -> bool {
    let a = write_dword(GAME_DVR_KEY, "AppCaptureEnabled", captures);
    let b = write_dword(GAME_CONFIG_STORE_KEY, "GameDVR_Enabled", dvr);
    a && b
}

#[cfg(not(windows))]
pub fn set_game_dvr_values(_captures: u32, _dvr: u32) -> bool {
    false
}

/// Le gestionnaire de secours de Nova couvre-t-il ces protocoles ?
#[cfg(windows)]
pub fn game_overlay_stub_installed() -> bool {
    GAME_OVERLAY_SCHEMES.iter().all(|s| game_overlay_stub_is_ours(s))
}

#[cfg(not(windows))]
pub fn game_overlay_stub_installed() -> bool {
    false
}

/// La Xbox Game Bar est-elle réellement installée (vrai gestionnaire) ?
#[cfg(windows)]
pub fn game_bar_installed() -> bool {
    GAME_OVERLAY_SCHEMES
        .iter()
        .any(|s| !game_overlay_stub_is_ours(s) && scheme_handler_exists(s))
}

#[cfg(not(windows))]
pub fn game_bar_installed() -> bool {
    false
}

/// Commande enregistrée par Nova quand le fichier a été déplacé ou renommé :
/// la clé doit alors être réécrite, sinon Windows chercherait un exécutable
/// absent.
#[cfg(windows)]
fn stub_is_stale(scheme: &str) -> bool {
    let Some(cmd) = protocol_command(scheme) else {
        return false;
    };
    if !cmd.contains(OVERLAY_STUB_ARG) {
        return false;
    }
    let exe = std::env::current_exe()
        .map(|p| p.display().to_string())
        .unwrap_or_default();
    !cmd.contains(&exe)
}

/// Installe (ou répare) le gestionnaire inerte **uniquement** là où il manque :
/// si un vrai gestionnaire existe (Game Bar installée), Nova ne touche à rien.
#[cfg(windows)]
pub fn ensure_game_overlay_stub() -> bool {
    let a_ecrire = GAME_OVERLAY_SCHEMES
        .iter()
        .any(|s| (!game_overlay_stub_is_ours(s) && !scheme_handler_exists(s)) || stub_is_stale(s));
    if a_ecrire {
        set_game_overlay_stub(true)
    } else {
        true
    }
}

#[cfg(not(windows))]
pub fn ensure_game_overlay_stub() -> bool {
    false
}

/// Ouvre la boîte de dialogue système « ouvrir un fichier » et renvoie le
/// chemin choisi (`None` si l'utilisateur ferme la fenêtre).
///
/// Appelée depuis un fil dédié : la boîte de dialogue possède sa propre boucle
/// de messages et la fenêtre de Nova reste réactive. Ailleurs qu'à Windows
/// (build de développement et tests), la fonction se contente de refuser.
#[cfg(windows)]
pub fn pick_file() -> Option<std::path::PathBuf> {
    rfd::FileDialog::new()
        .set_title("Fichier à importer (favoris ou historique)")
        .add_filter(
            "Données de navigateur",
            &["html", "htm", "json", "sqlite", "db", "sqlite3"],
        )
        .add_filter("Tous les fichiers", &["*"])
        .pick_file()
}

#[cfg(not(windows))]
pub fn pick_file() -> Option<std::path::PathBuf> {
    None
}

/// Réglages appliqués au moteur de rendu au moment de la création.
#[derive(Clone, Copy, Debug)]
#[cfg_attr(not(windows), allow(dead_code))]
pub struct WebPrefs {
    pub context_menus: bool,
    pub devtools: bool,
    pub passwords: bool,
}

impl Default for WebPrefs {
    fn default() -> Self {
        Self {
            context_menus: true,
            devtools: true,
            passwords: true,
        }
    }
}

/// À appeler une fois, avant toute création de fenêtre.
pub fn init() {
    #[cfg(windows)]
    {
        use windows::Win32::UI::HiDpi::{SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};
        use windows::Win32::UI::Shell::SetCurrentProcessExplicitAppUserModelID;
        use windows::core::HSTRING;

        unsafe {
            // Ignoré si le manifeste a déjà fixé la conscience DPI (cas normal).
            let _ = SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
            // Regroupe les fenêtres de Nova sous une identité propre dans la barre des tâches.
            let _ = SetCurrentProcessExplicitAppUserModelID(&HSTRING::from("Nova.Browser"));
        }
    }
}

/// Le système demande-t-il un thème sombre ?
pub fn system_prefers_dark() -> bool {
    #[cfg(windows)]
    {
        use windows::core::w;
        use windows::Win32::System::Registry::{RegGetValueW, HKEY_CURRENT_USER, RRF_RT_REG_DWORD};

        let mut value: u32 = 1;
        let mut size = std::mem::size_of::<u32>() as u32;
        let status = unsafe {
            RegGetValueW(
                HKEY_CURRENT_USER,
                w!("Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"),
                w!("AppsUseLightTheme"),
                RRF_RT_REG_DWORD,
                None,
                Some(&mut value as *mut _ as *mut core::ffi::c_void),
                Some(&mut size),
            )
        };
        // AppsUseLightTheme = 0 -> le système est en thème sombre.
        status == windows::Win32::Foundation::ERROR_SUCCESS && value == 0
    }
    #[cfg(not(windows))]
    {
        true
    }
}

/// Applique le thème sombre/clair à la barre de titre et arrondit les coins.
pub fn style_window(window: &Window, dark: bool) {
    #[cfg(windows)]
    {
        use std::ffi::c_void;
        use windows::Win32::Graphics::Dwm::{
            DwmSetWindowAttribute, DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_WINDOW_CORNER_PREFERENCE,
        };

        let Some(hwnd) = window_hwnd(window) else {
            return;
        };

        unsafe {
            let dark_flag: i32 = i32::from(dark);
            let _ = DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                &dark_flag as *const _ as *const c_void,
                std::mem::size_of::<i32>() as u32,
            );

            // Coins arrondis (Windows 11) : DWMWCP_ROUND = 2.
            let corner: i32 = 2;
            let _ = DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                &corner as *const _ as *const c_void,
                std::mem::size_of::<i32>() as u32,
            );
        }
    }
}

/// Handle brut de la fenêtre (indépendant de la version du crate `windows`).
#[cfg(windows)]
fn window_hwnd(window: &Window) -> Option<windows::Win32::Foundation::HWND> {
    use raw_window_handle::{HasWindowHandle, RawWindowHandle};
    use windows::Win32::Foundation::HWND;

    let handle = window.window_handle().ok()?;
    match handle.as_raw() {
        RawWindowHandle::Win32(win) => Some(HWND(win.hwnd.get() as *mut core::ffi::c_void)),
        _ => None,
    }
}

/// Réglages fins du contrôleur WebView2 (barre d'état, menus, autofill…).
pub fn tune_webview(webview: &WebView, prefs: WebPrefs, dark: bool) {
    #[cfg(windows)]
    {
        use webview2_com::Microsoft::Web::WebView2::Win32::{
            ICoreWebView2Controller2, ICoreWebView2Settings4, ICoreWebView2Settings5,
            ICoreWebView2Settings6, COREWEBVIEW2_COLOR,
        };
        use windows::core::Interface;
        use wry::WebViewExtWindows;

        let controller = webview.controller();
        let core = webview.webview();
        unsafe {
            if let Ok(settings) = core.Settings() {
                let _ = settings.SetAreDefaultContextMenusEnabled(prefs.context_menus);
                let _ = settings.SetAreDevToolsEnabled(prefs.devtools);
                let _ = settings.SetIsZoomControlEnabled(true);

                // Les réglages suivants n'existent que sur les versions récentes
                // du moteur : on tente la conversion et on ignore l'échec.
                if let Ok(forms) = settings.cast::<ICoreWebView2Settings4>() {
                    let _ = forms.SetIsPasswordAutosaveEnabled(prefs.passwords);
                    let _ = forms.SetIsGeneralAutofillEnabled(prefs.passwords);
                }
                if let Ok(zoom) = settings.cast::<ICoreWebView2Settings5>() {
                    let _ = zoom.SetIsPinchZoomEnabled(true);
                }
                if let Ok(gestures) = settings.cast::<ICoreWebView2Settings6>() {
                    let _ = gestures.SetIsSwipeNavigationEnabled(false);
                }
            }

            // Fond appliqué pendant le chargement : évite le flash blanc.
            let background = if dark {
                COREWEBVIEW2_COLOR { A: 255, R: 26, G: 26, B: 31 }
            } else {
                COREWEBVIEW2_COLOR { A: 255, R: 255, G: 255, B: 255 }
            };
            if let Ok(controller2) = controller.cast::<ICoreWebView2Controller2>() {
                let _ = controller2.SetDefaultBackgroundColor(background);
            }
        }
    }
}

/// Arrête le chargement en cours (WebView2 ne l'expose pas via `wry`).
pub fn stop_webview(webview: &WebView) {
    #[cfg(windows)]
    {
        use wry::WebViewExtWindows;

        let core = webview.webview();
        unsafe {
            let _ = core.Stop();
        }
    }
    #[cfg(not(windows))]
    {
        let _ = webview;
    }
}

/// Place du texte dans le presse-papiers (implémentation Win32 directe).
pub fn set_clipboard_text(text: &str) -> bool {
    #[cfg(windows)]
    {
        use windows::Win32::Foundation::HANDLE;
        // CF_UNICODETEXT = 13 (constante du presse-papiers Windows).
        const CF_UNICODETEXT: u32 = 13;
        use windows::Win32::System::DataExchange::{
            CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData,
        };
        use windows::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};

        unsafe {
            if OpenClipboard(None).is_err() {
                return false;
            }
            let _ = EmptyClipboard();
            let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
            let bytes = wide.len() * std::mem::size_of::<u16>();
            let Ok(mem) = GlobalAlloc(GMEM_MOVEABLE, bytes) else {
                let _ = CloseClipboard();
                return false;
            };
            let ptr = GlobalLock(mem);
            if ptr.is_null() {
                let _ = CloseClipboard();
                return false;
            }
            std::ptr::copy_nonoverlapping(wide.as_ptr() as *const u8, ptr as *mut u8, bytes);
            let _ = GlobalUnlock(mem);
            let ok = SetClipboardData(CF_UNICODETEXT, Some(HANDLE(mem.0))).is_ok();
            let _ = CloseClipboard();
            ok
        }
    }
    #[cfg(not(windows))]
    {
        let _ = text;
        false
    }
}

/// Ouvre un dossier dans l'explorateur de fichiers du système.
pub fn open_in_explorer(path: &str) {
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("explorer").arg(path).spawn();
    }
    #[cfg(not(windows))]
    {
        let _ = std::process::Command::new("xdg-open").arg(path).spawn();
    }
}

/// Message d'erreur bloquant, affiché avec les boîtes de dialogue natives.
pub fn fatal(title: &str, message: &str) -> ! {
    #[cfg(windows)]
    {
        use windows::core::HSTRING;
        use windows::Win32::UI::WindowsAndMessaging::{MessageBoxW, MB_ICONERROR, MB_OK, MB_SETFOREGROUND};

        let caption = HSTRING::from(title);
        let text = HSTRING::from(message);
        unsafe {
            MessageBoxW(None, &text, &caption, MB_OK | MB_ICONERROR | MB_SETFOREGROUND);
        }
    }
    #[cfg(not(windows))]
    {
        eprintln!("{title} : {message}");
    }
    std::process::exit(1)
}
