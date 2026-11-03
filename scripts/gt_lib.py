"""Shared helpers for building GatewayTech parts from gateway_source.blend.

Coordinate conventions
  station : the GLB frame after 01_import.py (metres, Blender Z-up). Station axis runs +X
            from PPE -> HALO -> I-Hab. ESPRIT and the Airlock stand radially along +Y.
  part    : Blender frame of one KSP part. Blender +Z becomes Unity +Y (part "up").
            Unity coords = (bx, bz, by)  -- see mu.py write_vector.
Every piece is an object whose mesh is stored in its own local frame; frames are
rotation+translation only (scale is baked into the mesh) because the .mu exporter
writes obj.location/rotation/scale directly and ignores matrix_parent_inverse.
"""
import bpy, bmesh, math, os
import numpy as np
from mathutils import Matrix, Vector, Quaternion

SCALE = 0.585            # HabTech2 Destiny: 2.5 m hull / 4.27 m real
FPS = 30
# station -> part rotations
R_AXIAL = Matrix(((0, 1, 0), (0, 0, 1), (1, 0, 0)))    # station +X -> part +Z
R_RADIAL = Matrix(((0, 0, 1), (1, 0, 0), (0, 1, 0)))   # station +Y -> part +Z


def enable_addon():
    import addon_utils
    addon_utils.enable('io_object_mu', default_set=True)


