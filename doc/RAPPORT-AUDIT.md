# Rapport d'audit — Nova

**Versions auditées :** 1.0.1 et 1.0.2 → **version corrigée livrée : 1.0.3**
**Date :** 15 octobre 2026
**Périmètre :** la totalité du code du projet — Rust (`src/`), module C (`native/`), interface
(`assets/ui/`, `assets/trackers.txt`), script de construction (`build.rs`), tests
(`tools/test_nova_core.c`) et documentation (`README.md`, `LISEZMOI.txt`).
**Objet :** « voir s'il y a des bugs ou des erreurs » — recherche, correction, vérification.

---

## 1. Méthode

L'audit a combiné quatre approches complémentaires :

| Approche | Ce qu'elle couvre |
|---|---|
| **Exploration par les cas limites** : un programme d'essai (`/tmp/edge.c`) appelant chaque fonction de résolution d'URL avec des entrées tordues (ports, punycode, casse, espaces, unicode, schémas inconnus) | logique de la barre d'adresse, des alias et du canoniseur |
| **Relecture ligne à ligne** des 6 modules Rust et du module C, en suivant chaque flux d'événement (souris, clavier, IPC, cycle de vie d'un onglet) | état incohérent, chemins de code jamais atteints, valeur de repli erronée |
| **Analyse statique automatique** : `gcc -fanalyzer -Wall -Wextra -Wpedantic -Wconversion -Wshadow`, `clang --analyze`, `cargo clippy` (cible Linux **et** cible Windows), revue de tous les `unwrap`/`expect`/indexations | fuites, débordements, accès non vérifiés, code mort |
| **Tests** : suite C (60 vérifications) et suite `cargo test`, dont des tests **ajoutés** pour chaque défaut trouvé, plus `node --check` sur chaque `<script>` des pages d'interface | non-régression |

Un défaut n'est retenu que s'il est **reproductible par lecture du code** — pas de « ça pourrait
peut-être arriver ».

**Résultat : 29 défauts, tous corrigés.** Ils sont classés ci-dessous par gravité. Le tableau
donne, pour chacun, le symptôme observable par l'utilisateur et le correctif appliqué.

---

## 2. Défauts de gravité élevée (7)

Ceux-là se voyaient à l'usage : une fonction qui ne fait rien, ou un état qui part en vrille.

| # | Zone | Symptôme | Correctif |
|---|---|---|---|
| 1 | `src/urls.rs:76` `strip_port` | Taper `github.com:8080` ne chargeait rien : la barre d'adresse gardait le port dans le nom d'hôte, qui n'était alors reconnu ni comme domaine ni comme URL. | `strip_port()` sépare l'hôte du `:port` (en respectant les IPv6 entre crochets) avant toute validation ; le port est conservé dans l'URL finale. |
| 2 | `native/nova_core.c` `nova_looks_like_host` | Un domaine internationalisé (`exemple.xn--p1ai`) était **refusé** — traité comme du texte à chercher sur Google. | Le dernier label est accepté s'il est entièrement alphabétique **ou** s'il commence par `xn--`. Règle affine appliquée aussi au repli Rust (`src/accel.rs`). |
| 3 | `src/urls.rs:171-195` `canonical` / `canon_eq` | `https://GitHub.com/PaTh` perdait son chemin : la comparaison d'onglets était trop permissive sur les URL courtes, et les deux fonctions n'utilisaient pas le même seuil. | Seuil unique `MIN_LEN_ROOT_SLASH = 9` partagé par les deux fonctions ; la casse du chemin n'est plus ignorée à tort. |
| 4 | `assets/ui/sidebar.html` `syncTabs` | Les onglets **épinglés** et les onglets normaux se détruisaient mutuellement leurs nœuds DOM lors d'un repaint : la liste clignotait et **tous** les favicons étaient re-téléchargés à chaque changement de titre. | `syncTabs(list, container, isPinned, seen)` accumule les identifiants vus, `pruneTabs(seen)` n'est appelé **qu'une fois** à la fin ; `applyFavicon` ne compare plus que l'hôte. |
| 5 | `src/main.rs:466` `with_active_view` | Sur un onglet **en veille** (restauré au démarrage, moteur non encore créé), `reload`, `back`, `forward`, `devtools`, `find`, `downloads` et `clear_data` ne faisaient **rien** — ni par le menu, ni au clavier. | Helper `with_active_view()` : il crée le moteur à la demande puis exécute l'action. Tous les points d'entrée (IPC et raccourcis) passent par lui. |
| 6 | `src/config.rs:287` `revision` | Le panneau d'historique restait figé : la « révision » était calculée à partir de la dernière entrée, donc **inchangée** lors d'une revisite ou d'un renommage. | Compteur `revision: u64` incrémenté à chaque visite, renommage, suppression ou effacement (champ `#[serde(skip)]`, non écrit sur disque). |
| 7 | `src/main.rs` `handle_ipc` | Le bouton « copier l'adresse » de la barre d'adresse ne copiait rien : les messages venant des surfaces d'interface arrivaient avec `from_tab = 0` et visaient un onglet inexistant. | Quand `id = 0` **et** `from_tab = 0`, l'onglet ciblé devient `active_id()`. |

---

## 3. Défauts de gravité moyenne (9)

Fonctionnalité incomplète ou incohérence d'état, sans blocage complet.

