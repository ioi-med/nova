#!/usr/bin/env python3
"""Correctif 1.3.0 — étape 3 : habillage sobre, dans l'esprit d'Arc.

Ce script :
1. remplace la palette de chaque page par une palette neutre et posée
   (mêmes noms de variables : rien d'autre à changer dans les feuilles) ;
2. ajoute une couche d'habillage commune qui retire les marqueurs « générés » :
   dégradés, halos flous, ombres lourdes, boutons pilule, survols qui sautent ;
3. applique quelques réglages par surface (barre latérale, barre d'adresse,
   nouvel onglet, assistant).
"""
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


# ---------------------------------------------------------------- palettes ---
PALETTES = {
    "sidebar": ("""  :root{
    --bg:#1b1b1f; --bg-2:#212127; --bg-3:#2a2a33; --bg-hover:#26262e;
    --text:#eaeaef; --muted:#9a9aa6; --line:#31313b; --scroll:#3a3a45;
    --fav-plate:#e9e9f2;
    --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;
    --radius:11px; --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f4f4f7; --bg-2:#ffffff; --bg-3:#e8e8ee; --bg-hover:#e9e9ef;
    --text:#191920; --muted:#6b6b76; --line:#dedee6; --scroll:#c6c6d0;
    --fav-plate:#f2f2f7;
  }""",
                """  :root{
    --bg:#1a1b1f; --bg-2:#202127; --bg-3:#292a31; --bg-hover:#232429;
    --text:#eceef2; --muted:#9a9ca7; --line:#2b2c33; --scroll:#37383f;
    --fav-plate:#e9e9f2;
    --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --radius:8px; --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --bg-2:#ffffff; --bg-3:#e9eaee; --bg-hover:#eceef2;
    --text:#15161a; --muted:#5f616d; --line:#e2e4e9; --scroll:#c9cbd3;
    --fav-plate:#f2f2f7;
  }"""),
    "toolbar": ("""  :root{
    --bg:#1b1b1f; --bg-2:#26262e; --bg-hover:#2f2f39;
    --text:#eaeaef; --muted:#9a9aa6; --line:#31313b;
    --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f4f4f7; --bg-2:#e8e8ee; --bg-hover:#dcdce4;
    --text:#191920; --muted:#6b6b76; --line:#dedee6;
  }""",
                """  :root{
    --bg:#f5f6f8; --bg-2:#eceef2; --bg-hover:#e4e6ec;
    --text:#15161a; --muted:#5f616d; --line:#e2e4e9;
    --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --bg-2:#eceef2; --bg-hover:#e4e6ec;
    --text:#15161a; --muted:#5f616d; --line:#e2e4e9;
  }"""),
    "newtab": ("""  :root{
    --bg:#16161a; --card:#1e1e24; --card-hover:#26262e; --text:#eaeaef; --muted:#9a9aa6;
    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#fbfbfd; --card:#ffffff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;
  }""",
               """  :root{
    --bg:#1a1b1f; --card:#202127; --card-hover:#26272e; --text:#eceef2; --muted:#9a9ca7;
    --line:#2b2c33; --line-2:#35363e; --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --card:#ffffff; --card-hover:#f1f2f5; --text:#15161a; --muted:#5f616d;
    --line:#e2e4e9; --line-2:#d5d8de;
  }"""),
    "settings": ("""  :root{
    --bg:#16161a; --card:#1e1e24; --card-hover:#26262e; --text:#eaeaef; --muted:#9a9aa6;
    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;
    --switch-off:#3a3a45;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#fbfbfd; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;
    --switch-off:#c9c9d2;
  }""",
                 """  :root{
    --bg:#1a1b1f; --card:#202127; --card-hover:#26272e; --text:#eceef2; --muted:#9a9ca7;
    --line:#2b2c33; --line-2:#35363e; --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --accent-soft:rgba(107,117,232,.18);
    --switch-off:#34353d; --ok:#3fb950;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --card:#fff; --card-hover:#f1f2f5; --text:#15161a; --muted:#5f616d; --line:#e2e4e9;
    --line-2:#d5d8de; --accent-soft:rgba(107,117,232,.12);
    --switch-off:#cdcfd6; --ok:#15803d;
  }"""),
    "history": ("""  :root{
    --bg:#16161a; --card:#1e1e24; --card-hover:#26262e; --text:#eaeaef; --muted:#9a9aa6;
    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#fbfbfd; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;
  }""",
                """  :root{
    --bg:#1a1b1f; --card:#202127; --card-hover:#26272e; --text:#eceef2; --muted:#9a9ca7;
    --line:#2b2c33; --line-2:#35363e; --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --card:#fff; --card-hover:#f1f2f5; --text:#15161a; --muted:#5f616d; --line:#e2e4e9;
    --line-2:#d5d8de;
  }"""),
    "welcome": ("""  :root{
    --bg:#141418; --card:#1d1d23; --card-hover:#26262e; --text:#eaeaef; --muted:#9a9aa6;
    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff;
    --switch-off:#3a3a45;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f7f7fb; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76;
    --line:#e6e6ec; --switch-off:#c9c9d2;
  }""",
                """  :root{
    --bg:#1a1b1f; --card:#202127; --card-hover:#26272e; --text:#eceef2; --muted:#9a9ca7;
    --line:#2b2c33; --line-2:#35363e; --accent:#6b75e8; --accent-2:#6b75e8;
    --switch-off:#34353d;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --card:#fff; --card-hover:#f1f2f5; --text:#15161a; --muted:#5f616d;
    --line:#e2e4e9; --line-2:#d5d8de; --switch-off:#cdcfd6;
  }"""),
    "import": ("""  :root{
    --bg:#16161a; --card:#1e1e24; --card-hover:#26262e; --text:#eaeaef; --muted:#9a9aa6;
    --line:#2c2c34; --accent:#7a6bff; --accent-2:#3ac1ff; --danger:#ff6b6b;
    --switch-off:#3a3a45; --ok:#4ade80;
    --font:-apple-system,"Segoe UI Variable Text","Segoe UI",system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#fbfbfd; --card:#fff; --card-hover:#f0f0f5; --text:#191920; --muted:#6b6b76; --line:#e6e6ec;
    --switch-off:#c9c9d2; --ok:#15803d;
  }""",
               """  :root{
    --bg:#1a1b1f; --card:#202127; --card-hover:#26272e; --text:#eceef2; --muted:#9a9ca7;
    --line:#2b2c33; --line-2:#35363e; --accent:#6b75e8; --accent-2:#6b75e8; --danger:#e5534b;
    --switch-off:#34353d; --ok:#3fb950;
    --font:"Segoe UI Variable Text","Segoe UI",Inter,-apple-system,system-ui,Roboto,sans-serif;
  }
  html[data-theme="light"]{
    --bg:#f5f6f8; --card:#fff; --card-hover:#f1f2f5; --text:#15161a; --muted:#5f616d; --line:#e2e4e9;
    --line-2:#d5d8de; --switch-off:#cdcfd6; --ok:#15803d;
  }"""),
}

