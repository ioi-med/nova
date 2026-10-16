#!/usr/bin/env python3
"""Correctifs des défauts visuels relevés par captures d'écran.

Aucune de ces corrections ne touche au chemin de rendu des pages web : elles ne
concernent que les surfaces d'interface de Nova (barre latérale, barre
d'adresse, pages internes), donc aucune régression possible sur la latence de
chargement des sites.

Défauts corrigés (voir RAPPORT-AUDIT.md, section « Défauts visuels ») :

1. Vignettes d'onglets épinglés : le favicon n'avait aucune règle de
   dimensionnement (`.pin .fav img` absente) et s'affichait **par-dessus la
   lettre de repli**, jusqu'à sortir du carré de 30 px.
2. Partout ailleurs (onglets normaux, page d'historique), la lettre de repli
   restait affichée **à côté** de l'image : les deux enfants de la vignette
   étaient côte à côte dans la boîte flex. La lettre devient un nœud à part que
   l'image recouvre.
3. `history.html` n'appliquait **jamais** le thème : la page restait sombre même
   avec « Clair » sélectionné.
4. `welcome.html` n'avait **aucune** palette claire ni application de thème :
   l'assistant de premier lancement restait sombre.
5. Le thème « Système » était ignoré : les pages comparaient `config.theme` à
   `"light"` au lieu d'utiliser le thème déjà résolu côté Rust. La valeur
   `dark` est désormais poussée par `main.rs` avec l'état.
6. Interrupteurs éteints codés en dur (`#3a3a45`) : invisibles sur fond clair.
7. Puces « Autres moteurs » de l'assistant : texte `#fff` codé en dur, illisible
   sur fond clair.
8. Barre de défilement de la barre latérale : poignée `#3a3a45` codée en dur,
   quasi invisible en thème clair.
9. Ombre des popovers trop dure sur fond clair.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def save(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def sub(text, old, new, rel, n=1):
    if old not in text:
        sys.exit(f"motif introuvable dans {rel} :\n{old[:300]}")
    return text.replace(old, new, n)


def swap(text, old, new, rel):
    if old not in text:
        sys.exit(f"motif introuvable dans {rel} :\n{old[:300]}")
    return text.replace(old, new)


# ======================================================================
# 1. main.rs — pousser le thème réellement appliqué (« Système » résolu)
# ======================================================================
m = load("src/main.rs")
m = sub(
    m,
    """            "theme": if self.cfg.dark() { "dark" } else { "light" },""",
    """            "theme": if self.cfg.dark() { "dark" } else { "light" },
            // Thème réellement appliqué, « Système » déjà résolu par Windows :
            // les pages d'interface ne peuvent pas interroger le système, elles
            // lisaient donc `config.theme` et ignoraient le mode clair du bureau.
            "dark": self.cfg.dark(),""",
    "src/main.rs",
)
save("src/main.rs", m)

# ======================================================================
# 2. sidebar.html — vignettes (épinglées et normales) + thème résolu
# ======================================================================
s = load("assets/ui/sidebar.html")

s = sub(
    s,
    """  .pin{
    width:30px;height:30px;border-radius:9px;background:var(--bg-2);border:1px solid var(--line);
    display:flex;align-items:center;justify-content:center;font-weight:600;font-size:12px;
    color:#fff;position:relative;
  }""",
    """  .pin{
    width:30px;height:30px;border-radius:9px;background:var(--bg-2);border:1px solid var(--line);
    display:flex;align-items:center;justify-content:center;font-weight:600;font-size:12px;
    color:#fff;position:relative;overflow:hidden;
  }""",
    "sidebar.html",
)

s = sub(
    s,
    """  .pin .fav{width:100%;height:100%;border-radius:9px;display:flex;align-items:center;justify-content:center}""",
    """  .pin .fav{
    position:relative;width:100%;height:100%;overflow:hidden;border-radius:9px;
    display:flex;align-items:center;justify-content:center;
  }
  /* Le favicon recouvre la lettre de repli et reste dans le carré : sans cette
     règle, l'image s'affichait à sa taille naturelle et débordait du bouton. */
  .pin .fav img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}""",
    "sidebar.html",
)

s = sub(
    s,
    """  .favicon{
    width:17px;height:17px;border-radius:5px;flex:0 0 auto;display:flex;align-items:center;
    justify-content:center;font-size:10px;font-weight:700;color:#fff;background:var(--accent);
    overflow:hidden;
  }
  .favicon img{width:100%;height:100%;object-fit:cover}""",
    """  .favicon{
    width:17px;height:17px;border-radius:5px;flex:0 0 auto;display:flex;align-items:center;
    justify-content:center;font-size:10px;font-weight:700;color:#fff;background:var(--accent);
    overflow:hidden;position:relative;
  }
  /* `absolute` : le favicon se superpose à la lettre au lieu de la pousser
     (avant, la lettre restait visible à côté de l'image). */
  .favicon img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}""",
    "sidebar.html",
)

s = sub(
    s,
    """  .tabs::-webkit-scrollbar-thumb{background:#3a3a45;border-radius:8px;border:2px solid transparent;background-clip:content-box}""",
    """  .tabs::-webkit-scrollbar-thumb{background:var(--scroll);border-radius:8px;border:2px solid transparent;background-clip:content-box}""",
    "sidebar.html",
)

