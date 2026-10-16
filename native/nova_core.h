/*
 * nova_core.h — accélérateur natif de Nova (C11)
 *
 * Ce module regroupe les opérations « chaudes » du pipeline d'URL et de la
 * liste de blocage (anti-traqueurs). Elles sont volontairement écrites en C
 * pur, sans allocation, afin d'être appelées depuis Rust sans coût de
 * conversion et d'être compilées en code machine optimal (clang-cl / GCC).
 */
#ifndef NOVA_CORE_H
#define NOVA_CORE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Version de l'ABI : permet à Rust de vérifier que le module C est bien le sien. */
#define NOVA_ABI_VERSION 3

uint32_t nova_abi_version(void);

/*
 * Recherche d'une sous-chaîne en ignorant la casse ASCII (Boyer-Moore-Horspool).
 * Retourne l'index de la première occurrence, ou -1.
 * Utilisé pour faire correspondre une URL à la liste de blocage.
 */
ptrdiff_t nova_find_ci(const char *hay, size_t hay_len, const char *needle, size_t needle_len);

/*
 * Extrait le nom d'hôte d'une URL (sans schéma, sans port, sans userinfo,
 * sans chemin) et le recopie en minuscules dans `out`.
 * Retourne le nombre d'octets écrits (0 si aucun hôte trouvé).
 * `out` est toujours terminé par un octet nul si out_len > 0.
 */
size_t nova_host_of(const char *url, size_t url_len, char *out, size_t out_len);

/*
 * Vrai (1) si `s` se termine par `suffix`, en ignorant la casse ASCII.
 */
int nova_ends_with_ci(const char *s, size_t s_len, const char *suffix, size_t suffix_len);

/*
 * Hachage FNV-1a 64 bits : indexation rapide de la liste de blocage.
 */
uint64_t nova_fnv1a64(const char *data, size_t len);

/*
 * Longueur (en octets) maximale ≤ max_bytes qui ne coupe pas un caractère
 * UTF-8 en deux. Évite les titres d'onglets tronqués au milieu d'un accent.
 */
size_t nova_utf8_prefix(const char *s, size_t len, size_t max_bytes);

/*
 * Vrai (1) si la chaîne ressemble à un nom de domaine (« example.com ») :
 * uniquement [a-z0-9.-], au moins un point, pas de point en début/fin, et un
 * dernier label plausible (2 à 63 caractères alphanumériques ou tirets avec au
 * moins une lettre — ce qui couvre le punycode des domaines internationalisés).
 */
int nova_looks_like_host(const char *s, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* NOVA_CORE_H */
