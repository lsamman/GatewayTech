"""Offline checks for the GatewayTech package, since KSP itself can't run here unattended:
  * every cfg parses (balanced braces)
  * every PART's MODEL exists; every texture a .mu references exists as a DDS next to it
  * transform / animation names used by modules exist in the .mu
  * module names exist in installed assemblies
  * every :NEEDS[] names a known mod (and says whether its folder is installed)
  * every @PART[] in Compatibility/ names a real GatewayTech part; patch transform names exist in some model
  * every agency logo texture exists
usage: python3 -I scripts/lint.py <GameData/GatewayTech> [installed GameData]"""
import os, re, sys, glob
A = os.path.expanduser('~/Applications/blender-3.6/3.6/scripts/addons/io_object_mu')
sys.path.insert(0, A)
from mu import Mu
root = sys.argv[1]
gd = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser('~/.local/share/Steam/steamapps/common/Kerbal Space Program Modded SOL/GameData')
errs = []; warns = []; infos = []
dll = os.path.join(os.path.dirname(gd), 'KSP_x64_Data', 'Managed', 'Assembly-CSharp.dll')
STOCK = open(dll, 'rb').read() if os.path.exists(dll) else b''
extra = b''
for d in ('B9PartSwitch', 'Waterfall', 'SystemHeat', 'ConnectedLivingSpace', 'KSPCommunityPartModules'):
    for f in glob.glob(os.path.join(gd, d, '**', '*.dll'), recursive=True):
        extra += open(f, 'rb').read()
ASMS = STOCK + extra
# mod name as written in :NEEDS[] -> the folder it installs into under GameData
MODS = {
    'ConnectedLivingSpace': 'ConnectedLivingSpace',
    'CommunityTechTree': 'CommunityTechTree',
    'SystemHeat': 'SystemHeat',
    'USILifeSupport': 'UmbraSpaceIndustries/LifeSupport',
    'TacLifeSupport': 'TacLifeSupport',
    'Snacks': 'Snacks',
    'Waterfall': 'Waterfall',
    'KSPRescuePodFix': 'KSPRescuePodFix',
    'VABOrganizer': 'VABOrganizer',
}


def known_module(n):
    return n.encode() in ASMS or n.encode('utf-16-le') in ASMS


def walk(o, names, anims):
    names.add(o.transform.name)
    if hasattr(o, 'animation'):
        for c in o.animation.clips:
            anims.add(c.name)
    for c in o.children:
        walk(c, names, anims)


def verts(o, f):
    if hasattr(o, 'shared_mesh') and len(o.shared_mesh.verts) > 65000:
        errs.append(f'{os.path.basename(f)}: {o.transform.name} has {len(o.shared_mesh.verts)} verts')
    for c in o.children:
        verts(c, f)


mu_info = {}
for f in glob.glob(os.path.join(root, '**', '*.mu'), recursive=True):
    m = Mu()
    if not m.read(f):
        errs.append(f'unreadable mu {f}'); continue
    names, anims = set(), set()
    walk(m.obj, names, anims)
    mu_info[os.path.splitext(os.path.relpath(f, os.path.dirname(root)))[0]] = (names, anims)
    d = os.path.dirname(f)
    for t in m.textures:
        base = os.path.splitext(t.name)[0]
        if not any(os.path.exists(os.path.join(d, base + e)) for e in ('.dds', '.png')):
            errs.append(f'{os.path.basename(f)}: missing texture {t.name}')
    verts(m.obj, f)

all_names = set().union(*[v[0] for v in mu_info.values()]) if mu_info else set()
TF = {'pivotName', 'raycastTransformName', 'thrustVectorTransformName', 'transformName', 'gimbalTransformName',
      'lightName', 'overrideParentTransform', 'RCSTransformName', 'thrustTransformName'}
part_names = set()
for c in glob.glob(os.path.join(root, 'Parts', '*.cfg')):
    part_names |= set(re.findall(r'^\s*name\s*=\s*(\S+)', re.sub(r'//.*', '', open(c, errors='replace').read()), re.M)[:1])

