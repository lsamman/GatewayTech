"""I-Hab: International Habitation module, with mounts for its radiator wings.
blender -b src/gateway_source.blend -P scripts/build_ihab.py -- <outdir>"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
hull = bpy.data.objects['I-Hab']
rad = bpy.data.objects['I-Hab Radiator']
P = G.Part('gt_IHab', G.R_AXIAL, (11.43, 0, 0))

ports = {
    'top':     ((14.80, 0, 0), (1, 0, 0)),
    'bottom':  ((7.86, 0, 0), (-1, 0, 0)),
    'radial1': ((11.97, 1.63, 0), (0, 1, 0)),
    'radial2': ((11.97, -1.63, 0), (0, -1, 0)),
}
for nm, (c, n) in ports.items():
    pos, d = G.port_cap(P, hull, c, n, name=f'plate_{nm}')
    P.node(nm, pos, d, 1)

# dexterous-arm mount (where the model's small arm stood)
apos, adir = G.arm_mount(bpy.data.objects['Little_Arm_1'])
P.node('arm', P.p(apos), P.d(adir), 0)

body = P.piece('ihab_body', [(hull, None)])

# radiator wing mounts: the accordion wings are a separate part (gt_IHabRadiator,
# build_radiator.py) that stacks onto these nodes at the root of each wing
for w, tag in ((1, 'radA'), (-1, 'radB')):
    P.node(tag, P.p(G.wing_root(rad, w)), P.d((0, 0, w)), 1)

G.airlock(P, body, (0, -1, 0), -0.6)
P.assign_ksp_materials({'iHab_main': 'iHAB_main', 'iHab_aux': 'iHAB_aux'})
co = np.array([v.co[:] for v in body.data.vertices])
r = np.hypot(co[:, 0], co[:, 1])
P.hull_collider('collider_body', co[r < 1.3][::5])

P.bake_clips(0)
P.export(os.path.join(out, 'gt_IHab.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()},
           'clips': {}}, open(os.path.join(out, 'gt_IHab.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_IHab.blend'))
