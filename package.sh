#!/bin/sh
# Assemble release metadata into GameData/GatewayTech and zip a release.
set -e
cd "$(dirname "$0")"
VERSION=${1:-1.0.0}
MAJ=$(echo "$VERSION" | cut -d. -f1); MIN=$(echo "$VERSION" | cut -d. -f2); PAT=$(echo "$VERSION" | cut -d. -f3)
D=GameData/GatewayTech
cat > "$D/GatewayTech.version" <<V
{
  "NAME": "GatewayTech",
  "URL": "https://raw.githubusercontent.com/lsamman/GatewayTech/main/GameData/GatewayTech/GatewayTech.version",
  "DOWNLOAD": "https://github.com/lsamman/GatewayTech/releases",
  "VERSION": { "MAJOR": $MAJ, "MINOR": $MIN, "PATCH": $PAT, "BUILD": 0 },
  "KSP_VERSION": { "MAJOR": 1, "MINOR": 12, "PATCH": 5 },
  "KSP_VERSION_MIN": { "MAJOR": 1, "MINOR": 12, "PATCH": 0 },
  "KSP_VERSION_MAX": { "MAJOR": 1, "MINOR": 12, "PATCH": 99 }
}
V
cp LICENSE "$D/LICENSE.txt"
cp LICENSE-ASSETS.txt "$D/LICENSE-ASSETS.txt"
cp README.md "$D/README.md"
mkdir -p release
rm -f "release/GatewayTech-$VERSION.zip"
zip -qr "release/GatewayTech-$VERSION.zip" GameData README.md LICENSE LICENSE-ASSETS.txt
echo "release/GatewayTech-$VERSION.zip"
