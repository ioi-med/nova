#!/usr/bin/env python3
"""Planche des nouveautés de la version 1.2.0 : import des données d'un
autre navigateur (captures de `audit_ui/`).

Assemble en une seule image : le haut de la page d'import (sources détectées),
le compte rendu d'un import réel, la barre latérale après un import de 30
favoris, et l'accès depuis les Paramètres.

    python3 tools/ui_features_plate.py
"""
import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "audit_ui"
SORTIE = SHOTS / "NOUVEAUTES-1.3.2.png"

# (libellé, fichier, découpe : (gauche, haut, droite, bas) ou None)
CASES = [
    ("Logos officiels des moteurs (page du nouvel onglet)", "newtab-dark.png", (150, 130, 1050, 480)),
    ("Logos dans les parametres", "settings-dark.png", (150, 90, 1050, 430)),
    ("Icone de Nova : carre arrondi, aplat, « N » blanc", "logo-nova.png", None),
    ("Assistant : quelle application importer", "welcome-import-dark.png", None),
    ("Parametres : etat des protections (captures, secours, journal)",
     "settings-protocoles-dark.png", (150, 380, 1050, 700)),
]


def main():
    planches = []
    for label, fichier, crop in CASES:
        img = Image.open(SHOTS / fichier).convert("RGB")
        if crop:
            img = img.crop(crop)
        planches.append((label, img))

    marge, gouttiere, titre = 18, 16, 30
    largeur = max(p.width for _, p in planches) + marge * 2
    hauteur = sum(p.height + titre for _, p in planches) + marge * 2 \
        + gouttiere * (len(planches) - 1)

    planche = Image.new("RGB", (largeur, hauteur), (16, 16, 20))
    draw = ImageDraw.Draw(planche)
    y = marge
    for label, img in planches:
        draw.text((marge, y + 8), label.upper(), fill=(154, 154, 166))
        y += titre
        planche.paste(img, (marge, y))
        y += img.height + gouttiere
    planche.save(SORTIE)
    print(f"{SORTIE.relative_to(ROOT)}  ({planche.width}x{planche.height})")


if __name__ == "__main__":
    main()
