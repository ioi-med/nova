#!/usr/bin/env bash
# Réinstalle entièrement la chaîne de compilation après une réinitialisation de
# la sandbox : Rust + cible Windows, cargo-xwin, clang/lld, mingw, les paquets
# système attendus par wry (webkit/libsoup) et chromium pour les captures.
#
#   bash tools/install_chain.sh        # marqueur CHAIN_READY à la fin
set -u
export RUSTUP_HOME=/home/user/.cache/rustup
export CARGO_HOME=/home/user/.cache/cargo
export PATH="/home/user/.cache/cargo/bin:$PATH"
export DEBIAN_FRONTEND=noninteractive
step() { echo "=== $*"; }

step "swap 4 Go"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap -q /swapfile && sudo swapon /swapfile
fi
swapon --show

step "paquets système"
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends \
  build-essential pkg-config libssl-dev curl ca-certificates git zip unzip \
  libwebkit2gtk-4.1-dev libsoup-3.0-dev libjavascriptcoregtk-4.1-dev \
  libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev clang lld llvm \
  gcc-mingw-w64-x86-64 chromium 2>&1 | tail -5

# clang-19/lld-19 (noms versionnés attendus par cargo-xwin)
llvm_ver="$(clang --version | head -1 | grep -oE '[0-9]+' | head -1)"
for bin in clang clang++ lld lld-link llvm-lib llvm-rc llvm-dlltool; do
  if [ -x "/usr/bin/${bin}-${llvm_ver}" ] && [ ! -e "/usr/local/bin/${bin}" ]; then
    sudo ln -sf "/usr/bin/${bin}-${llvm_ver}" "/usr/local/bin/${bin}"
  fi
done

step "rustup + cible Windows"
if [ ! -x "$CARGO_HOME/bin/rustup" ]; then
  curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable --no-modify-path
fi
rustup target add x86_64-pc-windows-msvc
rustup component add clippy

step "cargo-xwin"
cargo install cargo-xwin --locked 2>&1 | tail -3

step "versions"
rustc --version; cargo --version; cargo xwin --help >/dev/null && echo "cargo-xwin OK"
which clang lld chromium || true

echo "CHAIN_READY"