| # | Zone | Symptôme | Correctif |
|---|---|---|---|
| 8 | `src/ui.rs:13,21` + `assets/ui/history.html` | `nova://history` était une adresse reconnue **sans page** : écran blanc. | Nouvelle page interne française (filtre, regroupement par jour, suppression d'une entrée, tout effacer), branchée dans `ui.rs` et `internal_page`. |
| 9 | `src/urls.rs` alias | `nova://about` annonçait une page qui n'existe pas. | Alias vers `nova://settings`, où figurent la version, le moteur de calcul et les licences. |
| 10 | `src/main.rs` Alt+Entrée | Choisir un moteur avec `Alt+Entrée` **persistait** ce moteur pour toutes les recherches suivantes. | `target_engine = None` : le choix ne vaut que pour cette recherche. |
| 11 | `src/main.rs` création d'onglet | Le titre initial était « Nouvel onglet » même pour une URL déjà chargée. | Le titre initial est l'hôte de l'URL cible. |
| 12 | `src/main.rs` `select_tab` | Ouvrir une page interne après coup (onglet en veille) l'affichait vide : aucun état ne lui avait été poussé. | `select_tab` envoie `ui::render_call(&state)` si l'onglet actif est une page interne. |
| 13 | `src/main.rs` `flush_ui` | Quand l'onglet actif était `nova://history`, l'interface recevait l'état « léger » : la liste ne se mettait pas à jour. | Mode « riche » (historique complet) dès que l'onglet actif est la page d'historique. |
| 14 | `src/blocker.rs:66` + `src/main.rs` | Les règles de blocage étaient demandées avec un plafond de 160 alors que la liste en contient **146** : marge nulle, domaine ajouté = règle silencieusement ignorée. | `resolver_rules(blocker.len())` : le plafond suit la liste. |
| 15 | `build.rs` | Sans compilateur C installé, la compilation **échouait** avec un message obscur (« lib.exe not found »). | `try_compile()` + configuration `nova_c_accel` : le module C est optionnel, un avertissement clair s'affiche et le repli Rust prend le relais. |
| 16 | `src/accel.rs` | Le repli Rust n'appliquait pas les mêmes règles que le C (validation d'hôte différente) : le comportement changeait selon la présence du module C. | Parité stricte des deux implémentations, vérifiée par les tests exécutés **avec** et **sans** le module C. |

---

## 4. Défauts de gravité faible, robustesse et qualité (13)

| # | Zone | Symptôme | Correctif |
|---|---|---|---|
| 17 | `tools/test_nova_core.c` | Deux **faux échecs** de test : des longueurs de chaînes codées à la main (`16` au lieu de `17` pour `exemple.xn--p1ai`). Un test qui échoue sur le testeur ne teste rien. | Toutes les longueurs passent par `strlen()` ; la suite compte désormais **60 vérifications**. |
| 18 | `src/urls.rs` (tests) | Port, casse, alias et comparaison d'URL n'étaient **pas couverts** — c'est exactement là que se cachaient les défauts 1 à 3. | 4 tests ajoutés (port, casse du chemin, punycode, alias) + unification des seuils. |
| 19 | `assets/trackers.txt`, panneau de réglages | Les textes annonçaient encore une résolution vers `0.0.0.0` alors que la liste utilise `~NOTFOUND`. | Textes alignés sur la réalité (`~NOTFOUND`, aucune connexion sortante). |
| 20 | `README.md` section 6 | La documentation annonçait « le plein écran n'est pas implémenté » — **faux**, `F11` fonctionne (`src/main.rs:1030`, `assets/ui/inject.js:48`). | Limite corrigée : seul l'onglet privé reste à faire. |
| 21 | `src/config.rs` | `clippy::unnecessary_sort_by` : tri par `sort_by` avec une comparaison de clé. | `sort_by_key`. |
| 22 | `src/main.rs` | Idem `unnecessary_sort_by` sur le tri des onglets. | `sort_by_key`. |
| 23 | `src/main.rs:735` | `if let` imbriqué signalé par clippy (`collapsible_if`). | Condition fusionnée. |
| 24 | `src/main.rs` | Fermeture redondante passée à `with_active_view`. | Fonction passée directement. |
| 25 | `src/accel.rs` | `needless_return` dans les blocs de configuration en position finale. | `return` retiré. |
| 26 | `src/platform.rs:70` | `needless_return` (thème sombre) — **visible seulement** en compilation croisée Windows. | `return` retiré. |
| 27 | `src/platform.rs:220` | `needless_return` (presse-papiers) — même cas. | `return` retiré. |
| 28 | `src/main.rs` `make_view` | 8 paramètres : clippy ne peut pas trancher, le lecteur non plus. | `#[allow(clippy::too_many_arguments)]` **assumé et commenté** (les paramètres sont tous nécessaires à la création d'une vue). |
| 29 | `src/accel.rs` | Le module `tests` était au milieu du fichier, avant du code de production. | Déplacé en fin de fichier (convention Rust). |

---

## 5. Ce qui a été vérifié et jugé sain

* **Aucun `unsafe` non justifié** : les deux blocs `unsafe` de `platform.rs` (presse-papiers
  Win32, thème système) vérifient chaque valeur de retour, libèrent la mémoire globale en cas
  d'échec et ne transmettent jamais de pointeur nul.
* **Aucun `unwrap()`/`expect()` sur une entrée utilisateur** : les seuls présents portent sur des
  ressources embarquées à la compilation (`include_str!`) ou sur des mutex dont l'empoisonnement
  est impossible dans ce programme.
* **Aucune indexation non bornée** : tous les accès par index dans `urls.rs` et `native/nova_core.c`
  sont précédés d'un test de longueur (vérifié à la main, ligne à ligne).
* **Module C** : `gcc -fanalyzer` (fuites, double libération, débordements) **et** `clang --analyze`
  muets ; toute la mémoire allouée est libérée, y compris sur les chemins d'erreur.
* **Aucune dépendance externe** au binaire : l'exe lie statiquement la CRT (0 référence à
  `VCRUNTIME`), 15 DLL **système** uniquement, toutes présentes sur Windows 10/11.
* **Frontend** : chaque `<script>` extrait des 6 pages d'interface est syntaxiquement valide
  (`node --check`) ; aucun `innerHTML` alimenté par une donnée de page (protection XSS : seuls
  `textContent` et des nœuds créés par `createElement`).
* **Cohérence du blocage** : la liste de 146 domaines est convertie en 147+ règles
  (`MAP <domaine> ~NOTFOUND` + `*.<domaine>`), toutes transmises au moteur.

---

## 6. Vérifications exécutées après correction

