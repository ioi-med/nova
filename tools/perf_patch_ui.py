#!/usr/bin/env python3
"""Rendu incrémental de l'interface (barre latérale et barre d'adresse).

Avant : chaque rafraîchissement vidait les conteneurs et reconstruisait tous les
éléments — donc toutes les balises <img> de favicon (re-téléchargées), la liste
d'historique complète et la barre d'adresse. Après : les nœuds existants sont
réutilisés et réordonnés, seuls les champs qui ont changé sont réécrits.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def replace_js_fn(text, name, new_body):
    marker = "  function " + name
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"fonction JS introuvable : {name}")
    end = text.find("\n  }\n", start)
    if end < 0:
        raise SystemExit(f"fin de fonction introuvable : {name}")
    return text[:start] + new_body + text[end + len("\n  }\n") :]


# ======================================================================
# sidebar.html
# ======================================================================
path = ROOT / "assets" / "ui" / "sidebar.html"
html = path.read_text(encoding="utf-8")

# 1. caches d'éléments
html = html.replace(
    """  let state = null;
  let menuTabId = null;
  let dragId = null;""",
    """  let state = null;
  let dragId = null;
  /* Un nœud DOM par onglet, réutilisé d'un rafraîchissement à l'autre. */
  const tabNodes = new Map();
  /* Signature de l'historique déjà affiché (évite de le reconstruire pour rien). */
  let historySig = null;
  let historyWasOpen = false;""",
)

# 2. favicon : création unique + mise à jour ciblée
html = replace_js_fn(html, "faviconNode", """  /* Le favicon n'est instancié qu'une fois par onglet : l'ancienne version en
     recréait un par rafraîchissement, ce qui relançait une requête d'image. */
  function applyFavicon(el, tab){
    const host = hostOf(tab.url);
    if (el._favHost === host && el._favTitle === tab.title) return;
    el._favHost = host;
    el._favTitle = tab.title;

    const box = el._favicon;
    if (!box) return;
    const letter = (tab.title || host || "?").trim().charAt(0).toUpperCase() || "?";
    box.style.background = tint(host || letter);

    if (el._img) { el._img.remove(); el._img = null; }
    box.textContent = letter;

    if (tab.url.indexOf("http") === 0 && host.indexOf(".") !== -1) {
      const img = document.createElement("img");
      img.alt = "";
      img.src = "https://" + host + "/favicon.ico";
      img.addEventListener("error", () => img.remove());
      box.appendChild(img);
      el._img = img;
    }
  }

  function buildTab(tab, isPinned){
    const el = document.createElement("div");
    el.dataset.id = tab.id;
    el.dataset.pinned = isPinned ? "1" : "0";
    el.draggable = true;
    el._favHost = null;

    const fav = document.createElement("span");
    fav.className = isPinned ? "fav" : "favicon";
    el._favicon = fav;
    el.appendChild(fav);

    if (!isPinned) {
      const title = document.createElement("span");
      title.className = "title";
      el._title = title;
      el.appendChild(title);

      const close = document.createElement("button");
      close.className = "close";
      close.textContent = "\\u2715";
      close.title = "Fermer l'onglet";
      close.addEventListener("click", (e) => { e.stopPropagation(); post({cmd:"close_tab", id:tab.id}); });
      el.appendChild(close);
    }

    el.addEventListener("click", () => post({cmd:"select_tab", id:tab.id}));
    el.addEventListener("auxclick", (e) => { if (e.button === 1) post({cmd:"close_tab", id:tab.id}); });
    el.addEventListener("contextmenu", (e) => { e.preventDefault(); openTabMenu(e, tab); });

    el.addEventListener("dragstart", (e) => { dragId = tab.id; el.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; });
    el.addEventListener("dragend", () => { dragId = null; el.classList.remove("dragging"); });
    el.addEventListener("dragover", (e) => {
      if (dragId == null || dragId === tab.id) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const after = (e.clientY - r.top) > r.height / 2;
      el.classList.toggle("drop-after", after);
      el.classList.toggle("drop-before", !after);
    });
    el.addEventListener("dragleave", () => { el.classList.remove("drop-after","drop-before"); });
    el.addEventListener("drop", (e) => {
      e.preventDefault();
      const after = el.classList.contains("drop-after");
      el.classList.remove("drop-after","drop-before");
      if (dragId == null || dragId === tab.id) return;
      post({cmd:"move_tab", id:dragId, target:tab.id, after:after});
    });

    return el;
  }

  function updateTab(el, tab, isPinned){
    const want = (isPinned ? "pin" : "tab")
      + (tab.active ? " active" : "")
      + (tab.loading && !isPinned ? " loading" : "");
    if (el.className !== want) el.className = want;

    if (!isPinned && el._title) {
      const label = tab.title || "Sans titre";
      if (el._title.textContent !== label) el._title.textContent = label;
    }
    el.title = (tab.title || "") + "\\n" + (tab.url || "");
    applyFavicon(el, tab);
  }""")

# 3. rendu incrémental de la liste
html = replace_js_fn(html, "renderTabs", """  /* Les nœuds existants sont réutilisés puis réordonnés (`appendChild` déplace
     le nœud au lieu de le recréer) : plus de reconstruction complète. */
  function syncTabs(list, container, isPinned){
    const seen = new Set();
    list.forEach((tab) => {
      seen.add(tab.id);
      let el = tabNodes.get(tab.id);
      if (el && el.parentNode !== container) {
        el.remove();
        tabNodes.delete(tab.id);
        el = null;
      }
      if (!el) {
        el = buildTab(tab, isPinned);
        tabNodes.set(tab.id, el);
      }
      updateTab(el, tab, isPinned);
      container.appendChild(el);
    });
    Array.from(tabNodes.keys()).forEach((id) => {
      if (!seen.has(id)) {
        const el = tabNodes.get(id);
        if (el) el.remove();
        tabNodes.delete(id);
      }
    });
  }""")

# 4. historique : reconstruit uniquement s'il est visible et si la révision change
html = replace_js_fn(html, "renderHistory", """  function renderHistory(force){
    if (!state) return;
    const filter = ($("historySearch").value || "");
    const sig = (state.history_rev || 0) + "|" + filter;
    if (!force && sig === historySig) return;
    historySig = sig;

    const list = $("historyList");
    if ($("historyPanel").classList.contains("hidden")) return;

    list.textContent = "";
    const rows = (state.history || []).filter((h) =>
      !filter || h.title.toLowerCase().includes(filter.toLowerCase()) || h.url.toLowerCase().includes(filter.toLowerCase()));
    if (!rows.length) {
      const p = document.createElement("div");
      p.className = "empty";
      p.textContent = "Aucune entrée.";
      list.appendChild(p);
      return;
    }
    const frag = document.createDocumentFragment();
    rows.forEach((h) => {
      const it = document.createElement("div");
      it.className = "hist-item";
      it.title = h.url;
      const t = document.createElement("div"); t.className = "t"; t.textContent = h.title || h.url;
      const u = document.createElement("div"); u.className = "u"; u.textContent = hostOf(h.url);
      const w = document.createElement("div"); w.className = "w"; w.textContent = relative(h.ts);
      it.append(t, u, w);
      it.addEventListener("click", () => post({cmd:"open_url", url:h.url, new_tab:false}));
      it.addEventListener("auxclick", (e) => { if (e.button === 1) post({cmd:"open_url", url:h.url, new_tab:true}); });
      it.addEventListener("contextmenu", (e) => { e.preventDefault(); post({cmd:"forget_url", url:h.url}); });
      frag.appendChild(it);
    });
    list.appendChild(frag);
  }""")

# 5. render() : appels aux nouvelles fonctions
html = html.replace("""      renderTabs(pinned, pinnedBar, true);
      renderTabs(plain, $("tabList"), false);""",
"""      syncTabs(pinned, pinnedBar, true);
      syncTabs(plain, $("tabList"), false);""")

html = html.replace("""      renderHistory();
      if (next.history_open) $("historyPanel").classList.remove("hidden");
      else $("historyPanel").classList.add("hidden");""",
"""      if (next.history_open) $("historyPanel").classList.remove("hidden");
      else $("historyPanel").classList.add("hidden");
      renderHistory(next.history_open && !historyWasOpen);
      historyWasOpen = next.history_open;""")

html = html.replace("""  $("historySearch").addEventListener("input", renderHistory);""",
                    """  $("historySearch").addEventListener("input", () => renderHistory(true));""")

path.write_text(html, encoding="utf-8")

# ======================================================================
# toolbar.html : mise à jour en place de la barre d'adresse
# ======================================================================
path = ROOT / "assets" / "ui" / "toolbar.html"
html = path.read_text(encoding="utf-8")

html = html.replace("""  function paintOmnibox(active){
    if (editing) return;
    const url = active.url || "";
    const box = $("hint");
    if (active.search_mode) {
      box.innerHTML = "";
      $("url").value = "";
      $("url").placeholder = url || "Rechercher ou saisir une adresse";
      box.textContent = "";
      return;
    }
    const p = prettyUrl(url);
    $("url").value = "";
    $("url").placeholder = "";
    box.innerHTML = "";
    const h = document.createElement("span");
    h.className = "host";
    h.textContent = p.host;
    const r = document.createElement("span");
    r.className = "rest";
    r.textContent = p.rest.length > 90 ? p.rest.slice(0,90) + "…" : p.rest;
    box.append(h, r);
  }""", """  /* Les deux segments hôte / chemin sont créés une fois puis seulement
     réécrits : plus d'allocation de DOM à chaque événement de la page. */
  const hostSpan = document.createElement("span");
  hostSpan.className = "host";
  const restSpan = document.createElement("span");
  restSpan.className = "rest";

  function paintOmnibox(active){
    if (editing) return;
    const url = active.url || "";
    const box = $("hint");
    if (active.search_mode) {
      $("url").value = "";
      $("url").placeholder = url || "Rechercher ou saisir une adresse";
      box.textContent = "";
      return;
    }
    const p = prettyUrl(url);
    $("url").value = "";
    $("url").placeholder = "";
    if (box.firstChild !== hostSpan) {
      box.textContent = "";
      box.append(hostSpan, restSpan);
    }
    if (hostSpan.textContent !== p.host) hostSpan.textContent = p.host;
    const rest = p.rest.length > 90 ? p.rest.slice(0, 90) + "…" : p.rest;
    if (restSpan.textContent !== rest) restSpan.textContent = rest;
  }""")

html = html.replace("""      const lock = $("lock");
      lock.innerHTML = '<svg viewBox="0 0 24 24">' + (a.secure ? ICONS.lock : ICONS.unlock) + '</svg>';
      lock.classList.toggle("insecure", !a.secure);
      lock.title = a.secure ? "Connexion chiffrée" : "Connexion non chiffrée";""",
"""      const lock = $("lock");
      if (lock._secure !== a.secure) {
        lock._secure = a.secure;
        lock.innerHTML = '<svg viewBox="0 0 24 24">' + (a.secure ? ICONS.lock : ICONS.unlock) + '</svg>';
        lock.classList.toggle("insecure", !a.secure);
        lock.title = a.secure ? "Connexion chiffrée" : "Connexion non chiffrée";
      }""")

path.write_text(html, encoding="utf-8")

print("interface : rendu incrémental appliqué")