class Part:
    def __init__(self, name, R, origin_station):
        self.name = name
        self.R = R.to_4x4()
        self.M = Matrix.Scale(SCALE, 4) @ self.R @ Matrix.Translation(-Vector(origin_station))
        self.Mrot = R  # direction transform (unit)
        self.coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(self.coll)
        self.root = self.empty(name, Matrix())
        self.model = self.empty('model', Matrix(), self.root)
        self.mats = {}
        self.nodes = {}   # name -> (pos_part, dir_part, size)
        self.clips = {}   # clip name -> list of (obj, [(frame, prop, value)])

    # ------------------------------------------------------------------ helpers
    def p(self, v):
        """station point -> part point"""
        return self.M @ Vector(v)

    def d(self, v):
        """station direction -> part direction (unit)"""
        return (self.Mrot @ Vector(v)).normalized()

    def empty(self, name, frame, parent=None):
        o = bpy.data.objects.new(name, None)
        o.empty_display_size = 0.2
        self.coll.objects.link(o)
        self.place(o, frame, parent)
        return o

    def place(self, o, frame, parent):
        """Put object o at part-space frame (Matrix 4x4, rot+loc) under parent."""
        o.parent = parent
        o.matrix_parent_inverse = Matrix()
        pw = parent.matrix_world if parent else Matrix()
        o.matrix_basis = pw.inverted() @ frame
        bpy.context.view_layer.update()

    def piece(self, name, sources, frame=None, parent=None):
        """Create a mesh object from a list of (src_obj, face_mask|None), baked into part
        space and then expressed in local `frame` (part-space Matrix, default identity)."""
        frame = frame or Matrix()
        parent = parent or self.model
        bm_out = bmesh.new()
        me = bpy.data.meshes.new(name)
        for src, mask in sources:
            tmp = src.data.copy()
            if mask is not None:
                bm = bmesh.new(); bm.from_mesh(tmp); bm.faces.ensure_lookup_table()
                kill = [f for f in bm.faces if not mask[f.index]]
                bmesh.ops.delete(bm, geom=kill, context='FACES')
                bm.to_mesh(tmp); bm.free()
            tmp.transform(frame.inverted() @ self.M @ src.matrix_world)
            for m in tmp.materials:
                if m and m.name not in [x.name for x in me.materials]:
                    me.materials.append(m)
            # remap material indices to `me`
            remap = [[x.name for x in me.materials].index(m.name) if m else 0 for m in tmp.materials]
            for poly in tmp.polygons:
                poly.material_index = remap[poly.material_index] if remap else 0
            bm_out.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        bm_out.to_mesh(me); bm_out.free()
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.pi
        o = bpy.data.objects.new(name, me)
        self.coll.objects.link(o)
        self.place(o, frame, parent)
        return o

    def reparent(self, o, parent):
        w = o.matrix_world.copy()
        self.place(o, w, parent)

    def node(self, name, pos, direction, size):
        self.nodes[name] = (Vector(pos), Vector(direction).normalized(), size)

    # --------------------------------------------------------------- animation
    def key(self, clip, obj, frame, **props):
        """Record keyframes. props: location=Vector, rotation_quaternion=Quaternion, scale=Vector"""
        self.clips.setdefault(clip, {}).setdefault(obj.name, []).append((frame, props))

    def bake_clips(self, rest_frame=0):
        for clip, objs in self.clips.items():
            for oname, keys in objs.items():
                o = bpy.data.objects[oname]
                o.rotation_mode = 'QUATERNION'
                if not o.animation_data:
                    o.animation_data_create()
                act = bpy.data.actions.new(f"{clip}.{oname}")
                o.animation_data.action = act
                for frame, props in sorted(keys, key=lambda k: k[0]):
                    for prop, val in props.items():
                        setattr(o, prop, val)
                        o.keyframe_insert(prop, frame=frame)
                for fc in act.fcurves:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'BEZIER'
                        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
                    fc.update()
                o.animation_data.action = None
                tr = o.animation_data.nla_tracks.new()
                tr.name = clip
                tr.strips.new(clip, int(act.frame_range[0]), act)
        sc = bpy.context.scene
        sc.render.fps = FPS
        sc.frame_start = 0
        sc.frame_set(rest_frame)

    # --------------------------------------------------------------- materials
    def material(self, src_name, tex=None, spec=1.0, shininess=0.27):
        """KSP/Bumped Specular material named after the glTF one."""
        key = src_name
        if key in self.mats:
            return self.mats[key]
        tex = tex or src_name
        m = bpy.data.materials.new('gt_' + src_name)
        mp = m.mumatprop
        mp.shaderName = 'KSP/Bumped Specular'
        # HabTech .mu files reference textures as '<name>.png' even though the files are .dds
        for nm, t, isn in (('_MainTex', f'{tex}_diff.png', False), ('_BumpMap', (f'{tex}_nrm' if not tex.startswith('gt_') else 'gt_flat_nrm') + '.png', True)):
            it = mp.texture.properties.add(); it.name = nm; it.tex = t; it.type = False
            it.scale = (1, 1); it.offset = (0, 0)
        for nm, v in (('_Color', (1, 1, 1, 1)), ('_SpecColor', (spec, spec, spec, 1)), ('_RimColor', (0, 0, 0, 0)),
                      ('_TemperatureColor', (0, 0, 0, 0)), ('_BurnColor', (1, 1, 1, 1))):
            it = mp.color.properties.add(); it.name = nm; it.value = v
        for nm, v in (('_Shininess', shininess), ('_Opacity', 1.0), ('_RimFalloff', 0.1)):
            it = mp.float3.properties.add(); it.name = nm; it.value = v
        self.mats[key] = m
        return m

    def assign_ksp_materials(self, texmap):
        """Replace glTF materials on every mesh in the part with KSP materials.
        texmap: glTF material name -> texture base name (None = drop faces)."""
        for o in self.coll.objects:
            if o.type != 'MESH' or o.muproperties.collider != 'MU_COL_NONE':
                continue
            me = o.data
            for i, m in enumerate(me.materials):
                if m is None or m.name.startswith('gt_'):
                    continue
                base = m.name.split('.')[0]
                me.materials[i] = self.material(base, texmap.get(base, base))

    # --------------------------------------------------------------- colliders
    def hull_collider(self, name, points, parent=None, max_faces=200):
        """Convex mesh collider from a cloud of part-space points."""
        bm = bmesh.new()
        for p in points:
            bm.verts.new(p)
        bmesh.ops.convex_hull(bm, input=bm.verts)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        o = bpy.data.objects.new(name, me)
        self.coll.objects.link(o)
        if len(me.polygons) > max_faces:
            mod = o.modifiers.new('dec', 'DECIMATE'); mod.ratio = max_faces / len(me.polygons)
            dg = bpy.context.evaluated_depsgraph_get()
            me2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            o.modifiers.clear(); o.data = me2
        self.place(o, Matrix(), parent or self.model)
        o.muproperties.collider = 'MU_COL_MESH'
        o.muproperties.isConvex = True
        o.hide_render = True
        return o

    # --------------------------------------------------------------- export
    def export(self, path):
        from io_object_mu.export_mu.export import export_object
        for o in list(self.coll.objects):
            if o.type == 'MESH' and o.muproperties.collider == 'MU_COL_NONE' and not o.hide_render:
                double_side(self, o)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mu = export_object(self.root, path)
        for m in getattr(mu, 'messages', []):
            print('EXPORT MSG', m)
        return mu

    def cfg_nodes(self):
        """node_stack lines in Unity coords."""
        out = []
        for n, (p, d, s) in self.nodes.items():
            out.append(f"\tnode_stack_{n} = {p.x:.4f}, {p.z:.4f}, {p.y:.4f}, {d.x:.4f}, {d.z:.4f}, {d.y:.4f}, {s}")
        return "\n".join(out)


