# Licences des composants tiers

Nova (code) est distribué sous licence **MIT** — voir `LICENSE`. Ce fichier couvre
tout ce que Nova intègre ou affiche et qui ne lui appartient pas.

---

## 1. Marques et logos des moteurs de recherche

Les images de `assets/engines/` **ne sont pas** couvertes par la licence MIT de
Nova. Ce sont des marques déposées de leurs titulaires respectifs ; elles sont
affichées uniquement pour **désigner** le moteur de recherche correspondant
(usage nominatif), comme le font tous les navigateurs. Aucune affiliation,
aucun partenariat, aucune approbation n'est sous-entendue.

| Fichier | Titulaire de la marque | Source de l'image (récupérée le 2026-10-16) |
|---|---|---|
| `google.png` | Google LLC | `https://www.gstatic.com/images/branding/googleg/1x/googleg_standard_color_128dp.png` |
| `brave.png` | Brave Software, Inc. | `https://brave.com/static-assets/images/brave-logo-sans-text.svg` |
| `ecosia.png` | Ecosia GmbH | `https://www.ecosia.org/apple-touch-icon.png` |
| `duckduckgo.png` | DuckDuckGo, Inc. | `https://duckduckgo.com/assets/icons/meta/DDG-icon_256x256.png` |
| `startpage.png` | Startpage B.V. | `https://www.startpage.com/favicon.ico` |
| `qwant.png` | Qwant SAS | `https://www.qwant.com/favicon.ico` |

Ces images sont récupérées par le script `tools/fetch_engine_icons.py` (recadrage
et réduction à 64×64, transparence conservée). **Pour retirer un logo**, supprimez
le fichier correspondant et recompilez : l'interface retombe automatiquement sur
une pastille colorée portant l'initiale du moteur (`window.NovaEngineIcon`). La
distribution peut donc se faire sans aucun logo tiers.

Si un titulaire demande le retrait d'un logo, il suffit de supprimer le fichier
concerné dans `assets/engines/` : aucune autre modification n'est nécessaire.

---

## 2. Noms des moteurs et chaînes de recherche

Les noms des moteurs (« Google », « Brave Search », « Ecosia »…) sont des marques
de leurs titulaires respectifs. Les URL de recherche utilisées par `src/engines.rs`
sont publiques et ne nécessitent aucune clé d'API :

| Moteur | Paramètre d'URL |
|---|---|
| Google | `https://www.google.com/search?q=` |
| Brave Search | `https://search.brave.com/search?q=` |
| Ecosia | `https://www.ecosia.org/search?q=` |
| DuckDuckGo | `https://duckduckgo.com/?q=` |
| Startpage | `https://www.startpage.com/sp/search?query=` |
| Qwant | `https://www.qwant.com/?q=` |

---

## 3. Composants logiciels utilisés

Nova est construit avec Rust et un petit nombre de paquets, tous sous licence
permissive. Versions telles que figées dans `Cargo.lock`.

