"""Dump a KSP .mu file: transform tree, meshes, materials, animation clips."""
import sys
sys.path.insert(0, sys.argv[1])  # io_object_mu dir
from mu import Mu

def walk(o, d=0):
    t = o.transform
    bits = [f"pos={tuple(round(v,3) for v in t.localPosition)}"]
    if any(abs(v) > 1e-4 for v in list(t.localRotation)[1:]):
        bits.append(f"rot={tuple(round(v,3) for v in t.localRotation)}")
    if any(abs(v-1) > 1e-4 for v in t.localScale):
        bits.append(f"scl={tuple(round(v,3) for v in t.localScale)}")
    if hasattr(o, "shared_mesh"):
        m = o.shared_mesh
        bits.append(f"mesh verts={len(m.verts)} subs={len(m.submeshes)}")
    if hasattr(o, "renderer"):
        bits.append(f"mats={o.renderer.materials}")
    if hasattr(o, "collider"):
        bits.append(f"collider={type(o.collider).__name__}")
    print("  " * d + t.name, " ".join(bits))
    if hasattr(o, "animation"):
        for c in o.animation.clips:
            paths = sorted({cv.path + ':' + cv.property for cv in c.curves})
            print("  " * d + f"  >> CLIP {c.name} len={len(c.curves)} curves")
            for p in paths[:40]:
                print("  " * d + "     " + p)
    for c in o.children:
        walk(c, d + 1)

mu = Mu()
if not mu.read(sys.argv[2]):
    sys.exit("read failed")
walk(mu.obj)
for i, m in enumerate(mu.materials):
    print("MAT", i, m.name, m.shaderName, {k: v.index for k, v in m.textureProperties.items()}, m.colorProperties, m.floatProperties3)
print("TEX", [(t.name, t.type) for t in mu.textures])