for name, (old, new) in PALETTES.items():
    patch(f"assets/ui/{name}.html", old, new, label=f"palette {name}")

# ------------------------------------------------------------ habillage commun
COUCHE = """
<style>
/* ==================================================================
   Habillage 1.3 — sobre et posé, dans l'esprit d'Arc.
   Cette couche est ajoutée après la feuille d'origine : elle retire les
   marqueurs « décoratifs » (dégradés, halos flous, ombres lourdes, pastilles
   pilule, survols qui font sauter les éléments) et aligne les composants sur
   une même grille de 4 px.
   ================================================================== */
  *{letter-spacing:-.006em}
  h1{font-size:19px;font-weight:640;letter-spacing:-.022em;margin:0 0 4px}
  h2{font-size:10.5px;letter-spacing:.085em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:0 0 8px}
  .lead{font-size:12.5px;line-height:1.55;color:var(--muted);margin-bottom:22px}
  :focus-visible{outline:2px solid var(--accent);outline-offset:1px;border-radius:6px}
  .glow{display:none}

  /* --- cartes et lignes --- */
  .card{border:1px solid var(--line);border-radius:12px;box-shadow:none;overflow:hidden}
  .row{gap:12px;padding:11px 14px;border-top:1px solid var(--line)}
  .row:first-child{border-top:0}
  .row .txt b{font-weight:560}
  .row small{font-size:11.5px;line-height:1.5;margin-top:2px}

  /* --- boutons --- */
  .btn{
    height:28px;padding:0 11px;border-radius:7px;background:var(--card);border:1px solid var(--line);
    color:var(--text);font-size:12.5px;font-weight:500;display:inline-flex;align-items:center;
    justify-content:center;gap:6px;transition:background .12s,border-color .12s;
  }
  .btn:hover{background:var(--card-hover);border-color:var(--line-2)}
  .btn.primary{background:var(--accent);border-color:transparent;color:#fff;font-weight:550}
  .btn.primary:hover{background:#7c85ec;border-color:transparent}
  .btn.danger{color:var(--danger);border-color:rgba(229,83,75,.32);background:transparent}
  .btn.danger:hover{background:rgba(229,83,75,.10);border-color:rgba(229,83,75,.45)}

  /* --- interrupteurs --- */
  .switch{width:36px;height:20px;border-radius:999px;background:var(--switch-off)}
  .switch::after{width:14px;height:14px;top:3px;left:3px;box-shadow:0 1px 2px rgba(0,0,0,.22)}
  .switch.on{background:var(--accent)}
  .switch.on::after{transform:translateX(16px)}

  /* --- contrôles segmentés --- */
  .seg{border-radius:8px;padding:2px;background:var(--card-hover);border-color:var(--line)}
  .seg button{border-radius:6px;font-weight:500}
  .seg button.on{background:var(--card);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.16)}
  html[data-theme="light"] .seg button.on{background:#fff;box-shadow:0 1px 2px rgba(16,17,22,.08)}

  /* --- pastilles et étiquettes --- */
  .badge{border-radius:6px;font-weight:500;padding:2px 7px}

  /* --- tableaux --- */
  table{font-size:12.5px}
  td{padding:8px 0}
  kbd{border-radius:5px;font-size:10.5px}
</style>
"""

for name in PALETTES:
    patch(f"assets/ui/{name}.html", "</head>", COUCHE + "</head>", label=f"habillage {name}")

print("étape 3 (palettes + habillage commun) : terminée")
