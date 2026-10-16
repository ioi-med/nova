#!/usr/bin/env python3
"""Comparatif avant/après des correctifs visuels.

Capture les mêmes écrans avec les fichiers d'origine (sauvegarde `before/`) puis
avec les fichiers corrigés, et assemble une planche AVANT | APRÈS.

    python3 tools/ui_before_after.py
"""
import pathlib
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ui_shot  # noqa: E402

BEFORE = ROOT / "audit_ui" / "before"
AFTER = ROOT / "audit_ui"
ORIGINAUX = pathlib.Path("/tmp/assets_backup/ui")   # copie d'avant correctifs

SCENES = [
    # (libellé, page, thème, taille, script à exécuter, recadrage facultatif)
    ("Onglets épinglés", "sidebar", "dark", (248, 120),
     "window.NovaUI.render(window.__NOVA__);", (0, 26, 248, 84)),
    ("Paramètres (thème clair)", "settings", "light", (1200, 820),
     "window.NovaPage && window.NovaPage.render(window.__NOVA__);", (160, 380, 1040, 620)),
    ("Historique (thème clair)", "history", "light", (1200, 820),
     "window.NovaPage && window.NovaPage.render(window.__NOVA__);", None),
    ("Assistant (thème clair)", "welcome", "light", (900, 640),
     "window.NovaPage && window.NovaPage.render(window.__NOVA__);", None),
]


def uisource(name):
    """Le fichier d'interface courant (corrigé)."""
    return ROOT / "assets" / "ui" / f"{name}.html"


def capture(page, theme, size, tail, out_dir, tag, ui_dir):
    """Capture une page en utilisant un jeu de fichiers d'interface donné."""
    sauvegarde = (ui_shot.UI, ui_shot.OUT)
    try:
        ui_shot.UI = ui_dir
        ui_shot.OUT = out_dir
        ui_shot.CONFIG["theme"] = theme
        inner = ui_shot.page(page, theme, tail)
    finally:
        ui_shot.UI, ui_shot.OUT = sauvegarde
    w, h = size
    host = ui_shot.host(inner, w, h, theme)
    path = out_dir / "build" / f"{tag}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(host, encoding="utf-8")
    png = out_dir / f"{tag}.png"
    subprocess.run(
        [ui_shot.CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
         "--allow-file-access-from-files", "--force-color-profile=srgb",
         f"--window-size={w},{h}", "--virtual-time-budget=4000",
         f"--screenshot={png}", f"file://{path}"],
        capture_output=True, timeout=180)
    return png


def etiquette(img, texte, theme):
    """Ajoute un bandeau de titre au-dessus d'une capture."""
    largeur = img.width
    mur = Image.new("RGB", (largeur, 26), (24, 24, 28) if theme == "dark" else (232, 232, 238))
    d = ImageDraw.Draw(mur)
    d.text((9, 8), texte, fill=(200, 200, 210) if theme == "dark" else (60, 60, 70))
    bande = Image.new("RGB", (largeur, img.height + 26))
    bande.paste(mur, (0, 0))
    bande.paste(img, (0, 26))
    return bande


def main():
    if not ORIGINAUX.exists():
        sys.exit("copie des fichiers d'origine absente (before/) — comparatif impossible")
    BEFORE.mkdir(parents=True, exist_ok=True)
    after_dir = ROOT / "audit_ui" / "after"
    after_dir.mkdir(parents=True, exist_ok=True)

    lignes = []
    for i, (label, page, theme, size, tail, crop) in enumerate(SCENES):
        tag = f"s{i}"
        a = capture(page, theme, size, tail, BEFORE, tag, ORIGINAUX)
        b = capture(page, theme, size, tail, after_dir, tag, ROOT / "assets" / "ui")

        ia = Image.open(a).convert("RGB")
        ib = Image.open(b).convert("RGB")
        if crop:
            ia = ia.crop(crop)
            ib = ib.crop(crop)
        if ia.height > 380:                      # hauteur homogène
            ia = ia.crop((0, 0, ia.width, 380))
            ib = ib.crop((0, 0, ib.width, 380))
        lignes.append((label, etiquette(ia, "AVANT", theme),
                       etiquette(ib, "APRÈS", theme)))

    marge, gouttiere = 16, 14
    largeur = max(a.width + b.width for _, a, b in lignes) + marge * 2 + gouttiere
    hauteur = sum(max(a.height, b.height) for _, a, b in lignes) \
        + marge * 2 + gouttiere * (len(lignes) - 1) + 34 * len(lignes)
    planche = Image.new("RGB", (largeur, hauteur), (12, 12, 15))
    d = ImageDraw.Draw(planche)
    d.text((marge, 12), "Nova — correctifs visuels : AVANT / APRÈS", fill=(235, 235, 240))

    y = marge + 26
    for label, a, b in lignes:
        d.text((marge, y), label, fill=(150, 150, 165))
        y += 26
        planche.paste(a, (marge, y))
        planche.paste(b, (marge + a.width + gouttiere, y))
        y += max(a.height, b.height) + gouttiere

    sortie = ROOT / "audit_ui" / "AVANT-APRES-visuel.png"
    planche.save(sortie)
    print(f"planche écrite : {sortie.relative_to(ROOT)} ({planche.width}×{planche.height})")


if __name__ == "__main__":
    main()
