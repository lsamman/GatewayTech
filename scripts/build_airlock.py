"""Crew & Science Airlock, with folding radiator wings.
blender -b src/gateway_source.blend -P scripts/build_airlock.py -- <outdir>"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
hull = bpy.data.objects['Airlock']
rad = bpy.data.objects['Airlock_radiator']
P = G.Part('gt_Airlock', G.R_RADIAL, (11.97, 5.67, 0))

for nm, (c, n) in {'top': ((11.97, 8.67, 0), (0, 1, 0)), 'bottom': ((11.97, 2.37, 0), (0, -1, 0))}.items():
    pos, d = G.port_cap(P, hull, c, n, name=f'plate_{nm}')
    P.node(nm, pos, d, 1)

body = P.piece('airlock_body', [(hull, None)])

CLIP = 'radiatorDeploy'; N = 6 * G.FPS
fc = G.face_centres(rad)
for sgn, tag in ((1, 'A'), (-1, 'B')):
    G.accordion(P, CLIP, f'radiator{tag}', rad, span_st=(0, 0, sgn), hinge_axis_st=(1, 0, 0),
                cuts=[4.44, 6.405, 8.375], root_lo=None, tip_hi=None, thick_dir_st=(0, 1, 0),
                half_thick=0.055, n_frames=N, mask=fc[:, 2] * sgn > 0)

G.airlock(P, body, (0, -1, 0), 0.0)
P.assign_ksp_materials({})
co = np.array([v.co[:] for v in body.data.vertices])
r = np.hypot(co[:, 0], co[:, 1])
P.hull_collider('collider_body', co[r < 1.15][::5])

P.bake_clips(0)
P.export(os.path.join(out, 'gt_Airlock.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()},
           'clips': {CLIP: N}}, open(os.path.join(out, 'gt_Airlock.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_Airlock.blend'))
