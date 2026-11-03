"""Render preview PNGs of named objects (and their children) from several angles.
usage: blender -b file.blend -P preview.py -- outdir name1 [name2 ...]  [--hide-nds]"""
import bpy, sys, math
from mathutils import Vector
args = sys.argv[sys.argv.index('--') + 1:]
hide_nds = '--hide-nds' in args
args = [a for a in args if a != '--hide-nds']
outdir, names = args[0], args[1:]
keep = set()
def add(o):
    keep.add(o)
    for c in o.children: add(c)
for n in names: add(bpy.data.objects[n])
for o in bpy.data.objects:
    vis = o in keep and not (hide_nds and o.name.startswith('NDS'))
    o.hide_render = not vis
pts = [o.matrix_world @ Vector(c) for o in keep if o.type == 'MESH' and not o.hide_render for c in o.bound_box]
mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
ctr = (mn + mx) / 2; rad = (mx - mn).length / 2
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'
sc.display.shading.show_cavity = True
sc.render.resolution_x = 900; sc.render.resolution_y = 700
sc.render.film_transparent = False
cam_data = bpy.data.cameras.new('pcam'); cam_data.lens = 50; cam_data.clip_end = 1000
cam = bpy.data.objects.new('pcam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
views = {'iso': (1, -1, 0.7), 'front': (0, -1, 0), 'top': (0, 0, 1), 'side': (1, 0, 0), 'back': (0, 1, 0), 'end': (-1, 0, 0), 'bottom': (0, 0, -1)}
for vname, d in views.items():
    d = Vector(d).normalized()
    cam.location = ctr + d * rad * 2.6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y' if abs(d.z) > 0.9 else 'Z').to_euler()
    sc.render.filepath = f"{outdir}/{'_'.join(n.replace(' ', '') for n in names)[:40]}_{vname}.png"
    bpy.ops.render.render(write_still=True)