s = sub(
    s,
    """    --text:#eaeaef; --muted:#9a9aa6; --line:#31313b;""",
    """    --text:#eaeaef; --muted:#9a9aa6; --line:#31313b; --scroll:#3a3a45;""",
    "sidebar.html",
)

s = sub(
    s,
    """    --text:#191920; --muted:#6b6b76; --line:#dedee6;""",
    """    --text:#191920; --muted:#6b6b76; --line:#dedee6; --scroll:#c6c6d0;
  }
  html[data-theme="light"] .popover{box-shadow:0 18px 40px rgba(20,20,30,.18)}""",
    "sidebar.html",
)

# --- JS : vignette = lettre dans son propre nœud, image par-dessus
s = sub(
    s,
    """    const fav = document.createElement("span");
    fav.className = isPinned ? "fav" : "favicon";
    el._favicon = fav;
    el.appendChild(fav);""",
    """    const fav = document.createElement("span");
    fav.className = isPinned ? "fav" : "favicon";
    /* La lettre de repli est un nœud distinct : le favicon la recouvre au lieu
       de s'afficher à côté d'elle (les deux enfants étaient côte à côte). */
    const letter = document.createElement("span");
    letter.className = "letter";
    fav.appendChild(letter);
    el._favicon = fav;
    el._letter = letter;
    el.appendChild(fav);""",
    "sidebar.html",
)

s = sub(
    s,
    """  function applyFavicon(el, tab){
    const box = el._favicon;
    if (!box) return;
    const host = hostOf(tab.url);
    const letter = (tab.title || host || "?").trim().charAt(0).toUpperCase() || "?";

    if (el._favHost !== host) {
      el._favHost = host;
      if (el._img) { el._img.remove(); el._img = null; }
      box.style.background = tint(host || letter);
      box.textContent = letter;

      if (tab.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
        const img = document.createElement("img");
        img.alt = "";
        img.src = "https://" + host + "/favicon.ico";
        img.addEventListener("error", () => { img.remove(); el._img = null; });
        box.appendChild(img);
        el._img = img;
      }
    } else if (!el._img && box.textContent !== letter) {
      box.textContent = letter;
    }
  }""",
    """  function applyFavicon(el, tab){
    const box = el._favicon;
    if (!box) return;
    const host = hostOf(tab.url);
    const letter = (tab.title || host || "?").trim().charAt(0).toUpperCase() || "?";

    if (el._letter && el._letter.textContent !== letter) el._letter.textContent = letter;

    if (el._favHost !== host) {
      el._favHost = host;
      if (el._img) { el._img.remove(); el._img = null; }
      box.style.background = tint(host || letter);

      if (tab.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
        const img = document.createElement("img");
        img.alt = "";
        img.decoding = "async";
        img.src = "https://" + host + "/favicon.ico";
        /* En cas d'échec, l'image disparaît et la lettre reste visible. */
        img.addEventListener("error", () => { img.remove(); el._img = null; });
        box.appendChild(img);
        el._img = img;
      }
    }
  }""",
    "sidebar.html",
)

