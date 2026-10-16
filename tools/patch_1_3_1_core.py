#!/usr/bin/env python3
"""Nova 1.3.1 — cœur Rust :
   * neutraliser la demande d'overlay à la source (Game Bar + captures, HKCU) ;
   * mémoriser/restaurer l'état précédent ;
   * assistant au premier lancement : analyse des navigateurs + envoi de l'état ;
   * ne plus importer automatiquement avant la fin de l'assistant.
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


# (platform.rs : déjà patché lors du premier passage)

# =============================================================== config.rs ====
patch("src/config.rs",
"""    /// Empêche le message de Windows « Obtenir une application pour ouvrir ce""",
"""    /// Valeurs (captures, Game DVR) relevées avant que Nova ne les coupe, pour
    /// pouvoir les remettre exactement à l'identique si l'utilisateur décoche.
    #[serde(default)]
    pub dvr_prev: Option<[u32; 2]>,

    /// Coupe le message de Windows qui réclame l'overlay de jeu (Game Bar).""",
      label="config : mémoire des valeurs Game Bar")

# ================================================================= main.rs ====
patch("src/main.rs",
"""/// Arguments passés au moteur de rendu (identiques pour toutes les vues : c'est""",
"""/// Applique le réglage « supprimer le message de Windows » : gestionnaire de
/// secours pour ces adresses, et Game Bar / captures coupées pour le compte
/// courant — sans quoi Windows redemande l'overlay de lui-même. Les valeurs
/// trouvées avant l'intervention sont mémorisées pour être reposées à
/// l'identique si l'utilisateur décoche le réglage.
fn regler_overlay(cfg: &mut Config, cfg_dir: &std::path::Path, actif: bool) {
    if actif {
        let _ = platform::ensure_game_overlay_stub();
        if !platform::game_dvr_disabled() {
            if let Some((captures, dvr)) = platform::game_dvr_values() {
                cfg.dvr_prev = Some([captures, dvr]);
                let _ = cfg.save(cfg_dir);
            }
            let _ = platform::set_game_dvr_disabled(true);
        }
    } else {
        let _ = platform::set_game_overlay_stub(false);
        if let Some([captures, dvr]) = cfg.dvr_prev.take() {
            let _ = platform::set_game_dvr_values(captures, dvr);
            let _ = cfg.save(cfg_dir);
        }
    }
}

/// Arguments passés au moteur de rendu (identiques pour toutes les vues : c'est""",
      label="main : fonction regler_overlay")

patch("src/main.rs",
"""    fn start_auto_import(&mut self) {
        if self.cfg.auto_import && !self.import_auto && self.import_sources.is_empty() {""",
"""    fn start_auto_import(&mut self) {
        // Avant la fin de l'assistant, c'est lui qui demande ce qu'il faut
        // reprendre : l'import silencieux attendrait le prochain démarrage.
        if self.cfg.onboarding_done
            && self.cfg.auto_import
            && !self.import_auto
            && self.import_sources.is_empty()
        {""", label="main : pas d'import silencieux pendant l'assistant")

patch("src/main.rs",
"""    /// Affiche l'assistant de premier lancement (plein écran, au-dessus de tout).
    fn show_welcome(&mut self) -> Result<(), String> {
        let state = self.state_json(true);""",
"""    /// Affiche l'assistant de premier lancement (plein écran, au-dessus de tout).
    fn show_welcome(&mut self) -> Result<(), String> {
        // L'assistant propose de reprendre les données d'un autre navigateur :
        // la liste doit être prête dès l'affichage.
        self.start_import_scan(false);
        let state = self.state_json(true);""", label="main : analyse des navigateurs à l'assistant")

patch("src/main.rs",
"""        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.evaluate_script(&js);
        }""",
"""        if let Some(toolbar) = &self.toolbar {
            let _ = toolbar.evaluate_script(&js);
        }
        // L'assistant de premier lancement suit aussi l'état : liste des
        // navigateurs dès la fin de l'analyse, résultat de l'import ensuite.
        if let Some(welcome) = &self.welcome {
            let _ = welcome.evaluate_script(&ui::render_call(&state));
        }""", label="main : l'assistant reçoit l'état")

patch("src/main.rs",
"""            "stats": {
                "tabs": self.tabs.len(),""",
"""            "overlay": {
                "silenced": self.cfg.silence_game_overlay,
                "dvr_off": platform::game_dvr_disabled(),
                "stub": platform::game_overlay_stub_installed(),
                "game_bar": platform::game_bar_installed(),
                "refused": self.protocols_refused,
                "log": self.cfg_dir.join("protocoles-refuses.log").display().to_string(),
            },
            "stats": {
                "tabs": self.tabs.len(),""", label="main : état des protections dans l'état")

patch("src/main.rs",
"""                    if let Some(on) = overlay_changed {
                        let _ = platform::set_game_overlay_stub(on);
                    }""",
"""                    if let Some(on) = overlay_changed {
                        regler_overlay(&mut self.cfg, &self.cfg_dir, on);
                        self.request_sync();
                    }""", label="main : interrupteur appliqué aux deux verrous")

patch("src/main.rs",
"""                for key in ["block_trackers", "restore_session"] {""",
"""                for key in ["block_trackers", "restore_session", "silence_game_overlay"] {""",
      label="main : l'assistant transmet le réglage overlay")

patch("src/main.rs",
"""                self.cfg.patch(Value::Object(patch));
                self.cfg.save(&self.cfg_dir);

                self.welcome = None;""",
"""                self.cfg.patch(Value::Object(patch));
                self.cfg.save(&self.cfg_dir);
                let silencieux = self.cfg.silence_game_overlay;
                regler_overlay(&mut self.cfg, &self.cfg_dir, silencieux);

                self.welcome = None;""", label="main : l'assistant applique le réglage")

patch("src/main.rs",
"""    // Message de Windows « Obtenir une application pour ouvrir ce lien » :
    // Nova couvre les protocoles de la Game Bar si aucun logiciel ne les gère.
    #[cfg(windows)]
    if cfg.silence_game_overlay {
        let _ = platform::ensure_game_overlay_stub();
    }""",
"""    // Message de Windows « Obtenir une application pour ouvrir ce lien » :
    // Nova couvre les protocoles de la Game Bar si aucun logiciel ne les gère,
    // et coupe la demande à la source (Game Bar et captures du compte courant),
    // sinon Windows la réclame de lui-même (Win+G, manette, jeu lancé).
    if cfg.silence_game_overlay {
        regler_overlay(&mut cfg, &cfg_dir, true);
    }""", label="main : démarrage, les deux verrous")

print("étape cœur : terminée")
