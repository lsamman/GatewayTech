import bpy, numpy as np, json
OBJS = [o.name for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('NDS')]
out = {}
for n in OBJS:
    me = bpy.data.objects[n].data
    uv = np.empty(len(me.loops) * 2); me.uv_layers[0].data.foreach_get('uv', uv)
    ls = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('loop_total', lt)
    mi = np.empty(len(me.polygons), np.int64); me.polygons.foreach_get('material_index', mi)
    out[n] = dict(uv=uv.tolist(), ls=ls.tolist(), lt=lt.tolist(), mat=[me.materials[i].name for i in mi])
json.dump(out, open('build/uvdump.json', 'w'))
