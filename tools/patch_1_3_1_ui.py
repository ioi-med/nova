#!/usr/bin/env python3
"""Nova 1.3.1 — interface : assistant de premier lancement (import) + état des
protections dans les Paramètres."""
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


# =========================================================== welcome.html ====
w = ROOT / "assets/ui/welcome.html"
s = w.read_text(encoding="utf-8")

# 1. l'étape 3 remplace l'ancienne étape 2
s = s.replace('  .step2{display:none}\n  body[data-step="2"] .step1{display:none}\n  body[data-step="2"] .step2{display:block}',
              '  .step2,.step3{display:none}\n  body[data-step="2"] .step1{display:none}\n  body[data-step="2"] .step2{display:block}\n'
              '  body[data-step="3"] .step1,body[data-step="3"] .step2{display:none}\n  body[data-step="3"] .step3{display:block}', 1)
s = s.replace('  <div class="step2">\n    <p class="sub">\n      Derniers réglages.',
              '  <div class="step2" id="stepImport">\n'
              '    <p class="sub">\n'
              '      Dernière étape : vos <b>favoris</b> et votre <b>historique</b> peuvent venir du navigateur que vous\n'
              '      utilisiez déjà. Cochez les navigateurs dont Nova doit reprendre les données — l\'autre navigateur\n'
              '      n\'est pas modifié, les doublons sont écartés, et vous pouvez tout reprendre plus tard dans\n'
              '      <b>Paramètres &gt; Importer…</b>\n'
              '    </p>\n'
              '\n'
              '    <div class="apps" id="apps"></div>\n'
              '\n'
              '    <div class="actions">\n'
              '      <button class="go" id="doImport" disabled>Importer la sélection</button>\n'
              '      <button class="chip" id="toOptions">Plus tard</button>\n'
              '      <button class="go" id="afterImport" style="display:none">Continuer</button>\n'
              '      <span class="note" id="importNote">Recherche des navigateurs installés…</span>\n'
              '    </div>\n'
              '  </div>\n'
              '\n'
              '  <div class="step3">\n'
              '    <p class="sub">\n'
              '      Derniers réglages.', 1)

# 2. réglage « message de Windows » dans la dernière étape
s = s.replace('''      <div class="opt">
        <div class="txt">Thème sombre''',
'''      <div class="opt">
        <div class="txt">Supprimer le message de Windows sur l'overlay de jeu
          <small>Un jeu, une manette ou la touche <b>Win+G</b> font réclamer à Windows la
          barre de jeux Xbox ; comme elle n'est pas installée, une boîte « Obtenir une
          application pour ouvrir ce lien » s'ouvre. Nova coupe cette demande pour votre seul
          compte (aucun droit administrateur, réversible).</small>
        </div>
        <button class="switch on" id="swOverlay" aria-label="Supprimer le message de Windows"></button>
      </div>
      <div class="opt">
        <div class="txt">Thème sombre''', 1)

# 3. habillage de la liste des applications
s = s.replace('''  /* ---------- habillage 1.3 : assistant de premier lancement ---------- */''',
'''  /* ---------- étape 2 : navigateurs dont on reprend les données ---------- */
  .apps{display:flex;flex-direction:column;gap:6px;margin-top:18px;max-width:620px}
  .app{display:flex;align-items:center;gap:12px;background:var(--card);border:1px solid var(--line);
       border-radius:11px;padding:11px 14px;cursor:pointer}
  .app:hover{background:var(--card-hover);border-color:var(--line-2)}
  .app .logo{width:26px;height:26px;border-radius:7px;display:flex;align-items:center;
       justify-content:center;color:#fff;font-weight:600;font-size:12px;flex:0 0 auto}
  .app .txt{flex:1;min-width:0}
  .app .txt b{font-size:12.5px;font-weight:560}
  .app .txt small{display:block;color:var(--muted);font-size:11.5px;margin-top:2px;
       white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .app .box{width:18px;height:18px;border-radius:5px;border:1px solid var(--line-2);flex:0 0 auto;
       display:flex;align-items:center;justify-content:center;font-size:11px;color:transparent}
  .app.on .box{background:var(--accent);border-color:var(--accent);color:#fff}
  .apps .vide{color:var(--muted);font-size:12px}
  .actions .chip{height:34px;padding:0 14px;border-radius:8px}

  /* ---------- habillage 1.3 : assistant de premier lancement ---------- */''', 1)

