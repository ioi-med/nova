#!/usr/bin/env python3
"""Correctif 1.3.0 — étape 4 : habillage par surface + import « par application »."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def patch(path, old, new, label=""):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    if old not in s:
        sys.exit(f"MOTIF INTROUVABLE [{label}] dans {path}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")
    print(f"  ok {label}")


def append_style(path, css, label=""):
    patch(path, "</head>", f"<style>\n{css}\n</style>\n</head>", label)


# ------------------------------------------------------------------ barre latérale
append_style("assets/ui/sidebar.html", """/* ---------- habillage 1.3 : barre latérale à la manière d'Arc ---------- */
  .brand{padding:12px 10px 8px 12px}
  .logo{font-size:13px;font-weight:640;letter-spacing:-.014em}
  .logo svg{width:17px;height:17px}
  .icon-btn{width:26px;height:26px;border-radius:7px;color:var(--muted)}
  .icon-btn:hover{background:var(--bg-3);color:var(--text)}
  .engine-chip{height:24px;border-radius:7px;background:transparent;border-color:transparent;
    color:var(--muted);font-weight:500}
  .engine-chip:hover{background:var(--bg-3);border-color:transparent;color:var(--text)}
  .engine-chip .dot{width:6px;height:6px}
  .tabs{gap:1px;padding:2px 6px 10px}
  .tab{height:30px;min-height:30px;padding:0 6px;border-radius:7px;gap:9px}
  .tab:hover{background:var(--bg-hover)}
  .tab.active{background:var(--bg-3)}
  .tab .title{font-size:12.5px}
  .favicon{width:16px;height:16px;border-radius:4px;font-size:9.5px;font-weight:600}
  .tab .close{width:18px;height:18px;border-radius:6px;font-size:13px;line-height:1}
  .pinned{gap:4px;padding:2px 10px 10px}
  .pin,.app{width:28px;height:28px;border-radius:7px;background:transparent;border-color:transparent}
  .pin:hover,.app:hover{background:var(--bg-3);transform:none}
  .pin.active{outline:2px solid var(--accent);outline-offset:0}
  .apps{gap:4px;padding:0 10px 10px}
  .app.app-more{border:1px dashed var(--line);color:var(--muted)}
  .footer{border-top:1px solid var(--line)}
  .footer .icon-btn{color:var(--muted)}""", label="habillage barre latérale")

# ------------------------------------------------------------------ barre d'adresse
append_style("assets/ui/toolbar.html", """/* ---------- habillage 1.3 : barre d'adresse fine ---------- */
  .bar{gap:6px;padding:0 8px}
  .icon-btn{width:28px;height:28px;border-radius:7px;color:var(--muted)}
  .icon-btn:hover{background:var(--bg-hover);color:var(--text)}
  .omni{height:30px;border-radius:8px;background:var(--bg-2);border-color:transparent}
  .omni:focus-within{background:var(--bg-2);border-color:var(--line-2);
    box-shadow:0 0 0 3px rgba(107,117,232,.16)}
  .lock{color:var(--muted)}
  .hint{font-size:12.5px}
  .chip{width:20px;height:20px;border-radius:5px;font-size:10.5px;font-weight:600;color:var(--muted)}
  .progress{border-radius:0}""", label="habillage barre d'adresse")

# ------------------------------------------------------------------ historique
append_style("assets/ui/history.html", """/* ---------- habillage 1.3 : historique lisible ---------- */
  .page{max-width:820px;padding:28px 26px 64px}
  .bar{gap:8px;margin:16px 0 12px}
  .item{gap:12px;padding:9px 14px;border-top:1px solid var(--line)}
  .item:hover{background:var(--card-hover)}
  .item .t{font-size:12.5px;font-weight:500}
  .item .u{font-size:11.5px;color:var(--muted)}
  .item .when{font-size:11.5px;color:var(--muted);white-space:nowrap}
  .item .fav{width:16px;height:16px;border-radius:4px;font-size:9.5px;font-weight:600}
  .item .del{width:22px;height:22px;border-radius:6px;color:var(--muted)}
  .item .del:hover{background:var(--card);color:var(--danger)}
  .group{font-size:10.5px;letter-spacing:.085em;text-transform:uppercase;color:var(--muted);
    font-weight:600;padding:14px 14px 6px}
  .empty{padding:18px 14px;color:var(--muted);font-size:12.5px}""",
             label="habillage historique")

# ------------------------------------------------------------------ paramètres
append_style("assets/ui/settings.html", """/* ---------- habillage 1.3 : paramètres ---------- */
  .page{max-width:820px;padding:28px 26px 64px}
  section{margin-bottom:24px}
  .eng{padding:12px 13px;border-radius:11px;gap:11px}
  .eng:hover{background:var(--card-hover)}
  .eng.on{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
  .eng .logo{width:26px;height:26px;border-radius:7px;font-size:12px}
  .eng .nm{font-size:12.5px;font-weight:560}
  .eng .nt{font-size:11px}
  .bgpick .sw{width:22px;height:22px;border-radius:7px}
  .toast{border-radius:9px;font-size:12.5px}""", label="habillage paramètres")

# ------------------------------------------------------------------ import : applications
append_style("assets/ui/import.html", """/* ---------- habillage 1.3 : import ---------- */
  .page{max-width:820px;padding:28px 26px 64px}
  .app-row{display:flex;align-items:center;gap:12px;padding:11px 14px;border-top:1px solid var(--line)}
  .app-row:first-child{border-top:0}
  .app-row:hover{background:var(--card-hover)}
  .app-row .logo{width:26px;height:26px;border-radius:7px;font-size:12px}
  .app-row .txt b{font-size:12.5px;font-weight:560}
  .app-row .txt small{font-size:11.5px;color:var(--muted);margin-top:2px;display:block}
  .chips{display:flex;gap:5px;flex-wrap:wrap;margin-left:auto}
  .chip{height:24px;padding:0 9px;border-radius:6px;background:transparent;border:1px solid var(--line);
    color:var(--muted);font-size:11.5px;font-weight:500;font-family:inherit;cursor:pointer}
  .chip:hover{background:var(--card);color:var(--text)}
  .chip.on{background:var(--accent-soft, rgba(107,117,232,.16));border-color:transparent;
    color:var(--text);box-shadow:inset 0 0 0 1px var(--line-2)}
  .chip.all{margin-left:8px}
  .bar{height:3px}
  .bar i{width:26%}
  .res b{font-size:18px;font-weight:620}
  .res small{font-size:11.5px}
  .ok{color:var(--ok)}
  .err{color:var(--danger)}
  ul.notes{font-size:11.5px;line-height:1.7;padding-left:16px}
  .mono{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:11px;color:var(--muted)}""",
             label="habillage import")

# ---------------------------------------- import : choix par application (JS + texte)
patch("assets/ui/import.html",
      """  <section>
    <h2>1. Sources détectées sur cet ordinateur</h2>""",
      """  <section>
    <h2>1. Navigateurs détectés sur cet ordinateur</h2>""", label="import : titre de section")

patch("assets/ui/import.html",
      """        <button class="btn primary" id="runSelected">Importer la sélection</button>
        <button class="btn" id="runAll">Tout importer</button>
        <button class="btn" id="rescan">Réanalyser</button>
        <button class="btn" id="pick">Choisir un fichier…</button>""",
      """        <button class="btn primary" id="runSelected">Importer la sélection</button>
        <button class="btn" id="selectAll">Tout sélectionner</button>
        <button class="btn" id="selectNone">Rien</button>
        <button class="btn" id="rescan">Réanalyser</button>
        <button class="btn" id="pick">Choisir un fichier…</button>""",
      label="import : boutons de sélection")

# --- nouvelle version de renderSources : une ligne par APPLICATION -------------
old_js_start = "  function renderSources(list){"
s = (ROOT / "assets/ui/import.html").read_text(encoding="utf-8")
start = s.index(old_js_start)
end = s.index("  function renderResult(res){")
nouveau = '''  /* Regroupe les sources par APPLICATION : l'utilisateur choisit d'abord le
     navigateur (Chrome, Brave, Firefox…), puis éventuellement le détail
     (favoris / historique) avec les deux puces. */
  function groupApps(list){
    const apps = [];
    const byId = {};
    (list || []).forEach((s) => {
      const key = s.app_id || s.app || s.name;
      if (!byId[key]) {
        byId[key] = {id:key, name:s.app || s.name, sources:[], favoris:0, historique:0, profils:{}};
        apps.push(byId[key]);
      }
      const app = byId[key];
      app.sources.push(s);
      const kind = (s.kind || "").toLowerCase();
      if (kind === "favoris") app.favoris++; else app.historique++;
      app.profils[s.name] = true;
    });
    apps.sort((a, b) => a.name.localeCompare(b.name, "fr"));
    return apps;
  }

  function toggleSource(id, on){
    const i = picked.indexOf(id);
    if (on && i === -1) picked.push(id);
    if (!on && i !== -1) picked.splice(i, 1);
  }

  function renderSources(list){
    const box = $("srcList");
    box.textContent = "";
    const apps = groupApps(list);
    if (!apps.length) {
      const d = document.createElement("div");
      d.className = "empty";
      d.innerHTML = "Aucun navigateur détecté automatiquement. Utilisez <b>Choisir un fichier…</b> " +
                    "pour désigner vous-même un fichier de favoris (export HTML) ou d'historique.";
      box.appendChild(d);
      return;
    }
    if (picked === null) picked = (list || []).map((s) => s.id);

    apps.forEach((app) => {
      const row = document.createElement("div");
      row.className = "app-row";

      const logo = document.createElement("div");
      logo.className = "logo";
      logo.style.background = colorOf(app.name);
      logo.textContent = (app.name.trim().charAt(0) || "?").toUpperCase();

      const txt = document.createElement("div");
      txt.className = "txt";
      const b = document.createElement("b");
      b.textContent = app.name;
      const small = document.createElement("small");
      const nbProfils = Object.keys(app.profils).length;
      const morceaux = [];
      if (app.favoris) morceaux.push("favoris");
      if (app.historique) morceaux.push("historique");
      small.textContent = morceaux.join(" + ") +
        (nbProfils > 1 ? " · " + nbProfils + " profils" : "") +
        " · " + app.sources[0].path;
      txt.append(b, small);

      const chips = document.createElement("div");
      chips.className = "chips";
      [["favoris", "Favoris"], ["historique", "Historique"]].forEach(([kind, label]) => {
        const sources = app.sources.filter((s) => (s.kind || "").toLowerCase() === kind);
        if (!sources.length) return;
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip" + (sources.every((s) => picked.indexOf(s.id) !== -1) ? " on" : "");
        chip.textContent = label;
        chip.title = sources.map((s) => s.name + " — " + s.path).join("\\n");
        chip.addEventListener("click", () => {
          const on = !chip.classList.contains("on");
          sources.forEach((s) => toggleSource(s.id, on));
          chip.classList.toggle("on", on);
          majCheck();
        });
        chips.appendChild(chip);
      });
      row.append(logo, txt, chips);

      const check = document.createElement("div");
      check.className = "check";
      check.dataset.app = app.id;
      check.textContent = "✓";
      check.title = "Tout importer de ce navigateur";
      const majCheck = () => {
        const tout = app.sources.every((s) => picked.indexOf(s.id) !== -1);
        const rien = app.sources.every((s) => picked.indexOf(s.id) === -1);
        check.classList.toggle("on", tout && !rien);
        chips.querySelectorAll(".chip").forEach((c, i) => {
          const kind = i === 0 ? "favoris" : "historique";
          const srcs = app.sources.filter((s) => (s.kind || "").toLowerCase() === kind);
          if (srcs.length) c.classList.toggle("on", srcs.some((s) => picked.indexOf(s.id) !== -1));
        });
      };
      check.addEventListener("click", () => {
        const tout = app.sources.every((s) => picked.indexOf(s.id) !== -1);
        app.sources.forEach((s) => toggleSource(s.id, !tout));
        majCheck();
      });
      row.append(check);
      majCheck();
      box.appendChild(row);
    });
  }

'''
s = s[:start] + nouveau + s[end:]
(ROOT / "assets/ui/import.html").write_text(s, encoding="utf-8")
print("  ok import : rendu par application")

# --- boutons « tout sélectionner » / « rien » ---------------------------------
patch("assets/ui/import.html",
      """  $("pick").addEventListener("click", () => post({cmd:"import_pick"}));""",
      """  $("pick").addEventListener("click", () => post({cmd:"import_pick"}));
  $("selectAll").addEventListener("click", () => {
    picked = (N.import_sources || []).map((s) => s.id);
    renderSources(N.import_sources || []);
  });
  $("selectNone").addEventListener("click", () => {
    picked = [];
    renderSources(N.import_sources || []);
  });""", label="import : tout/rien")

print("étape 4 : terminée")