| Composant | Rôle | Licence |
|---|---|---|
| `tao` | fenêtre et boucle d'événements | Apache-2.0 / MIT |
| `wry` | vue WebView2 (moteur de rendu) | Apache-2.0 / MIT |
| `webview2-com`, `webview2-com-sys` | liaison COM avec WebView2 | Apache-2.0 / MIT |
| `windows`, `windows-core`, `windows-result`, `windows-strings`, `windows-link`, `windows-interface`, `windows-implement`, `windows-future`, `windows-numerics`, `windows-threading`, `windows-collections` | API Windows (registre, coquille, presse-papiers, DWM…) | Apache-2.0 / MIT |
| `rfd` | boîtes de dialogue de fichier (Windows) | MIT |
| `serde`, `serde_json` | configuration, session, historique, échanges avec l'interface | Apache-2.0 / MIT |
| `serde_derive`, `proc-macro2`, `quote`, `syn`, `synstructure` | macros de dérivation (compilation uniquement) | Apache-2.0 / MIT |
| `ico` | lecture des icônes `.ico` | Apache-2.0 / MIT |
| `winresource` | ressources Windows (icône, manifeste, version) | MIT |
| `unicase`, `unicode-segmentation`, `unicode-ident`, `zerocopy`, `percent-encoding`, `urlpattern`, `http`, `bytes`, `form_urlencoded`, `idna`, `smallvec`, `tendril`, `serde_urlencoded`, `thiserror`, `tracing`, `log`, `once_cell`, `pin-project-lite`, `bitflags`, `dpi`, `percent-encoding`, `raw-window-handle`, `same-file`, `sctk`, `x11-dl`, `memchr`, `cfg-if`, `itoa`, `ryu`, `libc`, `fastrand`, `dyn-clone`, `futures-*`, `parking_lot*`, `lock_api`, `scopeguard`, `slab`, `zune-inflate`, `png`, `flate2`, `miniz_oxide`, `crc32fast`, `simd-adler32`, `adler2`, `indexmap`, `equivalent`, `hashbrown`, `winapi-util`, `allocator-api2`, `zerofrom`, `zerovec`, `tinystr`, `writeable`, `litemap`, `icu_locale*`, `icu_properties*`, `icu_normalizer*`, `potential_utf`, `stable_deref_trait`, `yoke`, `yoke-derive`, `zerofrom-derive`, `zerovec-derive`, `displaydoc`, `utf8_iter`, `rhai`, `getrandom`, `ahash` | dépendances transitives (fenêtre, WebView2, sérialisation, icônes, Unicode) | Apache-2.0 / MIT (voir l'index de crates.io pour chacune) |

Aucun de ces composants n'est modifié ; tous sont utilisés sous leur licence
d'origine. La liste exacte et l'arbre des dépendances se vérifient avec

```bash
cargo tree                      # arbre des dépendances
cargo license                   # tableau des licences (outil tiers, si installé)
```

### Moteur de rendu

Le rendu des pages est assuré par **Microsoft Edge WebView2**, fourni par Windows
et régi par les termes de Microsoft (il n'est ni inclus ni redistribué par Nova).
Le fichier `WebView2Loader.dll` n'est pas livré : `webview2-com-sys` est compilé
en **liaison statique** (`WebView2LoaderStatic`), ce qui évite toute DLL
supplémentaire à côté de `Nova.exe`.

---

## 4. Liste de filtrage des traqueurs

`assets/trackers.txt` est une liste de **domaines** (146 entrées) établie pour
Nova à partir de sources publiques de filtrage (EasyList/EasyPrivacy, listes
« Peter Lowe », listes AdGuard). Les listes de domaines publiques sont
généralement placées sous **CC BY-SA 3.0** ou dans le domaine public selon leur
origine ; les entrées retenues ici sont des noms de domaines de régies
publicitaires et de traqueurs, qui ne constituent pas une œuvre protégeable en
tant que telle. La liste est fournie à titre technique et peut être remplacée ou
vidée librement : Nova fonctionne sans elle (le réglage « Bloquer publicités et
traqueurs » se désactive dans les Paramètres).

---

## 5. Interface

Les pages de `assets/ui/` (HTML, CSS, JavaScript) ont été écrites pour Nova et
sont sous licence MIT comme le reste du projet. Les icônes d'interface (barre
latérale, barre d'adresse, boutons) sont dessinées dans le fichier, en SVG, et
n'empruntent à aucune bibliothèque d'icônes. Les favicons des sites visités sont
chargés directement depuis le site concerné (`https://<hôte>/favicon.ico`) et
restent la propriété de leur site.

---

## 6. Contact licence

Toute demande de retrait (logo, nom, entrée de liste) est satisfaite par la
suppression du fichier concerné, sans autre modification du programme. Les
fichiers visés sont tous rassemblés dans `assets/` :
`engines/*.png` (logos), `trackers.txt` (liste de filtrage).
