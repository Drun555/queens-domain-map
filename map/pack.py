#!/usr/bin/env python3
"""Regroupe les tranches de hauteur d'une zone en une image par étage (fusionné), pour limiter le nombre de fichiers."""
import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
import json, os, sys, glob
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assemble import merge_floors, MIN_GAP

def pack(src, dst):
    meta = json.load(open(os.path.join(src, 'meta.json')))
    fl = merge_floors([dict(f) for f in meta['floors']], meta.get('mergeGap', MIN_GAP))
    bands = sorted(meta['bands'], key=lambda b: b['z'])
    groups = [[] for _ in fl]
    for b in bands:
        m = (b['z'] + b['z1']) / 2
        k = next((i for i, f in enumerate(fl) if f['z0'] <= m < f['z1']), 0 if m < fl[0]['z0'] else len(fl) - 1)
        groups[k].append(b)
    os.makedirs(dst, exist_ok=True)
    for f in glob.glob(os.path.join(dst, '*.webp')): os.remove(f)
    out = []
    for k, (f, g) in enumerate(zip(fl, groups)):
        if not g: continue
        im = Image.new('RGBA', (meta['w'], meta['h']), (0, 0, 0, 0))
        for b in g: im.alpha_composite(Image.open(os.path.join(src, b['f'])).convert('RGBA'))
        if im.getbbox() is None: continue
        name = 'f%02d.webp' % k
        im.save(os.path.join(dst, name), 'WEBP', quality=88, method=6)
        out.append({'f': name, 'z': min(f['z0'], g[0]['z']), 'z1': max(f['z1'], g[-1]['z1'])})
    meta['bands'] = out; meta['floors'] = fl
    json.dump(meta, open(os.path.join(dst, 'meta.json'), 'w'))
    return len(bands), len(out)

if __name__ == '__main__':
    for z in sys.argv[1:]:
        n0, n1 = pack(ROOT + '/render/tiles_tex/' + z, ROOT + '/map/site/tiles/' + z)
        print(z, n0, '->', n1)
