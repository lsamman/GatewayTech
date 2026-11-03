"""Import Gateway Core.glb, bake away the 'mover' root rotation, save src/gateway_source.blend."""
import bpy, sys
from mathutils import Matrix
glb, out = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
mover = bpy.data.objects['mover']
# Un-rotate the root so the station sits in a clean frame.
mover.rotation_mode = 'QUATERNION'
mover.rotation_quaternion = (1, 0, 0, 0)
mover.location = (0, 0, 0)
bpy.context.view_layer.update()
for o in bpy.data.objects:
    if o.type == 'MESH':
        bb = [o.matrix_world @ __import__('mathutils').Vector(c) for c in o.bound_box]
        mn = [round(min(v[i] for v in bb), 2) for i in range(3)]
        mx = [round(max(v[i] for v in bb), 2) for i in range(3)]
        print(f"OBJ {o.name:32s} parent={o.parent.name if o.parent else '-':22s} mats={[m.name for m in o.data.materials]} bbox={mn}..{mx}")
bpy.ops.wm.save_as_mainfile(filepath=out)