for c in glob.glob(os.path.join(root, '**', '*.cfg'), recursive=True):
    bn = os.path.basename(c)
    t = open(c, errors='replace').read()
    s = re.sub(r'//.*', '', t)
    if s.count('{') != s.count('}'):
        errs.append(f'{bn}: unbalanced braces {s.count("{")} vs {s.count("}")}')
    for ln, line in enumerate(s.splitlines(), 1):
        l = line.strip()
        if l and l not in ('{', '}') and '=' not in l and not re.match(r'^[@!%+\-]?\w\S*(\s*\{\})?$', l):
            errs.append(f'{bn}:{ln}: cannot parse line: {l}')
    # :NEEDS[]
    for grp in re.findall(r':NEEDS\[([^\]]*)\]', s):
        for n in re.split(r'[,&|]', grp):
            n = n.strip().lstrip('!')
            if not n:
                continue
            if n not in MODS:
                errs.append(f'{bn}: :NEEDS[{n}] is not a known mod name')
            elif os.path.isdir(os.path.join(gd, MODS[n])):
                infos.append(f'NEEDS {n}: installed ({MODS[n]})')
            else:
                infos.append(f'NEEDS {n}: NOT installed ({MODS[n]}); patch unchecked in-game')
    # agency logos
    for k, v in re.findall(r'^\s*(logoURL|logoScaledURL)\s*=\s*(\S+)', s, re.M):
        base = os.path.join(os.path.dirname(root), v)
        if not any(os.path.exists(base + e) for e in ('.dds', '.png', '.jpg', '.tga')):
            errs.append(f'{bn}: {k} texture {v} not found')
    # patches: target parts and transforms
    for tgt in re.findall(r'^\s*@PART\[([^\]]+)\]', s, re.M):
        for n in re.split(r'[|,]', tgt):
            n = n.strip()
            if n and '*' not in n and n not in part_names:
                errs.append(f'{bn}: @PART[{n}] is not a GatewayTech part')
    for tgt in re.findall(r'^\s*part\s*=\s*(\S+)', s, re.M) if 'RESCUE_POD_TYPES' in s else []:
        if tgt not in part_names:
            errs.append(f'{bn}: part = {tgt} is not a GatewayTech part')
    for n in re.findall(r'MODULE\s*\{\s*name\s*=\s*(\S+)', s):
        if not known_module(n):
            warns.append(f'{bn}: module {n} not found in scanned assemblies')
    # part cfgs
    models = [m_ for m_ in re.findall(r'model\s*=\s*(\S+)', s)]
    allnames = set(); allanims = set()
    for m_ in models:
        if m_ in mu_info:
            allnames |= mu_info[m_][0]; allanims |= mu_info[m_][1]
        elif not os.path.exists(os.path.join(gd, m_ + '.mu')):
            errs.append(f'{bn}: model not found {m_}')
    if models and all(m_ in mu_info for m_ in models):
        for k, v in re.findall(r'^\s*(\w+)\s*=\s*([^\n]+)$', s, re.M):
            v = v.strip()
            if k == 'animationName' and v not in allanims:
                errs.append(f'{bn}: animation {v} not in model {sorted(allanims)}')
            if k in TF:
                for name in re.split(r'\s*,\s*', v):
                    if name and name not in allnames:
                        errs.append(f'{bn}: {k} = {name} not in model')
        # every IVA / resource sanity: mass and cost present
        for need in ('mass', 'cost', 'TechRequired', 'title'):
            if not re.search(rf'^\s*{need}\s*=', s, re.M):
                errs.append(f'{bn}: missing {need}')
    elif not models:
        for k, v in re.findall(r'^\s*(overrideParentTransform)\s*=\s*([^\n]+)$', s, re.M):
            if v.strip() not in all_names:
                errs.append(f'{bn}: {k} = {v.strip()} not in any model')
if not STOCK:
    warns.append('stock assembly not found, module names unchecked')
for i in sorted(set(infos)):
    print('INFO', i)
for w in sorted(set(warns)):
    print('WARN', w)
for e in errs:
    print('ERROR', e)
print(f'lint: {len(mu_info)} models, {len(errs)} errors, {len(set(warns))} warnings')
sys.exit(1 if errs else 0)