s = sub(
    s,
    """      document.documentElement.dataset.theme = next.theme === "light" ? "light" : "dark";
      document.body.style.background = next.theme === "light" ? "#f4f4f7" : "#1b1b1f";""",
    """      /* `next.dark` est calculé par Rust (« Système » déjà résolu en clair ou
         sombre) ; repli sur `theme` pour un état incomplet. */
      const dark = (typeof next.dark === "boolean") ? next.dark : next.theme !== "light";
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      document.body.style.background = dark ? "#1b1b1f" : "#f4f4f7";""",
    "sidebar.html",
)
save("assets/ui/sidebar.html", s)

# ======================================================================
# 3. history.html — thème jamais appliqué + vignettes à lettre + image
# ======================================================================
h = load("assets/ui/history.html")

h = sub(
    h,
    """  .item .fav{
    width:26px;height:26px;border-radius:8px;flex:0 0 auto;display:flex;align-items:center;
    justify-content:center;font-weight:700;font-size:11px;color:#fff;overflow:hidden;
  }
  .item .fav img{width:100%;height:100%;object-fit:cover}""",
    """  .item .fav{
    width:26px;height:26px;border-radius:8px;flex:0 0 auto;display:flex;align-items:center;
    justify-content:center;font-weight:700;font-size:11px;color:#fff;overflow:hidden;
    position:relative;
  }
  /* Le favicon recouvre la lettre de repli (avant : les deux s'affichaient). */
  .item .fav img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}""",
    "history.html",
)

h = sub(
    h,
    """  const $ = (id) => document.getElementById(id);""",
    """  const $ = (id) => document.getElementById(id);

  /* Cette page n'appliquait jamais le thème : elle restait sombre même avec
     « Clair » choisi. `dark` est fourni par Rust (« Système » déjà résolu). */
  function applyTheme(){
    const dark = (typeof N.dark === "boolean") ? N.dark : (N.config && N.config.theme !== "light");
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }
  applyTheme();""",
    "history.html",
)

h = sub(
    h,
    """  function render(){
    const filter = ($("q").value || "").trim().toLowerCase();""",
    """  function render(){
    applyTheme();
    const filter = ($("q").value || "").trim().toLowerCase();""",
    "history.html",
)

h = sub(
    h,
    """      fav.style.background = "hsl(" + hash + ",58%,48%)";
      fav.textContent = letter;
      if (h.url.indexOf("http") === 0) {""",
    """      fav.style.background = "hsl(" + hash + ",58%,48%)";
      const fallback = document.createElement("span");
      fallback.className = "letter";
      fallback.textContent = letter;
      fav.appendChild(fallback);
      if (h.url.indexOf("http") === 0) {""",
    "history.html",
)
save("assets/ui/history.html", h)

# ======================================================================
# 4. settings.html — interrupteurs lisibles en clair + thème résolu
# ======================================================================
t = load("assets/ui/settings.html")

