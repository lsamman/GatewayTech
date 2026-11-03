"""ESPRIT: refuelling & communications module (windowed).
blender -b src/gateway_source.blend -P scripts/build_esprit.py -- <outdir>"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import gt_lib as G

out = sys.argv[sys.argv.index('--') + 1]
G.enable_addon()
hull = bpy.data.objects['ERMXL_LoRes']
P = G.Part('gt_ESPRIT', G.R_RADIAL, (4.44, 5.285, 0))
for nm, (c, n) in {'top': ((4.44, 8.28, 0), (0, 1, 0)), 'bottom': ((4.44, 2.20, 0), (0, -1, 0))}.items():
    pos, d = G.port_cap(P, hull, c, n, name=f'plate_{nm}')
    P.node(nm, pos, d, 1)
body = P.piece('esprit_body', [(hull, None)])
G.airlock(P, body, (0, -1, 0), 0.6)
P.assign_ksp_materials({})
co = np.array([v.co[:] for v in body.data.vertices])
P.hull_collider('collider_body', co[::3])
P.bake_clips(0)
P.export(os.path.join(out, 'gt_ESPRIT.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()}, 'clips': {}},
          open(os.path.join(out, 'gt_ESPRIT.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_ESPRIT.blend'))
