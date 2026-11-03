#!/bin/sh
# Copy GameData/GatewayTech into the Sol KSP install.
set -e
cd "$(dirname "$0")"
DEST="$HOME/.local/share/Steam/steamapps/common/Kerbal Space Program Modded SOL/GameData/GatewayTech"
mkdir -p "$DEST"
cp -a GameData/GatewayTech/. "$DEST/"
echo "deployed to $DEST"
