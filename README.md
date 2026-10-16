# Nova — navigateur web à onglets verticaux

**Nova** est un navigateur pour Windows 10/11 écrit en **Rust**, avec un **module d'accélération en C**.
Comme Arc, ses onglets ne sont pas en haut mais **dans une barre latérale à gauche** ; la page
occupe toute la largeur restante. Il interroge **Google**, **Brave Search** et **Ecosia** (plus
DuckDuckGo, Startpage et Qwant), et le moteur par défaut se choisit au premier lancement.

Le binaire livré est **un seul fichier `.exe`** : l'interface, les pages internes, l'icône et le
manifeste sont compilés à l'intérieur. Rien à installer à côté.

---

## 1. Ce que fait Nova

### Onglets à gauche, comme Arc
* Barre latérale avec onglets **épinglés** (affichés en pastilles en haut) et onglets classiques.
* Titre, favicon, indicateur de chargement, fermeture au survol.
* **Glisser-déposer** pour réordonner ; **clic molette** pour fermer ; menu contextuel
  (épingler, dupliquer, copier l'adresse, recharger, fermer les autres).
* Bouton « rouvrir l'onglet fermé » (Ctrl+Maj+T) et restauration de la session au démarrage.
* **Onglets en veille** : les onglets restaurés ne sont chargés qu'au moment où vous
  les ouvrez — au démarrage, une seule page est chargée, même avec vingt onglets.

### Trois moteurs de recherche (et plus)
| Moteur | Raccourci | Remarque |
|---|---|---|
| Google | `!g` | le plus complet |
| Brave Search | `!b` | index indépendant, sans traqueurs |
| Ecosia | `!e` | finance la plantation d'arbres |
| DuckDuckGo | `!d` | recherche privée |
| Startpage | `!s` | résultats Google anonymisés |
| Qwant | `!q` | moteur européen |

* Le moteur par défaut se choisit dans l'**assistant de premier lancement** ou dans **Paramètres**.
* `!b clavier mécanique` force Brave pour une requête ; `?texte` cherche directement.
* **Alt+Entrée** dans la barre d'adresse cherche avec le moteur suivant.
* Les pastilles de la page « nouvel onglet » changent aussi le moteur d'un clic.

### Rendu des pages : WebView2 (Chromium)
Le rendu web est confié à **Microsoft WebView2**, le moteur **Chromium/Blink** de Windows 11
(présent sur Windows 10/11 avec Edge, sinon installable en quelques Mo chez Microsoft). C'est ce
qui rend les sites modernes (YouTube, banques, WebGL, DRM…) réellement fonctionnels — écrire un
moteur HTML/CSS/JS complet est un chantier de plusieurs millions de lignes.

L'interface de navigation (barre latérale, barre d'adresse, pages internes) est, elle, du
**HTML/CSS/JS servi par Nova depuis le binaire** : c'est du code original, pas celui d'un autre
navigateur.

### Favoris (apps)

L'étoile de la barre d'adresse ajoute la page courante aux **favoris** (ou l'en
retire). Les favoris apparaissent :

