#!/usr/bin/env bash
# Construit l'archive de distribution de Nova.
#
#   bash tools/package.sh            # -> Nova-<version>-win64.zip
#
# L'archive contient l'exécutable, son empreinte SHA-256, la documentation et
# **toutes les sources** (Rust + module C + interface + scripts de test) : elle
# doit suffire à recompiler Nova depuis zéro, sans rien télécharger d'autre que
# les dépendances de `Cargo.toml`.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(grep -m1 '^version' Cargo.toml | cut -d'"' -f2)"
NAME="Nova-${VERSION}-win64"
STAGE="/tmp/${NAME}"

[ -f Nova.exe ] || { echo "Nova.exe absent : lancez d'abord la compilation release."; exit 1; }

echo "==> Empreinte du binaire"
sha256sum Nova.exe > Nova.exe.sha256
cat Nova.exe.sha256

echo "==> Préparation de /tmp/${NAME}"
rm -rf "$STAGE"
mkdir -p "$STAGE/sources/src" "$STAGE/sources/assets/ui" "$STAGE/sources/assets/engines" \
         "$STAGE/sources/native" "$STAGE/sources/tools/fixtures"

cp Nova.exe Nova.exe.sha256 LISEZMOI.txt README.md README-DEV.md RAPPORT-AUDIT.md \
   LICENSE LICENCES-TIERS.md "$STAGE/"

# Sources du programme
cp Cargo.toml Cargo.lock build.rs "$STAGE/sources/"
cp src/*.rs "$STAGE/sources/src/"
cp assets/ui/*.html assets/ui/*.js "$STAGE/sources/assets/ui/"
# Ressources embarquées dans le binaire : indispensables pour recompiler.
cp assets/trackers.txt "$STAGE/sources/assets/"
cp assets/engines/*.png "$STAGE/sources/assets/engines/"
cp assets/nova.ico assets/nova-logo.png assets/nova-64.rgba "$STAGE/sources/assets/"
cp native/*.c native/*.h "$STAGE/sources/native/"
cp tools/make_icon.py "$STAGE/sources/tools/" 2>/dev/null || true
cp tools/fetch_engine_icons.py "$STAGE/sources/tools/" 2>/dev/null || true
cp tools/sources_zip.sh "$STAGE/sources/tools/" 2>/dev/null || true

# Scripts de test et de contrôle visuel (+ jeu de données d'import)
cp tools/*.py tools/*.c tools/*.sh "$STAGE/sources/tools/"
cp tools/fixtures/* "$STAGE/sources/tools/fixtures/"

echo "==> Archive"
rm -f "/home/user/${NAME}.zip"
(cd /tmp && zip -qr9 "/home/user/${NAME}.zip" "$NAME")

FILES=$(find "$STAGE" -type f | wc -l)
SIZE=$(stat -c%s "/home/user/${NAME}.zip")
echo
echo "${NAME}.zip : ${SIZE} octets, ${FILES} fichiers"
echo "Contenu :"
(cd "$STAGE" && find . -type f | sort | sed 's|^\./|  |')