# ------------------------------------------------------------------- geometry
def world_verts(o):
    mw = o.matrix_world
    co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return (np.c_[co, np.ones(len(co))] @ np.array(mw).T)[:, :3]


def face_islands(o, tol=1e-4):
    """Connected face islands (welding coincident verts). Returns (labels per face, n)."""
    me = o.data
    co = world_verts(o)
    key = np.round(co / tol).astype(np.int64)
    _, vid = np.unique(key, axis=0, return_inverse=True)
    vid = vid.ravel()
    parent = list(range(len(me.polygons)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    owner = {}
    for f in me.polygons:
        for v in f.vertices:
            k = vid[v]
            if k in owner:
                ra, rb = find(owner[k]), find(f.index)
                if ra != rb:
                    parent[ra] = rb
            else:
                owner[k] = f.index
    roots = np.array([find(i) for i in range(len(me.polygons))])
    _, labels = np.unique(roots, return_inverse=True)
    return labels, labels.max() + 1


def face_centres(o):
    me = o.data
    c = np.empty(len(me.polygons) * 3); me.polygons.foreach_get('center', c)
    c = c.reshape(-1, 3)
    mw = np.array(o.matrix_world)
    return (np.c_[c, np.ones(len(c))] @ mw.T)[:, :3]


def island_select(o, pred, max_size=None):
    """Face mask selecting whole islands whose (centroid, bbox_min, bbox_max) satisfy pred."""
    labels, n = face_islands(o)
    fc = face_centres(o)
    mask = np.zeros(len(labels), bool)
    for i in range(n):
        sel = labels == i
        pts = fc[sel]
        mn, mx = pts.min(0), pts.max(0)
        if max_size and (mx - mn).max() > max_size:
            continue
        if pred(pts.mean(0), mn, mx):
            mask |= sel
    return mask


def frame_from_axes(origin, x=None, y=None, z=None):
    """Right-handed frame matrix from two given axes (part space)."""
    if z is not None and y is not None:
        z = Vector(z).normalized(); y = (Vector(y) - Vector(y).dot(z) * z).normalized(); x = y.cross(z)
    elif z is not None and x is not None:
        z = Vector(z).normalized(); x = (Vector(x) - Vector(x).dot(z) * z).normalized(); y = z.cross(x)
    elif x is not None and y is not None:
        x = Vector(x).normalized(); y = (Vector(y) - Vector(y).dot(x) * x).normalized(); z = x.cross(y)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def port_cap(part, hull_obj, centre_st, axis_st, r_search=1.15, name='cap'):
    """Recessed docking-port seat where a model NDS port was removed.

    The node goes on the plane where the original NDS port's base sat (from the NDS
    meshes still in the source scene), so Benjee10's B10_NDS / B10_NDS_passive (the
    HabTech-family port, same size at HabTech scale) sits exactly where the model's
    own port did. A thin floor disc closes the bore at that depth; its edge tucks into
    the bore wall, leaving the collar lip visible around the port.
    Returns (node_pos_part, node_dir_part)."""
    c_st = np.array(centre_st, float); n_st = np.array(axis_st, float)
    # original port base plane (station metres, along the outward axis)
    t_base = None
    for o in bpy.data.objects:
        if not (o.name.startswith('NDS') and o.type == 'MESH'):
            continue
        v = world_verts(o); rel = v - c_st; t = rel @ n_st
        rad = np.linalg.norm(rel - np.outer(t, n_st), axis=1)
        if np.median(rad) < 1.3 and abs(np.median(t)) < 1.0:
            t_base = t.min() if t_base is None else min(t_base, t.min())
    if t_base is None:
        t_base = -0.09
    # bore radius at that depth (hull verts forming the opening's wall)
    hv = world_verts(hull_obj); rel = hv - c_st; t = rel @ n_st
    rad = np.linalg.norm(rel - np.outer(t, n_st), axis=1)
    wall = (np.abs(t - t_base) < 0.15) & (rad > 0.4) & (rad < 1.4)
    bore = rad[wall].min() if wall.any() else 0.8
    r_floor = (bore + 0.07) * SCALE          # edge tucks into the bore wall, closing any hairline gap
    # collar top: highest hull point around the opening (lip of the docking collar)
    near = (rad < 1.15) & (t > t_base - 0.2) & (t < 0.8)
    t_top = max(t[near].max(), t_base + 0.06) if near.any() else t_base + 0.1
    c = part.p(c_st); n = part.d(n_st)
    seat = Vector(c) + Vector(n) * (t_base * SCALE)
    depth = 0.05 * SCALE
    fr = frame_from_axes(seat, z=n, x=Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0)))
    bm = bmesh.new()
    # floor disc
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=r_floor, radius2=r_floor, depth=depth)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -depth / 2 - 0.002))
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for l in f.loops:
            x, y, zz = l.vert.co
            l[uv].uv = (0.5 + 0.5 * x / r_floor, 0.5 + 0.5 * y / r_floor)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(part.material('gt_plate', tex='gt_plate', spec=0.4, shininess=0.25))
    o = bpy.data.objects.new(name, me); part.coll.objects.link(o)
    part.place(o, fr, part.model)
    print(f"  {name}: seat t={t_base:+.3f} m(real) below hatch centre, bore r={bore:.3f} m(real)")
    return seat, n