* en **rangée d'icônes** en haut de la barre latérale, sous le logo — clic pour
  ouvrir, clic molette pour un nouvel onglet, clic droit pour le menu
  (*Ouvrir dans un nouvel onglet*, *Copier l'adresse*, *Retirer des favoris*) ;
* dans une section **Favoris** sur la page du nouvel onglet.

Jusqu'à 24 favoris, enregistrés dans `config.json`.

### Couleur du fond

**Paramètres → Apparence → Couleur du fond** : neuf teintes prêtes (noir OLED,
Nova sombre, violet nuit, forêt, bleu nuit, cacao, Nova clair, sépia, ciel) et
un sélecteur libre pour n'importe quelle couleur. Le réglage s'applique à la
barre latérale, à la barre d'adresse et aux pages internes — jamais aux sites
web. La palette complète (cartes, séparateurs, survols) et la couleur du texte
sont recalculées automatiquement d'après la luminance du fond choisi : un fond
sombre garde un texte clair, un fond clair passe en texte sombre. « Thème
standard » (la pastille `A`) revient aux couleurs d'origine.

### Vie privée
* **Blocage de 146 domaines** de régies publicitaires et de traqueurs
  (`assets/trackers.txt`), appliqué à deux niveaux :
  * résolution DNS neutralisée (`--host-resolver-rules=MAP *.doubleclick.net 0.0.0.0`), ce qui
    coupe les scripts publicitaires **et leurs sous-requêtes** ;
  * refus des navigations de premier niveau vers ces domaines.
* Aucun domaine de CDN, d'authentification tierce ou de bandeau de consentement n'est filtré :
  les sites ne cassent pas.
* Cookies, mots de passe et cache restent dans un **profil local** (`%LOCALAPPDATA%\Nova\WebView2`).
* Historique enregistré localement, consultable et effaçable depuis la barre latérale.

### Raccourcis clavier
| Action | Raccourci |
|---|---|
| Nouvel onglet / fermer l'onglet | `Ctrl+T` · `Ctrl+W` |
| Rouvrir l'onglet fermé | `Ctrl+Maj+T` |
| Barre d'adresse | `Ctrl+L` (ou `F6`) |
| Onglet suivant / précédent | `Ctrl+Tab` · `Ctrl+Maj+Tab` |
| Aller à l'onglet 1…9 | `Ctrl+1` … `Ctrl+9` |
| Précédent / suivant | `Alt+←` · `Alt+→` (aussi boutons 3/4 de la souris) |
| Recharger / arrêter | `Ctrl+R` · `F5` |
| Zoom | `Ctrl++` · `Ctrl+-` · `Ctrl+0` |
| Paramètres / historique | `Ctrl+,` · `Ctrl+H` |
| Rechercher dans la page | `Ctrl+F` |
| Ajouter / retirer des favoris | `Ctrl+D` |
| Plein écran | `F11` |
| Outils de développement | `F12` |

---

## 2. Lancer Nova

1. Copiez `Nova.exe` où vous voulez (Bureau, `C:\Program Files\Nova`…).
2. Double-cliquez. Au premier lancement, l'assistant propose le moteur de recherche, le blocage
   des traqueurs, la restauration de session et le thème.
3. Si Windows signale l'absence de **WebView2** (rare sur Windows 11, parfois sur Windows 10),
   installez-le une fois : <https://developer.microsoft.com/microsoft-edge/webview2/>
   (« Evergreen Standalone Installer »).

Nova n'écrit rien en dehors de `%APPDATA%\Nova` (réglages, historique, session) et de
`%LOCALAPPDATA%\Nova\WebView2` (profil du moteur de rendu).

---

## 3. Architecture du code

```
Cargo.toml              dépendances et profils de compilation
build.rs                compile le module C + les ressources Windows (icône, manifeste)
assets/
  nova.ico              icône multi-résolutions (générée par tools/make_icon.py)
  trackers.txt          liste de blocage locale
  ui/
    sidebar.html        barre latérale : onglets, épinglés, historique, menus
    toolbar.html        barre d'adresse, navigation, menu principal
    newtab.html         page « nouvel onglet » (moteur + sites fréquents)
    settings.html       paramètres, raccourcis, à propos
    history.html        page interne nova://history (filtre, regroupement, suppression)
    welcome.html        assistant de premier lancement
    inject.js           relais des raccourcis clavier / souris vers Rust
native/
  nova_core.h/.c        accélérateur C (ABI versionnée, vérifiée au démarrage)
src/
  main.rs               fenêtre, onglets, cycle de vie, routage des messages
  ui.rs                 ressources embarquées + injection de l'état
  config.rs             réglages, historique, session (JSON)
  engines.rs            moteurs de recherche et construction des URL
  urls.rs               interprétation de la barre d'adresse (+ tests unitaires)
  blocker.rs            correspondance de la liste anti-traqueurs
  accel.rs              passerelle FFI vers le module C
  platform.rs           Windows : DWM, thème système, WebView2, presse-papiers
tools/make_icon.py      génération de l'icône (sans dépendance externe)
tools/test_nova_core.c  suite de tests du module C (60 vérifications)
RAPPORT-AUDIT.md        audit complet du code : 29 défauts trouvés et corrigés (v1.0.2)
```

### Comment l'interface parle au cœur
Les vues envoient `window.ipc.postMessage({cmd:"…", …})` ; `main.rs` traite la commande sur le fil
de la boucle d'événements, puis renvoie **l'état complet** aux surfaces d'interface, qui le
rejouent (`window.NovaUI.render(state)`). Une seule source de vérité, aucun verrou partagé.

### Rôle du module C (`native/nova_core.c`)
| Fonction | Usage |
|---|---|
| `nova_find_ci` | recherche Boyer-Moore-Horspool insensible à la casse (liste de blocage) |
| `nova_host_of` | extraction de l'hôte d'une URL, en minuscules, sans allocation |
| `nova_ends_with_ci` | correspondance de suffixe de domaine (`ads.doubleclick.net`) |
| `nova_fnv1a64` | hachage FNV-1a utilisé pour indexer les sites fréquents |
| `nova_utf8_prefix` | troncature de titres sans casser un caractère accentué |
| `nova_looks_like_host` | décide « adresse » ou « recherche » pour la barre d'adresse |
| `nova_abi_version` | contrôle de compatibilité ABI au démarrage |

Compilé par `clang-cl` en `/O3` (avec `/arch:AVX2` sur x86_64). Rust appelle ces fonctions sur des
tranches bornées (`&str`) : aucune chaîne non terminée, aucun `memcpy` non vérifié.

---

## 4. Recompiler depuis les sources

### Windows (chaîne native, recommandé)
```powershell
# 1. Rust : https://rustup.rs
# 2. Visual Studio Build Tools 2022 (charge de travail « Développement Desktop en C++ »)
git clone <ce-dépôt> ; cd nova
cargo build --release
# -> target\release\nova.exe
```
Le module C est compilé automatiquement par `cc` (MSVC). Pour produire un binaire sans lui :
`cargo build --release --no-default-features`.

### Compilation croisée depuis Linux
```bash
rustup target add x86_64-pc-windows-msvc
cargo install cargo-xwin
# clang-cl + lld-link + llvm-lib + llvm-rc (paquets clang, lld, llvm)
cargo xwin build --release --target x86_64-pc-windows-msvc
```
`wry`/`webview2-com` utilisent le **WebView2Loader import-lib** (`x64/WebView2Loader.dll.lib`)
fourni par la crate : le lien avec `lld-link` fonctionne sans Visual Studio.

### Tests
```bash
cargo test                     # analyse de la barre d'adresse, blocage des traqueurs
cargo test --no-default-features   # variante sans module C
```

---

## 5. Performances : ce qui a été optimisé

La première version ralentissait les chargements. Trois causes ont été identifiées et corrigées :

| Cause | Correctif |
|---|---|
| `wry` créait un **environnement WebView2 par onglet** (aucun cache sous Windows) : chaque nouvel onglet repayait l'initialisation du moteur | Un environnement unique est créé au premier lancement puis **réutilisé** par toutes les vues (`with_environment`) : un seul processus de navigateur, cache HTTP et résolution partagés |
| `navigation_handler` correspond à WebView2 `NavigationStarting`, qui se déclenche **pour chaque iframe** : une bannière publicitaire ou un lecteur vidéo provoquait une reconstruction complète de l'état et trois `ExecuteScript` — et pouvait afficher l'URL de l'iframe dans la barre d'adresse | Le rappel ne fait plus que décider du **blocage**. L'URL de premier niveau vient de `ContentLoading`/`NavigationCompleted`, qui décrivent toujours le document principal |
| L'interface était **reconstruite intégralement** à chaque événement (tous les onglets, tous les favicons re-téléchargés, la liste d'historique en entier) et l'historique était **écrit sur disque** de façon synchrone à chaque fin de chargement | Rendu **incrémental** (les nœuds DOM sont réutilisés et réordonnés, les favicons instanciés une seule fois), **regroupement des repaints à 60 ms**, écritures disque différées de 4 s, historique comparé **sans allocation** |

