#!/usr/bin/env bash
# Construit l'archive des **sources seules** de Nova.
#
#   bash tools/sources_zip.sh        # -> Nova-<version>-sources.zip
#
# Contenu : tout ce qui est nécessaire pour recompiler Nova et comprendre le
# projet — sources Rust et C, interface, ressources embarquées, scripts de test,
# documentation, licences. Ni binaire, ni capture d'écran.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(grep -m1 '^version' Cargo.toml | cut -d'"' -f2)"
NAME="Nova-${VERSION}-sources"
STAGE="/tmp/${NAME}"

echo "==> Préparation de /tmp/${NAME}"
rm -rf "$STAGE"
mkdir -p "$STAGE"/{src,native,assets/ui,assets/engines,tools/fixtures,doc}

# Programme
cp Cargo.toml Cargo.lock build.rs "$STAGE/"
cp src/*.rs "$STAGE/src/"
cp native/*.c native/*.h "$STAGE/native/"

# Ressources embarquées dans le binaire
cp assets/ui/*.html assets/ui/*.js "$STAGE/assets/ui/"
cp assets/trackers.txt "$STAGE/assets/"
cp assets/engines/*.png "$STAGE/assets/engines/"
cp assets/nova.ico assets/nova-logo.png assets/nova-64.rgba "$STAGE/assets/"

# Outils de construction, de test et de contrôle visuel
cp tools/*.py tools/*.c tools/*.sh "$STAGE/tools/"
cp tools/fixtures/* "$STAGE/tools/fixtures/"

# Documentation et licences
cp README-DEV.md README.md LISEZMOI.txt LICENSE LICENCES-TIERS.md "$STAGE/"
cp RAPPORT-AUDIT.md "$STAGE/doc/"
cp audit_ui/NOUVEAUTES-*.png audit_ui/LOGOS-MOTEURS.png "$STAGE/doc/" 2>/dev/null || true

# Fichier de présentation à la racine de l'archive
cat > "$STAGE/LIRE-MOI.txt" <<TXT
Nova ${VERSION} — sources

* README-DEV.md    présentation du projet : fonctions, architecture, compilation, tests
* LICENSE          licence MIT du code
* LICENCES-TIERS.md marques et logos des moteurs, licences des composants tiers
* doc/             rapport d'audit complet (13 passes) et planches d'écrans
* src/  native/    sources Rust et module C
* assets/          interface, logos des moteurs, liste de filtrage, icônes
* tools/           scripts de compilation, de test et de contrôle visuel

Recompiler :

    cargo test                                   # 29 tests unitaires
    cargo build --release                        # Windows (chaîne MSVC)
    # ou, depuis Linux :
    bash tools/install_chain.sh
    cargo xwin build --release --target x86_64-pc-windows-msvc
    bash tools/package.sh
TXT

echo "==> Archive"
rm -f "/home/user/${NAME}.zip"
(cd /tmp && zip -qr9 "/home/user/${NAME}.zip" "$NAME")

FILES=$(find "$STAGE" -type f | wc -l)
SIZE=$(stat -c%s "/home/user/${NAME}.zip")
echo
echo "${NAME}.zip : ${SIZE} octets, ${FILES} fichiers"
