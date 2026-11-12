"""Emissive window maps for KSP/Emissive/Bumped Specular.

  <mat>_emit.dds : RGB = warm white on window-glass texels, black elsewhere        DXT1
Glass in the glTF source is the blue, near-mirror (roughness < .2) material, which only
the ESPRIT windows and the HALO camera-lamp lenses use; I-Hab and the Airlock have none.
ModuleColorChanger (_EmissiveColor, default 0,0,0) switches them on in game.
gt_lib.material() gives a material the emissive shader when <tex>_emit.dds exists here.
usage: python3 -I emit.py <tex_src dir> <out dir>
"""
import os, subprocess, sys
import numpy as np
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
tmp = os.path.join(out, '_png'); os.makedirs(tmp, exist_ok=True)

MATS = ['HALO_main', 'iHAB_main', 'iHAB_aux', 'ERMXL_main', 'ERMXL_aux', 'ALM_main', 'ALM_aux']
WARM = np.array([255, 244, 224], np.uint8)
MIN_TEXELS = 16          # fewer than this: no emit map, material keeps the plain shader


def to_dds(img, name):
    png = os.path.join(tmp, name + '.png')
    img.save(png)
    # same conventions as textures.py: flip for KSP, full mip chain; DXT1 (no alpha needed)
    subprocess.run(['magick', png, '-flip', '-define', 'dds:compression=dxt1',
                    '-define', 'dds:cluster-fit=true', os.path.join(out, name + '.dds')], check=True)


def load(name):
    return np.asarray(Image.open(os.path.join(src, name + '.png')).convert('RGB')).astype(np.float32) / 255


def neighbours(m):
    p = np.pad(m.astype(np.int32), 1)
    return sum(p[1 + dy:p.shape[0] - 1 + dy, 1 + dx:p.shape[1] - 1 + dx]
               for dy in (-1, 0, 1) for dx in (-1, 0, 1))


for m in MATS:
    base = load(f'{m}_BaseColor'); rough = load(f'{m}_Metallic')[..., 1]
    r, g, b = base[..., 0], base[..., 1], base[..., 2]
    glass = (b - r > 0.08) & (b >= g) & (rough < 0.2)
    glass &= neighbours(glass) >= 5            # drop stray texels (noise in MLI/paint)
    n = int(glass.sum())
    stale = os.path.join(out, f'{m}_emit.dds')
    if n < MIN_TEXELS:
        if os.path.exists(stale):
            os.remove(stale)
        print(f'{m}: {n} window texels, no emit map')
        continue
    img = np.zeros(base.shape[:2] + (3,), np.uint8)
    img[glass] = WARM
    to_dds(Image.fromarray(img, 'RGB'), f'{m}_emit')
    print(f'{m}: {n} window texels -> {m}_emit.dds')