Effets mesurables :

* **Démarrage** : les onglets restaurés ne créent plus de moteur de rendu avant d'être ouverts ;
* **Navigation** : le travail effectué dans la boucle d'événements par page est divisé par
  plusieurs dizaines (une iframe ne déclenche plus rien côté interface) ;
* **Blocage** : les domaines publicitaires sont résolus en `~NOTFOUND` au lieu de `0.0.0.0` —
  échec de résolution immédiat, aucune tentative de connexion (et plus de risque de tomber sur
  un serveur local, ce que fait Windows avec `0.0.0.0`) ;
* **Mémoire** : un seul processus de navigateur partagé, plus les moteurs des onglets en veille.

Les tokens d'exécution de la boucle d'événements sont désormais : état des onglets (léger) à
chaque repaint, historique **uniquement quand le panneau est ouvert**, et rien du tout pour une
navigation d'iframe non bloquée.

## 6. Limites assumées (honnêtement)

* **La Game Bar de Windows** : depuis la v1.3.0, Nova prend en charge les
  protocoles de la Game Bar dans `HKCU\Software\Classes` et les ignore, ce qui
  fait disparaître la boîte « Obtenir une application pour ouvrir ce lien » même
  quand *Windows* est à l'origine de l'ouverture (raccourci `Win+G`, manette).
  Le réglage est désactivable dans les Paramètres. Si la Xbox Game Bar
  n'est pas installée, Windows affiche « Obtenir une application pour ouvrir ce
  lien ». C'est une boîte de dialogue du système : voir la section
  correspondante de `LISEZMOI.txt` pour la faire disparaître.

