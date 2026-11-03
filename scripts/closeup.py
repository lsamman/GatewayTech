"""Close-up renders around a point. usage: -- outdir label x y z dist obj1 [obj2...]"""
import bpy, sys
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
outdir, label = a[0], a[1]; tgt = Vector(map(float, a[2:5])); dist = float(a[5]); names = set(a[6:])
for o in bpy.data.objects:
    o.hide_render = not (o.name in names)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE'; sc.display.shading.show_cavity = True
sc.render.resolution_x = 700; sc.render.resolution_y = 560
cd = bpy.data.cameras.new('c'); cd.lens = 50; cd.clip_start = 0.01
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
for vn, d in {'a': (1, -1, 0.8), 'b': (-1, 1, 0.8), 'c': (0.3, -1, -0.2), 'd': (0.2, 0.2, 1)}.items():
    d = Vector(d).normalized(); cam.location = tgt + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Z' if abs(d.z) < 0.9 else 'Y').to_euler()
    sc.render.filepath = f"{outdir}/{label}_{vn}.png"; bpy.ops.render.render(write_still=True)
