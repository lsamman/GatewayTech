"""Accordion radiator wing (one I-Hab or Airlock wing) as its own part.
Origin = wing root at the hull; the wing spans part +Z (Unity +Y), like gt_ROSA.
blender -b src/gateway_source.blend -P scripts/build_radiator.py -- <outdir> ihab|airlock"""
import bpy, sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from mathutils import Vector, Matrix
import gt_lib as G

out, which = sys.argv[sys.argv.index('--') + 1:][:2]
G.enable_addon()
# source object, part name, panel cuts (station Z), half thickness (real m), texture map
SPEC = {
    'ihab': ('I-Hab Radiator', 'gt_IHabRadiator', [4.355, 6.605, 8.855], 0.12,
             {'iHab_main': 'iHAB_main', 'iHab_aux': 'iHAB_aux'}),
    'airlock': ('Airlock_radiator', 'gt_AirlockRadiator', [4.44, 6.405, 8.375], 0.055, {}),
}
src_name, name, cuts, half_thick, texmap = SPEC[which]
rad = bpy.data.objects[src_name]
fc = G.face_centres(rad)
mask = fc[:, 2] > 0                       # wing A (+Z); the -Z wing is its mirror
root_st = G.wing_root(rad, 1)
# station -> part: span (station +Z) -> part +Z, panel width (station X) -> part -Y,
# panel thickness (station Y) -> part X
R = Matrix(((0, 1, 0), (-1, 0, 0), (0, 0, 1)))
P = G.Part(name, R, root_st)

CLIP = 'radiatorDeploy'; N = 6 * G.FPS
panels = G.accordion(P, CLIP, 'radiator', rad, span_st=(0, 0, 1), hinge_axis_st=(1, 0, 0),
                     cuts=cuts, root_lo=None, tip_hi=None, thick_dir_st=(0, 1, 0),
                     half_thick=half_thick, n_frames=N, mask=mask)
print(f"{name}: {len(panels)} panels, root {np.round(root_st, 3)}")

P.assign_ksp_materials(texmap)
# collider on the root panel (it stays put; the folded stack lies against it when stowed)
p0 = panels[0]
co = np.array([(p0.matrix_world @ v.co)[:] for v in p0.data.vertices])
P.hull_collider('collider_root', co)

P.node('bottom', Vector((0, 0, 0)), Vector((0, 0, -1)), 1)
P.bake_clips(0)
P.export(os.path.join(out, f'{name}.mu'))
json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()}, 'clips': {CLIP: N}},
          open(os.path.join(out, f'{name}.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f'{name}.blend'))