* **Import** : les **mots de passe**, les **cookies** et les **sessions** d'un
  autre navigateur ne sont pas importables (chiffrés par Windows avec la clé du
  compte d'origine ; Nova a de plus son propre profil de navigation). Si un
  navigateur est ouvert pendant l'analyse, son historique peut être verrouillé :
  les favoris se lisent malgré tout, et l'erreur est signalée par source.
  Un import est borné à 4 000 visites par source et 240 favoris au total.

* **Ce n'est pas un moteur de rendu écrit de zéro.** Le HTML/CSS/JS des sites est rendu par
  WebView2/Chromium, comme la plupart des navigateurs « maison » (et comme Arc, qui s'appuie sur
  Chromium). Écrire un moteur équivalent représenterait des années-homme.
* **Pas de synchronisation de compte**, ni d'extensions Chrome, ni de traduction intégrée.
* **Blocage de publicités** : liste locale de domaines, volontairement courte et sûre. Ce n'est pas
  uBlock Origin (pas de filtrage par sélecteur CSS, ni de listes EasyList complètes).
* **Une seule fenêtre**, plusieurs onglets. Le **plein écran** (`F11`) et le plein écran d'une
  **vidéo** fonctionnent : l'interface s'efface, la fenêtre passe en plein écran, et tout revient
  à la sortie (ou au changement d'onglet). La détection se fait au niveau du moteur
  (`ContainsFullScreenElementChanged`), donc elle ne dépend pas du JavaScript de la page ; les
  onglets **privés** ne sont pas encore implémentés.
* Les onglets **en veille** (restaurés mais non ouverts) n'exécutent aucun script tant que vous
  ne cliquez pas dessus : c'est voulu, mais une page qui jouait de la musique en arrière-plan
  ne le fera plus après un redémarrage.
* L'exécutable **n'est pas signé numériquement** : Windows SmartScreen peut afficher un
  avertissement au premier lancement (« Informations complémentaires » → « Exécuter quand même »).

---

## 7. Licence

MIT. Le code de Nova est original ; il repose sur des bibliothèques libres :
[`wry`](https://crates.io/crates/wry) et [`tao`](https://crates.io/crates/tao) (Tauri Programme),
[`windows`](https://crates.io/crates/windows), [`serde`](https://serde.rs),
[`percent-encoding`](https://crates.io/crates/percent-encoding), [`dirs`](https://crates.io/crates/dirs).

---

## 8. Journal des versions

### v1.3.2 — icône de Nova, logos officiels, sources documentées *(version livrée)*

**Corrigé**

* **L'icône de Nova est enfin la bonne** dans la barre de titre et dans la barre
  des tâches : la fenêtre reçoit désormais explicitement l'icône
  (`Icon::from_rgba`, pixels engendrés par `tools/make_icon.py`), au lieu de
  laisser Windows afficher l'icône générique de l'exécutable. La même source
  produit le fichier `.ico` des ressources, le logo PNG et les pixels de la
  fenêtre : impossible qu'ils divergent.
* **Favicons des onglets** : les logos carrés dessinés bord à bord (X, YouTube,
  Reddit…) s'affichaient comme des rectangles pleins ; ils sont maintenant
  affichés « à l'intérieur » de leur case, avec une petite marge.

**Nouveau**

* **Logos officiels des moteurs** : Google, Brave Search, Ecosia, DuckDuckGo,
  Startpage et Qwant sont reconnaissables dans toute l'interface (page du nouvel
  onglet, Paramètres, barre latérale, assistant). Les images sont récupérées aux
  sources officielles par `tools/fetch_engine_icons.py`, embarquées dans le
  binaire et servies en `data:` (aucune requête réseau pour les afficher). Sans
  elles, `window.NovaEngineIcon` retombe sur la pastille colorée : le programme
  fonctionne sans aucune marque tierce.
* **Archive des sources** : `Nova-1.3.2-sources.zip` contient tout ce qu'il faut
  pour recompiler (Rust, C, interface, ressources, outils de test) avec
  `README-DEV.md` — présentation du projet, architecture, procédures de
  compilation et de test — et `LICENCES-TIERS.md`, qui détaille les marques, les
  logos et les licences des composants. `tools/sources_zip.sh` la reconstruit.
* L'archive de distribution contient elle aussi ces deux documents, plus les
  ressources nécessaires à la recompilation (trackers, logos, icônes) : elle
  était incomplète à ce sujet.

### v1.3.1 — le message de Windows coupé à la source, assistant avec import *(version livrée)*

**Corrigé**

* La boîte de Windows revenait encore en v1.3.0, sous une autre forme
  (« Sélectionner une application pour ouvrir ce lien *ms-gamingoverlay* ») :
  preuve que la demande ne vient pas de Nova mais de **Windows lui-même**
  (touche `Win+G`, manette branchée, jeu lancé). Couvrir le protocole ne
  suffisait donc pas : Nova **coupe la demande à la source**, pour le compte
  courant uniquement :
  * `HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR\AppCaptureEnabled = 0`
  * `HKCU\System\GameConfigStore\GameDVR_Enabled = 0`
  * plus le gestionnaire de secours de la v1.3.0, qui garantit qu'aucune de ces
    adresses n'aboutisse sur une boîte de dialogue.
  Les valeurs trouvées avant l'intervention sont mémorisées (`dvr_prev`) et
  reposées à l'identique si le réglage est décoché. L'état réel est affiché
  dans les Paramètres, avec le compteur de refus et le chemin du journal.

**Nouveau**

* **L'assistant de premier lancement demande quoi importer** : nouvelle étape
  listant une ligne par navigateur détecté, avec case à cocher, « Importer la
  sélection » et « Plus tard ». L'import silencieux du démarrage n'a plus lieu
  tant que l'assistant n'est pas terminé — vous décidez.
* Le réglage « supprimer le message de Windows » est proposé dès l'assistant.

### v1.3.0 — fin du message Windows, import par application, interface assagie *(version livrée)*

**Corrigé**

* La boîte de dialogue « Obtenir une application pour ouvrir ce lien
  *ms-gamingoverlay* » **ne peut plus réapparaître**, même déclenchée par
  Windows lui-même (raccourci `Win+G`, manette branchée). Cause : Windows ouvre
  ce protocole sans passer par le navigateur, et, faute de logiciel pour
  l'accepter, propose d'aller le chercher. Nova déclare donc les trois
  protocoles de la Game Bar (`ms-gamingoverlay`, `ms-gamebar`,
  `ms-gamebarservices`) dans **`HKCU\Software\Classes`** et se contente de
  quitter immédiatement lorsqu'il est appelé ainsi (`--ignore-protocol`).
  Aucun droit administrateur, aucune écriture si un vrai gestionnaire existe,
  et la désactivation supprime exactement la clé créée par Nova.
  *Réglage : Paramètres > « Message de Windows sur l'overlay de jeu ».*

**Nouveau**

* **Import par application** : la page `nova://import` présente une ligne par
  navigateur (avec son logo, ses profils regroupés et les fichiers trouvés) et
  deux puces — **Favoris** / **Historique** — pour choisir exactement ce qui est
  importé. Boutons « Tout sélectionner » et « Rien ».

**Modifié**

* **Interface assagie** : palette neutre et posée (mêmes valeurs en clair qu'en
  sombre), un seul accent, rayons de bordure homogènes, plus de dégradés, de
  halos flous, d'ombres lourdes ni de survols qui font sauter les éléments.
  La marque est désormais un simple carré arrondi plutôt qu'un logo à dégradé.
  Aucun changement de disposition ni de fonction.

### v1.2.1 — la boîte de dialogue « ms-gamingoverlay » ne peut plus venir de Nova *(version livrée)*

**Corrigé**

* La boîte de dialogue Windows « Obtenir une application pour ouvrir ce lien
  'ms-gamingoverlay' » apparaissait au lancement. Cause : Nova laissait le
  moteur WebView2 **confier à Windows** toute adresse dont il ne connaissait pas
  le protocole ; quand aucun logiciel n'est enregistré pour ce protocole,
  Windows propose d'aller le chercher dans le Microsoft Store.
  Désormais Nova interroge le registre (`HKEY_CLASSES_ROOT\<protocole>`,
  valeurs `URL Protocol` + `shell\open\command`) **avant** de laisser passer :
  un protocole géré s'ouvre dans son logiciel (`mailto:`, `ms-settings:`,
  `steam:`…), un protocole non géré est refusé sans jamais atteindre Windows.
  Les protocoles de la Xbox Game Bar (`ms-gamingoverlay`, `ms-gamebar`,
  `ms-gamebarservices`) sont refusés dans tous les cas : l'overlay de jeu n'a
  rien à faire dans une fenêtre de navigateur.
* Un onglet restauré dont l'adresse n'est pas chargeable par un navigateur est
  écarté au chargement de la session (`config::loadable_url`) : sans ce filtre,
  un onglet corrompu redemandait le protocole à Windows **à chaque démarrage**.
* Les refus sont comptés (`Paramètres > Liens non ouverts`) et journalisés dans
  `%APPDATA%\Nova\protocoles-refuses.log`, avec l'onglet et l'adresse d'origine
  — de quoi prouver qui a demandé l'ouverture si le message revient.

### v1.2.0 — import des données d'un autre navigateur *(version livrée)*

**Nouveau**

* **Import des favoris et de l'historique** d'un autre navigateur, depuis la
  page interne `nova://import` (bouton « Importer… » dans les Paramètres) :
  * analyse de la machine — Chrome, Edge, Brave, Vivaldi, Chromium, Ecosia,
    Opera, Opera GX (profils `Default`, `Profile 1..3`) et chaque profil
    Firefox ;
  * lecture directe des fichiers : `Bookmarks` (JSON), `History` (base SQLite
    de Chromium), `places.sqlite` (Firefox) et l'export HTML des favoris ;
  * **fichier au choix** : boîte de dialogue système (rfd), format reconnu
    automatiquement ;
  * fusion sans doublon (comparaison sur l'URL canonique) ou remplacement de
    la liste existante ; compte rendu détaillé (favoris, visites, sources,
    doublons écartés, erreurs) ;
  * **import automatique au démarrage**, activé par défaut et idempotent : une
    URL déjà connue ne voit pas son compteur de visites grimper.
* Plafond de favoris porté de 24 à **240** (l'import en apporte facilement
  plus). La barre latérale affiche les 24 premiers et un compteur « +N » ; la
  page du nouvel onglet les affiche tous.

**Sous le capot**

* `src/sqlread.rs` : **lecteur SQLite minimal en lecture seule, sans aucune
  dépendance** (arbre B par pages, varints, enregistrements, chaînes de pages
  de débordement) — lire quelques colonnes ne justifiait pas d'embarquer SQLite
  entier. Colonnes résolues **par leur nom** (les schémas changent d'une version
  de navigateur à l'autre).
* `src/import.rs` : analyseurs (JSON, SQLite, HTML) et fusion ; détection des
  profils installés.
* Les lectures disque (détection, bases, historique) se font sur des **fils
  dédiés** : l'interface ne se fige jamais, même sur une base de plusieurs
  mégaoctets.
* Jeu de test **réel** (`tools/fixtures/`, produit par
  `tools/make_import_fixtures.py` avec un vrai SQLite) : 397 lignes, un titre de
  7 600 octets (pages de débordement), des lignes supprimées, un schéma aux
  colonnes mélangées. Il a mis au jour **trois bugs de lecture** (en-tête de la
  page 1, descente des pages intérieures, taille « locale » d'un enregistrement
  débordant) — corrigés et couverts par des tests.

### v1.1.1 — plein écran vidéo, deuxième correctif

Le plein écran d'une vidéo ne masquait toujours pas la barre latérale chez
certains utilisateurs : la détection reposait uniquement sur l'événement
JavaScript `fullscreenchange`, que tous les moteurs n'émettent pas. Nova
surveille désormais le **plein écran au niveau du moteur** (événement COM
`ContainsFullScreenElementChanged`), avec deux replis : l'événement JavaScript
et une relecture de l'état deux fois par seconde. La fenêtre passe en plein
écran puis revient, comme dans Chrome.

### v1.1.0 — favoris, couleur de fond, plein écran vidéo

**Nouveau**

* **Favoris (apps)** : l'étoile de la barre d'adresse ajoute la page courante,
  les favoris s'affichent en rangée d'icônes dans la barre latérale et sur la
  page du nouvel onglet (24 au maximum).
* **Couleur du fond** : neuf teintes prêtes + sélecteur libre, appliquées à
  toute l'interface ; la palette et la couleur du texte se recalculent
  automatiquement selon la luminance du fond.

**Corrigé**

* **Plein écran vidéo** : mettre une vidéo en plein écran masque maintenant la
  barre latérale et la barre d'adresse, et donne toute la fenêtre à la vidéo.
  La barre latérale étant une vue séparée, elle restait affichée par-dessus la
  vidéo. Changer d'onglet pendant le plein écran rend l'interface, comme dans
  Chrome.

### v1.0.3 — audit visuel

Les défauts d'interface ne se voient pas dans un diff. Chaque page a donc été
**rendue dans Chromium à la taille réelle de sa WebView** (248 × 900 px pour la
barre latérale) puis inspectée, captures et géométrie à l'appui
(`tools/ui_shot.py`, `tools/ui_probe.py`). **8 défauts visuels** corrigés, dont :

* les favicons des onglets épinglés s'affichaient **par-dessus la lettre** et
  débordaient du carré ; ceux à fond transparent reposaient sur une plaque
  rose/verte (lettre de repli restée peinte derrière l'image) ;
* la page **Historique restait sombre** en thème clair — le fichier
  n'appliquait tout simplement jamais le thème ;
* l'**assistant de premier lancement** n'avait aucune palette claire et ses
  puces étaient illisibles sur fond clair ;
* les **interrupteurs éteints** et la barre de défilement étaient invisibles en
  thème clair (couleurs codées en dur) ;
* le réglage **« Système » était ignoré** : sur un bureau clair, Nova restait
  sombre. `main.rs` pousse désormais le thème déjà résolu.

Vérification automatique : **14 éléments débordant du cadre avant, 0 après** ;
**4 pages sur 6 restaient sombres en mode « Système » clair, 0 après**.
Comparatif visuel : `audit_ui/AVANT-APRES-visuel.png`.

### v1.0.2 — audit complet du code

Un audit complet (relecture ligne à ligne, cas limites, analyse statique `gcc -fanalyzer` /
`clang --analyze` / `clippy` sur les deux cibles, tests) a relevé **29 défauts**, tous corrigés.
Le détail complet, par gravité, avec fichiers et symptômes, est dans **`RAPPORT-AUDIT.md`**.
Les plus visibles à l'usage :

* `github.com:8080` et les domaines **punycode** (`exemple.xn--p1ai`) ne se chargeaient pas ;
* `https://GitHub.com/PaTh` perdait son chemin ;
* les listes d'onglets épinglés/normaux se détruisaient mutuellement leurs nœuds DOM (clignotement
  et re-téléchargement de tous les favicons à chaque changement de titre) ;
* `reload`, `back`, `forward`, `devtools`, `find`… étaient **sans effet** sur un onglet en veille ;
* le panneau d'historique restait figé ; « copier l'adresse » ne copiait rien ;
* `nova://history` était une adresse sans page (écran blanc) ;
* la compilation échouait avec un message obscur s'il n'y avait pas de compilateur C.

### v1.0.1

Onglets **en veille** (les onglets restaurés ne créent leur moteur qu'au premier clic) et
optimisations de latence décrites à la section 5.

### v1.0.0

Première version livrée : onglets verticaux, sélecteur de moteur au premier lancement,
blocage anti-traqueurs, module d'accélération C.
