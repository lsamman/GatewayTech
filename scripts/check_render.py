"""Render a built part blend: objects coloured, at given frames, several views.
usage: blender -b build/mu/X.blend -P check_render.py -- outprefix frame1 [frame2..] [--tex]"""
import bpy, sys, random, addon_utils
addon_utils.enable("io_object_mu")
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
tex = '--tex' in a; a = [x for x in a if x != '--tex']
pref, frames = a[0], [int(f) for f in a[1:]]
sc = bpy.context.scene
for o in sc.objects:
    o.hide_render = o.muproperties.collider != 'MU_COL_NONE' or not any(c.name.startswith('gt_') for c in o.users_collection)
    random.seed(hash(o.name) & 0xffff)
    o.color = (random.random() * .8 + .2, random.random() * .8 + .2, random.random() * .8 + .2, 1)
if tex:
    import os
    texdir = os.path.join(os.path.dirname(bpy.data.filepath), '..', 'tex', '_png')
    for m in bpy.data.materials:
        if not m.name.startswith('gt_'):
            continue
        mt = {t.name: t.tex for t in m.mumatprop.texture.properties}
        f = os.path.join(texdir, mt.get('_MainTex', '').replace('.png', '') + '.png')
        if not os.path.exists(f):
            continue
        m.use_nodes = True
        nt = m.node_tree
        img = nt.nodes.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(f)
        bsdf = nt.nodes.get('Principled BSDF')
        nt.links.new(img.outputs['Color'], bsdf.inputs['Base Color'])
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'TEXTURE' if tex else 'OBJECT'
sc.display.shading.show_cavity = True
sc.display.shading.show_backface_culling = True
sc.render.resolution_x = 640; sc.render.resolution_y = 520
cd = bpy.data.cameras.new('c'); cd.lens = 40; cd.clip_start = 0.01; cd.clip_end = 500
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
for f in frames:
    sc.frame_set(f)
    pts = [o.matrix_world @ Vector(c) for o in sc.objects if o.type == 'MESH' and not o.hide_render for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)]); mx = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr = (mn + mx) / 2; rad = (mx - mn).length / 2
    for vn, d in {'a': (1, -1, 0.6), 'b': (-1, 1, 0.6), 'c': (1, 0.2, 0.1), 'd': (0.1, -1, 0.05)}.items():
        d = Vector(d).normalized(); cam.location = ctr + d * rad * 2.2
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Z').to_euler()
        sc.render.filepath = f"{pref}_f{f}_{vn}.png"; bpy.ops.render.render(write_still=True)