# 4. logique de l'étape import
s = s.replace('''  document.getElementById("next").addEventListener("click", () => { document.body.dataset.step = "2"; });''',
'''  /* ---------- étape 2 : import des données d'un autre navigateur ---------- */
  let apps = [];
  let coches = null;      // null = tout ce qui est détecté
  let importe = false;

  function grouper(liste){
    const out = [];
    const index = {};
    (liste || []).forEach((src) => {
      const cle = src.app_id || src.app || src.name;
      if (!index[cle]) {
        index[cle] = {id:cle, nom:src.app || src.name, favoris:0, historique:0, profils:{},
                      chemins:[]};
        out.push(index[cle]);
      }
      const a = index[cle];
      a.profils[src.name] = true;
      a.chemins.push(src.path);
      if ((src.kind || "").toLowerCase() === "favoris") a.favoris++; else a.historique++;
    });
    out.sort((a, b) => a.nom.localeCompare(b.nom, "fr"));
    return out;
  }

  function couleur(nom){
    let h = 0;
    for (let i = 0; i < nom.length; i++) h = (h * 31 + nom.charCodeAt(i)) % 360;
    return "hsl(" + h + ",45%,42%)";
  }

  function dessinerApps(){
    const box = document.getElementById("apps");
    const note = document.getElementById("importNote");
    box.textContent = "";
    apps = grouper(N.import_sources);
    if (!apps.length) {
      const d = document.createElement("div");
      d.className = "vide";
      d.textContent = (N.import_busy ? "Recherche des navigateurs installés…" :
        "Aucun navigateur détecté. Vous pourrez en désigner un vous-même dans Paramètres > Importer…");
      box.appendChild(d);
      document.getElementById("doImport").disabled = true;
      if (N.import_busy) note.textContent = "Recherche des navigateurs installés…";
      return;
    }
    if (coches === null) coches = apps.map((a) => a.id);

    apps.forEach((app) => {
      const row = document.createElement("div");
      row.className = "app" + (coches.indexOf(app.id) !== -1 ? " on" : "");
      const logo = document.createElement("div");
      logo.className = "logo";
      logo.style.background = couleur(app.nom);
      logo.textContent = (app.nom.trim().charAt(0) || "?").toUpperCase();
      const txt = document.createElement("div");
      txt.className = "txt";
      const b = document.createElement("b");
      b.textContent = app.nom;
      const small = document.createElement("small");
      const bouts = [];
      if (app.favoris) bouts.push("favoris");
      if (app.historique) bouts.push("historique");
      const nbProfils = Object.keys(app.profils).length;
      small.textContent = bouts.join(" + ") + (nbProfils > 1 ? " · " + nbProfils + " profils" : "") +
                          " · " + app.chemins[0];
      txt.append(b, small);
      const box2 = document.createElement("div");
      box2.className = "box";
      box2.textContent = "✓";
      row.append(logo, txt, box2);
      row.addEventListener("click", () => {
        const i = coches.indexOf(app.id);
        if (i === -1) coches.push(app.id);
        else if (coches.length > 0 && apps.length > 1) coches.splice(i, 1);
        if (coches.indexOf(app.id) === -1 && i === -1) coches.splice(i, 0);
        row.classList.toggle("on", coches.indexOf(app.id) !== -1);
        maj();
      });
      box.appendChild(row);
    });
    maj();
  }

  function maj(){
    const btn = document.getElementById("doImport");
    btn.disabled = !coches || coches.length === 0;
    const note = document.getElementById("importNote");
    if (importe) return;
    if (!coches) { note.textContent = "Recherche des navigateurs installés…"; return; }
    const noms = apps.filter((a) => coches.indexOf(a.id) !== -1).map((a) => a.nom);
    note.textContent = noms.length ? "Sera repris de : " + noms.join(", ")
      : "Aucun navigateur sélectionné.";
  }

  function lancerImport(){
    const ids = [];
    (N.import_sources || []).forEach((src) => {
      const cle = src.app_id || src.app || src.name;
      if (coches.indexOf(cle) !== -1) ids.push(src.id);
    });
    importe = true;
    document.getElementById("doImport").disabled = true;
    document.getElementById("importNote").textContent = "Import en cours…";
    post({cmd:"import_run", ids:ids, favorites:true, history:true, replace:false});
  }

  document.getElementById("doImport").addEventListener("click", lancerImport);
  document.getElementById("toOptions").addEventListener("click", () => { document.body.dataset.step = "3"; });
  document.getElementById("afterImport").addEventListener("click", () => { document.body.dataset.step = "3"; });

  document.getElementById("next").addEventListener("click", () => { document.body.dataset.step = "2"; });''', 1)

