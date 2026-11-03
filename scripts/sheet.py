import sys, glob
from PIL import Image
pref, out = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(pref + '_f*.png'))
ims = [Image.open(f).resize((400, 325)) for f in fs]
cols = 4; rows = (len(ims) + cols - 1) // cols
s = Image.new('RGB', (400 * cols, 325 * rows))
for i, im in enumerate(ims): s.paste(im, ((i % cols) * 400, (i // cols) * 325))
s.save(out)
