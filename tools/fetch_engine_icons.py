#!/usr/bin/env python3
"""Récupère les logos officiels des moteurs de recherche et les prépare pour
l'interface (assets/engines/<id>.png, 64×64, transparence conservée).

Les images sont prises **aux sources officielles** (favicon ou icône déclarée
par le site du moteur), puis recadrées et redimensionnées. Elles ne servent
qu'à désigner le moteur correspondant dans l'interface : voir
`LICENCES-TIERS.md` (marques et licences).

    python3 tools/fetch_engine_icons.py

Sans accès réseau, les fichiers déjà présents dans `assets/engines/` sont
conservés : l'interface retombe alors sur la pastille de couleur du moteur
(`window.NovaEngineIcon`).
"""

import io
import pathlib
import subprocess
import sys

from PIL import Image

RACINE = pathlib.Path(__file__).resolve().parent.parent
SORTIE = RACINE / "assets" / "engines"

# id du moteur -> (URL de l'image, éventuel rendu SVG à effectuer)
SOURCES = {
    "google": ("https://www.gstatic.com/images/branding/googleg/1x/googleg_standard_color_128dp.png", False),
    "brave": ("https://brave.com/static-assets/images/brave-logo-sans-text.svg", True),
    "ecosia": ("https://www.ecosia.org/apple-touch-icon.png", False),
    "duckduckgo": ("https://duckduckgo.com/assets/icons/meta/DDG-icon_256x256.png", False),
    "startpage": ("https://www.startpage.com/favicon.ico", False),
    "qwant": ("https://www.qwant.com/favicon.ico", False),
}

TAILLE = 64
MARGE = 0.04


def telecharger(url, destination):
    """Télécharge une ressource (curl : présent partout, aucune dépendance Python)."""
    resultat = subprocess.run(
        ["curl", "-sSL", "-A", "Mozilla/5.0 (Nova; recup logos)",
         "-o", str(destination), url],
        capture_output=True,
    )
    return resultat.returncode == 0 and destination.exists() and destination.stat().st_size > 0


def rendre_svg(source, destination):
    """Rasterise un SVG avec le moteur déjà installé sur la machine (Chromium)."""
    page = source.with_suffix(".html")
    page.write_text(
        '<!doctype html><meta charset="utf-8">'
        '<style>html,body{margin:0;background:transparent}'
        'img{width:256px;height:256px;object-fit:contain;display:block}</style>'
        f'<img src="{source.name}">',
        encoding="utf-8",
    )
    resultat = subprocess.run(
        ["chromium", "--headless=new", "--no-sandbox", "--disable-gpu",
         "--default-background-color=00000000", "--hide-scrollbars",
         "--window-size=256,256", f"--screenshot={destination}", page.as_uri()],
        capture_output=True,
    )
    return resultat.returncode == 0 and destination.exists()


def preparer(chemin, taille=TAILLE, marge=MARGE):
    """Recadre au contenu, met dans un carré et réduit proprement."""
    image = Image.open(chemin).convert("RGBA")
    cadre = image.getbbox()
    if cadre:
        image = image.crop(cadre)
    cote = max(image.size)
    carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    carre.paste(image, ((cote - image.width) // 2, (cote - image.height) // 2))
    pad = int(cote * marge)
    final = Image.new("RGBA", (cote + 2 * pad, cote + 2 * pad), (0, 0, 0, 0))
    final.paste(carre, (pad, pad))
    return final.resize((taille, taille), Image.LANCZOS)


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    temporaire = SORTIE / "_recu"
    temporaire.mkdir(exist_ok=True)
    echecs = []

    for identifiant, (url, est_svg) in SOURCES.items():
        brut = temporaire / (identifiant + (".svg" if est_svg else pathlib.Path(url).suffix))
        if not telecharger(url, brut):
            echecs.append((identifiant, "téléchargement impossible"))
            continue
        if est_svg and not rendre_svg(brut, brut.with_suffix(".png")):
            echecs.append((identifiant, "rendu du SVG impossible (chromium ?)"))
            continue
        try:
            image = preparer(brut.with_suffix(".png") if est_svg else brut)
        except Exception as erreur:  # image illisible : on garde l'ancienne
            echecs.append((identifiant, f"image illisible ({erreur})"))
            continue
        destination = SORTIE / f"{identifiant}.png"
        image.save(destination, optimize=True)
        print(f"  {destination.relative_to(RACINE)}  {destination.stat().st_size} o  <- {url}")

    for identifiant, raison in echecs:
        deja = (SORTIE / f"{identifiant}.png").exists()
        print(f"  !! {identifiant} : {raison}" + (" — ancienne image conservée" if deja else ""))
    return 1 if echecs and not any((SORTIE / f"{i}.png").exists() for i in SOURCES) else 0


if __name__ == "__main__":
    sys.exit(main())