t = sub(
    t,
    """  .switch{width:42px;height:24px;border-radius:99px;background:#3a3a45;border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    """  .switch{width:42px;height:24px;border-radius:99px;background:var(--switch-off);border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    "settings.html",
)

t = sub(
    t,
    """    --text:#eaeaef; --muted:#9a9aa6; --line:#2c2c34;""",
    """    --text:#eaeaef; --muted:#9a9aa6; --line:#2c2c34; --switch-off:#3a3a45;""",
    "settings.html",
)

t = sub(
    t,
    """    --text:#191920; --muted:#6b6b76; --line:#e6e6ec;""",
    """    --text:#191920; --muted:#6b6b76; --line:#e6e6ec; --switch-off:#c9c9d2;""",
    "settings.html",
)

t = sub(
    t,
    """      document.documentElement.dataset.theme = state.config.theme === "light" ? "light" : "dark";""",
    """      const dark = (typeof state.dark === "boolean") ? state.dark : state.config.theme !== "light";
      document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "settings.html",
)
save("assets/ui/settings.html", t)

# ======================================================================
# 5. newtab.html — thème résolu (« Système »)
# ======================================================================
n = load("assets/ui/newtab.html")
n = sub(
    n,
    """  document.documentElement.dataset.theme = N.config.theme === "light" ? "light" : "dark";""",
    """  const dark = (typeof N.dark === "boolean") ? N.dark : N.config.theme !== "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "newtab.html",
)
save("assets/ui/newtab.html", n)

# ======================================================================
# 6. toolbar.html — thème résolu (« Système »)
# ======================================================================
b = load("assets/ui/toolbar.html")
b = sub(
    b,
    """      document.documentElement.dataset.theme = next.theme === "light" ? "light" : "dark";""",
    """      const dark = (typeof next.dark === "boolean") ? next.dark : next.theme !== "light";
      document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    "toolbar.html",
)
save("assets/ui/toolbar.html", b)

# ======================================================================
# 7. welcome.html — palette claire + application du thème
# ======================================================================
w = load("assets/ui/welcome.html")

w = sub(
    w,
    """    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  *{box-sizing:border-box}""",
    """    --switch-off:#3a3a45;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  /* L'assistant n'avait aucune palette claire : il restait sombre même lorsque
     l'utilisateur venait de choisir le thème clair. */
  html[data-theme="light"]{
    --bg:#f7f7fb; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76;
    --line:#e6e6ec; --switch-off:#c9c9d2;
  }
  html[data-theme="light"] .glow{opacity:.20}
  *{box-sizing:border-box}""",
    "welcome.html",
)

w = sub(
    w,
    """  .switch{width:42px;height:24px;border-radius:99px;background:#3a3a45;border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    """  .switch{width:42px;height:24px;border-radius:99px;background:var(--switch-off);border:0;position:relative;cursor:pointer;flex:0 0 auto}""",
    "welcome.html",
)

w = sub(
    w,
    """  .chip:hover{background:var(--card-hover);color:#fff}
  .chip.on{border-color:var(--accent);color:#fff}""",
    """  /* Texte blanc codé en dur : illisible sur fond clair. */
  .chip:hover{background:var(--card-hover);color:var(--text)}
  .chip.on{border-color:var(--accent);color:var(--text)}""",
    "welcome.html",
)

w = sub(
    w,
    """  const MAIN = ["google","brave","ecosia"];""",
    """  /* Thème appliqué dès l'affichage (et « Système » déjà résolu par Rust). */
  function applyTheme(){
    const dark = (typeof N.dark === "boolean") ? N.dark : (N.config && N.config.theme !== "light");
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }
  applyTheme();

  const MAIN = ["google","brave","ecosia"];""",
    "welcome.html",
)

w = sub(
    w,
    """  const swDark = bindSwitch("swDark");""",
    """  const swDark = bindSwitch("swDark");
  /* Le choix « thème sombre » se voit désormais immédiatement. */
  swDark.addEventListener("click", () => {
    N.dark = swDark.classList.contains("on");
    applyTheme();
  });""",
    "welcome.html",
)
save("assets/ui/welcome.html", w)

print("Correctifs visuels appliqués :")
print("  src/main.rs            thème résolu poussé aux pages (dark)")
print("  assets/ui/sidebar.html vignettes épinglées/normales, barre de défilement, thème")
print("  assets/ui/history.html thème (page toujours sombre) + vignettes")
print("  assets/ui/settings.html interrupteurs éteints lisibles en clair, thème")
print("  assets/ui/newtab.html  thème résolu")
print("  assets/ui/toolbar.html thème résolu")
print("  assets/ui/welcome.html palette claire, puces lisibles, aperçu du thème")
