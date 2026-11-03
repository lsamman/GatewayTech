"""ROSA roll-out solar wing (one PPE wing) as its own part.
Origin = base of the yoke; the wing spans part +Z (Unity +Y), like HabTech's iROSA.
blender -b src/gateway_source.blend -P scripts/build_rosa.py -- <outdir>"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from mathutils import Vector, Matrix
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
arr = bpy.data.objects['Maxar_PPE Array']
S = G.SCALE
x_c = float(G.world_verts(arr)[:, 0].mean())
# station -> part: span (station +Z) -> part +Z, blanket width (station Y) -> part X,
# panel normal (station X) -> part -Y
R = Matrix(((0, 1, 0), (-1, 0, 0), (0, 0, 1)))
P = G.Part('gt_ROSA', R, (x_c, 0, 1.42))

ROOT, TIP = 3.58, 21.04
STOW_LEN = 0.30
N = 8 * G.FPS
span_p = P.d((0, 0, 1)); norm_p = P.d((1, 0, 0))
pivot = P.empty('sunPivot', G.frame_from_axes(P.p((x_c, 0, 1.42)), z=span_p, y=norm_p), P.model)

labels, _ = G.face_islands(arr)
fc = G.face_centres(arr)
stat, stretch, tip = (np.zeros(len(fc), bool) for _ in range(3))
for i in range(labels.max() + 1):
    sel = labels == i
    lo, hi = fc[sel, 2].min(), fc[sel, 2].max()
    if hi < 0:
        continue                                    # the other wing
    if hi <= ROOT + 0.05:
        stat |= sel
    elif lo >= TIP - 0.1:
        tip |= sel
    else:
        stretch |= sel
root = P.piece('wing_root', [(arr, stat)], G.frame_from_axes(P.p((x_c, 0, 1.42)), z=span_p, y=norm_p), pivot)
blanket = P.piece('wing_blanket', [(arr, stretch)], G.frame_from_axes(P.p((x_c, 0, ROOT)), z=span_p, y=norm_p), pivot)
tipo = P.piece('wing_tip', [(arr, tip)], G.frame_from_axes(P.p((x_c, 0, TIP)), z=span_p, y=norm_p), pivot)
s0 = STOW_LEN / (TIP - ROOT)
dep_loc = tipo.location.copy()
stow_loc = dep_loc - Vector((0, 0, (TIP - ROOT - STOW_LEN) * S))
for k in range(0, 9):
    f = int(N * k / 8); t = k / 8
    e = t * t * (3 - 2 * t)
    sc = s0 + (1 - s0) * e
    P.key('deploy', blanket, f, scale=Vector((1, 1, sc)))
    P.key('deploy', tipo, f, location=stow_loc.lerp(dep_loc, (sc - s0) / (1 - s0)))
P.empty('sunCatcher', G.frame_from_axes(P.p((x_c, 0, 12.0)), z=span_p, y=norm_p), pivot)
print(f"ROSA: static {stat.sum()} stretch {stretch.sum()} tip {tip.sum()} faces")

P.assign_ksp_materials({'PPE_aux': 'PPE_array'})
# collider on the yoke/root bar only (blankets stay collider-free, like HabTech)
co = np.array([(root.matrix_world @ v.co)[:] for v in root.data.vertices])
P.hull_collider('collider_root', co, parent=root)
# the hull collider was built in part space; express it in the root's frame
col = [o for o in P.coll.objects if o.name.startswith('collider_root')][0]
G.reframe(P, col, root.matrix_world.copy(), root)

P.node('bottom', Vector((0, 0, 0)), Vector((0, 0, -1)), 1)
P.bake_clips(0)
P.export(os.path.join(out, 'gt_ROSA.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()}, 'clips': {'deploy': N}},
          open(os.path.join(out, 'gt_ROSA.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_ROSA.blend'))
