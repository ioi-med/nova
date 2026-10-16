/*
 * nova_core.c — implémentation de l'accélérateur natif de Nova.
 *
 * Contraintes de conception :
 *  - aucune allocation mémoire (tout se fait sur des tampons fournis),
 *  - aucune dépendance à la libc au-delà de <string.h>,
 *  - sûr vis-à-vis des bornes : chaque accès est vérifié,
 *  - l'ABI est vérifiée par Rust au démarrage.
 */
#include "nova_core.h"

#include <string.h>

#define NOVA_TOLOWER(c) (((c) >= 'A' && (c) <= 'Z') ? (char)((c) + 32) : (char)(c))

uint32_t nova_abi_version(void) { return (uint32_t)NOVA_ABI_VERSION; }

/* ------------------------------------------------------------------ */
/* Recherche insensible à la casse : Boyer-Moore-Horspool             */
/* ------------------------------------------------------------------ */

ptrdiff_t nova_find_ci(const char *hay, size_t hay_len, const char *needle, size_t needle_len) {
    if (hay == NULL || needle == NULL || needle_len == 0 || hay_len < needle_len) {
        return -1;
    }

    /* Table de décalage (mauvais caractère) construite à chaque appel :
     * la liste de blocage est courte, le gain d'un cache statique serait nul. */
    size_t shift[256];
    size_t i;

    for (i = 0; i < 256; i++) {
        shift[i] = needle_len;
    }
    for (i = 0; i + 1 < needle_len; i++) {
        shift[(unsigned char)NOVA_TOLOWER(needle[i])] = needle_len - 1 - i;
    }

    size_t pos = 0;
    const size_t last = needle_len - 1;
    const char last_lower = NOVA_TOLOWER(needle[last]);

    while (pos + needle_len <= hay_len) {
        const char c = NOVA_TOLOWER(hay[pos + last]);
        if (c == last_lower) {
            size_t j = 0;
            while (j < last && NOVA_TOLOWER(hay[pos + j]) == NOVA_TOLOWER(needle[j])) {
                j++;
            }
            if (j == last) {
                return (ptrdiff_t)pos;
            }
        }
        pos += shift[(unsigned char)c];
    }

    return -1;
}

/* ------------------------------------------------------------------ */
/* Extraction du nom d'hôte d'une URL                                 */
/* ------------------------------------------------------------------ */

size_t nova_host_of(const char *url, size_t url_len, char *out, size_t out_len) {
    if (url == NULL || out == NULL || out_len == 0 || url_len == 0) {
        if (out != NULL && out_len > 0) {
            out[0] = '\0';
        }
        return 0;
    }

    size_t start = 0;
    size_t end = url_len;

    /* 1. Schéma « scheme:// » */
    size_t scheme_end = 0;
    for (size_t i = 0; i < url_len; i++) {
        if (url[i] == ':') {
            scheme_end = i;
            break;
        }
        /* Un caractère invalide avant les deux-points : ce n'est pas un schéma. */
        if (url[i] == '/' || url[i] == '?' || url[i] == '#') {
            break;
        }
    }
    if (scheme_end > 0 && scheme_end + 2 <= url_len && url[scheme_end + 1] == '/' && url[scheme_end + 2] == '/') {
        start = scheme_end + 3;
    } else if (scheme_end > 0 && scheme_end + 1 < url_len && url[scheme_end + 1] == '/') {
        /* schéma de type « file:/chemin » : pas d'hôte */
        start = scheme_end + 2;
    }

    /* 2. Identifiants « user:pass@hôte » */
    for (size_t i = start; i < url_len; i++) {
        if (url[i] == '/' || url[i] == '?' || url[i] == '#') {
            break;
        }
        if (url[i] == '@') {
            start = i + 1;
        }
    }

    /* 3. Fin de l'hôte : / ? # */
    end = url_len;
    for (size_t i = start; i < url_len; i++) {
        if (url[i] == '/' || url[i] == '?' || url[i] == '#') {
            end = i;
            break;
        }
    }

    /* 4. Port « :8080 » et IPv6 « [::1] » */
    if (end > start && url[start] == '[') {
        for (size_t i = start; i < end; i++) {
            if (url[i] == ']') {
                start = start + 1;
                end = i;
                break;
            }
        }
    } else {
        for (size_t i = start; i < end; i++) {
            if (url[i] == ':') {
                end = i;
                break;
            }
        }
    }

    if (end <= start) {
        out[0] = '\0';
        return 0;
    }

    size_t n = end - start;
    if (n > out_len - 1) {
        n = out_len - 1;
    }
    for (size_t i = 0; i < n; i++) {
        out[i] = NOVA_TOLOWER(url[start + i]);
    }
    out[n] = '\0';
    return n;
}

