# Nova — navigateur web à onglets verticaux

**Nova** est un navigateur de bureau pour **Windows x64**, écrit en **Rust** (avec un
cœur d'accélération en **C**), compilé en **un seul exécutable**. Les onglets vivent
dans une barre latérale à gauche, comme dans Arc, et la page occupe toute la largeur
restante. L'interface est en français.

| | |
|---|---|
| **Version** | 1.3.2 |
| **Cible** | Windows 10 / 11, 64 bits (un seul `Nova.exe`, 15 DLL système) |
| **Langages** | Rust 2021 (programme), C11 (cœur d'accélération), HTML/CSS/JS (interface, embarquée) |
| **Moteur de rendu** | WebView2 (Chromium), celui fourni par Windows |
| **Licence** | MIT (voir `LICENSE`) — marques et logos tiers : `LICENCES-TIERS.md` |

---

## 1. Ce que fait Nova

* **Onglets verticaux** dans une barre latérale, avec épinglage, liste des onglets
  récents fermés (`Ctrl+Maj+T`), recherche instantanée (`Ctrl+Maj+F`).
* **Moteurs de recherche** : Google, Brave Search, Ecosia, DuckDuckGo, Startpage,
  Qwant — logos officiels dans l'interface, choix au premier lancement, changement
  à tout moment, et forcage ponctuel avec `!g`, `!b`, `!e`, `!d`, `!s`, `!q`.
* **Favoris** (appelés « apps ») : bandeau de raccourcis dans la barre latérale et
  grille sur la page du nouvel onglet.
* **Historique** : page complète (`Ctrl+H`), recherche, suppression d'une entrée
  ou de tout l'historique.
* **Import des données d'un autre navigateur** : Chrome, Edge, Brave, Vivaldi,
  Opera, Ecosia (fichiers `Bookmarks` / `History`) et Firefox (`places.sqlite`),
  plus les exports HTML. Une ligne par navigateur, choix des favoris et/ou de
  l'historique, fusion sans doublon.
* **Filtrage des publicités et traqueurs** par liste locale (146 domaines) :
  résolution DNS neutralisée + blocage des redirections, aucune connexion sortante.
* **Plein écran vidéo** : la barre latérale et la barre d'adresse disparaissent
  quand une vidéo passe en plein écran (`F11` pour le plein écran de Nova).
* **Apparence réglable** : thème sombre, clair ou système ; couleur de fond au
  choix (appliquée à la barre latérale, à la barre d'adresse et aux pages internes).
* **Fin du message Windows « ms-gamingoverlay »** : Nova coupe la demande d'overlay
  de jeu à la source, dans le compte de l'utilisateur uniquement, et ignore ces
  adresses s'il est appelé (`--ignore-protocol`).
* **Une seule fenêtre, un seul fichier** : aucune installation, aucun service,
  aucune donnée envoyée à un serveur.

Limites assumées (documentées et vérifiées) : rendu WebView2, pas de synchronisation
de compte ni d'extensions, une seule fenêtre, binaire non signé (SmartScreen),
mots de passe et cookies non importables depuis un autre navigateur.

---

## 2. Compiler

### 2.1 Sous Windows, avec la chaîne MSVC

```powershell
cargo test                       # 29 tests unitaires (hôte)
cargo build --release            # -> target\release\nova.exe
```

`WebView2` doit être présent (il l'est sur Windows 10/11 récents ; sinon installez le
« WebView2 Runtime » de Microsoft). Le fichier `build.rs` compile les ressources
Windows (icône `assets/nova.ico`, manifeste, version) et, si ce n'est pas possible,
laisse la compilation se poursuivre avec un avertissement.

### 2.2 Compilation croisée depuis Linux (c'est ainsi que Nova est construit ici)

```bash
bash tools/install_chain.sh      # rustup + cible MSVC + cargo-xwin + lld + chromium
export CARGO_BUILD_JOBS=1
cargo test
cargo xwin clippy --all-targets --target x86_64-pc-windows-msvc
cargo xwin build --release --target x86_64-pc-windows-msvc
cp target/x86_64-pc-windows-msvc/release/nova.exe .
bash tools/package.sh            # -> Nova-<version>-win64.zip (+ sources)
bash tools/sources_zip.sh        # -> Nova-<version>-sources.zip (sources seules)
```

L'icône de l'application (`assets/nova.ico`), le logo (`assets/nova-logo.png`) et
les pixels de l'icône de fenêtre (`assets/nova-64.rgba`, 64×64 RGBA) sont **engendrés**
par `python3 tools/make_icon.py` : le dessin est vectoriel, sans dépendance (champs de
distance signés, encodage PNG/ICO à la main).

---

## 3. Architecture

```
src/
  main.rs       fenêtre (tao), boucle d'événements, onglets, IPC de l'interface,
                favoris, historique, plein écran, import, applique les réglages
  ui.rs         chargement des pages d'interface, injection de l'état et de la
                peau commune (`NovaSkin`), logos des moteurs en `data:`
  config.rs     configuration et session (JSON), horodatage ISO sans dépendance
  urls.rs       interprétation de la barre d'adresse, schémas, URL canoniques
  engines.rs    moteurs de recherche (identifiant, URL de recherche, « bang »)
  blocker.rs    liste locale de traqueurs -> règles de résolution pour WebView2
  import.rs     détection et lecture des navigateurs installés (favoris, historique)
  sqlread.rs    lecteur SQLite minimal (lecture seule, pour `places.sqlite`)
  accel.rs      cœur d'accélération natif : ABI, repli, appel des fonctions C
  block.rs      verrou d'instance unique
  platform.rs   code spécifique Windows : thème, icône, boîtes natives, Game Bar
native/
  nova_core.c   cœur C : hachage, comparaison d'URL, découpage — appelé par Rust
  nova_core.h
assets/
  ui/*.html     interface (barre latérale, barre d'adresse, nouvel onglet, réglages,
                historique, assistant, import) + inject.js (raccourcis globaux)
  engines/*.png logos officiels des moteurs (voir LICENCES-TIERS.md)
  trackers.txt  liste des domaines filtrés
  nova.ico, nova-logo.png, nova-64.rgba   icônes (engendrées)
tools/
  install_chain.sh  mise en place de la chaîne de compilation croisée
  package.sh        archive de distribution (binaire + sources)
  sources_zip.sh    archive des sources seules (avec README-DEV.md)
  check_js.py       contrôle syntaxique des scripts de l'interface (8 scripts)
  ui_probe.py       sonde de mise en page (30 scènes × 2 thèmes)
  ui_shot.py        banc de captures (32 scènes × 2 thèmes -> audit_ui/)
  test_nova_core.c  60 vérifications du cœur C
  ui_fullscreen_test.py  non-régression du plein écran vidéo
  make_icon.py      engendre les icônes
  fetch_engine_icons.py  récupère les logos officiels des moteurs
```

**Comment Rust et l'interface communiquent.** Chaque surface (barre latérale, barre
d'adresse, pages internes) est une vue WebView2 qui reçoit son état par injection
(`window.__NOVA__`, puis `NovaUI.render` / `NovaPage.render`) et renvoie des commandes
JSON (`window.ipc.postMessage`). Les traitements longs — analyse des navigateurs,
lecture des bases — tournent sur des fils dédiés (`nova-import-scan`, `-load`, `-pick`)
et renvoient leur résultat par événements, sans bloquer l'affichage.

**Pourquoi du C ?** `native/nova_core.c` contient les opérations appelées des milliers
de fois par navigation (comparaison d'URL canonique, découpage, hachage). Le module Rust
`accel.rs` vérifie l'ABI, appelle les fonctions C et **retombe sur une implémentation
Rust** si la bibliothèque est absente ou incompatible : le navigateur fonctionne à
l'identique, seule la vitesse change. Les 60 vérifications de `tools/test_nova_core.c`
comparent les deux implémentations.

---

## 4. Tests et contrôles

| Outil | Ce qu'il vérifie |
|---|---|
| `cargo test` | 29 tests unitaires (import, URL, configuration, SQLite, accélération, filtrage) |
| `cargo xwin clippy --all-targets` | analyse statique croisée Windows, **0 avertissement** attendu |
| `tools/check_js.py` | syntaxe des 8 scripts de l'interface (Node ou repli interne) |
| `tools/ui_probe.py dark` / `light` | mise en page : débordements, chevauchements, contrastes (0 anomalie attendue) |
| `tools/ui_shot.py dark` / `light` | captures de toutes les scènes dans `audit_ui/` (relues une par une) |
| `tools/test_nova_core.c` | 60 vérifications du cœur C, en regard de l'implémentation Rust |
| `tools/ui_fullscreen_test.py` | le menu de gauche disparaît bien en plein écran vidéo |

Le banc de captures (`ui_shot.py`) reconstitue l'état exact que Rust injecte aux pages :
il rend les mêmes documents dans Chromium sans interface graphique, ce qui permet de
vérifier visuellement chaque écran (les deux thèmes) sur une machine sans Windows.

---

## 5. Données de l'utilisateur

| Chemin | Contenu |
|---|---|
| `%APPDATA%\Nova\config.json` | réglages (moteur, thème, couleur de fond, favoris, bornes…) |
| `%APPDATA%\Nova\session.json` | onglets de la session précédente |
| `%APPDATA%\Nova\historique.json` | historique (5 000 visites glissantes) |
| `%APPDATA%\Nova\protocoles-refuses.log` | adresses système que Nova a refusé d'ouvrir |
| `%LOCALAPPDATA%\Nova\WebView2\` | profil du moteur de rendu (cookies, cache) |

Rien n'est écrit ailleurs, rien n'est envoyé sur le réseau. Les clés de registre
touchées par Nova sont **dans le compte de l'utilisateur seulement** (`HKCU`) :
`Software\Classes\ms-gamingoverlay` (+ `ms-gamebar`, `ms-gamebarservices`) et, si le
réglage est actif, les deux valeurs de capture de jeu (`GameDVR\AppCaptureEnabled`,
`GameConfigStore\GameDVR_Enabled`). Les valeurs trouvées avant l'intervention sont
mémorisées et reposées à l'identique si l'utilisateur décoche le réglage.

---

## 6. Historique des versions

| Version | Apports principaux |
|---|---|
| 1.0 | premier navigateur : onglets verticaux, six moteurs, favoris |
| 1.1 | audit complet, filtrage des traqueurs, plein écran vidéo, couleur de fond |
| 1.2 | import des données d'un autre navigateur (favoris + historique) |
| 1.2.1 | la boîte `ms-gamingoverlay` ne peut plus venir du navigateur |
| 1.3.0 | import par application, apparence assagie, protocoles couverts |
| 1.3.1 | demande de Windows coupée à la source, assistant avec choix à importer |
| 1.3.2 | icône de Nova dans la fenêtre, logos officiels des moteurs, sources en archive |

Le détail complet des corrections, des mesures et des relectures se trouve dans
`RAPPORT-AUDIT.md` (13 passes d'audit).

---

## 7. Licence et marques

Le code de Nova est distribué sous **licence MIT** (voir `LICENSE`) : utilisation,
modification et redistribution libres, avec conservation de la mention de copyright.

Les logos des moteurs de recherche appartiennent à leurs titulaires (Google, Brave
Software, Ecosia, DuckDuckGo, Startpage, Qwant) et sont utilisés uniquement pour
**désigner** le moteur correspondant dans l'interface. Les conditions, les sources
exactes de chaque image et les licences des composants Rust sont détaillées dans
`LICENCES-TIERS.md`. Nova n'est affilié à aucune de ces sociétés.
