#!/usr/bin/env python3
"""Cinquième lot, 2e partie : interfaces des favoris et de la couleur de fond.

* `toolbar.html`  — l'étoile devient « ajouter/retirer des favoris », entrée de
  menu correspondante.
* `sidebar.html`  — rangée d'apps (favoris) sous le logo + menu contextuel.
* `newtab.html`   — section « Favoris » sur la page du nouvel onglet.
* `settings.html` — réglage « Couleur du fond » (teintes prêtes + choix libre).
* tous           — appel de `window.NovaSkin.apply()` (peau commune, `src/ui.rs`).
* `main.rs`       — petite commande IPC `copy_text` (copier l'adresse d'un favori).
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
        sys.exit(f"motif introuvable dans {rel} :\n{old[:400]}")
    return text.replace(old, new, n)


# ======================================================================
# main.rs — copier un texte quelconque (adresse d'un favori)
# ======================================================================
m = load("src/main.rs")
m = sub(
    m,
    """            /* --- favoris (apps) --- */
            "toggle_favorite" => {""",
    """            "copy_text" => {
                if let Some(text) = cmd.get("text").and_then(Value::as_str) {
                    let text = text.to_string();
                    platform::set_clipboard(&text);
                }
            }
            /* --- favoris (apps) --- */
            "toggle_favorite" => {""",
    "src/main.rs",
)
save("src/main.rs", m)

# ======================================================================
# toolbar.html
# ======================================================================
t = load("assets/ui/toolbar.html")

t = sub(
    t,
    """  <button class="icon-btn" id="star" title="Copier l'adresse">""",
    """  <button class="icon-btn" id="star" title="Ajouter aux favoris">""",
    "toolbar.html",
)

t = sub(
    t,
    """  <div class="row" data-cmd="zoom_reset">Zoom 100 %<span class="k">Ctrl+0</span></div>""",
    """  <div class="row" data-cmd="toggle_favorite" id="favRow">Ajouter aux favoris<span class="k">Ctrl+D</span></div>
  <div class="row" data-cmd="zoom_reset">Zoom 100 %<span class="k">Ctrl+0</span></div>""",
    "toolbar.html",
)

# CSS : étoile active + libellé du menu
t = sub(
    t,
    """  .progress{""",
    """  /* Étoile remplie quand la page courante est dans les favoris. */
  .icon-btn.on{color:var(--accent)}
  .icon-btn.on svg{fill:var(--accent);stroke:var(--accent)}
  .progress{""",
    "toolbar.html",
)

t = sub(
    t,
    """      $("progress").classList.toggle("on", !!a.loading);
      paintOmnibox(a);""",
    """      /* Favoris : étoile remplie + libellé de menu cohérent. */
      const fav = !!a.is_favorite;
      $("star").classList.toggle("on", fav);
      $("star").title = fav ? "Retirer des favoris" : "Ajouter aux favoris (Ctrl+D)";
      $("favRow").textContent = fav ? "Retirer des favoris" : "Ajouter aux favoris";
      const kbd = document.createElement("span");
      kbd.className = "k";
      kbd.textContent = "Ctrl+D";
      $("favRow").appendChild(kbd);

      /* Couleur de fond choisie dans les paramètres (vide = thème standard). */
      if (window.NovaSkin) window.NovaSkin.apply(next.ui_bg);

      $("progress").classList.toggle("on", !!a.loading);
      paintOmnibox(a);""",
    "toolbar.html",
)

t = sub(
    t,
    """  $("star").addEventListener("click", () => post({cmd:"copy_url", id:0}));""",
    """  /* L'étoile gère désormais les favoris (le copier-coller d'adresse reste
     dans le menu contextuel des onglets et de la barre d'adresse). */
  $("star").addEventListener("click", () => post({cmd:"toggle_favorite"}));""",
    "toolbar.html",
)
save("assets/ui/toolbar.html", t)

# ======================================================================
# sidebar.html — rangée d'apps
# ======================================================================
s = load("assets/ui/sidebar.html")

s = sub(
    s,
    """  /* ---------- Onglets épinglés ---------- */""",
    """  /* ---------- Favoris (apps) ---------- */
  .apps{display:flex;flex-wrap:wrap;gap:5px;padding:0 10px 8px}
  .app{
    width:30px;height:30px;border-radius:9px;background:var(--bg-2);border:1px solid var(--line);
    display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;
    font-weight:600;font-size:12px;color:#fff;flex:0 0 auto;padding:0;
  }
  .app:hover{transform:translateY(-1px)}
  .app .fav{
    position:relative;width:100%;height:100%;display:flex;align-items:center;
    justify-content:center;overflow:hidden;
  }
  .app .fav img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1}
  .app .fav.has-img{background:var(--fav-plate)}
  .app .fav.has-img .letter{visibility:hidden}

  /* ---------- Onglets épinglés ---------- */""",
    "sidebar.html",
)

s = sub(
    s,
    """<section class="pinned hidden" id="pinnedBar"></section>""",
    """<section class="apps hidden" id="appsBar"></section>
<section class="pinned hidden" id="pinnedBar"></section>""",
    "sidebar.html",
)

s = sub(
    s,
    """  /* ---------- menu contextuel d'un onglet ---------- */""",
    """  /* ---------- favoris (apps) ---------- */
  /* La signature évite de reconstruire la rangée (et de relancer les requêtes
     de favicons) à chaque repaint : elle ne change que si la liste change. */
  let appsSig = null;
  function renderApps(list){
    const bar = $("appsBar");
    const sig = list.map((f) => f.url + "|" + f.title).join("~");
    if (sig === appsSig) return;
    appsSig = sig;
    bar.classList.toggle("hidden", list.length === 0);
    bar.textContent = "";
    list.forEach((fav) => {
      const host = hostOf(fav.url);
      const el = document.createElement("button");
      el.className = "app";
      el.title = (fav.title || host || fav.url) + "\\n" + fav.url;
      const box = document.createElement("span");
      box.className = "fav";
      const letter = document.createElement("span");
      letter.className = "letter";
      letter.textContent = ((fav.title || host || "?").trim().charAt(0) || "?").toUpperCase();
      box.style.background = tint(host);
      box.appendChild(letter);
      if (fav.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
        const img = document.createElement("img");
        img.alt = "";
        img.decoding = "async";
        img.src = "https://" + host + "/favicon.ico";
        img.addEventListener("error", () => {
          img.remove();
          box.classList.remove("has-img");
          box.style.background = tint(host);
        });
        box.appendChild(img);
        box.style.background = "";
        box.classList.add("has-img");
      }
      el.appendChild(box);
      el.addEventListener("click", () => post({cmd:"open_url", url:fav.url, new_tab:false}));
      el.addEventListener("auxclick", (e) => { if (e.button === 1) post({cmd:"open_url", url:fav.url, new_tab:true}); });
      el.addEventListener("contextmenu", (e) => { e.preventDefault(); openAppMenu(e, fav); });
      bar.appendChild(el);
    });
  }

  function openAppMenu(e, fav){
    closeCtx();
    ctx = document.createElement("div");
    ctx.className = "popover ctx";
    const items = [
      ["Ouvrir", () => post({cmd:"open_url", url:fav.url, new_tab:false})],
      ["Ouvrir dans un nouvel onglet", () => post({cmd:"open_url", url:fav.url, new_tab:true})],
      ["Copier l'adresse", () => post({cmd:"copy_text", text:fav.url})],
      ["Retirer des favoris", () => post({cmd:"remove_favorite", url:fav.url})]
    ];
    items.forEach(([label, fn]) => {
      const row = document.createElement("div");
      row.className = "row";
      row.textContent = label;
      row.addEventListener("click", () => { closeCtx(); fn(); });
      ctx.appendChild(row);
    });
    document.body.appendChild(ctx);
    const w = 220, h = ctx.offsetHeight;
    const x = Math.min(e.clientX, window.innerWidth - w - 8);
    const y = Math.min(e.clientY, window.innerHeight - h - 8);
    ctx.style.left = Math.max(8, x) + "px";
    ctx.style.top = Math.max(8, y) + "px";
  }

  /* ---------- menu contextuel d'un onglet ---------- */""",
    "sidebar.html",
)

s = sub(
    s,
    """      $("engineName").textContent = eng.name;
      document.querySelector("#engineBtn .dot").style.background = eng.color;""",
    """      $("engineName").textContent = eng.name;
      document.querySelector("#engineBtn .dot").style.background = eng.color;

      /* Couleur de fond choisie dans les paramètres (vide = thème standard). */
      if (window.NovaSkin) window.NovaSkin.apply(next.ui_bg);
      renderApps(next.favorites || []);""",
    "sidebar.html",
)

s = sub(
    s,
    """      document.body.style.background = dark ? "#1b1b1f" : "#f4f4f7";""",
    """      /* `var(--bg)` suit la couleur de fond personnalisée. */
      document.body.style.background = "var(--bg)";""",
    "sidebar.html",
)
save("assets/ui/sidebar.html", s)

# ======================================================================
# newtab.html — section Favoris
# ======================================================================
n = load("assets/ui/newtab.html")

n = sub(
    n,
    """  const N = window.__NOVA__ || {config:{engine:"google"}, engines:[], topsites:[]};""",
    """  const N = window.__NOVA__ || {config:{engine:"google"}, engines:[], topsites:[], favorites:[]};""",
    "newtab.html",
)

n = sub(
    n,
    """  const grid = document.getElementById("topSites");""",
    """  /* Favoris (apps) : rangée affichée avant les sites fréquents. */
  (function renderFavorites(){
    const favs = N.favorites || [];
    const box = document.getElementById("favorites");
    if (!favs.length) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    const grid = document.getElementById("favGrid");
    favs.forEach((f) => {
      const host = hostOf(f.url);
      const a = document.createElement("a");
      a.className = "tile";
      a.href = "#";
      const fav = document.createElement("div");
      fav.className = "fav";
      const fallback = document.createElement("span");
      fallback.className = "letter";
      fallback.textContent = ((f.title || host || "?").trim().charAt(0) || "?").toUpperCase();
      fav.appendChild(fallback);
      fav.style.background = tint(host);
      if (f.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
        const img = document.createElement("img");
        img.alt = "";
        img.src = "https://" + host + "/favicon.ico";
        img.addEventListener("error", () => { img.remove(); fav.classList.remove("has-img"); fav.style.background = tint(host); });
        img.addEventListener("load", () => { fav.classList.add("has-img"); fav.style.background = ""; });
        fav.appendChild(img);
      }
      const label = document.createElement("span");
      label.textContent = (f.title || host).slice(0, 24);
      a.append(fav, label);
      a.title = f.url;
      a.addEventListener("click", (e) => { e.preventDefault(); post({cmd:"open_url", url:f.url, new_tab:false}); });
      a.addEventListener("auxclick", (e) => { if (e.button === 1) post({cmd:"open_url", url:f.url, new_tab:true}); });
      grid.appendChild(a);
    });
  })();

  const grid = document.getElementById("topSites");""",
    "newtab.html",
)

n = sub(
    n,
    """  document.documentElement.dataset.theme = dark ? "dark" : "light";""",
    """  document.documentElement.dataset.theme = dark ? "dark" : "light";
  if (window.NovaSkin) window.NovaSkin.apply(N.ui_bg);""",
    "newtab.html",
)
save("assets/ui/newtab.html", n)

# ======================================================================
# settings.html — réglage de la couleur de fond
# ======================================================================
g = load("assets/ui/settings.html")

g = sub(
    g,
    """  .seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}""",
    """  /* Sélecteur de couleur de fond : teintes prêtes + choix libre. */
  .bgpick{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}
  .bgpick .sw{
    width:24px;height:24px;border-radius:8px;border:1px solid var(--line);cursor:pointer;padding:0;
    background:var(--bg);position:relative;
  }
  .bgpick .sw.on{outline:2px solid var(--accent);outline-offset:1px}
  .bgpick .sw.auto::after{
    content:"A";position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    font-size:10px;font-weight:700;color:var(--muted);
  }
  .bgpick input[type=color]{
    width:34px;height:26px;padding:0;border:1px solid var(--line);border-radius:8px;background:none;cursor:pointer;
  }
  .seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}""",
    "settings.html",
)

g = sub(
    g,
    """      <div class="row">
        <div class="txt"><b>Largeur de la barre latérale</b><small>Les onglets restent à gauche, comme dans Arc.</small></div>""",
    """      <div class="row">
        <div class="txt">
          <b>Couleur du fond</b>
          <small>S'applique à la barre latérale, à la barre d'adresse et aux pages internes.
            Les sites web ne sont pas concernés. Le texte s'adapte automatiquement.</small>
        </div>
        <div class="bgpick" id="bgPick"></div>
      </div>
      <div class="row">
        <div class="txt"><b>Largeur de la barre latérale</b><small>Les onglets restent à gauche, comme dans Arc.</small></div>""",
    "settings.html",
)

g = sub(
    g,
    """  window.NovaPage = {""",
    """  /* ---------- couleur de fond ---------- */
  /* Le libellé vide = thème standard (sombre ou clair selon le réglage). */
  const BGS = [
    ["", "Thème standard"],
    ["#0b0b0e", "Noir OLED"],
    ["#1b1b1f", "Nova sombre"],
    ["#2a2035", "Violet nuit"],
    ["#0f2a24", "Forêt"],
    ["#101a2e", "Bleu nuit"],
    ["#3a2b2b", "Cacao"],
    ["#f4f4f7", "Nova clair"],
    ["#f7efe0", "Sépia"],
    ["#dfe7f5", "Ciel"]
  ];

  function renderBgPick(){
    const box = $("bgPick");
    box.textContent = "";
    const cur = (N.config.ui_bg || "").toLowerCase();
    const list = BGS.slice();
    if (cur && !list.some((b) => b[0].toLowerCase() === cur)) list.splice(1, 0, [cur, "Couleur choisie"]);
    list.forEach(([value, label]) => {
      const b = document.createElement("button");
      b.className = "sw" + (value === "" ? " auto" : "") + (value.toLowerCase() === cur ? " on" : "");
      b.title = label;
      if (value) b.style.background = value;
      b.addEventListener("click", () => setBg(value));
      box.appendChild(b);
    });
    const pick = document.createElement("input");
    pick.type = "color";
    pick.value = cur || (document.documentElement.dataset.theme === "light" ? "#f4f4f7" : "#1b1b1f");
    pick.title = "Couleur personnalisée";
    pick.addEventListener("change", () => setBg(pick.value));
    box.appendChild(pick);
  }

  function setBg(value){
    N.config.ui_bg = value;
    /* Aperçu immédiat, sans attendre le prochain repaint. */
    if (window.NovaSkin) window.NovaSkin.apply(value);
    renderBgPick();
    post({cmd:"set_config", patch:{ui_bg:value}});
  }

  window.NovaPage = {""",
    "settings.html",
)

g = sub(
    g,
    """      $("datadir").textContent = state.data_dir;""",
    """      $("datadir").textContent = state.data_dir;
      if (window.NovaSkin) window.NovaSkin.apply(state.ui_bg);
      renderBgPick();""",
    "settings.html",
)
save("assets/ui/settings.html", g)

# ======================================================================
# history.html / welcome.html — appliquer la peau
# ======================================================================
h = load("assets/ui/history.html")
h = sub(
    h,
    """    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }""",
    """    document.documentElement.dataset.theme = dark ? "dark" : "light";
    if (window.NovaSkin) window.NovaSkin.apply(N.ui_bg);
  }""",
    "history.html",
)
save("assets/ui/history.html", h)

w = load("assets/ui/welcome.html")
w = sub(
    w,
    """    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }""",
    """    document.documentElement.dataset.theme = dark ? "dark" : "light";
    if (window.NovaSkin) window.NovaSkin.apply(N.ui_bg);
  }""",
    "welcome.html",
)
save("assets/ui/welcome.html", w)

print("Interfaces mises à jour : étoile/favoris, rangée d'apps, section Favoris, couleur de fond.")