# 5. états reçus de Rust (liste + résultat d'import)
s = s.replace('''  document.getElementById("start").addEventListener("click", () => {''',
'''  /* Rust pousse l'état (liste des navigateurs, résultat de l'import). */
  window.NovaPage = {
    render(state){
      N = state;
      applyTheme();
      dessinerApps();
      const res = state.import_result;
      if (importe && res) {
        const fav = res.favorites || 0;
        const vis = res.visits || 0;
        document.getElementById("importNote").textContent =
          (fav || vis) ? (fav + " favori(s) et " + vis + " visite(s) repris.")
                       : "Rien de nouveau à reprendre (tout était déjà là).";
        document.getElementById("doImport").style.display = "none";
        document.getElementById("toOptions").style.display = "none";
        document.getElementById("afterImport").style.display = "";
      } else if (!importe && state.import_busy === false && (state.import_sources || []).length) {
        maj();
      }
    },
    toast(){}
  };

  document.getElementById("start").addEventListener("click", () => {''', 1)

# 6. le réglage part avec la fin de l'assistant + état initial
s = s.replace('''  const swDark = bindSwitch("swDark");''',
'''  const swDark = bindSwitch("swDark");
  const swOverlay = bindSwitch("swOverlay");''', 1)
s = s.replace('''      theme:swDark.classList.contains("on") ? "dark" : "light"});''',
'''      theme:swDark.classList.contains("on") ? "dark" : "light",
      silence_game_overlay:swOverlay.classList.contains("on")});''', 1)
w.write_text(s, encoding="utf-8")
print("  ok welcome.html : étape import + réglage")


# ========================================================== settings.html ====
patch("assets/ui/settings.html",
"""      <div class="row">
        <div class="txt"><b>Message de Windows sur l'overlay de jeu</b>
          <small>Quand un jeu ou une manette demande l'overlay Xbox
          (<span style="font-family:ui-monospace,monospace">ms-gamingoverlay:</span>) et que ce logiciel n'est pas
          installé, Windows ouvre une boîte « Obtenir une application pour ouvrir ce lien ». Nova peut accepter ces
          adresses à votre place et les ignorer : le message ne revient plus. Écriture dans votre seul compte
          (<span style="font-family:ui-monospace,monospace">HKCU</span>), sans droits administrateur, et réversible.</small></div>
        <button class="switch" id="swOverlay"></button>
      </div>""",
"""      <div class="row">
        <div class="txt"><b>Supprimer le message de Windows sur l'overlay de jeu</b>
          <small>C'est <b>Windows</b> qui réclame l'overlay Xbox — touche <b>Win+G</b>, manette branchée,
          ou jeu qui démarre — et comme la barre de jeux n'est pas installée, il ouvre « Obtenir une application
          pour ouvrir ce lien ». Nova coupe cette demande à la source pour votre seul compte : captures et
          barre de jeux désactivées (<span style="font-family:ui-monospace,monospace">HKCU</span>), et un
          gestionnaire de secours pour que ces adresses n'aboutissent jamais sur une boîte de dialogue.
          Aucun droit administrateur, réversible en décochant.</small>
          <small id="ovState" class="ov"></small></div>
        <button class="switch" id="swOverlay"></button>
      </div>""", label="paramètres : bloc overlay")

patch("assets/ui/settings.html",
"""      setSwitch($("swOverlay"), state.config.silence_game_overlay !== false);""",
"""      setSwitch($("swOverlay"), state.config.silence_game_overlay !== false);
      const ov = state.overlay || {};
      const etat = $("ovState");
      if (etat) {
        const lignes = [];
        lignes.push(ov.dvr_off
          ? "Captures et barre de jeux : désactivées pour votre compte."
          : "Captures et barre de jeux : encore actives (Win+G peut rouvrir la boîte).");
        lignes.push(ov.stub
          ? "Gestionnaire de secours : enregistré (Nova ignore ces adresses)."
          : "Gestionnaire de secours : non enregistré.");
        if (ov.game_bar) lignes.push("La barre de jeux Xbox est installée : rien n'est modifié.");
        lignes.push((ov.refused || 0) + " demande(s) d'ouverture refusée(s) par Nova · journal : " +
                    (ov.log || "protocoles-refuses.log"));
        etat.textContent = lignes.join(" ");
      }""", label="paramètres : état des protections")

patch("assets/ui/settings.html",
"""  .row .txt b{font-weight:560}
  .row small{font-size:11.5px;line-height:1.5;margin-top:2px}""",
"""  .row .txt b{font-weight:560}
  .row small{font-size:11.5px;line-height:1.5;margin-top:2px}
  .row small.ov{color:var(--accent);margin-top:5px}""", label="paramètres : style de l'état")
print("étape interface : terminée")
