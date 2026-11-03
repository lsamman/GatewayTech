"""Report loose-part islands protruding from each module hull, and NDS port centres/axes."""
import bpy, bmesh, sys, math
import numpy as np
from mathutils import Vector
MODULES = {  # hull object: axis ('x' or 'y') through module centre
    'NG_HALO.001': 0, 'I-Hab': 0, 'ERMXL_LoRes': 1, 'Airlock': 1, 'Maxar_PPE.001': 0,
}
def islands(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4); bm.verts.ensure_lookup_table()
    mw = obj.matrix_world
    seen = set(); out = []
    for v in bm.verts:
        if v.index in seen: continue
        stack = [v]; comp = []
        seen.add(v.index)
        while stack:
            a = stack.pop(); comp.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index); stack.append(b)
        out.append(np.array([tuple(mw @ x.co) for x in comp]))
    return out
for name, ax in MODULES.items():
    obj = bpy.data.objects[name]
    isl = islands(obj)
    allv = np.concatenate(isl)
    o = [i for i in range(3) if i != ax]
    # module axis line: centre of the other two coords
    c = np.median(allv[:, o], axis=0)
    rad = np.hypot(allv[:, o[0]] - c[0], allv[:, o[1]] - c[1])
    r_hull = np.percentile(rad, 60)
    print(f"\n== {name}: {len(isl)} islands, {len(allv)} verts, axis={'xyz'[ax]} centre={c.round(2)} hull_r~{r_hull:.2f} along={allv[:,ax].min():.2f}..{allv[:,ax].max():.2f}")
    rows = []
    for k, p in enumerate(isl):
        r = np.hypot(p[:, o[0]] - c[0], p[:, o[1]] - c[1])
        size = p.max(0) - p.min(0)
        if r.max() > r_hull + 0.35 and size.max() > 0.4 and len(p) > 20:
            rows.append((r.max(), k, len(p), p.mean(0).round(2), size.round(2)))
    for r, k, n, ctr, size in sorted(rows, key=lambda x: -x[0])[:25]:
        print(f"  island {k:4d} verts={n:5d} rmax={r:.2f} ctr={ctr} size={size}")
# Port groups: cluster NDS objects by world centre
print("\n== NDS ports")
pts = {}
for ob in bpy.data.objects:
    if ob.name.startswith('NDS') and ob.type == 'MESH' and 'Shutter' not in ob.name:
        v = np.array([tuple(ob.matrix_world @ x.co) for x in ob.data.vertices])
        ctr = v.mean(0)
        cov = np.cov((v - ctr).T); w, e = np.linalg.eigh(cov)
        print(f"  {ob.name:28s} parent={ob.parent.name:22s} ctr={ctr.round(2)} axis={e[:,0].round(2)} span={(v.max(0)-v.min(0)).round(2)}")
