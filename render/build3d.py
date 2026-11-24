#!/usr/bin/env python3
"""Construit un modèle 3D texturé (GLB) d'une zone + les points d'intérêt, pour la vue 3D.
Usage : python3 build3d.py <zone> <dossier de sortie>
Réutilise la configuration et le placement des objets de render_zone.py."""
import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
import sys, os, io, re, json, struct
import numpy as np
from PIL import Image

zid, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
# on exécute la première partie de render_zone.py (index des modèles, textures, placement des objets)
src = open(ROOT + '/render/render_zone.py', encoding='utf-8').read()
src = src[:src.index('# cadre de la zone')]
sys.argv = ['render_zone.py', zid]
G = {'__name__': 'r3d', '__file__': ROOT + '/render/render_zone.py'}
exec(compile(src, 'render_zone.py', 'exec'), G)
Z, pl, prims, texture, TECH, exclude, WATERMAT = G['Z'], G['pl'], G['prims'], G['texture'], G['TECH'], G['exclude'], G['WATERMAT']
TECHMAT = G['TECHMAT']

# arbres de Dekanima : leur matériau n'a pas de texture de base (en jeu, ils reflètent un décor bleu-vert) ;
# on fabrique une texture répétable : motif gris du jeu teinté bleu-vert, trous des masques en taches lumineuses
DEK_MATS = {'Dekanima_MA_Inst', 'Dekanima_MI_Dissolve', 'Dekanima_Full_MI'}
_dek = []
def dek_texture():
    from PIL import ImageFilter
    if not _dek:
        png = G['png']
        base = np.asarray(Image.open(png['Dekanima_Tile_00_tx']).convert('L').resize((512, 512)), np.float32) / 255
        r, g, _ = [np.asarray(c, np.float32) / 255 for c in Image.open(png['Dekanima_Tile_Masks_tx']).convert('RGB').resize((512, 512)).split()]
        hole = Image.fromarray((np.clip((0.13 - np.minimum(r, g)) / 0.08, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
        hole = np.asarray(hole, np.float32)[..., None] / 255
        t = np.clip(base * 1.3, 0, 1)[..., None]
        img = np.array([22, 52, 50], np.float32) * (1 - t) + np.array([70, 128, 118], np.float32) * t
        _dek.append(np.clip(img * (1 - hole) + np.array([95, 200, 180], np.float32) * hole, 0, 255).astype(np.uint8))
    return _dek[0]
_texture = texture
def texture(mat):
    return dek_texture() if mat in DEK_MATS else _texture(mat)

# modèles posés par un blueprint (absent de l'export) : le niveau ne donne que la place de l'acteur ; on y pose le modèle
# du jeu correspondant. Téléporteurs : Teleporter_Preview_SM est le même modèle (le jeu s'en sert, réduit, comme objet
# de la boutique). Statues des dieux sans forme (Sanctuaire primordial, autels de Sipeha des zones secrètes).
BP_MESH = {'Teleporter_C': 'Teleporter_Preview_SM', 'FS_Jigeki_Statue_BP_C': 'Jigeki_Statue_SM', 'FS_Puwema_Statue_BP_C': 'Puwema_Statue_SM',
           'FS_SipehaStatue_BP_C': 'Sipeha_Statue_SM', 'FS_Wodaso_Statue_BP_C': 'Wodaso_Statue_SM'}
for lv in Z['levels']:
    objs = json.load(open(G['MAPS'] + lv + '.json', encoding='utf-8-sig'))
    roots = {o['Name']: (o['Type'], (o.get('Properties') or {}).get('RootComponent')) for o in objs if o['Type'] in BP_MESH}
    for o in objs:
        outer = (o.get('Outer') or {}).get('ObjectName', '')
        for a, (cls, rc) in roots.items():
            if rc and outer.endswith('PersistentLevel.' + a + "'") and rc['ObjectName'].endswith('.' + o['Name'] + "'"):
                p = o.get('Properties') or {}; place = G['place']
                pl.append((BP_MESH[cls], place._rot(p.get('RelativeRotation')) * place._vec(p.get('RelativeScale3D'), 1.0),
                           place._vec(p.get('RelativeLocation')), 'c'))

# cadre : points d'intérêt de la zone + marge
dd = json.load(open(ROOT + '/map/data.json', encoding='utf-8'))
zone = [z for z in dd['zones'] if z['id'] == zid][0]
P = np.array([p[1:4] for p in zone['pois']], float)
lo = np.percentile(P, 1, axis=0) - 6000; hi = np.percentile(P, 99, axis=0) + 6000
lo[2] -= 4000; hi[2] += 6000
if 'box' in Z: lo, hi = np.array(Z['box'][0], float), np.array(Z['box'][1], float)

# modèles exportés déjà en coordonnées du monde (bibliothèque de la Tour) : ajoutés une seule fois, sans transformation
placed = {n for n, *_ in pl}
if Z.get('world_meshes'):
    for n, f in G['mesh_file'].items():
        if not f.startswith(Z['world_meshes']) or n in placed: continue
        pr = prims(n)
        if not pr: continue
        Pp = np.vstack([q['pos'] for q in pr]); c = (Pp.min(0) + Pp.max(0)) / 2; e = Pp.max(0) - Pp.min(0)
        if c[0] > 15000 and max(e[0], e[1]) > 300: pl.append((n, np.eye(3), np.zeros(3), 'c'))
groups = {}       # matériau -> listes de (V, F, UV)
water_z = []
CLUTTER = re.compile(r'(gd_plant|gd_pots|gd_grass|gd_moss|gd_vine|Rubble|Lib_Book_|^Book|Necro_Deco|Chain|^Pot_|or_pot|Candle|^Web_|Bug_|Deco_Stalag|Deco_Rock|Crate_Remnant|Barrel_Remnant|KE_Bag|Scroll|Paper|OW_MK_Tank|OW_MK_Generator|MachineBarrel|PipeSet|DS_Bottle|BigCrate|ElecLink|ElecNodeConnector)', re.I)
for n, M, T, kind in pl:
    if TECH.search(n) or (exclude and exclude.search(n)) or CLUTTER.search(n): continue
    for pr in prims(n):
        if TECHMAT.search(pr['mat']): continue      # surfaces de blocage invisibles en jeu
        V = pr['pos'] @ M.T + T
        mn, mx = V.min(0), V.max(0)
        if (mx < lo).any() or (mn > hi).any(): continue
        if WATERMAT.search(pr['mat']):
            # eau : gardée comme vraie surface (un plan infini cacherait les étages souterrains)
            F = pr['idx']; a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
            tmn = np.minimum(np.minimum(a, b), c); tmx = np.maximum(np.maximum(a, b), c)
            keep = ((tmx >= lo) & (tmn <= hi)).all(1)
            if keep.any(): groups.setdefault('__water__', []).append((V, F[keep], pr['uv']))
            continue
        if kind == 'a' and texture(pr['mat']) is None: continue
        F = pr['idx']
        # on ne garde que les triangles dont le centre est dans le cadre
        c = (V[F[:, 0]] + V[F[:, 1]] + V[F[:, 2]]) / 3
        keep = ((c >= lo) & (c <= hi)).all(1)
        if not keep.any(): continue
        groups.setdefault(pr['mat'], []).append((V, F[keep], pr['uv']))

# --- écriture du GLB (glTF 2.0 binaire) ---
bin_parts, views, accessors, meshes_prims, images, textures, materials = [], [], [], [], [], [], []
def add_view(data, target=None):
    off = sum(len(b) for b in bin_parts)
    pad = (-off) % 4
    if pad: bin_parts.append(b'\0' * pad); off += pad
    bin_parts.append(data)
    v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
    if target: v['target'] = target
    views.append(v); return len(views) - 1
def add_acc(arr, typ, comp, target, minmax=False):
    vi = add_view(arr.tobytes(), target)
    a = {'bufferView': vi, 'componentType': comp, 'count': int(arr.shape[0]), 'type': typ}
    if minmax: a['min'] = arr.min(0).tolist(); a['max'] = arr.max(0).tolist()
    accessors.append(a); return len(accessors) - 1

ntri = 0
for mat, parts in groups.items():
    Vs, Fs, UVs, base = [], [], [], 0
    for V, F, UV in parts:
        used = np.unique(F); remap = -np.ones(len(V), np.int64); remap[used] = np.arange(len(used)) + base
        Vs.append(V[used]); UVs.append(UV[used]); Fs.append(remap[F]); base += len(used)
    V = np.vstack(Vs); UV = np.vstack(UVs).astype(np.float32); F = np.vstack(Fs)
    # repère Unreal (cm, Z en haut) -> repère three.js (m, Y en haut) : (x, z, y) / 100 ; la symétrie inverse le sens des triangles
    pos = (np.stack([V[:, 0], V[:, 2], V[:, 1]], 1) / 100.0).astype(np.float32)
    F = F[:, [0, 2, 1]].astype(np.uint32)
    # normales lissées par sommet
    n = np.cross(pos[F[:, 1]] - pos[F[:, 0]], pos[F[:, 2]] - pos[F[:, 0]])
    nrm = np.zeros_like(pos); np.add.at(nrm, F[:, 0], n); np.add.at(nrm, F[:, 1], n); np.add.at(nrm, F[:, 2], n)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9); nrm = nrm.astype(np.float32)
    tex = None if mat == '__water__' else texture(mat)
    if mat == '__water__':
        materials.append({'name': 'eau', 'pbrMetallicRoughness': {'baseColorFactor': [0.06, 0.13, 0.17, 0.86],
                          'metallicFactor': 0.1, 'roughnessFactor': 0.35}, 'alphaMode': 'BLEND', 'doubleSided': True})
    elif tex is not None:
        im = Image.fromarray(tex)
        if max(im.size) > 512: im.thumbnail((512, 512))
        b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=82)
        images.append({'bufferView': add_view(b.getvalue()), 'mimeType': 'image/jpeg'})
        textures.append({'source': len(images) - 1, 'sampler': 0})
        materials.append({'name': mat, 'pbrMetallicRoughness': {'baseColorTexture': {'index': len(textures) - 1},
                          'metallicFactor': 0.0, 'roughnessFactor': 0.95}, 'doubleSided': True})
    else:
        materials.append({'name': mat, 'pbrMetallicRoughness': {'baseColorFactor': [0.55, 0.55, 0.53, 1],
                          'metallicFactor': 0.0, 'roughnessFactor': 1.0}, 'doubleSided': True})
    attrs = {'POSITION': add_acc(pos, 'VEC3', 5126, 34962, True), 'TEXCOORD_0': add_acc(UV, 'VEC2', 5126, 34962)}
    ind = add_acc(F.reshape(-1).astype(np.uint16), 'SCALAR', 5123, 34963) if len(pos) < 65535 else add_acc(F.reshape(-1), 'SCALAR', 5125, 34963)
    meshes_prims.append({'attributes': attrs, 'indices': ind, 'material': len(materials) - 1})
    ntri += len(F)

gltf = {'asset': {'version': '2.0', 'generator': 'Carte de Neasied'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0, 'name': zid}], 'meshes': [{'primitives': meshes_prims}],
        'materials': materials, 'textures': textures, 'images': images,
        'samplers': [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}],
        'accessors': accessors, 'bufferViews': views}
