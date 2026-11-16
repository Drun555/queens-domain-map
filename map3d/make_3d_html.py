#!/usr/bin/env python3
"""Génère site/3d.html : le gabarit viewer3d_site.html + la liste des zones (zlist.json, écrite par place3d.py)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('QD_ROOT', os.path.dirname(HERE))
tpl = open(os.path.join(HERE, 'viewer3d_site.html'), encoding='utf-8').read()
zl = json.load(open(os.path.join(HERE, 'zlist.json'), encoding='utf-8'))
out = os.path.join(ROOT, 'map', 'site', '3d.html')
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w', encoding='utf-8').write(tpl.replace('__ZONES__', json.dumps(zl, ensure_ascii=False)))
print(out)