| Vérification | Résultat |
|---|---|
| Suite C, 60 vérifications (`tools/test_nova_core.c`) | **60 / 60** |
| `cargo test` (avec module C) | **10 / 10** |
| `cargo test --no-default-features` (repli Rust seul) | **10 / 10** — les deux implémentations concordent |
| `cargo clippy` cible **Linux**, tous les avertissements | **0** |
| `cargo clippy --target x86_64-pc-windows-msvc --all-targets` | **0** (2 avant correction) |
| `gcc -Wall -Wextra -Wpedantic -Wconversion -Wshadow -fanalyzer` | **muet** |
| `clang --analyze -std=c11` | **muet** |
| Compilation **sans** compilateur C (repli) | **réussit** avec un avertissement explicite |
| `cargo xwin build --release` (cible Windows x64) | **réussit** |

---

## 7. Défauts visuels (2e passe, v1.0.3)

Les défauts d'interface ne se voient pas dans un diff : ils ont été relevés en
**rendant chaque page dans Chromium** (le moteur de rendu de WebView2) à la
**taille réelle de sa WebView** — 248 × 900 px pour la barre latérale, par
exemple — puis en inspectant les captures et, automatiquement, la géométrie de
la page (sonde `tools/ui_probe.py` : éléments hors cadre, contenus plus larges
que leur boîte, et thème réellement appliqué).

Outils livrés avec les sources : `tools/ui_shot.py` (captures),
`tools/ui_probe.py` (sonde de mise en page + thème),
`tools/ui_before_after.py` (planche avant/après).

### 7.1 Défauts vus par l'utilisateur (8)

| # | Zone | Ce qu'on voyait | Cause exacte | Correctif |
|---|---|---|---|---|
| 30 | `sidebar.html` — onglets épinglés | Le favicon s'affichait **par-dessus la lettre de repli**, débordant du carré de 30 px (rendu illisible : « jeu de lettres »). | Aucune règle `.pin .fav img` : l'image prenait sa taille naturelle (jusqu'à 64 px) **et** la lettre restait affichée à côté d'elle. | Vignette `overflow:hidden`, image en `position:absolute` couvrante, lettre masquée dès que l'image est là. |
| 31 | `sidebar.html`, `history.html` — onglets et historique | Même défaut, en plus petit : la lettre restait visible **à côté** du favicon. | La lettre et l'image étaient deux enfants de la boîte flex : ils se plaçaient côte à côte. | La lettre devient un nœud `.letter` propre, recouvert par l'image. |
| 32 | `sidebar.html`, `history.html` | Les favicons **à fond transparent** (GitHub, Wikipédia, Le Monde) apparaissaient sur une **plaque rose, bleue, verte…** | La couleur de repli (teinte calculée d'après l'hôte) restait peinte derrière l'image ; elle **écrasait la plaque neutre** car posée en style inline. | Plaque neutre (`--fav-plate`) quand l'image est présente ; style inline effacé à ce moment-là et rétabli si l'image échoue. |
| 33 | `history.html` | La page interne `nova://history` restait **entièrement sombre** même avec le thème « Clair ». | Le fichier ne contenait **aucune** ligne appliquant `data-theme` : la palette claire existait mais n'était jamais activée. | `applyTheme()` appelé à l'ouverture **et** à chaque rendu. |
| 34 | `welcome.html` | L'assistant de premier lancement restait sombre, même après avoir choisi le thème clair ; les puces « Autres moteurs » étaient **illisibles** (texte blanc sur fond clair). | Aucune palette claire dans le fichier, et `#fff` codé en dur sur `.chip:hover` / `.chip.on`. | Palette claire complète + couleur de texte prise dans les variables de thème. |
| 35 | `settings.html` | Les interrupteurs **éteints** étaient presque invisibles en thème clair (gris foncé sur carte blanche). | `background:#3a3a45` codé en dur, hors des variables de thème. | Variable `--switch-off` (`#3a3a45` en sombre, `#c9c9d2` en clair) ; même correctif dans l'assistant. |
| 36 | `sidebar.html` | La poignée de la barre de défilement des onglets disparaissait en thème clair. | `#3a3a45` codé en dur. | Variable `--scroll` par thème. |
| 37 | Toutes les pages | Le réglage **« Système »** était ignoré : choisir « Système » sur un bureau clair laissait Nova sombre. | Les pages testaient `config.theme === "light"` or `theme` valait `"system"` — seul `main.rs` savait quel thème était réellement appliqué. | `main.rs` pousse désormais un champ **`dark`** (booléen déjà résolu) dans l'état ; les six pages l'utilisent, avec repli sur l'ancienne logique. |

### 7.2 Corrections de robustesse au passage

| Zone | Problème | Correctif |
|---|---|---|
| `assets/ui/*.html` (6 pages) | La logique de thème était **dupliquée** six fois, avec des variantes divergentes — c'est ce qui a laissé `history.html` et `welcome.html` sans thème. | Une seule expression par page, toutes identiques, s'appuyant sur le champ `dark` : la prochaine page interne n'aura rien à recopier. |
| `sidebar.html` | `applyFavicon` réécrivait `textContent` de la vignette, ce qui **détruisait** le nœud de l'image à chaque changement de titre. | Lettre et image sont des nœuds séparés, chacun mis à jour indépendamment. |
| `sidebar.html`, `history.html` | Une image cassée laissait la vignette **sans aucun repère** (fond neutre vide). | Sur `error`, l'image est retirée, la plaque neutre enlevée et la lettre colorée réaffichée. |

### 7.3 Vérification avant/après

Sonde exécutée sur les fichiers **d'origine** puis sur les fichiers **corrigés** :

| Contrôle (jeu de captures complet) | Avant | Après |
|---|---|---|
| Éléments débordant de leur cadre | **14** | **0** |
| Pages restant sombres alors que le système est en clair (`theme=system`) | **4 / 6** | **0 / 6** |
| Barres de défilement horizontales parasites | 0 | 0 |
| Erreurs JavaScript (`node --check` sur les 7 scripts) | 0 | 0 |

La planche **`audit_ui/AVANT-APRES-visuel.png`** montre les quatre écrans
concernés, avant et après. Aucune de ces corrections ne touche au chemin de
rendu des pages web : elles ne concernent que les surfaces d'interface, donc
aucune régression possible sur la latence de chargement.

---

## 8. Ce qui n'est pas un défaut

Pour éviter les malentendus, voici ce que l'audit a **cherché sans le trouver** :

* pas de fuite mémoire dans la boucle d'événements (les vues sont libérées à la fermeture d'un
  onglet, l'environnement WebView2 est unique et partagé) ;
* pas de course de données (tout l'état vit dans un seul thread, celui de la boucle d'événements) ;
* pas d'écriture disque synchrone restante sur le chemin d'une navigation ;
* pas de requête réseau sortante hors des sites visités, des favicons et de la recherche.

Les limites **connues et documentées** (pas des bugs) restent dans le `README.md` : moteur de rendu
WebView2/Chromium, absence de synchronisation de compte et d'extensions, blocage par liste locale,
fenêtre unique, exécutable non signé, onglets en veille silencieux jusqu'au clic.

---

## 9. Troisième passe (v1.1.0) : plein écran vidéo, fond, favoris

### 9.1 Bug corrigé : la vidéo en plein écran laissait la barre latérale

| # | Zone | Symptôme signalé | Cause exacte | Correctif |
|---|---|---|---|---|
| 38 | `main.rs`, `inject.js` | En mettant une **vidéo en plein écran**, le menu de gauche restait affiché par-dessus. | La barre latérale et la barre d'adresse sont deux **vues WebView séparées** posées sur la fenêtre. Le plein écran demandé par la page s'appliquait à la *vue de la page* : celle-ci ne pouvait donc jamais couvrir les autres vues. Rien dans le code n'écoutait `fullscreenchange`. | Un écouteur `fullscreenchange` est injecté dans chaque page (`inject.js`) et prévient Rust (`{cmd:"page_fullscreen", on:true|false}`). Sur entrée : barre latérale et barre d'adresse passent en `set_visible(false)` et la page est redimensionnée à la fenêtre entière (`content_rect()` renvoie `full_rect()`). Sur sortie : tout revient en place. Changer d'onglet ou fermer l'onglet concerné quitte le plein écran (comportement de Chrome). |

Vérification : `tools/ui_fullscreen_test.py` charge une page avec le script
injecté, simule l'entrée puis la sortie du plein écran et contrôle les deux
messages reçus par Nova — **OK**.

### 9.2 Nouvelles fonctions, avec leur vérification

| Fonction | Mise en œuvre | Vérification |
|---|---|---|
| **Favoris (apps)** | `Favorite {title, url}` dans `config.rs` (24 max, nettoyage des adresses vides) ; étoile de la barre d'adresse (`toggle_favorite`, `Ctrl+D`), rangée d'icônes dans la barre latérale, section « Favoris » sur le nouvel onglet, menu contextuel (ouvrir, nouvel onglet, copier, retirer). | Tests `favoris_nettoyes_et_relus`, `liste_de_favoris_bornee`, `config_ancienne_relue` ; captures `sidebar-favoris`, `newtab-favoris`, et cas **sans favori** (`sidebar-sans-favoris`, `newtab-sans-favoris`) |
| **Couleur du fond** | Champ `ui_bg` (`#rrggbb` validé côté Rust **et** côté page) ; 9 teintes prêtes + sélecteur libre dans les paramètres ; palette complète (cartes, lignes, survols, texte) recalculée d'après la luminance par `NovaSkin`, défini **une seule fois** dans `src/ui.rs` et injecté dans les six pages. | Test `couleur_de_fond_validee` (refus de `javascript:`, `#1b1b1`, `#zzzzzz`) ; captures `sidebar-fond`, `toolbar-fond`, `settings-fond`, `newtab-fond` ; mesure des couleurs calculées dans le moteur (fond `rgb(42,32,53)`, texte `rgb(242,242,243)`) |
| **Raccourci** | `Ctrl+D` = ajouter/retirer des favoris (usage établi des navigateurs) ; l'ancien `Ctrl+D` maison (« copier l'adresse ») reste accessible par les menus contextuels. | `node --check` sur `inject.js` ; branchement ajouté dans `hotkey()` |

