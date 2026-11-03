import bpy
for m in bpy.data.materials:
    if not m.use_nodes: continue
    bsdf = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    links = {}
    for l in m.node_tree.links:
        if l.to_node.type == 'BSDF_PRINCIPLED':
            src = l.from_node
            # walk back through separate/normal map nodes to the image
            while src.type != 'TEX_IMAGE' and src.inputs and any(i.is_linked for i in src.inputs):
                src = next(i for i in src.inputs if i.is_linked).links[0].from_node
            links[l.to_socket.name] = (src.image.name if src.type == 'TEX_IMAGE' and src.image else src.type, l.from_socket.name)
    print(f"MAT {m.name:14s} blend={m.blend_method} {links}")
for im in bpy.data.images:
    print(f"IMG {im.name:45s} {tuple(im.size)} ch={im.channels} alpha={im.alpha_mode}")
