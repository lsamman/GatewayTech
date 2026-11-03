"""HALO: Habitation and Logistics Outpost.
blender -b src/gateway_source.blend -P scripts/build_halo.py -- <outdir>"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(__file__))
from mathutils import Matrix, Vector, Quaternion
import numpy as np
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
hull = bpy.data.objects['NG_HALO.001']
P = G.Part('gt_HALO', G.R_AXIAL, (3.71, 0, 0))

# --- antennas: two dishes on booms at the forward top corners ------------------
ANT = 'antennaDeploy'; N = 4 * G.FPS
ants = []
for side in (+1, -1):
    def pred(c, mn, mx, s=side):
        return 6.0 < c[0] < 7.35 and 0.8 < c[1] * s < 2.6 and 1.38 < c[2] < 3.3
    mask = G.island_select(hull, pred, max_size=1.45)
    pts = G.face_centres(hull)[mask]
    hinge_st = pts[np.argmin(pts[:, 2])]
    hinge = P.p(hinge_st)
    fr = G.frame_from_axes(hinge, z=(0, 0, 1), x=(1, 0, 0))
    a = P.piece(f'antenna{"L" if side > 0 else "R"}', [(hull, mask)], fr)
    G.remove_faces(hull, mask)
    # stowed: folded outward ~80 deg about the station X axis (= part Z)
    stow = Quaternion(P.d((1, 0, 0)), math.radians(-80 * side))
    P.key(ANT, a, 0, rotation_quaternion=stow)
    P.key(ANT, a, N // 2, rotation_quaternion=Quaternion(P.d((1, 0, 0)), math.radians(-30 * side)))
    P.key(ANT, a, N, rotation_quaternion=Quaternion())
    ants.append(a)
    print(f"antenna side {side}: {mask.sum()} faces, hinge {hinge_st.round(3)}")

# --- docking ports -> flat mounting faces ---------------------------------------
ports = {
    'top':    ((7.12, 0, 0), (1, 0, 0)),
    'radial1': ((4.44, 1.46, 0), (0, 1, 0)),
    'radial2': ((4.45, -1.46, 0), (0, -1, 0)),
}
for nm, (c, n) in ports.items():
    pos, d = G.port_cap(P, hull, c, n, name=f'plate_{nm}')
    P.node(nm, pos, d, 1)
# aft ring that mates with the PPE
aft = G.world_verts(hull)[:, 0].min()
P.node('bottom', P.p((aft, 0, 0)), P.d((-1, 0, 0)), 2)

# Canadarm3 mount (where the model's large arm stood)
apos, adir = G.arm_mount(bpy.data.objects['Big Arm_1'])
P.node('arm', P.p(apos), P.d(adir), 0)

body = P.piece('halo_body', [(hull, None)])
P.assign_ksp_materials({'Default': 'gt_white'})
G.airlock(P, body, (0, -1, 0), 0.0)

# collider: convex hull of the pressure vessel (ignore far-out greebles)
co = np.array([v.co[:] for v in body.data.vertices])
r = np.hypot(co[:, 0], co[:, 1])
P.hull_collider('collider_body', co[r < 0.95][::7])

P.bake_clips(rest_frame=0)
P.export(os.path.join(out, 'gt_HALO.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()},
           'clips': {k: N for k in P.clips}}, open(os.path.join(out, 'gt_HALO.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_HALO.blend'))
