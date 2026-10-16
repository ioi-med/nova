//! Liste locale de blocage (publicité & traqueurs) et moteur de correspondance.
//!
//! La correspondance s'appuie sur l'accélérateur C : recherche de motifs
//! Boyer-Moore-Horspool + comparaison de suffixe, ce qui permet de tester
//! ~150 domaines par navigation sans coût perceptible.

use crate::accel;

pub struct Blocker {
    /// Domaine suivi de sa version « préfixée par un point » pour le test de suffixe.
    domains: Vec<(&'static str, String)>,
}

impl Blocker {
    pub fn new() -> Self {
        let mut domains: Vec<(&'static str, String)> = include_str!("../assets/trackers.txt")
            .lines()
            .map(|l| l.trim())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .map(|l| (l, format!(".{l}")))
            .collect();
        domains.sort_by_key(|(d, _)| *d);
        Self { domains }
    }

    pub fn len(&self) -> usize {
        self.domains.len()
    }

    #[allow(dead_code)] // API publique du module.
    pub fn is_empty(&self) -> bool {
        self.domains.is_empty()
    }

    /// `true` si l'hôte appartient à un domaine de la liste (sous-domaines inclus).
    pub fn is_blocked(&self, host: &str) -> bool {
        if host.is_empty() {
            return false;
        }
        self.domains.iter().any(|(domain, dotted)| {
            (host.len() == domain.len() && accel::find_ci(host, domain))
                || accel::ends_with_ci(host, dotted)
        })
    }

    /// Vérifie une URL complète (utilisé pour les redirections publicitaires).
    #[allow(dead_code)]
    pub fn is_blocked_url(&self, url: &str) -> bool {
        let host = accel::host_of(url);
        if self.is_blocked(&host) {
            return true;
        }
        // Filet de sécurité : certains liens de suivi passent l'hôte en paramètre.
        self.domains
            .iter()
            .any(|(_, dotted)| accel::find_ci(url, dotted))
    }

    /// Liste de règles passée au moteur de rendu.
    ///
    /// Les domaines concernés sont résolus en `~NOTFOUND`, c'est-à-dire un
    /// échec de résolution immédiat : plus rapide qu'une redirection vers
    /// `0.0.0.0`, qui oblige le moteur à ouvrir une connexion (et qui, sous
    /// Windows, aboutit à la machine locale). Le blocage est instantané et
    /// aucune connexion n'est tentée.
    pub fn resolver_rules(&self, max_hosts: usize) -> String {
        let mut arg = String::from("--host-resolver-rules=");
        let mut first = true;
        // `max_hosts` doit couvrir toute la liste : une limite trop basse
        // désactiverait silencieusement une partie du filtrage.
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
    }
}

impl Default for Blocker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocage_sous_domaines() {
        let b = Blocker::new();
        assert!(b.len() > 50);
        assert!(b.is_blocked("ads.doubleclick.net"));
        assert!(b.is_blocked("doubleclick.net"));
        assert!(!b.is_blocked("mydoubleclick.net"));
        assert!(!b.is_blocked("github.com"));
    }
}