### 9.3 Contrôles de non-régression (v1.1.0)

| Vérification | Résultat |
|---|---|
| Sonde de mise en page, **18 scènes** × 2 thèmes (dont fond personnalisé et favoris) | **0 anomalie** |
| Thème réellement appliqué sur les 6 pages (`theme=system`, système clair) | **6/6 en clair** |
| Signal de plein écran (entrée + sortie) | **OK** |
| `cargo test` (avec et sans module C) | **14/14** et **14/14** |
| Suite C du module d'accélération | **60/60** |
| `cargo clippy` cible hôte | **0** avertissement |
| Syntaxe des 7 scripts d'interface (`node --check`) | **0 erreur** |
| Chargement d'un `config.json` de la version 1.0.3 | **OK** (`config_ancienne_relue`) |
| Aucune régression de latence | seules les surfaces d'interface changent ; le chemin de rendu des pages web n'est pas touché |

### 9.4 Deuxième correctif du plein écran vidéo (v1.1.1)

Le premier correctif ne reposait que sur l'événement JavaScript
`fullscreenchange` : si le moteur de rendu ne le dispatche pas, Nova n'est
jamais prévenu et le menu de gauche reste affiché. Trois couches indépendantes
sont désormais en place — si l'une lâche, les autres prennent le relais :

