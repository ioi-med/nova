//! Script de compilation de Nova.
//!
//! 1. Compile l'accélérateur natif écrit en C (`native/nova_core.c`) et le
//!    transforme en bibliothèque statique liée au binaire Rust.
//! 2. Sous Windows, attache l'icône, les métadonnées de version et le
//!    manifeste (DPI par écran, Windows 10/11, UTF-8) à l'exécutable.

fn main() {
    // Configuration posée par ce script si (et seulement si) le module C a
    // réellement été compilé : `src/accel.rs` s'en sert pour choisir entre
    // l'appel natif et l'implémentation Rust équivalente.
    println!("cargo:rustc-check-cfg=cfg(nova_c_accel)");
    println!("cargo:rerun-if-changed=native/nova_core.c");
    println!("cargo:rerun-if-changed=native/nova_core.h");
    println!("cargo:rerun-if-changed=assets/nova.rc");
    println!("cargo:rerun-if-changed=assets/nova.ico");

    compile_native_accelerator();
    compile_windows_resources();
}

/// Accélérateur C : recherche de motifs, extraction d'hôtes, hachage, découpe UTF-8.
#[cfg(feature = "native-accel")]
fn compile_native_accelerator() {
    let target_os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let mut build = cc::Build::new();

    build
        .file("native/nova_core.c")
        .include("native")
        .opt_level(3)
        .warnings(true)
        .define("NOVA_TARGET_WINDOWS", if target_os == "windows" { "1" } else { "0" });

    // Windows : on active les intrinsèques de comparaison d'octets disponibles sur x86_64.
    if target_os == "windows" && std::env::var("CARGO_CFG_TARGET_ARCH").as_deref() == Ok("x86_64") {
        build.flag_if_supported("/arch:AVX2");
        build.flag_if_supported("-mavx2");
    }

    // `try_compile` plutôt que `compile` : sans compilateur C (ou si la chaîne
    // est incomplète), on prévient et on continue avec le repli Rust au lieu
    // d'échouer sur un message obscur du type « lib.exe not found ».
    match build.try_compile("nova_core") {
        Ok(()) => println!("cargo:rustc-cfg=nova_c_accel"),
        Err(err) => println!(
            "cargo:warning=accélérateur C non compilé ({err}) : repli sur l'implémentation Rust"
        ),
    }
}

#[cfg(not(feature = "native-accel"))]
fn compile_native_accelerator() {}

fn compile_windows_resources() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() != Ok("windows") {
        return;
    }

    let mut res = winresource::WindowsResource::new();
    if std::path::Path::new("assets/nova.ico").exists() {
        res.set_icon("assets/nova.ico");
    }
    res.set("ProductName", "Nova");
    res.set("FileDescription", "Nova — navigateur web à onglets verticaux");
    res.set("CompanyName", "Nova");
    res.set("LegalCopyright", "MIT");
    res.set("OriginalFilename", "nova.exe");
    res.set(
        "FileVersion",
        &format!("{}.0", env!("CARGO_PKG_VERSION")),
    );
    res.set("ProductVersion", env!("CARGO_PKG_VERSION"));
    res.set_manifest(MANIFEST);

    if let Err(err) = res.compile() {
        // Pas de compilateur de ressources ? On continue : le binaire reste fonctionnel,
        // il n'aura simplement pas d'icône ni de manifeste embarqué.
        println!("cargo:warning=ressources Windows non compilées : {err}");
    }
}

const MANIFEST: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="Nova.Browser" version="1.0.0.0" processorArchitecture="*"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
      <supportedOS Id="{4f476546-937e-4f26-8c72-90b8bd5ba8e8}"/>
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}"/>
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
    </application>
  </compatibility>
  <application xmlns="urn:schemas-microsoft-com:asm.v3">
    <windowsSettings>
      <dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>
      <dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">permonitorv2,permonitor</dpiAwareness>
      <longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware>
      <activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">UTF-8</activeCodePage>
    </windowsSettings>
  </application>
</assembly>
"#;