binb = b''.join(bin_parts); binb += b'\0' * ((-len(binb)) % 4)
gltf['buffers'] = [{'byteLength': len(binb)}]
js = json.dumps(gltf, separators=(',', ':')).encode(); js += b' ' * ((-len(js)) % 4)
glb = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binb)) + struct.pack('<II', len(js), 0x4E4F534A) + js \
      + struct.pack('<II', len(binb), 0x004E4942) + binb
open(os.path.join(OUT, 'scene.glb'), 'wb').write(glb)

# points d'intérêt (même repère) + hauteur d'eau
cats = {c['id']: c for c in dd['cats']}
pois = [{'c': p[0], 'x': p[1] / 100, 'y': p[3] / 100, 'z': p[2] / 100, 'n': p[4], 'k': p[7] if len(p) > 7 else []} for p in zone['pois']]
meta = {'zone': zone['label'], 'cats': dd['cats'], 'pois': pois,
        'water': None,
        'box': {'lo': [lo[0] / 100, lo[2] / 100, lo[1] / 100], 'hi': [hi[0] / 100, hi[2] / 100, hi[1] / 100]}}
json.dump(meta, open(os.path.join(OUT, 'zone.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('GLB', round(len(glb) / 1e6, 2), 'Mo |', len(materials), 'matériaux |', ntri, 'triangles |', len(pois), 'points | eau', meta['water'])