/* ------------------------------------------------------------------ */
/* Divers                                                             */
/* ------------------------------------------------------------------ */

int nova_ends_with_ci(const char *s, size_t s_len, const char *suffix, size_t suffix_len) {
    if (s == NULL || suffix == NULL || suffix_len > s_len) {
        return 0;
    }
    const size_t off = s_len - suffix_len;
    for (size_t i = 0; i < suffix_len; i++) {
        if (NOVA_TOLOWER(s[off + i]) != NOVA_TOLOWER(suffix[i])) {
            return 0;
        }
    }
    return 1;
}

uint64_t nova_fnv1a64(const char *data, size_t len) {
    uint64_t hash = 1469598103934665603ULL; /* offset basis */
    if (data == NULL) {
        return hash;
    }
    for (size_t i = 0; i < len; i++) {
        hash ^= (uint64_t)(unsigned char)data[i];
        hash *= 1099511628211ULL; /* prime FNV */
    }
    return hash;
}

size_t nova_utf8_prefix(const char *s, size_t len, size_t max_bytes) {
    if (s == NULL || max_bytes == 0) {
        return 0;
    }
    if (max_bytes >= len) {
        return len;
    }
    size_t i = max_bytes;
    /* On recule tant que l'octet courant est une continuation (10xxxxxx). */
    while (i > 0 && ((unsigned char)s[i] & 0xC0) == 0x80) {
        i--;
    }
    return i;
}

int nova_looks_like_host(const char *s, size_t len) {
    if (s == NULL || len < 3 || len > 255) {
        return 0;
    }

    int dots = 0;
    for (size_t i = 0; i < len; i++) {
        const unsigned char c = (unsigned char)s[i];
        if (c == '.') {
            /* Ni premier, ni dernier caractère, ni répété. */
            if (i == 0 || i + 1 == len || s[i - 1] == '.') {
                return 0;
            }
            dots++;
        } else if (c == '-') {
            if (i == 0 || i + 1 == len) {
                return 0;
            }
        } else if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'))) {
            return 0;
        }
    }

    if (dots == 0) {
        return 0;
    }

    /* Le dernier label (TLD) doit être plausible : 2 à 63 caractères
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
    const size_t tld_start = len - label;
    int all_letters = 1;
    int has_letter = 0;
    for (size_t i = tld_start; i < len; i++) {
        const unsigned char c = (unsigned char)s[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) {
            has_letter = 1;
        } else if ((c >= '0' && c <= '9') || c == '-') {
            all_letters = 0; /* ce n'est plus un TLD alphabétique classique */
        } else {
            return 0;
        }
    }
    if (all_letters && has_letter) {
        return 1; /* « com », « fr », « travel », « paris »… */
    }
    /* Sinon, seul le punycode est admis : « xn--p1ai » pour .рф, par exemple.
     * On évite ainsi de prendre « test.c0m » pour un domaine, tout en
     * acceptant les domaines internationalisés. */
    if (label >= 5 && has_letter && NOVA_TOLOWER(s[tld_start]) == 'x' &&
        NOVA_TOLOWER(s[tld_start + 1]) == 'n' && s[tld_start + 2] == '-' && s[tld_start + 3] == '-') {
        return 1;
    }
    return 0;
}
