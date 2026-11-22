"""Convert extracted glTF PBR textures into KSP/Bumped Specular maps (DDS).

  <mat>_diff.dds : RGB = base colour (metal darkened slightly), A = gloss (1 - roughness)   DXT5
  <mat>_nrm.dds  : DXT5nm (R=1, G=Y, B=Y, A=X)                                            DXT5
Every map then gets the Bluedog-style look pass (scripts/bdb_look.py): normals scaled to an
A-channel std of NORMAL_STD, relief softened to the crease target, broad occlusion and grime;
texels lit in <mat>_emit.dds (out dir, else build/tex) are left alone.
usage: python3 -I textures.py <tex_src dir> <out dir> [mat ...]     (mats: default all)
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdb_look

src, out = sys.argv[1], sys.argv[2]
ONLY = set(sys.argv[3:])
os.makedirs(out, exist_ok=True)
tmp = os.path.join(out, '_png'); os.makedirs(tmp, exist_ok=True)

def to_dds(img, name, cover=None):
    png = os.path.join(tmp, name + '.png')
    img.save(png)
    # KSP reads DDS bottom-up relative to PNG, so flip; full mip chain built by bdb_look.write_dds
    # (straight box filter: ImageMagick's own weights colour by alpha = gloss / normal X), after
    # the gutters are padded out from the UV islands (`cover`) so mips 2-4 keep island colours
    bdb_look.write_dds(np.asarray(img.convert('RGBA')), os.path.join(out, name + '.dds'), cover)

def load(name):
    p = os.path.join(src, name + '.png')
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.float32) / 255 if os.path.exists(p) else None

mats = sorted({f.rsplit('_', 1)[0] for f in os.listdir(src) if f.endswith('_BaseColor.png')})
mats = [m for m in mats if not ONLY or m in ONLY]
# Calibrated to HabTech2's own maps (its white USOS panels: diffuse p90 ~0.78, gloss mean ~0.3)
# so Gateway parts sit next to HabTech parts under the same stock KSP/Bumped Specular shader.
TARGET_P90 = 0.78
NORMAL_GAIN = 1.0      # the model's own normal map as authored (was 1.5; Bluedog-style softer relief)
DETAIL_GAIN = 1.1      # relief derived from the colour map (panel seams, rivets, MLI creases)
CAVITY_GAIN = 0.20     # darken grooves / lighten edges from normal-map curvature
GLOSS_CAVITY = 0.30    # the same curvature's pull on gloss (the pre-Bluedog CAVITY_GAIN, unchanged)
NORMAL_STD = 0.10      # DXT5nm A-channel std after the look pass (Bluedog .09-.11)
NORMAL_MAX_UP = 1.6    # maps whose own relief is softer are scaled up to NORMAL_STD, at most this much
UVDUMP = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), 'uvdump.json')
EMIT_DIRS = (out, os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), 'tex'))


def blur(a, r):
    """Separable Gaussian blur of a float image (H, W), edge-clamped."""
    k = np.arange(-int(3 * r + 1), int(3 * r + 1) + 1)
    w = np.exp(-(k * k) / (2 * r * r)); w /= w.sum()
    pad = len(k) // 2
    out = np.pad(a, ((0, 0), (pad, pad)), mode='edge')
    out = sum(wi * out[:, i:i + a.shape[1]] for i, wi in enumerate(w))
    out = np.pad(out, ((pad, pad), (0, 0)), mode='edge')
    return sum(wi * out[i:i + a.shape[0], :] for i, wi in enumerate(w)).astype(np.float32)


TEXMAP = {'iHab_main': 'iHAB_main', 'iHab_aux': 'iHAB_aux', 'PPE_aux': 'PPE_array'}


def coverage_masks(uvdump, size):
    """Per-texture mask of texels actually covered by UV islands (from scripts/uvdump.py)."""
    import json
    from PIL import ImageDraw
    d = json.load(open(uvdump))
    ims = {}
    for obj in d.values():
        uv = np.array(obj['uv']).reshape(-1, 2)
        for ls, lt, mat in zip(obj['ls'], obj['lt'], obj['mat']):
            t = TEXMAP.get(mat.split('.')[0], mat.split('.')[0])
            im = ims.setdefault(t, Image.new('L', (size, size), 0))
            q = uv[ls:ls + lt] - np.floor(uv[ls:ls + lt].min(0))      # UDIM-style tiles (u 1..2) wrap to 0..1
            pts = [(float(a * size), float((1 - b) * size)) for a, b in q]
            ImageDraw.Draw(im).polygon(pts, fill=255)
    from PIL import ImageFilter
    return {t: np.asarray(im.filter(ImageFilter.MaxFilter(5)), np.float32) / 255 for t, im in ims.items()}


def blur_m(a, m, r):
    """Blur restricted to the mask (normalised convolution) so gutters don't bleed in."""
    return blur(a * m, r) / np.maximum(blur(m, r), 1e-4)


