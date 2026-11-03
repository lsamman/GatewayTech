"""Canadarm3-style large arm and the small dexterous arm, each a surface-attach part with an
unfold/stow animation. The fold pose is found by a grid search over the arm's own joint axes.
blender -b src/gateway_source.blend -P scripts/build_arms.py -- <outdir>"""
import bpy, sys, os, json, math, itertools
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from mathutils import Vector, Quaternion, Matrix
import gt_lib as G

out, which = sys.argv[sys.argv.index('--') + 1:][:2]
G.enable_addon()
S = G.SCALE


def chain(prefix, n):
    return [bpy.data.objects[f'{prefix}{i}'] for i in range(1, n + 1)]


def build(partname, segs, mode, joints, search):
    """mode 'fold': model pose = deployed, search pose minimising height = stowed.
       mode 'reach': model pose = stowed, search pose maximising reach = deployed."""
    base = segs[0]
    bw = base.matrix_world
    # outward axis of the base = local axis along which the base mesh extends from 0
    co = np.array([v.co[:] for v in base.data.vertices])
    ext = [(abs(co[:, i].max()) - abs(co[:, i].min()), i) for i in range(3)]
    ax_i = max(ext, key=lambda e: abs(e[0]))
    out_local = Vector([0, 0, 0]); out_local[ax_i[1]] = 1 if ax_i[0] > 0 else -1
    # part rotation: base local out-axis -> part +Z
    rot_b = bw.to_quaternion()
    out_st = rot_b @ out_local
    any_perp = rot_b @ Vector([1, 0, 0] if ax_i[1] != 0 else [0, 1, 0])
    F = G.frame_from_axes(Vector(), z=out_st, x=any_perp).to_3x3()
    P = G.Part(partname, F.transposed(), bw.translation)
    pieces = []
    parent = P.model
    for sg in segs:
        mw = sg.matrix_world
        fr = (P.R @ Matrix.Translation(mw.translation - bw.translation)).to_3x3()  # unused
        loc = P.p(mw.translation)
        rot = (P.R.to_3x3() @ mw.to_3x3().normalized())
        frame = rot.to_4x4(); frame.translation = loc
        pc = P.piece(sg.name.replace(' ', '_'), [(sg, None)], frame, parent)
        pieces.append(pc); parent = pc
    # joint axes (in each piece's parent frame) from the rest rotations
    jinfo = []
    for j in joints:
        pc = pieces[j]
        q0 = pc.matrix_basis.to_quaternion()
        axis = q0.axis if q0.angle > 1e-3 else Vector((1, 0, 0))
        jinfo.append((pc, q0, axis.normalized()))
    # sample points per piece (bbox corners + vertex subsample), in piece-local coords
    samples = []
    for pc in pieces:
        v = np.array([x.co[:] for x in pc.data.vertices])
        samples.append(v[:: max(1, len(v) // 60)])

    def evaluate(angles):
        for (pc, q0, ax), a in zip(jinfo, angles):
            pc.rotation_mode = 'QUATERNION'
            pc.rotation_quaternion = q0 @ Quaternion(ax, a)
        bpy.context.view_layer.update()
        pts = []
        for pc, smp in zip(pieces, samples):
            m = np.array(pc.matrix_world)
            pts.append(np.c_[smp, np.ones(len(smp))] @ m.T)
        pts = np.concatenate(pts)[:, :3]
        return pts

    rest = evaluate([0] * len(jinfo))
    floor = min(rest[:, 2].min(), 0.0) - 0.02
    best = None
    for angles in itertools.product(*search):
        a = [math.radians(x) for x in angles]
        pts = evaluate(a)
        if pts[:, 2].min() < floor:              # keep clear of the mounting surface
            continue
        if mode == 'fold':
            score = pts[:, 2].max() + 0.15 * np.linalg.norm(pts[:, :2], axis=1).max()
        else:
            tip = pts[-len(samples[-1]):].mean(0)
            score = -np.linalg.norm(tip)
        if best is None or score < best[0]:
            best = (score, a)
    print(partname, 'best', [round(math.degrees(x)) for x in best[1]], 'score', round(best[0], 3))
    evaluate([0] * len(jinfo))
    clip = 'armDeploy'; N = 10 * G.FPS
    for k in range(0, 11):
        t = k / 10; e = t * t * (3 - 2 * t)
        # frame 0 = stowed, frame N = deployed
        for (pc, q0, ax), a in zip(jinfo, best[1]):
            if mode == 'fold':
                ang = a * (1 - e)      # stowed = searched pose, deployed = model pose
            else:
                ang = a * e            # stowed = model pose, deployed = searched pose
            P.key(clip, pc, int(N * t), rotation_quaternion=q0 @ Quaternion(ax, ang))
    # materials, collider on the base only
    P.assign_ksp_materials({})
    bv = np.array([v.co[:] for v in pieces[0].data.vertices])
    col = P.hull_collider('collider_base', bv[::2], parent=pieces[0])
    P.bake_clips(0)
    P.export(os.path.join(out, f'{partname}.mu'))
    P.node('bottom', Vector((0, 0, 0)), Vector((0, 0, -1)), 0)
    json.dump({'nodes': {k: [list(v[0]), list(v[1]), v[2]] for k, v in P.nodes.items()},
               'clips': {clip: N}, 'reach': float(np.abs(rest).max())},
              open(os.path.join(out, f'{partname}.json'), 'w'), indent=1)
    return P


rng = lambda a, b, s: list(range(a, b + 1, s))
if which == 'big':
    build('gt_Canadarm3', chain('Big Arm_', 8), 'fold', joints=[3, 4, 5],
          search=[rng(-150, 150, 10), rng(-180, 180, 10), rng(-120, 120, 20)])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_Canadarm3.blend'))
else:
    for o in chain('Little_Arm_', 9):
        q = o.matrix_basis.to_quaternion()
        print('little joint', o.name, round(math.degrees(q.angle)), tuple(round(x, 2) for x in q.axis))
    build('gt_DexArm', chain('Little_Arm_', 9), 'reach', joints=[3, 5, 6],
          search=[rng(-90, 90, 30), rng(-150, 150, 10), rng(-150, 150, 10)])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'gt_DexArm.blend'))
