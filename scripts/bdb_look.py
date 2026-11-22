"""Bluedog-style look pass for hull maps (KSP/Bumped Specular, DXT5 _diff + DXT5nm _nrm).

Softens sharp fine-grain creases, multiplies in broad mid-frequency occlusion (blurred
curvature + UV-island-edge darkening), faint grime and edge highlights, while keeping the
white point (paint p90), hue neutrality, gloss-in-alpha, the KSP vertical flip, the DXT5nm
layout and the full mip chain. Shadows are never pushed darker than the input's paint p10.

usage:
  python3 -I bdb_look.py --check <name>_diff.dds [...]            # targets table per map
  python3 -I bdb_look.py --check new_diff.dds --ref old_diff.dds   # same, with before/after deltas
  python3 -I bdb_look.py --roundtrip <map>.dds [...]               # DXT5 recompression loss
  blender -b -P bdb_look.py -- --dump-uv OUT.json part.mu [...]    # uvdump from KSP .mu files
                                                                   # (needs io_object_mu)
  python3 -I bdb_look.py <name>_diff.dds [...] -o OUTDIR [options] # process (DDS -> DDS)
options:
  --keep-normals      (--check) normal std must stay as it was instead of landing in .09-.11
  --nstd .10          scale the sibling <name>_nrm.dds X/Y toward this A-channel std (never up);
                      omit to leave the normal map untouched (ShabTech)
  --crease -.05       crease-contrast target (p5 of paint luma - 19x19 box mean); the paint
                      relief is soft-knee compressed until it is met, its lost darkness given
                      back as wide shading
  --occ .12           broad-occlusion strength (8-15 %)   --isl .06 island-edge darkening
  --grime .04         grey low-frequency noise            --edge .02 convex-edge highlights
  --uvdump FILE       build/uvdump.json (GatewayTech: scripts/uvdump.py; ShabTech: --dump-uv):
                      coverage mask -> island-edge darkening, noise faded at island edges
  --measure-cover     measure the targets on UV-covered paint only (process and --check);
                      for atlases with large unused filler (ShabTech)
  --uvmat NAME        material key in the uvdump (default: map name, via TEXMAP)
  --emit FILE|auto    emissive map; lit texels are left untouched ('auto': the sibling
                      <name>_emit.dds, when there is one)
  --wrap              treat the atlas as periodic in X (ShabTech lathe strips)
The `nrm` sibling is found as <name>_nrm.dds next to the diffuse. Images are handled in PNG
orientation (top row = v 1); DDS rows are flipped on read and on write, as the generators do.

Importable core (float32 arrays in PNG orientation, rgb in 0..1, nx/ny in -1..1):
  metrics(rgb, gloss, nrm_a=None) -> dict      look(rgb, nx, ny, cover, emit, **kw) -> (rgb, info)
  scale_normal(nx, ny, target_std) -> (nx, ny, s)   read_dds(path) / write_dds(uint8 RGBA, path)
"""
import os, sys, shutil, subprocess, tempfile
import numpy as np
try:
    from PIL import Image
except ImportError:          # Blender's Python (only the --dump-uv mode runs there)
    Image = None

# --- targets (Bluedog OWS / MOL, measured on paint: luma > .45, saturation < .12) -------------
# goal: 'range' = must land in the range; 'keep' = must not move from the input (spec: white point,
# neutrality and gloss already match Bluedog), checked against --ref, else against the range.
TARGETS = {          # Bluedog value, range, goal, tolerance for 'keep'
    'paint p10': (.49, None, 'info', 0), 'paint p50': (.76, None, 'info', 0),
    'paint p90': (.78, (.76, .81), 'keep', .01),
    'crease contrast': (-.05, (-.06, -.04), 'range', 0),
    'warmth R-B': (0.0, (-.02, .02), 'keep', .005),
    'normal std': (.10, (.09, .11), 'range', 0),
    'gloss p50': (.315, (.28, .35), 'keep', .01),
}
LUMA = np.array([.299, .587, .114], np.float32)
TEXMAP = {'iHab_main': 'iHAB_main', 'iHab_aux': 'iHAB_aux', 'PPE_aux': 'PPE_array'}


# --- DDS I/O --------------------------------------------------------------------------------
def read_dds(path):
    """DXT5 DDS -> float32 RGBA (H, W, 4) in PNG orientation (undoes the generators' -flip)."""
    a = np.asarray(Image.open(path).convert('RGBA'), np.float32) / 255
    return np.ascontiguousarray(a[::-1])