| Couche | Mécanisme | Dépend de la page ? |
|---|---|---|
| **1. Événement COM du moteur** (principale) | `ICoreWebView2::ContainsFullScreenElementChanged`, branché sur chaque vue de page via `with_webview`, relayé à la boucle d'événements sous forme de `UserEvent::PageFullScreen { tab, on }` | **non** |
| **2. Événement JavaScript** | `fullscreenchange` + `webkitfullscreenchange`, dans le script injecté | oui |
| **3. Interrogation** (repli) | le script injecté relit `document.fullscreenElement` **2 fois par seconde** (minuterie suspendue quand l'onglet est masqué) et ne signalle que les changements | oui |

En complément, le comportement rejoint celui de Chrome : la **fenêtre** passe en
plein écran (et non seulement la zone de page), puis revient à l'état antérieur
— un `F11` demandé par l'utilisateur n'est pas écrasé (champ `page_fs_window`).

Vérification (`tools/ui_fullscreen_test.py`, dans un vrai moteur) : l'entrée et
la sortie sont signalées **dans les deux cas** (avec événement, et avec la seule
interrogation), et un état stable **n'envoie aucun message** — pas de trafic IPC
inutile, aucune incidence sur la latence.

## 10. Quatrième passe (v1.2.0) : import des données d'un autre navigateur

### 10.1 Ce qui a été mis en place

| Élément | Fichier | Rôle |
|---|---|---|
| Lecteur SQLite | `src/sqlread.rs` | Lecture seule, **sans dépendance** : en-tête, arbre B par pages, varints, enregistrements, chaînes de pages de débordement. Colonnes résolues par leur **nom**. |
| Analyseurs | `src/import.rs` | `Bookmarks` (JSON), `History` / `places.sqlite` (SQLite), export HTML Netscape ; détection des profils installés ; fusion sans doublon. |
| Boîte de dialogue | `src/platform.rs::pick_file` | `rfd` (cible Windows uniquement), appelée **sur un fil dédié** : la fenêtre reste réactive. |
| Page interne | `assets/ui/import.html` (`nova://import`) | Sources détectées, options, compte rendu, formats reconnus. |
| Câblage | `src/main.rs` | IPC `import`, `import_scan`, `import_run`, `import_pick` ; événements `ImportScan` / `ImportLoaded` / `ImportPicked` ; clés d'état `import_sources`, `import_result`, `import_busy`, `limits`. |

### 10.2 Trois bugs de lecture trouvés par les tests (et corrigés)

Les tests ne se contentent pas d'un fichier jouet : `tools/fixtures/` contient de
**vraies** bases produites par SQLite, dont une de 397 lignes avec un titre de
7 600 octets — donc des pages de débordement, un arbre à plusieurs niveaux et
des lignes supprimées.

| Bug | Symptôme | Cause | Correction |
|---|---|---|---|
| 1. En-tête de la page 1 | Aucune ligne lue : `sqlite_master` paraissait vide | Le type d'arbre B était lu à l'octet 0 de la page, c'est-à-dire sur le « S » de « SQLite format 3 » | Lire à l'offset 100 sur la page 1 |
| 2. Descente des pages intérieures | Les tables de plus d'une page ne renvoyaient rien | Le numéro de page de l'enfant était lu dans le **tableau des pointeurs** au lieu de la cellule pointée | Lire l'offset, puis le numéro dans la cellule |
| 3. Enregistrements débordants | Les titres longs étaient perdus / rejetés | La part gardée dans la page était fixée à `usable − 39` au lieu de la règle de SQLite (`minLocal` + arrondi) | Appliquer la règle de `fillInCell` |

Le troisième bug rendait invisible tout titre de plus de ~4 Ko. C'est aussi la
raison d'être du titre de 7 600 octets dans le jeu de test : sans lui, le défaut
serait passé inaperçu.

### 10.3 Deux bugs d'interface trouvés par le banc visuel (et corrigés)

| Bug | Symptôme | Cause | Correction |
|---|---|---|---|
| 1. Barre latérale vide | Plus aucun onglet ni favori affiché | Le patch référençait `N` (nom de la variable d'état dans `settings.html` / `newtab.html`) alors que `sidebar.html` utilise `state` → exception JavaScript au rendu | Utiliser `state.limits` |
| 2. Date du compte rendu | « Dernier import : à l'instant » en toutes circonstances | L'interface lisait `res.when` alors que Rust envoie `when_ts` | Formater `when_ts` en français (`toLocaleString('fr-FR')`) |

Le bug 1 rappelle pourquoi chaque version repasse par le banc : aucune erreur de
compilation, aucun avertissement de `clippy`, mais une page vide à l'écran.

### 10.4 Vérifications exécutées (v1.2.0)

| Vérification | Commande | Résultat |
|---|---|---|
| Tests unitaires | `cargo test` | **26/26** (import 8, urls 6, config 4, sqlread 4, accel 3, blocker 1) |
| Analyse statique croisée | `cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc` | **0 avertissement** |
| Module C | `tools/test_nova_core.c` | **60/60** |
| Mise en page | `tools/ui_probe.py dark` / `light` | **0 anomalie** (24 scènes × 2 thèmes) |
| Captures | `tools/ui_shot.py dark` / `light` | **54 captures** relues (27 scènes × 2 thèmes), dont `import*`, `import-resultat-bas`, `sidebar-favoris-import`, `settings-import` |
| Plein écran vidéo | `tools/ui_fullscreen_test.py` | **OK** (non-régression) |
| Compilation release | `cargo xwin build --release` | `Finished` en 4 min 23 s |
| Reproductibilité | reconstruction forcée (`touch` des sources puis rebuild) | binaire identique après reconstruction, empreinte vérifiée ci-dessous |
| Binaire | `Nova.exe` (SHA-256 dans `Nova.exe.sha256`) | 1 340 416 o, empreinte `0ecba376f4d171bf49a90b2a1198462503303fac9e379f898e0e7710da016966`, 15 DLL importées, aucune DLL à côté |

### 10.5 Ce qui n'est pas un défaut

* **Les mots de passe ne sont pas importés** : ils sont chiffrés par Windows
  (DPAPI) avec la clé du compte d'origine, et le moteur de rendu de Nova a son
  propre magasin de mots de passe. C'est annoncé dans l'interface plutôt que
  proposé puis échouant.
* **Un fichier `History` verrouillé** par un navigateur ouvert lève une erreur
  *par source*, sans interrompre les autres imports.
* **Une seconde exécution de l'import ne change rien** : c'est le comportement
  voulu (idempotence), et non un import qui « ne fait rien ».
* **Le compteur « +N »** de la barre latérale n'est pas un bug d'affichage : au
  delà de 24 favoris, la liste des onglets serait écrasée.

## 11. Cinquième passe (v1.2.1) : la boîte de dialogue « Obtenir une application pour ouvrir ce lien »

### 11.1 Le défaut signalé

Depuis les premières versions, une boîte de dialogue **de Windows** apparaissait
au lancement de Nova :

> Obtenir une application pour ouvrir ce lien « ms-gamingoverlay » — Votre PC n'a
> pas d'application qui peut ouvrir ce lien.

Le défaut a longtemps été impossible à reproduire faute de capture. Elle est
arrivée : l'utilisateur a joint l'écran du message.

### 11.2 Diagnostic

`ms-gamingoverlay:` est le protocole de la **Xbox Game Bar**. Le message n'est pas
une erreur de Nova : c'est **Windows** qui propose d'aller chercher dans le
Microsoft Store l'application qui saurait l'ouvrir (elle a été désinstallée sur
le poste). Deux causes se cumulaient :

| # | Cause | Explication |
|---|---|---|
| 1 | Nova confiait les protocoles inconnus à Windows | Dans `make_view`, le gestionnaire de navigation renvoyait `true` pour tout schéma exotique (« on laisse le moteur décider »). WebView2 exécute alors `ShellExecute` sur l'adresse : sans logiciel enregistré, Windows affiche la boîte de dialogue. |
| 2 | Une adresse inchargeable pouvait être **conservée** | `session.json` (onglets restaurés) et `homepage` acceptaient n'importe quelle chaîne. Une adresse en `ms-gamingoverlay:` enregistrée une fois était donc redemandée **à chaque démarrage** — d'où le « à chaque lancement ». |

### 11.3 Correction

* `urls::scheme_of` / `is_engine_scheme` / `is_blocked_scheme` : classement des
  schémas. Le moteur ne charge que ce qu'il sait charger (`http`, `https`,
  `nova`, `about`, `data`, `blob`, `file`, `edge`, `chrome-extension`…) ;
  `ms-gamingoverlay`, `ms-gamebar` et `ms-gamebarservices` sont **toujours**
  refusés (l'overlay de jeu n'a rien à faire dans un navigateur).
* `platform::scheme_handler_exists` : **lecture du registre** dans la vue
  fusionnée `HKEY_CLASSES_ROOT\<protocole>` — un protocole n'est ouvrable que
  s'il déclare `URL Protocol` **et** une commande `shell\open\command`.
* `platform::open_external` : `ShellExecuteW` (échec si le retour est ≤ 32), pour
  les protocoles réellement gérés (`mailto:`, `ms-settings:`, `steam:`…).
* Le gestionnaire de navigation, le gestionnaire de fenêtres surgissantes et la
  barre d'adresse appliquent la même règle : **rien ne part vers Windows sans
  vérification**. Un refus est compté et journalisé.
* `config::loadable_url` : les onglets restaurés et la page d'accueil sont
  filtrés au chargement — une adresse que le moteur ne peut pas ouvrir ne peut
  plus revenir hanter le démarrage.
* `config::iso_time` : horodatage lisible pour le journal
  (`%APPDATA%\Nova\protocoles-refuses.log`), avec rotation à 256 Ko.
* Paramètres : ligne « Liens non ouverts » (compteur + chemin du journal), pour
  que l'utilisateur puisse constater *qui* a demandé l'ouverture.

### 11.4 Ce que le correctif ne fait pas (et pourquoi)

Windows peut ouvrir lui-même l'overlay de jeu — raccourci `Win+G`, manette de
jeu branchée (Windows tente l'ouverture dès la connexion). Ce chemin ne passe
**pas** par Nova : aucune application ne peut l'intercepter. Le `LISEZMOI.txt`
donne donc la marche à suivre côté système (réinstaller la Game Bar, ou la
désactiver par les deux clés `GameDVR` du registre). Le journal des protocoles
permet de trancher : s'il reste vide alors que la boîte de dialogue réapparaît,
c'est bien Windows qui l'a ouverte.

### 11.5 Vérifications exécutées (v1.2.1)

| Vérification | Commande | Résultat |
|---|---|---|
| Tests unitaires | `cargo test` | **29/29** (dont `schemas_du_systeme`, `horodatage_lisible`, `session_sans_url_inchargeable`) |
| Analyse statique croisée | `cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc` | **0 avertissement** |
| API Windows utilisées | `cargo xwin check` | `RegOpenKeyExW`, `RegQueryValueExW`, `ShellExecuteW` : signatures validées à la compilation |
| Mise en page | `tools/ui_probe.py dark` / `light` | **0 anomalie** |
| Captures | `tools/ui_shot.py dark` / `light` | relues, dont `settings-protocoles` |
| Compilation release | `cargo xwin build --release` | `Finished` en 2 min 32 s |
| Binaire | `Nova.exe` | 1 348 096 o, empreinte `a3c5a1b36a0fe0edba3201af90a7bfd0cfbf636ae62b2b2d5d3f9ea407e997cc`, 15 DLL importées |

## 12. Sixième passe (v1.3.0) : le message de Windows, l'import par application, l'apparence

### 12.1 Le message revenait encore (v1.2.1)

Le correctif de la v1.2.1 avait fermé la voie « navigateur » : Nova ne confie
plus un protocole à Windows sans vérifier le registre, et les onglets restaurés
inchargeables sont écartés. Le message est pourtant revenu — ce qui confirme le
diagnostic restant : **Windows ouvre `ms-gamingoverlay:` de lui-même**, hors de
portée d'un navigateur :

* touche **`Win+G`** (raccourci système),
* **manette de jeu branchée** : Windows tente l'ouverture dès la connexion,
  sans qu'aucun jeu ni navigateur ne soit lancé.

### 12.2 Correction : couvrir le protocole au lieu de le subir

Windows n'affiche sa boîte que s'il **n'existe aucun** gestionnaire pour le
protocole. Nova en déclare donc un, inerte, pour le compte courant :

| Élément | Valeur |
|---|---|
| Clé | `HKCU\Software\Classes\ms-gamingoverlay` (+ `ms-gamebar`, `ms-gamebarservices`) |
| `URL Protocol` | *(chaîne vide)* — marque d'un vrai protocole |
| `shell\open\command` | `"<chemin de Nova.exe>" --ignore-protocol` |

Quand Windows appelle Nova avec `--ignore-protocol`, `main()` **retourne
immédiatement** : aucun processus visible, aucune fenêtre, aucun travail.

Garde-fous : rien n'est écrit dans `HKEY_LOCAL_MACHINE` ; rien n'est écrit du
tout si la Game Bar est réellement installée (`scheme_handler_exists`) ; la
désactivation supprime **uniquement** une clé reconnue comme celle de Nova (la
commande doit contenir `--ignore-protocol`) ; l'opération ne demande aucun droit
administrateur.

### 12.3 Import par application

`import::Source` porte désormais un champ `app`, et l'interface regroupe les
sources par navigateur :

* une ligne par application, avec ses profils comptés ;
* deux puces **Favoris** / **Historique** (annulables) pour choisir le contenu ;
* « Tout sélectionner » / « Rien » ;
* le chemin affiché est tronqué proprement, l'adresse complète restant dans
  l'infobulle de la puce.

### 12.4 Apparence

Objectif : retirer les marqueurs « générés » sans rien changer à la disposition
ni aux fonctions.

* **Palette** : tons neutres, un seul accent (#6b75e8), séparateurs à 15 % / 22 %
  d'opacité selon le rôle (`--line`, `--line-2`), valeurs identiques entre les
  sept pages (elles divergeaient).
* **Formes** : rayons resserrés (cartes 12 px, contrôles 5 à 9 px), hauteurs de
  contrôles alignées (28 px pour les boutons, 30 px pour la barre d'adresse et
  les onglets).
* **Décoration** : halos flous supprimés, dégradés retirés (bouton principal et
  logo), ombres lourdes remplacées par des contours, survols sans translation,
  interrupteurs à 20 px au lieu de 24.
* **Marque** : carré arrondi à fond plein avec le « N », au lieu du losange à
  dégradé.
* La couleur de fond choisie par l'utilisateur couvre la nouvelle variable
  `--line-2` (la peau `NovaSkin` la recalcule).

### 12.5 Vérifications exécutées (v1.3.0)

| Vérification | Commande | Résultat |
|---|---|---|
| Tests unitaires | `cargo test` | 29/29 (inchangés, plus `loadable_url` et `iso_time`) |
| Analyse statique croisée | `cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc` | 0 avertissement |
| Compilation release | `cargo xwin build --release` | `Finished` en 2 min 16 s |
| Binaire | `Nova.exe` | 1 400 320 o, empreinte `50a411bc106c2e73a347f27a6ab5a008fbaeda17de84f9c7333de1f563881d2a`, 15 DLL importées |
| Mise en page | `tools/ui_probe.py dark` / `light` | 0 anomalie (30 scènes × 2 thèmes) |
| Captures | `tools/ui_shot.py dark` / `light` | 58 captures relues (29 scènes × 2 thèmes) |
| Module C | `tools/test_nova_core.c` | 60/60 |
| Plein écran vidéo | `tools/ui_fullscreen_test.py` | OK (non-régression) |

## 13. Septième passe (v1.3.1) : la demande vient de Windows, l'assistant décide

### 13.1 Ce que la capture du 2026-10-16 montre

La v1.3.0 avait fermé toutes les voies « navigateur » : Nova ne confie jamais
`ms-gamingoverlay:` à Windows, et le journal `protocoles-refuses.log` est resté
sans nouvelle entrée. La boîte est pourtant revenue — sous une forme voisine :

> « Sélectionner une application pour ouvrir ce lien *ms-gamingoverlay* »
> (avec, dans la liste, « Nova — navigateur web à onglets verticaux »)

Cette boîte est celle que Windows 11 affiche quand **un composant du système**
réclame le protocole et qu'aucune association par défaut n'est confirmée. Le
gestionnaire de secours de la v1.3.0 explique aussi la différence avec le
message précédent : Windows ne proposait plus d'aller au Microsoft Store, il
proposait Nova. Conclusion : la demande d'ouverture vient bien de **Windows**
(touche `Win+G`, manette branchée, jeu qui démarre), pas de Nova, et il faut la
couper à la source.

### 13.2 Correction : couper la demande, pas seulement la couvrir

| Levier | Clé / valeur | Effet |
|---|---|---|
| Captures | `HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR` → `AppCaptureEnabled` = 0 | Windows ne déclenche plus la capture |
| Game DVR | `HKCU\System\GameConfigStore` → `GameDVR_Enabled` = 0 | Le profil cesse d'activer l'overlay |
| Secours | `HKCU\Software\Classes\ms-*` (v1.3.0) | Si une demande passe malgré tout, elle aboutit sur Nova, qui quitte aussitôt |

* Aucune écriture dans `HKEY_LOCAL_MACHINE`, aucun droit administrateur.
* Les valeurs trouvées avant l'intervention sont conservées dans la
  configuration (`dvr_prev`) : décocher le réglage **repose exactement** l'état
  d'origine, il ne « force » pas les captures à s'activer.
* Le réglage est appliqué au démarrage (vérification de l'état réel à chaque
  lancement), depuis les Paramètres, et dès la dernière étape de l'assistant.
* Si la boîte apparaissait encore (par exemple sur un PC où la Game Bar a été
  remise en place par Windows Update), choisir **Nova** puis **Toujours** dans
  la boîte enregistre le choix une fois pour toutes : ensuite l'adresse aboutit
  au secours de Nova et plus rien ne s'affiche.

### 13.3 Assistant : c'est l'utilisateur qui choisit quoi importer

L'import automatique du démarrage n'a plus lieu **avant la fin de l'assistant**
(`onboarding_done`), et une nouvelle étape de l'assistant présente une ligne par
navigateur détecté :

* une case à cocher par application (favoris et historique de cette
  application), profils regroupés, chemins affichés ;
* « Importer la sélection » → `import_run` avec les sources cochées, puis
  « Continuer » avec le bilan (« 12 favori(s) et 340 visite(s) repris ») ;
* « Plus tard » → l'import reste disponible dans **Paramètres > Importer…**.

`show_welcome()` déclenche l'analyse des navigateurs à l'affichage, et
`flush_ui()` pousse désormais l'état à l'assistant comme aux autres surfaces :
la liste apparaît dès la fin de l'analyse, sans rechargement.

### 13.4 Vérifications exécutées (v1.3.1)

| Vérification | Commande | Résultat |
|---|---|---|
| Tests unitaires | `cargo test` | 29/29 |
| Analyse statique croisée | `cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc` | 0 avertissement |
| Compilation release | `cargo xwin build --release` | `Finished` (3 min 54 s à froid, 18 s ensuite ; seul message : LNK4099, informations de débogage absentes des bibliothèques MSVC téléchargées) |
| Binaire | `Nova.exe` | 1 418 752 o, empreinte `77d20e2234c3716d4d649054d5a9234019d136af633b54d7a258cbacfd517d96`, 15 DLL |
| Module C | `tools/test_nova_core.c` | 60/60 |
| Plein écran vidéo | `tools/ui_fullscreen_test.py` | OK |
| Mise en page | `tools/ui_probe.py dark` / `light` | 0 anomalie |
| Captures relues | `tools/ui_shot.py dark` / `light` | 32 scènes × 2 thèmes (assistant import, assistant réglages, état des protections) |
| Un défaut trouvé et corrigé par la relecture | `welcome.html` : `const N` réaffecté par `NovaPage.render` → `TypeError` silencieux (l'étape 2 ne s'affichait pas) ; passé en `let` | vérifié par capture d'écran |

## 14. Huitième passe (v1.3.2) : icône, logos officiels, sources documentées

### 14.1 L'icône générique de Windows

Le fichier `assets/nova.ico` était bien compilé dans les ressources du binaire
(RT_ICON/RT_GROUP_ICON présents, vérifié), mais la fenêtre ne recevait aucune
icône : Windows affichait alors l'icône générique de l'exécutable dans la barre
de titre et dans la barre des tâches.

* `main.rs` construit maintenant la fenêtre avec
  `Icon::from_rgba(include_bytes!("../assets/nova-64.rgba"), 64, 64)`.
* Les trois représentations — `.ico` des ressources, `nova-logo.png` et les
  pixels `nova-64.rgba` — sortent du **même** `tools/make_icon.py` : elles ne
  peuvent plus diverger. Le dessin a été aligné sur l'interface assagie
  (1.3.0) : carré arrondi à aplat `#6b75e8`, « N » blanc, plus de dégradé.

### 14.2 Logos officiels des moteurs

Les pastilles de couleur (initiale du moteur) sont remplacées par les logos
officiels, dans les quatre surfaces où le moteur est nommé : page du nouvel
onglet, Paramètres, barre latérale, assistant de premier lancement.

| Point | Décision |
|---|---|
| Source des images | `tools/fetch_engine_icons.py` : favicon ou icône déclarée par le site **officiel** de chaque moteur, recadrée et réduite à 64×64 |
| Transport dans le binaire | `include_bytes!` puis `data:` (base64 encodé par Nova, sans dépendance ajoutée) : **aucune requête réseau** pour afficher un logo |
| Repli | `window.NovaEngineIcon` : si l'image manque, pastille colorée + initiale (le programme fonctionne sans aucune marque tierce) |
| Licences | `LICENCES-TIERS.md` : chaque logo est daté, sourcé, et attribué à son titulaire ; supprimer le fichier suffit à le retirer |

### 14.3 Favicons des onglets

Constat de relecture : les logos dessinés bord à bord (X, YouTube, Reddit)
s'affichaient comme des rectangles pleins, `object-fit: cover` les rognant.
`object-fit: contain` et une marge d'un pixel à l'intérieur de la case règlent
le problème sans toucher à la taille de la liste.

### 14.4 Archives

| Archive | Contenu | Taille |
|---|---|---|
| `Nova-1.3.2-win64.zip` | binaire, empreinte, `LISEZMOI.txt`, `README.md`, `README-DEV.md`, `LICENCES-TIERS.md`, licence, rapport, **sources complètes** (Rust, C, interface, ressources embarquées, outils) | voir ci-dessous |
| `Nova-1.3.2-sources.zip` | sources et documentation seules (ni binaire, ni captures), reconstruite par `tools/sources_zip.sh` | voir ci-dessous |

`package.sh` a été corrigé : il omettait `assets/trackers.txt`, `assets/engines/*`,
`assets/nova.ico`, `assets/nova-logo.png`, `assets/nova-64.rgba` et
`tools/make_icon.py`, tous nécessaires à une recompilation depuis l'archive.

Le fichier `README-DEV.md` (présentation du projet : fonctions, architecture,
procédures de compilation et de test, historique) est désormais livré dans les
deux archives et à la racine du dossier de travail.

### 14.5 Vérifications exécutées (v1.3.2)

| Vérification | Commande | Résultat |
|---|---|---|
| Tests unitaires | `cargo test` | 29/29 |
| Analyse statique croisée | `cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc` | 0 avertissement |
| Compilation release | `cargo xwin build --release` | `Finished` en 3 min 16 s (seul message : LNK4099, informations de débogage absentes des bibliothèques MSVC de cargo-xwin) |
| Binaire | `Nova.exe` | 1 445 888 o, empreinte `b0c05f71ce2dc93e76b9a080e18e414bca1abd28657f74096827eef4e168a869`, 15 DLL |
| Ressources réellement embarquées | recherche des octets dans `Nova.exe` | 6 logos moteurs, pixels d'icône 64×64 et image `.ico` présents |
| Module C | `tools/test_nova_core.c` | 60/60 |
| Plein écran vidéo | `tools/ui_fullscreen_test.py` | OK |
| Scripts de l'interface | `tools/check_js.py` | 8/8 |
| Mise en page | `tools/ui_probe.py dark` / `light` | 0 anomalie |
| Captures relues | `tools/ui_shot.py dark` / `light` | 32 scènes × 2 thèmes (`audit_ui/`), planche des logos `audit_ui/LOGOS-MOTEURS.png` |
