/*
 * test_nova_core.c — tests unitaires du module d'accélération de Nova.
 *
 * Compilation et exécution :
 *   gcc -O2 -Wall -Wextra -std=c11 -Inative tools/test_nova_core.c native/nova_core.c -o test_core
 *   ./test_core
 *
 * Les longueurs sont calculées avec strlen() : coder des longueurs en dur a
 * déjà provoqué deux faux échecs lors de l'audit.
 */
#include "nova_core.h"

#include <stdio.h>
#include <string.h>

static int fails = 0;
static int total = 0;

#define CHECK(cond, msg)                          \
    do {                                          \
        total++;                                  \
        if (!(cond)) {                            \
            fails++;                              \
            printf("  ECHEC : %s\n", (msg));       \
        }                                         \
    } while (0)

static void check_host(const char *url, const char *expected, const char *msg) {
    char host[256];
    size_t n = nova_host_of(url, strlen(url), host, sizeof host);
    total++;
    if (strcmp(host, expected) != 0 || n != strlen(expected)) {
        fails++;
        printf("  ECHEC : %s — attendu '%s', obtenu '%s' (%zu octets)\n", msg, expected, host, n);
    }
}

static void check_host_flag(const char *value, int expected, const char *msg) {
    total++;
    int got = nova_looks_like_host(value, strlen(value));
    if (got != expected) {
        fails++;
        printf("  ECHEC : %s — attendu %d pour '%s', obtenu %d\n", msg, expected, value, got);
    }
}

int main(void) {
    printf("ABI du module C : %u (attendu %u)\n", nova_abi_version(), NOVA_ABI_VERSION);
    CHECK(nova_abi_version() == NOVA_ABI_VERSION, "version d'ABI");

    /* ---------- extraction du nom d'hôte ---------- */
    check_host("https://user:pw@www.Example.COM:8443/chemin?q=1", "www.example.com",
               "hôte avec identifiants, casse et port");
    check_host("http://[::1]:8080/x", "::1", "hôte IPv6");
    check_host("nova://newtab", "newtab", "hôte d'une URL interne");
    check_host("localhost:3000/api", "localhost", "hôte sans schéma, avec port");
    check_host("gitlab.example.org", "gitlab.example.org", "hôte nu");
    check_host("", "", "chaîne vide");
    check_host("data:text/html,hello", "data", "schéma sans hôte (valeur de repli)");

    /* ---------- recherche insensible à la casse ---------- */
    CHECK(nova_find_ci("https://ADS.DoubleClick.net/x", strlen("https://ADS.DoubleClick.net/x"),
                       "doubleclick.net", strlen("doubleclick.net")) > 0,
          "recherche insensible à la casse");
    CHECK(nova_find_ci("abc", 3, "zzz", 3) == -1, "motif absent");
    CHECK(nova_find_ci("abc", 3, "", 0) == -1, "motif vide");
    CHECK(nova_find_ci("", 0, "a", 1) == -1, "botte vide");

    /* ---------- suffixes de domaine ---------- */
    CHECK(nova_ends_with_ci("ads.doubleclick.net", strlen("ads.doubleclick.net"),
                            ".doubleclick.net", strlen(".doubleclick.net")) == 1,
          "suffixe de domaine");
    CHECK(nova_ends_with_ci("mydoubleclick.net", strlen("mydoubleclick.net"),
                            ".doubleclick.net", strlen(".doubleclick.net")) == 0,
          "suffixe trompeur rejeté");

    /* ---------- hachage ---------- */
    CHECK(nova_fnv1a64("a", 1) != nova_fnv1a64("b", 1), "le hachage discrimine");
    CHECK(nova_fnv1a64("github.com", 10) == nova_fnv1a64("github.com", 10), "hachage déterministe");

    /* ---------- troncature UTF-8 ---------- */
    {
        const char *accent = "Prévisions météo détaillées";
        size_t len = strlen(accent);
        for (size_t max = 1; max <= 12; max++) {
            size_t cut = nova_utf8_prefix(accent, len, max);
            CHECK(cut <= max, "troncature bornée");
            CHECK(cut == 0 || ((unsigned char)accent[cut] & 0xC0) != 0x80,
                  "troncature sur une frontière de caractère");
        }
        CHECK(nova_utf8_prefix(accent, len, len) == len, "troncature sans effet");
        CHECK(nova_utf8_prefix(accent, 0, 0) == 0, "troncature à zéro");
    }

    /* ---------- reconnaissance d'un nom d'hôte ---------- */
    check_host_flag("example.com", 1, "domaine simple");
    check_host_flag("sub.example.travel", 1, "sous-domaine et TLD long");
    check_host_flag("my-site.co.uk", 1, "tirets autorisés");
    check_host_flag("exemple.xn--p1ai", 1, "domaine internationalisé (punycode)");
    check_host_flag("x.com", 1, "domaine court");
    check_host_flag("bonjour le monde", 0, "phrase");
    check_host_flag("intel i5 13600k", 0, "requête avec chiffres");
    check_host_flag("localhost", 0, "nom simple sans point");
    check_host_flag("a.b", 0, "TLD d'un caractère");
    check_host_flag("test.c0m", 0, "TLD mélangeant chiffres et lettres");
    check_host_flag("test.123", 0, "TLD numérique");
    check_host_flag("-x.com", 0, "tiret en tête");
    check_host_flag("x.com-", 0, "tiret en fin");
    check_host_flag(".com", 0, "point en tête");
    check_host_flag("x..com", 0, "point doublé");
    check_host_flag("x.", 0, "point final");
    check_host_flag("", 0, "chaîne vide");
    check_host_flag("127.0.0.1", 0, "adresse IP (traitée comme locale, pas comme hôte)");

    printf("%d/%d vérifications réussies\n", total - fails, total);
    return fails ? 1 : 0;
}