def grad(a):
    """d/du (columns) and d/dv (v increases upward = -rows)."""
    gu = np.zeros_like(a); gv = np.zeros_like(a)
    gu[:, 1:-1] = (a[:, 2:] - a[:, :-2]) / 2
    gv[1:-1, :] = -(a[2:, :] - a[:-2, :]) / 2
    return gu, gv


MASKS = coverage_masks(UVDUMP, 1024) if os.path.exists(UVDUMP) else {}
print('coverage masks:', sorted(MASKS))
for m in mats:
    base = load(f'{m}_BaseColor'); mr = load(f'{m}_Metallic'); nrm = load(f'{m}_Normal')
    metal = mr[..., 2] if mr is not None else np.zeros(base.shape[:2])
    rough = mr[..., 1] if mr is not None else np.full(base.shape[:2], 0.6)
    lum = base[..., :3] @ np.array([0.299, 0.587, 0.114])

    # --- normal map: model normals (strengthened) + detail from colour high-pass ---
    if nrm is not None:
        nx = (nrm[..., 0] * 2 - 1) * NORMAL_GAIN
        ny = (nrm[..., 1] * 2 - 1) * NORMAL_GAIN
    else:
        nx = np.zeros_like(lum); ny = np.zeros_like(lum)
    M = MASKS.get(m, np.ones_like(lum))
    if M.shape != lum.shape:
        M = np.asarray(Image.fromarray((M * 255).astype(np.uint8)).resize(lum.shape[::-1]), np.float32) / 255
    height = (lum - blur_m(lum, M, 2.5)) * M             # fine relief only, inside UV islands
    hu, hv = grad(blur_m(height, M, 0.7))
    hu *= M; hv *= M
    nx = nx - hu * DETAIL_GAIN
    ny = ny - hv * DETAIL_GAIN
    l2 = nx * nx + ny * ny
    over = l2 > 0.85
    sc = np.where(over, np.sqrt(0.85 / np.maximum(l2, 1e-6)), 1.0)
    nx *= sc; ny *= sc
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))

    # --- cavity from curvature of the final normal field ---
    du, _ = grad(nx); _, dv = grad(ny)
    curv = du + dv                                      # >0 convex edge, <0 groove
    curv *= M
    cav = blur_m(curv, M, 1.0) * 5 + blur_m(curv, M, 3.0) * 6
    cav = np.clip(cav, -1, 1) * M
    shade = 1 + CAVITY_GAIN * np.where(cav < 0, cav, cav * 0.35)

    # no reflections in stock: tone dark/bare metal down, but keep white-painted metal white
    rgb = base[..., :3] * (1 - 0.45 * (metal * (1 - lum))[..., None])
    rgb = rgb * shade[..., None]
    p90 = np.percentile(rgb.mean(-1), 90)
    if p90 > TARGET_P90:
        rgb = rgb * (TARGET_P90 / p90)
    # gloss keeps the cavity modulation it was calibrated with (GLOSS_CAVITY), so the softer
    # CAVITY_GAIN changes the diffuse only: gloss already matches Bluedog
    gshade = 1 + GLOSS_CAVITY * np.where(cav < 0, cav, cav * 0.35)
    gloss = (1 - rough) * (0.38 + 0.30 * metal) * np.clip(gshade, 0.6, 1.1)
    # gutters take the nearest island texels (colour, gloss, normal) before the look pass, so its
    # targets are solved on what ships and mips 2-4 never blend gutter filler into the islands
    PAD = M if m in MASKS else None
    if PAD is not None:
        g = bdb_look.pad_gutters(np.dstack([rgb, gloss, nx, ny]), PAD > .5)
        rgb, gloss, nx, ny = g[..., :3], g[..., 3], g[..., 4], g[..., 5]
    # Bluedog-style look pass, the same core bdb_look.py applies to the committed DDS
    emit = next((bdb_look.read_dds(p)[..., :3] for p in (os.path.join(d, f'{m}_emit.dds') for d in EMIT_DIRS)
                 if os.path.exists(p)), None)
    rgb, info = bdb_look.look(np.clip(rgb, 0, 1), nx, ny, M if m in MASKS else None, emit)
    nsc = float(np.clip(NORMAL_STD / max(float((nx * .5).std()), 1e-6), 0, NORMAL_MAX_UP))
    nx = nx * nsc; ny = ny * nsc                        # A-channel std onto NORMAL_STD (up or down)
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    diff = np.dstack([np.clip(rgb, 0, 1), np.clip(gloss, 0, 1)])
    to_dds(Image.fromarray((diff * 255 + 0.5).astype(np.uint8), 'RGBA'), f'{m}_diff')   # padded above

    n = np.empty(base.shape[:2] + (4,), np.float32)
    n[..., 0] = 1; n[..., 1] = ny * 0.5 + 0.5; n[..., 2] = n[..., 1]; n[..., 3] = nx * 0.5 + 0.5
    to_dds(Image.fromarray((n * 255 + 0.5).astype(np.uint8), 'RGBA'), f'{m}_nrm')
    # previews for inspection
    Image.fromarray((np.dstack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz]) * 255).astype(np.uint8)).save(os.path.join(tmp, f'{m}_nrm_preview.png'))
    print(f'converted {m}: diffuse p90 {np.percentile(diff[...,:3].mean(-1),90):.2f}, gloss mean {diff[...,3].mean():.2f}, cavity range {shade.min():.2f}..{shade.max():.2f}, '
          f'look: relief kept {info["g"]:.2f}, crease {info["crease"]:.3f}, normals x{nsc:.2f}' + (', emissive masked' if emit is not None else ''))

# Shared mounting-plate texture for the flat faces left where docking ports were removed.
S = 512
img = Image.new('RGBA', (S, S), (206, 208, 210, 90)); d = ImageDraw.Draw(img)
c = S / 2
for r, col in ((0.98, (150, 152, 155, 140)), (0.93, (214, 216, 218, 90)), (0.62, (186, 188, 191, 120)), (0.58, (222, 223, 225, 80))):
    d.ellipse([c - r * c, c - r * c, c + r * c, c + r * c], fill=col)
import math
for k in range(24):  # bolt ring
    a = 2 * math.pi * k / 24; x, y = c + 0.80 * c * math.cos(a), c + 0.80 * c * math.sin(a)
    d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(120, 122, 126, 200))
to_dds(img, 'gt_plate_diff')
flat = Image.new('RGBA', (64, 64), (255, 128, 128, 128)); to_dds(flat, 'gt_flat_nrm')
white = Image.new('RGBA', (64, 64), (225, 225, 225, 70)); to_dds(white, 'gt_white_diff')
