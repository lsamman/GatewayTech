#!/bin/sh
# Rebuild every GatewayTech part from src/gateway_source.blend and assemble GameData/GatewayTech.
set -e
cd "$(dirname "$0")"
B="$HOME/Applications/blender-3.6/blender"
mkdir -p build/mu
# Emissive window maps must exist before the parts are built: gt_lib.material() switches to the emissive shader only when build/tex/<mat>_emit.dds is present.
python3 -I scripts/emit.py build/tex_src build/tex
for s in halo ihab airlock esprit ppe rosa; do
    "$B" -b src/gateway_source.blend --python-exit-code 1 -P scripts/build_$s.py -- build/mu 2>&1 | grep -E "plate|antenna|wing|airlock|EXPORT|Error|rror" || true
done
for r in ihab airlock; do
    "$B" -b src/gateway_source.blend --python-exit-code 1 -P scripts/build_radiator.py -- build/mu $r 2>&1 | grep -E "panels|Error|rror" || true
done
"$B" -b src/gateway_source.blend --python-exit-code 1 -P scripts/build_arms.py -- build/mu big 2>&1 | grep -E "best|Error" || true
"$B" -b src/gateway_source.blend --python-exit-code 1 -P scripts/build_arms.py -- build/mu small 2>&1 | grep -E "best|Error" || true
python3 -I scripts/make_cfgs.py build/mu build/tex GameData/GatewayTech
