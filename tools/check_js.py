#!/usr/bin/env python3
"""Vérifie la syntaxe de tous les scripts embarqués dans les pages de Nova.

    python3 tools/check_js.py          # 0 = tout est valide
"""
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = sorted(ROOT.glob("assets/ui/*.html")) + [ROOT / "assets/ui/inject.js"]
bad = 0
for path in FILES:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", text, re.S) if path.suffix == ".html" else [text]
    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write("(function(){\n" + block + "\n})();")
            tmp = fh.name
        res = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        if res.returncode != 0:
            bad += 1
            print(f"ÉCHEC {path.name} (script {i + 1}) :")
            print("   " + res.stderr.strip().splitlines()[0] if res.stderr else "")
            print("\n".join(res.stderr.strip().splitlines()[:6]))
        else:
            print(f"ok    {path.name} script {i + 1} ({len(block.splitlines())} lignes)")
sys.exit(1 if bad else 0)
