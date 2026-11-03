import bpy, bmesh, numpy as np
for name in ['Maxar_PPE Array', 'I-Hab Radiator', 'Airlock_radiator']:
    ob = bpy.data.objects[name]
    bm = bmesh.new(); bm.from_mesh(ob.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.verts.ensure_lookup_table(); mw = ob.matrix_world
    seen=set(); isl=[]
    for v in bm.verts:
        if v.index in seen: continue
        st=[v]; comp=[]; seen.add(v.index)
        while st:
            a=st.pop(); comp.append(a)
            for e in a.link_edges:
                b=e.other_vert(a)
                if b.index not in seen: seen.add(b.index); st.append(b)
        isl.append(np.array([tuple(mw@x.co) for x in comp]))
    print(f"== {name}: {len(isl)} islands, materials={[m.name for m in ob.data.materials]}")
    for p in sorted(isl, key=lambda p: p[:,2].mean()):
        print(f"   n={len(p):4d} min={p.min(0).round(2)} max={p.max(0).round(2)}")
