"""PPE: Power & Propulsion Element with two roll-out solar wings and folding dish antennas.
blender -b src/gateway_source.blend -P scripts/build_ppe.py -- <outdir>"""
import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from mathutils import Vector, Quaternion, Matrix
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
hull = bpy.data.objects['Maxar_PPE.001']
arr = bpy.data.objects['Maxar_PPE Array']
P = G.Part('gt_PPE', G.R_AXIAL, (-2.74, 0, 0))
S = G.SCALE

# --- nodes: front ring mates with HALO's aft ring at station x=0 ----------------
xs = G.world_verts(hull)[:, 0]
P.node('top', P.p((0.0, 0, 0)), P.d((1, 0, 0)), 2)
P.node('bottom', P.p((xs.min(), 0, 0)), P.d((-1, 0, 0)), 2)

# --- antennas: one boom + a two-dish platform per side ---------------------------
# The boom folds aft along the bus. In the model the dishes look along station +Z, straight
# at a solar wing; deploying tips the platform 90 deg about its boom link so both dishes
# look along +X, at HALO.
ANT = 'antennaDeploy'; NA = 5 * G.FPS
ants = []
for s, tag in ((1, 'L'), (-1, 'R')):
    labels, nisl = G.face_islands(hull)
    fc = G.face_centres(hull)
    main_isl = np.bincount(labels).argmax()
    def pred(c, mn, mx, s=s):
        return c[1] * s > 1.35 and c[2] > 0.3 and -3.4 < c[0] < 0.0
    mask = G.island_select(hull, pred, max_size=2.3) & (labels != main_isl)
    pts = fc[mask]
    hinge_st = pts[np.argmin(np.abs(pts[:, 1]))]
    # dish head: the islands outboard of the boom's elbow (link stub, platform, dishes, feeds)
    isl = np.unique(labels[mask])
    out_y = {i: fc[labels == i, 1].mean() * s for i in isl}
    head_isl = [i for i in isl if out_y[i] > 2.5]
    head = np.isin(labels, head_isl)
    link = fc[labels == min(head_isl, key=out_y.get)]
    piv_st = (link.min(0) + link.max(0)) / 2      # the link stub runs along station Y
    fr = G.frame_from_axes(P.p(hinge_st), z=(0, 0, 1), x=(1, 0, 0))
    a = P.piece(f'antenna{tag}', [(hull, mask & ~head)], fr)
    d = P.piece(f'dish{tag}', [(hull, head)], G.frame_from_axes(P.p(piv_st), z=(0, 0, 1), x=(1, 0, 0)), a)
    G.remove_faces(hull, mask)
    ax = P.d((0, 0, 1))                      # station Z (vertical) in part space
    stow = Quaternion(ax, math.radians(90 * s))
    P.key(ANT, a, 0, rotation_quaternion=stow)
    P.key(ANT, a, int(NA * 0.3), rotation_quaternion=Quaternion(ax, math.radians(45 * s)))
    P.key(ANT, a, int(NA * 0.6), rotation_quaternion=Quaternion())
    P.key(ANT, a, NA, rotation_quaternion=Quaternion())
    # +90 deg about station Y turns the dish boresight from station +Z to +X
    P.key(ANT, d, 0, rotation_quaternion=Quaternion())
    P.key(ANT, d, int(NA * 0.5), rotation_quaternion=Quaternion())
    P.key(ANT, d, NA, rotation_quaternion=Quaternion(P.d((0, 1, 0)), math.radians(90)))
    ants.append(a)
    print(f"antenna {tag}: {mask.sum()} faces hinge {np.round(hinge_st, 3)} dish pivot {np.round(piv_st, 3)}")

body = P.piece('ppe_body', [(hull, None)])

# --- thrusters: 3 large Hall thrusters (AEPS) on the aft face, 2 smaller ones (BHT-6000) on
# each boom; points are the centres of each nozzle's exit face -------------------------
for plume, pts in (('plumeLarge', [(-5.463, y, 0.0) for y in (-1.043, 0.0, 1.043)]),
                   ('plumeSmall', [(-4.996, y, 0.0) for y in (-2.391, -1.975, 1.975, 2.391)])):
    for pt in pts:
        # io_object_mu turns a thrustTransform's local +Z into Unity forward (exhaust direction)
        fr = G.frame_from_axes(P.p(pt), z=P.d((-1, 0, 0)), x=P.d((0, 1, 0)))
        t = P.empty('thrustTransform', fr, P.model)
        # child at identity inherits that forward; the part cfg picks plume size by this name
        P.empty(plume, fr, t)

# --- solar wing mounts: the roll-out wings are a separate part (gt_ROSA, build_rosa.py)
# that stacks onto these nodes at the base of each yoke ----------------------------
x_c = float(G.world_verts(arr)[:, 0].mean())
for w, tag in ((1, 'wingA'), (-1, 'wingB')):
    P.node(tag, P.p((x_c, 0, 1.42 * w)), P.d((0, 0, w)), 1)
NW = 0

P.assign_ksp_materials({'PPE_aux': 'PPE_array'})
co = np.array([v.co[:] for v in body.data.vertices])
r = np.hypot(co[:, 0], co[:, 1])
P.hull_collider('collider_body', co[r < 1.6][::4])

P.bake_clips(0)
P.export(os.path.join(out, 'gt_PPE.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()},
           'clips': {k: (NA if k == ANT else NW) for k in P.clips}},
          open(os.path.join(out, 'gt_PPE.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_PPE.blend'))