def remove_faces(o, mask):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if mask[f.index]], context='FACES')
    bm.to_mesh(o.data); bm.free()


def bisect_mesh_object(o, plane_co, plane_no):
    """Split object o (station frame) into two objects along a plane. Returns (below, above)."""
    out = []
    for keep_above in (False, True):
        me = o.data.copy()
        bm = bmesh.new(); bm.from_mesh(me)
        mw = o.matrix_world
        co = mw.inverted() @ Vector(plane_co)
        no = (mw.inverted().to_3x3().transposed().inverted() @ Vector(plane_no)).normalized() if False else (mw.to_3x3().inverted().transposed() @ Vector(plane_no)).normalized()
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_inner=keep_above, clear_outer=not keep_above)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(o.name + ('_hi' if keep_above else '_lo'), me)
        ob.matrix_world = mw.copy()
        bpy.context.scene.collection.objects.link(ob)
        out.append(ob)
    return out


# ------------------------------------------------------------- slicing / re-framing
def slab(part, name, src, axis_st, lo, hi, frame=None, parent=None, mask=None):
    """Piece of `src` between station-space planes dot(p, axis)=lo..hi (cut faces filled)."""
    o = part.piece(name, [(src, mask)], Matrix(), part.model)
    n = part.d(axis_st)
    # plane offsets in part space: p_part = M p_st ; dot(p_st, a) = c  ->  point on plane
    a = Vector(axis_st).normalized()
    bm = bmesh.new(); bm.from_mesh(o.data)
    for c, clear_inner in ((lo, True), (hi, False)):
        if c is None:
            continue
        co = part.p(a * c)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=n,
                                   clear_inner=clear_inner, clear_outer=not clear_inner)
        edges = [e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            try:
                bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
            except Exception as ex:
                print('fill failed', name, ex)
    bm.to_mesh(o.data); bm.free()
    if frame is not None or parent is not None:
        reframe(part, o, frame or Matrix(), parent or part.model)
    return o


def reframe(part, o, frame, parent):
    """Move object's origin/orientation to `frame` (part space) keeping geometry in place."""
    cur = o.matrix_world.copy()
    o.data.transform(frame.inverted() @ cur)
    part.place(o, frame, parent)


def accordion(part, clip, name, src, span_st, hinge_axis_st, cuts, root_lo, tip_hi, thick_dir_st, half_thick,
              n_frames, mask=None, parent=None):
    """Split a flat radiator wing into panels at `cuts` (station offsets along span_st) and
    build a zig-zag fold: every panel after the root folds 180deg onto the one before it.
    Returns the root panel object."""
    edges = [root_lo] + list(cuts) + [tip_hi]
    span = part.d(span_st); hax = part.d(hinge_axis_st); tdir = part.d(thick_dir_st)
    parent = parent or part.model
    prev = None; panels = []
    for k in range(len(edges) - 1):
        lo, hi = edges[k], edges[k + 1]
        if k == 0:
            o = slab(part, f'{name}_p0', src, span_st, lo, hi, mask=mask)
            # root origin: panel centre line, at its innermost end along the span
            vs = np.array([v.co[:] for v in o.data.vertices])
            cen = Vector(vs.mean(0))
            inner = (vs @ np.array(span)).min()
            cen = cen + span * (inner - cen.dot(span))
            fr = frame_from_axes(cen, z=span, x=hax)
            reframe(part, o, fr, parent)
        else:
            o = slab(part, f'{name}_p{k}', src, span_st, lo, hi, mask=mask)
            side = 1 if k % 2 else -1
            vs = np.array([v.co[:] for v in o.data.vertices])
            mid = Vector(vs.mean(0))
            # hinge line: on the cut plane, on one face of the panel (alternating), along hax
            cut_pt = part.p(Vector(span_st).normalized() * lo)
            hp = mid + span * (cut_pt - mid).dot(span) + tdir * side * half_thick * SCALE
            fr = frame_from_axes(hp, z=span, x=hax)
            reframe(part, o, fr, prev)
            # +angle about local X swings the panel toward local -Y; fold toward the hinge face
            ydir = span.cross(hax)
            sgn = -1 if ydir.dot(tdir) > 0 else 1
            ang = math.radians(178 * side * sgn)
            # zig-zag: stowed folded, deployed flat; staged so outer panels open last
            t0 = int(n_frames * 0.15 * (k - 1)); t1 = int(n_frames * (0.55 + 0.15 * (k - 1)))
            t1 = min(t1, n_frames)
            q_st = Quaternion(Vector((1, 0, 0)), ang)
            part.key(clip, o, 0, rotation_quaternion=q_st)
            if t0 > 0:
                part.key(clip, o, t0, rotation_quaternion=q_st)
            for s in range(1, 6):
                f = t0 + (t1 - t0) * s / 6
                part.key(clip, o, int(round(f)), rotation_quaternion=Quaternion(Vector((1, 0, 0)), ang * (1 - s / 6)))
            part.key(clip, o, t1, rotation_quaternion=Quaternion())
            if t1 < n_frames:
                part.key(clip, o, n_frames, rotation_quaternion=Quaternion())
        panels.append(o); prev = o
    return panels


def wing_root(o, w):
    """Station-space root point of the radiator wing of `o` on the station +Z (w=1) or -Z (w=-1)
    side: centre of the wing's footprint, at its innermost Z."""
    v = world_verts(o)
    v = v[v[:, 2] * w > 0]
    return ((v[:, 0].min() + v[:, 0].max()) / 2, (v[:, 1].min() + v[:, 1].max()) / 2, w * np.abs(v[:, 2]).min())


def airlock(part, body, direction, z, size=0.6):
    """EVA hatch trigger: box collider tagged 'Airlock' just outside the hull on `direction`."""
    d = Vector(direction).normalized()
    co = np.array([v.co[:] for v in body.data.vertices])
    near = np.abs(co[:, 2] - z) < 0.35
    perp = np.linalg.norm(co[:, :2] - np.outer(co[:, :2] @ np.array(d[:2]), np.array(d[:2])), axis=1) < 0.35
    reach = (co[near & perp][:, :2] @ np.array(d[:2])).max()
    pos = Vector((d.x * (reach + 0.1), d.y * (reach + 0.1), z))
    o = part.empty('airlock', frame_from_axes(pos, z=(0, 0, 1), x=(1, 0, 0)), part.model)
    mp = o.muproperties
    mp.collider = 'MU_COL_BOX'; mp.isTrigger = True; mp.tag = 'Airlock'
    mp.size = (size, size, size); mp.center = (0, 0, 0)
    print(f"  airlock at {tuple(round(x, 3) for x in pos)}")
    return o


# ----------------------------------------------------------- double-sided export
MAX_LOOPS = 60000   # every loop may become its own Unity vertex; Unity limit is 65534


def double_side(part, o):
    """Give `o` back faces: append a reversed copy of every face with negated normals
    (the source glTF is all doubleSided; KSP shaders cull back faces). Meshes that would
    exceed the vertex limit are split into child chunks with identity transforms."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.use_auto_smooth = True
    me.calc_normals_split()
    L = len(me.loops); P = len(me.polygons)
    if P == 0:
        return
    vidx = np.empty(L, np.int64); me.loops.foreach_get('vertex_index', vidx)
    nrm = np.empty(L * 3); me.loops.foreach_get('normal', nrm); nrm = nrm.reshape(-1, 3)
    mat = np.empty(P, np.int64); me.polygons.foreach_get('material_index', mat)
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
    uvs = []
    for lay in me.uv_layers:
        a = np.empty(L * 2); lay.data.foreach_get('uv', a); uvs.append((lay.name, a.reshape(-1, 2)))
    tri = np.arange(L).reshape(-1, 3)                 # all triangles now
    rev = tri[:, ::-1]
    loops_all = np.concatenate([tri, rev])            # indices into the old loop arrays
    flip = np.concatenate([np.ones(P), -np.ones(P)])
    mats_all = np.concatenate([mat, mat])
    n_tri = len(loops_all)
    per_chunk = MAX_LOOPS // 3
    # One material per mesh object, like HabTech: KSP does not pair multi-material
    # renderers with their submeshes reliably. Then split by size for the vertex limit.
    cen = co.reshape(-1, 3)[vidx[loops_all[:, 0]]]
    chunks = []
    for m in np.unique(mats_all):
        idx = np.nonzero(mats_all == m)[0]
        idx = idx[np.lexsort((cen[idx, 1], cen[idx, 0], cen[idx, 2]))]
        chunks += [idx[i:i + per_chunk] for i in range(0, len(idx), per_chunk)]
    src_mats = list(me.materials)
    targets = [o]
    for k in range(1, len(chunks)):
        c = bpy.data.objects.new(f'{o.name}_part{k}', bpy.data.meshes.new(f'{o.name}_part{k}'))
        part.coll.objects.link(c)
        part.place(c, o.matrix_world.copy(), o)
        targets.append(c)
    for tgt, sel in zip(targets, chunks):
        lsel = loops_all[sel]                         # (n, 3) old-loop indices
        used = np.unique(mats_all[sel])
        remap = {m: i for i, m in enumerate(used)}
        new = bpy.data.meshes.new(tgt.name + '_ds')
        new.vertices.add(len(co) // 3); new.vertices.foreach_set('co', co)
        n = len(sel)
        new.loops.add(n * 3); new.polygons.add(n)
        new.loops.foreach_set('vertex_index', vidx[lsel.ravel()])
        new.polygons.foreach_set('loop_start', np.arange(0, n * 3, 3))
        new.polygons.foreach_set('loop_total', np.full(n, 3))
        new.polygons.foreach_set('material_index', np.array([remap[m] for m in mats_all[sel]]))
        new.polygons.foreach_set('use_smooth', np.ones(n, bool))
        for name, a in uvs:
            lay = new.uv_layers.new(name=name)
            lay.data.foreach_set('uv', a[lsel.ravel()].ravel())
        new.update()
        for m in used:
            new.materials.append(src_mats[int(m)])
        nn = nrm[lsel.ravel()] * np.repeat(flip[sel], 3)[:, None]
        new.use_auto_smooth = True
        new.normals_split_custom_set([tuple(v) for v in nn])
        # drop vertices no face uses
        bm = bmesh.new(); bm.from_mesh(new)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(new); bm.free()
        new.use_auto_smooth = True
        tgt.data = new
    if me.users == 0:
        bpy.data.meshes.remove(me)
    return targets


def arm_mount(base_obj):
    """(position, outward direction) in station space of a robotic arm's base segment:
    the base mesh extends from its origin along one local axis, away from the hull."""
    co = np.array([v.co[:] for v in base_obj.data.vertices])
    ext = [(abs(co[:, i].max()) - abs(co[:, i].min()), i) for i in range(3)]
    val, ax = max(ext, key=lambda e: abs(e[0]))
    local = Vector((0, 0, 0)); local[ax] = 1 if val > 0 else -1
    mw = base_obj.matrix_world
    return mw.translation.copy(), (mw.to_3x3().normalized() @ local).normalized()
