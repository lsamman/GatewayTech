"""Save every packed GLB image to build/tex_src/<name>.png"""
import bpy, sys, os
out = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out, exist_ok=True)
for im in bpy.data.images:
    if im.name.startswith('NDS') or not im.has_data and not im.packed_file: continue
    nm = im.name.replace('.png', '').split('-')[0]   # 'HALO_main_BaseColor.png-HALO_main_Alpha' -> 'HALO_main_BaseColor'
    im.filepath_raw = f"{out}/{nm}.png"; im.file_format = 'PNG'; im.save()