def _encoder():
    for exe in ('magick', 'convert'):
        if shutil.which(exe):
            return exe
    raise SystemExit('ImageMagick (magick / convert) not found')


def pad_gutters(a, cover, radius=32):
    """Fill the texels outside the UV islands (cover False) from the nearest covered texels, so
    mips never blend neighbouring islands or gutter filler into an island's edge: `radius`
    one-texel rings averaged from covered/filled neighbours, then a push-pull fill of the rest.
    a: float (H, W, C); returns a new array (covered texels unchanged)."""
    a = a.astype(np.float32).copy()
    known = np.asarray(cover, bool).copy()
    if known.all() or not known.any():
        return a
    a[~known] = 0
    for _ in range(radius):
        kp = np.pad(known, 1).astype(np.float32); ap = np.pad(a * known[..., None], ((1, 1), (1, 1), (0, 0)))
        h, w = known.shape
        cnt = sum(kp[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        tot = sum(ap[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        new = ~known & (cnt > 0)
        if not new.any():
            break
        a[new] = tot[new] / cnt[new][:, None]
        known |= new
    if not known.all():                            # push-pull: coarser levels fill what is left
        lv = [(a * known[..., None], known.astype(np.float32))]
        while min(lv[-1][1].shape) > 1:
            v, k = lv[-1]
            h2, w2 = k.shape[0] // 2, k.shape[1] // 2
            v = v[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, -1).sum((1, 3))
            k = k[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3))
            lv.append((v, k))
        fill = lv[-1][0] / np.maximum(lv[-1][1], 1e-6)[..., None]
        for v, k in reversed(lv[:-1]):
            up = np.repeat(np.repeat(fill, 2, 0), 2, 1)
            up = np.pad(up, ((0, k.shape[0] - up.shape[0]), (0, k.shape[1] - up.shape[1]), (0, 0)), mode='edge')
            fill = np.where((k > 0)[..., None], v / np.maximum(k, 1e-6)[..., None], up)
        a[~known] = fill[~known]
    return a


def mip_chain(a):
    """Box-filtered mip levels of a float (H, W, C) image, every channel on its own (straight,
    not alpha-weighted: ImageMagick's own chain premultiplies by alpha, which here is gloss or
    normal X, and turns every zero-gloss texel black from mip 1 on)."""
    out = [a]
    while max(a.shape[:2]) > 1:
        h, w = max(a.shape[0] // 2, 1), max(a.shape[1] // 2, 1)
        b = a
        if b.shape[0] > 1:
            b = (b[0:h * 2:2] + b[1:h * 2:2]) / 2
        if b.shape[1] > 1:
            b = (b[:, 0:w * 2:2] + b[:, 1:w * 2:2]) / 2
        a = b; out.append(a)
    return out


def write_dds(arr, path, cover=None, compression='dxt5'):
    """uint8 RGBA/RGB (PNG orientation) -> DDS (DXT5 default), flipped for KSP, full mip chain built
    here (straight box filter, see mip_chain) after padding the gutters from the islands when a
    coverage mask is given."""
    f = arr.astype(np.float32)
    if cover is not None:
        if cover.shape != f.shape[:2]:
            cover = np.asarray(Image.fromarray(to_u8(cover)).resize(f.shape[1::-1]), np.float32) / 255
        f = pad_gutters(f, cover > .5)
    mode = 'RGBA' if f.shape[2] == 4 else 'RGB'
    with tempfile.TemporaryDirectory() as td:
        files = []
        for k, lv in enumerate(mip_chain(f)):
            png = os.path.join(td, f'm{k:02d}.png')
            Image.fromarray(np.ascontiguousarray((np.clip(lv, 0, 255) + .5).astype(np.uint8)[::-1]), mode).save(png, compress_level=1)
            files.append(png)
        subprocess.run([_encoder(), *files, '-define', f'dds:compression={compression}',
                        '-define', 'dds:cluster-fit=true', '-define', 'dds:mipmaps=fromlist', path], check=True)


def dds_mips(path):
    with open(path, 'rb') as f:
        h = f.read(32)
    return int.from_bytes(h[28:32], 'little')


def psnr(a, b):
    mse = float(((a.astype(np.float64) - b) ** 2).mean())
    return float('inf') if mse == 0 else 10 * np.log10(1 / mse)


def roundtrip(path):
    """DXT5 generation loss: decode -> re-encode (same settings) -> decode, per channel group."""
    a = read_dds(path)
    with tempfile.TemporaryDirectory() as td:
        q = os.path.join(td, 'rt.dds'); write_dds(to_u8(a), q); b = read_dds(q)
    nrm = path.endswith('_nrm.dds')
    groups = {'G,A (normal X/Y)': [1, 3]} if nrm else {'RGB': [0, 1, 2], 'A (gloss)': [3]}
    return {k: (psnr(a[..., c], b[..., c]), float(np.abs(a[..., c] - b[..., c]).mean() * 255),
                float(np.abs(a[..., c] - b[..., c]).max() * 255)) for k, c in groups.items()}


def to_u8(a):
    return (np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)


# --- filters --------------------------------------------------------------------------------
def gblur(a, sigma):
    """Periodic Gaussian blur via FFT (sigma in px)."""
    if sigma <= 0:
        return a
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape).astype(np.float32)


def blur(a, sigma, wrap=False):
    """Gaussian blur; edge-clamped unless wrap (padding then FFT)."""
    if wrap:
        return gblur(a, sigma)
    p = int(3 * sigma + 2)
    return gblur(np.pad(a, p, mode='edge'), sigma)[p:-p, p:-p]


def blur_m(a, m, sigma, wrap=False):
    """Blur restricted to mask m (normalised convolution): nothing bleeds in from outside."""
    return blur(a * m, sigma, wrap) / np.maximum(blur(m, sigma, wrap), 1e-4)


def box(a, r):
    """Mean over a (2r+1)^2 window, edge-clamped (the crease-contrast reference blur)."""
    k = 2 * r + 1
    c = np.pad(np.pad(a.astype(np.float64), r, mode='edge').cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def grad(a):
    """d/du (columns) and d/dv (v up = -rows), as textures.py."""
    gu = np.zeros_like(a); gv = np.zeros_like(a)
    gu[:, 1:-1] = (a[:, 2:] - a[:, :-2]) / 2
    gv[1:-1, :] = -(a[2:, :] - a[:-2, :]) / 2
    return gu, gv


# --- measurement ----------------------------------------------------------------------------
def paint_mask(rgb):
    l = rgb @ LUMA
    mx = rgb.max(-1); mn = rgb.min(-1)
    return (l > .45) & ((mx - mn) / np.maximum(mx, 1e-6) < .12)


def metrics(rgb, gloss, nrm_a=None, cover=None):
    l = rgb @ LUMA
    P = paint_mask(rgb)
    if cover is not None:
        P &= cover > .5
    p10, p50, p90 = np.percentile(l[P], [10, 50, 90])
    m = {'paint p10': p10, 'paint p50': p50, 'paint p90': p90,
         'crease contrast': np.percentile((l - box(l, 9))[P], 5),
         'warmth R-B': float((rgb[..., 0] - rgb[..., 2])[P].mean()),
         'normal std': float(nrm_a.std()) if nrm_a is not None else float('nan'),
         'gloss p50': float(np.percentile(gloss[P], 50)), 'paint frac': float(P.mean())}
    return {k: float(v) for k, v in m.items()}


def map_name(diff_path):
    return os.path.basename(diff_path)[:-len('_diff.dds')]


def map_metrics(diff_path, uvdump=None):
    """Targets for one map; with a uvdump, measured on UV-covered paint only."""
    d = read_dds(diff_path)
    n = sibling_nrm(diff_path)
    a = read_dds(n)[..., 3] if n else None
    cover = coverage_mask(uvdump, map_name(diff_path), d.shape[0]) if uvdump else None
    return metrics(d[..., :3], d[..., 3], a, cover)


def sibling_nrm(diff_path):
    p = diff_path.replace('_diff.dds', '_nrm.dds')
    return p if p != diff_path and os.path.exists(p) else None


def check_table(name, m, ref=None, nstd_goal=True):
    """Targets table for one map. With nstd_goal False (ShabTech) the normal std is 'keep'."""
    rows = ['', f'== {name}  (paint {m["paint frac"]*100:.0f}% of texels)',
            f'{"metric":<16}{"Bluedog":>8}{"range":>13}{"goal":>6}'
            + (f'{"before":>8}{"after":>8}{"delta":>8}' if ref else f'{"map":>8}') + '  status']
    for k, (tgt, rng, goal, tol) in TARGETS.items():
        v = m[k]
        if k == 'normal std' and not nstd_goal:
            goal, tol = 'keep', .002
        inr = rng is not None and not np.isnan(v) and rng[0] <= v <= rng[1]
        if goal == 'info' or np.isnan(v):
            st = 'info' if goal == 'info' else 'n/a'
        elif goal == 'range' or ref is None:
            st = 'ok' if inr else ('LOW' if v < rng[0] else 'HIGH')
            if goal == 'keep':
                st += ' (vs Bluedog; no --ref)'
        else:
            st = ('ok (unchanged)' if abs(v - ref[k]) <= tol else 'MOVED') + ('' if inr else ', outside Bluedog range as before')
        rs = f'{rng[0]:+.2f}..{rng[1]:+.2f}' if rng else ''
        line = f'{k:<16}{tgt:>+8.3f}{rs:>13}{goal:>6}'
        line += f'{ref[k]:>+8.3f}{v:>+8.3f}{v - ref[k]:>+8.3f}' if ref else f'{v:>+8.3f}'
        rows.append(line + '  ' + st)
    return '\n'.join(rows)


# --- masks ----------------------------------------------------------------------------------
def coverage_mask(uvdump, key, size):
    """Texels covered by UV islands of material `key` (GatewayTech scripts/uvdump.py output)."""
    import json
    from PIL import ImageDraw, ImageFilter
    im = Image.new('L', (size, size), 0); dr = ImageDraw.Draw(im); n = 0
    for obj in json.load(open(uvdump)).values():
        uv = np.array(obj['uv']).reshape(-1, 2)
        for ls, lt, mat in zip(obj['ls'], obj['lt'], obj['mat']):
            t = mat.split('.')[0]
            if TEXMAP.get(t, t) != key:
                continue
            q = uv[ls:ls + lt] - np.floor(uv[ls:ls + lt].min(0))
            dr.polygon([(float(a * size), float((1 - b) * size)) for a, b in q], fill=255); n += 1
    if not n:
        return None
    return np.asarray(im.filter(ImageFilter.MaxFilter(5)), np.float32) / 255


def fbm_noise(h, w, seed, wrap):
    """Low-frequency grey noise, zero mean, about unit amplitude (p99 of |n| = 1)."""
    r = np.random.default_rng(seed)
    s = max(h, w)
    n = sum(blur(r.standard_normal((h, w)).astype(np.float32), s / f, wrap) * a
            for f, a in ((14, 1.0), (32, .5), (80, .25)))
    n -= n.mean()
    return n / (np.percentile(np.abs(n), 99) + 1e-9)


def edge_gate(M, thin=24, soft=8):
    """1 inside islands at least `thin` texels across, easing to 0 on thinner ones (greeble
    islands): local island width = 2 x the largest inset distance within thin/2 texels."""
    r = thin // 2
    inside = M > .5
    d = np.zeros(M.shape, np.float32); cur = inside.copy()
    for _ in range(r):                             # chessboard inset distance, capped at r
        p = np.pad(cur, 1)
        cur = cur & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
        d += cur
    t = d
    for _ in range(r):                             # running max over a (2r+1)^2 window
        p = np.pad(t, 1, mode='edge')
        t = np.maximum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return np.clip((2 * t + 1 - (thin - soft)) / soft, 0, 1).astype(np.float32)


# --- the look -------------------------------------------------------------------------------
def scale_normal(nx, ny, target_std):
    """Scale tangent X/Y so the DXT5nm A channel (= nx/2 + .5) has std <= target_std."""
    cur = float((nx * .5).std())
    s = min(1.0, target_std / max(cur, 1e-6))
    return nx * s, ny * s, s


def look(rgb, nx=None, ny=None, cover=None, emit=None, crease=-.05, occ=.12, isl=.06,
         grime=.04, edge=.02, wrap=False, seed=1, verbose=False, base_r=16.0, spread_r=24.0, core=.45, floor=.35,
         measure_cover=False, contact_max=.15, p10_slack=0.0, thin=24):
    """rgb (H, W, 3) float -> processed rgb. Returns (rgb, info)."""
    h, w = rgb.shape[:2]
    S = 1.0                                        # radii in texels, as the targets are measured
    l = np.maximum(rgb @ LUMA, 1e-4)
    M = np.ones((h, w), np.float32) if cover is None else cover.astype(np.float32)
    P = paint_mask(rgb).astype(np.float32)        # gutters included: they are measured, and mip down
    Ph = P > .5
    MC = (M > .5) if (measure_cover and cover is not None) else True

    def meas(x):                                   # the texels the targets are measured on
        return paint_mask(x) & MC

    p10_0, p90_0 = np.percentile(l[meas(rgb)], [10, 90])
    Ps = np.clip(blur(P, 1.0 * S, wrap) * 2 - 1, 0, 1) * P      # paint, eased off decal edges
    E = np.ones((h, w), np.float32)
    if emit is not None:
        E = 1 - np.clip(blur((emit.max(-1) > .06).astype(np.float32), 1.5 * S, wrap) * 3, 0, 1)
    Ps *= E

    # 1. local contrast on neutral surfaces (paint plus the mid-grey crease cores inside it; dark
    #    or saturated decals and materials are left alone): split luma into a soft base (blur at
    #    `base_r`) and the relief on top of it. The relief is scaled down by g (solved below for the
    #    crease target); `floor` of the darkness taken out of the creases comes back spread wide,
    #    as broad soft shading instead of sharp lines.
    mx = rgb.max(-1); mn = rgb.min(-1)
    R = (l > core) & ((mx - mn) / np.maximum(mx, 1e-6) < .12)
    if emit is not None:
        R &= E > .5
    Rf = R.astype(np.float32)
    base = blur_m(l, Rf, base_r * S, wrap)
    dev = np.where(R, l - base, 0)
    neg = np.minimum(dev, 0); pos = np.maximum(dev, 0)

    def spread_of(x):                              # darkness taken out, given back wide and shallow
        return np.where(R, blur_m(x, Rf, spread_r * S, wrap), 0)

    # 2. broad occlusion: curvature of the normal field (or of luma), band-passed at ~16 px
    if nx is not None:
        du, _ = grad(nx); _, dv = grad(ny)
        curv = (du + dv) * M
    else:
        gu, gv = grad(l); du, _ = grad(gu); _, dv = grad(gv)
        curv = (du + dv) * M
    c = blur_m(curv, M, 12 * S, wrap) * .5 + blur_m(curv, M, 24 * S, wrap) * .5
    c /= np.percentile(np.abs(c[M > .5]), 98) + 1e-9
    c = np.clip(c, -1, 1)
    sh = 1 - occ * np.clip(-c, 0, 1) * (Ps + .5 * (1 - Ps)) * E * M
    G = edge_gate(M, thin) if cover is not None else 1.0   # 0 on islands thinner than `thin` px
    if cover is not None:                          # UV-island-edge darkening (soft, both sides of seams)
        inner = blur(M, 10 * S, wrap)
        sh *= 1 - isl * np.clip(1 - inner, 0, .5) * 2 * E * M * G
        fade = np.clip(blur(M, 16 * S, wrap) * 2 - 1, 0, 1) ** 2  # no noise steps across seams
    else:
        fade = 1.0
    # 3. grime (+-grime, grey) and faint convex-edge highlights, paint only
    nz = fbm_noise(h, w, seed, wrap)
    sh *= 1 + grime * nz * Ps * fade
    sh *= 1 + edge * np.clip(c, 0, 1) * Ps

    # 4. contact shading for maps that are already softer than the target (near-uniform panels):
    #    darkening hugging UV-island (panel) edges and tight concave curvature, strength solved
    #    up to `contact_max`
    cs = np.clip(blur(curv, 3 * S, wrap) / (np.percentile(np.abs(blur(curv, 3 * S, wrap)[M > .5]), 98) + 1e-9), -1, 0) * -1
    if cover is not None:
        cs = np.maximum(cs, np.clip(1 - blur(M, 5 * S, wrap), 0, .5) * 2 * G)
    cs *= E * M

    def build(g, kc=0.0):
        # soft knee: relief deviations much smaller than k pass unchanged (weave, mesh, rivets
        # keep their texture), big ones saturate at about k (the sharp dark creases and steps)
        k = .002 + .5 * g ** 2
        np_ = k * np.tanh(neg / k); pp_ = k * np.tanh(pos / k)
        l2 = base + pp_ + np_ + spread_of(neg - np_) * floor
        l2 = np.where(R, np.maximum(l2, 1e-4), l)
        out = rgb * ((l2 / l) * sh * (1 - kc * cs))[..., None]
        L2 = out @ LUMA; P2 = meas(out)
        out *= p90_0 / np.percentile(L2[P2], 90)   # white point back to the input's
        # never darken the shadows: lift the paint below the input's p10 back up to it
        L2 = out @ LUMA; P2 = meas(out)
        p10 = np.percentile(L2[P2], 10)
        if p10 < p10_0 - p10_slack:
            lift = np.clip((p10_0 - L2) / max(p10_0 - .45, 1e-3), 0, 1) * (p10_0 - p10_slack - p10)
            out *= (1 + lift / np.maximum(L2, 1e-4) * Ps)[..., None]
        return out

    def crease_of(out):
        L2 = out @ LUMA
        return float(np.percentile((L2 - box(L2, 9))[meas(out)], 5))

    def solve(f, lo, hi, rising):                  # bisection for crease_of(f(x)) == crease
        for _ in range(14):
            mid = (lo + hi) / 2
            if (crease_of(f(mid)) < crease) == rising:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    g, kc = 1.0, 0.0
    c1 = crease_of(build(1.0))
    if c1 < crease:                                # too sharp: compress the relief (g = relief kept)
        g = solve(build, 0.0, 1.0, rising=False)
    elif c1 > crease + .005:                       # too smooth: add contact shading
        kc = contact_max
        if crease_of(build(1.0, kc)) < crease:
            kc = solve(lambda x: build(1.0, x), 0.0, contact_max, rising=False)
    out = build(g, kc)
    info = dict(g=g, contact=kc, occ_min=float(sh.min()), occ_mean=float(sh[Ph].mean()), crease=crease_of(out))
    if verbose:
        print('  relief kept g %.3f, contact %.3f, shade %.3f..%.3f (paint mean %.3f), crease before DXT5 %.3f'
              % (g, kc, sh.min(), sh.max(), info['occ_mean'], info['crease']))
    return np.clip(out, 0, 1).astype(np.float32), info


def process(diff_path, out_dir, nstd=None, uvdump=None, uvmat=None, emit_path=None, **kw):
    """One map, DDS -> DDS: <out_dir>/<name>_diff.dds (+ _nrm.dds scaled with nstd, else copied)."""
    name = os.path.basename(diff_path)[:-len('_diff.dds')]
    d = read_dds(diff_path)
    npath = sibling_nrm(diff_path)
    nr = read_dds(npath) if npath else None
    nx = nr[..., 3] * 2 - 1 if nr is not None else None
    ny = nr[..., 1] * 2 - 1 if nr is not None else None
    cover = None
    if uvdump:
        cover = coverage_mask(uvdump, uvmat or name, d.shape[0])
        if cover is not None and cover.shape != d.shape[:2]:
            cover = np.asarray(Image.fromarray(to_u8(cover)).resize(d.shape[1::-1]), np.float32) / 255
        print(f'{name}: coverage mask', 'none' if cover is None else f'{cover.mean()*100:.0f}% of texels')
    if emit_path == 'auto':
        emit_path = diff_path.replace('_diff.dds', '_emit.dds')
        emit_path = emit_path if os.path.exists(emit_path) else None
    emit = read_dds(emit_path)[..., :3] if emit_path else None
    if emit is not None:
        print(f'{name}: emissive mask {os.path.basename(emit_path)}, {(emit.max(-1) > .06).mean()*100:.2f}% lit')
    rgb, info = look(d[..., :3], nx, ny, cover, emit, verbose=True, **kw)
    os.makedirs(out_dir, exist_ok=True)
    od = os.path.join(out_dir, f'{name}_diff.dds')
    u8 = to_u8(np.dstack([rgb, d[..., 3]]))                 # gloss alpha passes through
    write_dds(u8, od, cover)
    back = read_dds(od); pre = u8.astype(np.float32) / 255
    print('  DXT5 encode of the new diffuse: RGB PSNR %.2f dB, mean |d| %.3f/255; alpha max |d| %d/255'
          % (psnr(pre[..., :3], back[..., :3]), np.abs(pre[..., :3] - back[..., :3]).mean() * 255,
             round(np.abs(back[..., 3] - d[..., 3]).max() * 255)))
    if nr is not None and nstd:
        nx2, ny2, s = scale_normal(nx, ny, nstd)
        n = np.empty_like(nr)
        n[..., 0] = 1; n[..., 1] = ny2 * .5 + .5; n[..., 2] = n[..., 1]; n[..., 3] = nx2 * .5 + .5
        on = os.path.join(out_dir, f'{name}_nrm.dds'); nu = to_u8(n); write_dds(nu, on, cover)
        back = read_dds(on); pre = nu.astype(np.float32) / 255
        print(f'  normal X/Y x{s:.3f}; DXT5 encode G,A PSNR %.2f dB, mean |d| %.3f/255'
              % (psnr(pre[..., [1, 3]], back[..., [1, 3]]), np.abs(pre[..., [1, 3]] - back[..., [1, 3]]).mean() * 255))
    elif npath and os.path.abspath(os.path.dirname(npath)) != os.path.abspath(out_dir):
        shutil.copy2(npath, os.path.join(out_dir, f'{name}_nrm.dds'))   # untouched, byte for byte
    return od


def dump_uv(out, mus):
    """Inside Blender: import KSP .mu files, write uvdump.json keyed by part/object, with each
    polygon's map named after its material's _MainTex (minus _diff), so keys match map names."""
    import bpy, json, addon_utils
    addon_utils.enable('io_object_mu', default_set=True)
    res = {}
    for f in mus:
        before = set(bpy.data.objects)
        bpy.ops.import_object.ksp_mu(filepath=f)
        part = os.path.splitext(os.path.basename(f))[0]
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.type != 'MESH' or o.muproperties.collider != 'MU_COL_NONE' or not o.data.uv_layers:
                continue
            me = o.data
            names = []
            for m in me.materials:
                t = {p.name: p.tex for p in m.mumatprop.texture.properties}.get('_MainTex', '') if m else ''
                names.append(os.path.splitext(t)[0].replace('_diff', '') or (m.name if m else ''))
            uv = np.empty(len(me.loops) * 2); me.uv_layers[0].data.foreach_get('uv', uv)
            ls = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', ls)
            lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt)
            mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
            res[f'{part}/{o.name}'] = dict(uv=uv.round(6).tolist(), ls=ls.tolist(), lt=lt.tolist(),
                                          mat=[names[i] if i < len(names) else '' for i in mi])
    json.dump(res, open(out, 'w'))
    print('wrote', out, len(res), 'meshes')


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('maps', nargs='+')
    ap.add_argument('--roundtrip', action='store_true', help='measure DXT5 decode/re-encode loss')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--ref', nargs='*')
    ap.add_argument('-o', '--out'); ap.add_argument('--nstd', type=float)
    ap.add_argument('--crease', type=float, default=-.05); ap.add_argument('--occ', type=float, default=.12)
    ap.add_argument('--isl', type=float, default=.06)
    ap.add_argument('--grime', type=float, default=.04); ap.add_argument('--edge', type=float, default=.02)
    ap.add_argument('--measure-cover', action='store_true')
    ap.add_argument('--uvdump'); ap.add_argument('--uvmat'); ap.add_argument('--emit')
    ap.add_argument('--keep-normals', action='store_true', help='--check: normal std is "keep" (ShabTech)')
    ap.add_argument('--wrap', action='store_true'); ap.add_argument('--seed', type=int, default=1)
    o = ap.parse_args(argv)
    if o.roundtrip:
        for p in o.maps:
            for k, (ps, mad, mx) in roundtrip(p).items():
                print(f'{p}: {k:<16} PSNR {ps:6.2f} dB   mean |d| {mad:.3f}/255   max {mx:.0f}/255')
        return
    if o.check:
        refs = o.ref or [None] * len(o.maps)
        for p, r in zip(o.maps, refs):
            u = o.uvdump if o.measure_cover else None
            print(check_table(p, map_metrics(p, u), map_metrics(r, u) if r else None, nstd_goal=not o.keep_normals))
        return
    if not o.out:
        ap.error('-o OUTDIR is required when processing (refusing to overwrite in place by default)')
    for p in o.maps:
        process(p, o.out, nstd=o.nstd, uvdump=o.uvdump, uvmat=o.uvmat, emit_path=o.emit,
                crease=o.crease, occ=o.occ, isl=o.isl, grime=o.grime, edge=o.edge, wrap=o.wrap, seed=o.seed,
                measure_cover=o.measure_cover)


if __name__ == '__main__':
    if '--dump-uv' in sys.argv:
        a = sys.argv[sys.argv.index('--dump-uv') + 1:]
        dump_uv(a[0], a[1:])
    else:
        main(sys.argv[1:])
