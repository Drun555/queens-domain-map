#!/usr/bin/env python3
"""Modèles allégés des mondes, montrés autour du monde affiché en 3D : tiles3d/<zone>/voisin.glb.

Les mondes partagent le repère du jeu, rien n'est à placer. De chaque modèle complet on ne garde que les triangles
visibles de dehors : il est rendu sous une trentaine d'angles et on note le triangle le plus proche dans chaque
pixel. Les mondes de surface perdent ce qui est sous l'eau. Les mondes souterrains sont vus comme dans la vue 3D,
plafonds transparents (dos des faces). Positions sur 16 bits, textures réduites.

Usage : python make_neighbours.py [dossier du site [zone ...]]        (par défaut map3d/ovh, toutes les zones)
"""
import io, json, os, struct, sys
import numpy as np
from PIL import Image

ROOT = os.environ.get('QD_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SURFACE = ('ile', 'marchand', 'aquatique', 'tour-du-savoir')
# souterrains : seulement les groupes lisibles côte à côte (voir UNDER dans viewer3d_site.html). Les mondes imbriqués
# (mausolées, Registre du péché, Temple de Jigeki, zone secrète aquatique) et les mondes à part n'ont pas de voisins.
SOUTERRAIN = ('automne', 'chateau', 'foret', 'marais', 'jardin-de-pierre', 'zone-finale', 'prison', 'sz-ruines', 'sz-tour', 'hod')
SOUS_EAU = -4.0      # m : la mer est à -1,1 m, on garde le bord immergé des plages et des rochers
PIXEL = 0.22         # m par pixel pour chercher les triangles visibles
MIN_PIXELS = 4       # un triangle vu sur moins de pixels (tous angles cumulés) ne se voit pas de loin
TEX_MAX = 128        # côté des textures
FOND = dict(PIXEL=0.6, MIN_PIXELS=14, TEX_MAX=64)     # souterrains : un arrière-plan sombre, moins de détail suffit
CACHE = ('WorldGridMaterial', 'eau')                        # ni les murs invisibles, ni l'eau (la page dessine la mer)
COMP = {5121: 'u1', 5123: '<u2', 5125: '<u4', 5126: '<f4'}
DIM = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}


def read(path, floor):
    """Primitives du modèle : positions, UV, triangles, matériau, image."""
    b = open(path, 'rb').read()
    n = struct.unpack_from('<I', b, 12)[0]
    js = json.loads(b[20:20 + n]); base = 20 + n + 8

    def acc(i):
        a = js['accessors'][i]; v = js['bufferViews'][a['bufferView']]; c = DIM[a['type']]
        dt = np.dtype(COMP[a['componentType']])
        o = base + v.get('byteOffset', 0) + a.get('byteOffset', 0)
        return np.array(np.ndarray((a['count'], c), dtype=dt, buffer=b, offset=o,
                                   strides=(v.get('byteStride', dt.itemsize * c), dt.itemsize)))

    out = []
    for m in js['meshes']:
        for p in m['primitives']:
            mat = js['materials'][p['material']]
            if mat['name'] in CACHE or mat['name'].startswith('mpswamp') or mat.get('alphaMode') == 'BLEND' or 'FakeSky' in mat['name']:
                continue
            P = acc(p['attributes']['POSITION']).astype(np.float64)
            F = acc(p['indices']).reshape(-1, 3).astype(np.int64)
            F = F[P[F][:, :, 1].max(1) > floor]
            if not len(F):
                continue
            uv = acc(p['attributes']['TEXCOORD_0']).astype('<f4') if 'TEXCOORD_0' in p['attributes'] else None
            img = None
            tex = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
            if tex and uv is not None:
                t = js['textures'][tex['index']]
                v = js['bufferViews'][js['images'][t['source']]['bufferView']]
                o = base + v.get('byteOffset', 0)
                img = b[o:o + v['byteLength']]
            out.append(dict(P=P, F=F, uv=uv, mat=mat, img=img))
    return out


def directions():
    d = [(0.001, 1, 0.0005)]
    for tilt, n, shift in ((0.12, 10, 0.2), (0.5, 12, 0.0), (1.4, 8, 0.35)):
        d += [(np.cos(a), tilt, np.sin(a)) for a in np.arange(n) * 2 * np.pi / n + shift]
    return [np.array(v) / np.linalg.norm(v) for v in d]


def visible(T, floor, pixel, min_pixels):
    """Pixels couverts par chaque triangle, une fois les surfaces cachées retirées, tous angles cumulés."""
    score = np.zeros(len(T), np.int64)
    for d in directions():
        r = np.cross([0, 1, 0], d); r /= np.linalg.norm(r)
        u = np.cross(d, r)
        x, y, z = (T @ r) / pixel, (T @ u) / pixel, T @ d
        x -= np.floor(x.min()); y -= np.floor(y.min())
        area = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
        W, H = int(x.max()) + 2, int(y.max()) + 2
        depth = np.full(W * H, -np.inf, np.float32); owner = np.full(W * H, -1, np.int64)
        x0, y0 = np.ceil(x.min(1) - .5).astype(np.int64), np.ceil(y.min(1) - .5).astype(np.int64)
        w, h = np.floor(x.max(1) - .5).astype(np.int64) - x0 + 1, np.floor(y.max(1) - .5).astype(np.int64) - y0 + 1
        # côté visible des surfaces du jeu : le dos des faces du modèle, comme dans la vue 3D
        keep = np.flatnonzero((area < -1e-9) & (w > 0) & (h > 0))
        bw, bh = np.ceil(np.log2(w[keep])).astype(int), np.ceil(np.log2(h[keep])).astype(int)
        bucket = bw * 64 + bh
        for k in np.unique(bucket):
            ids = keep[bucket == k]
            gx, gy = np.meshgrid(np.arange(w[ids].max()), np.arange(h[ids].max()))
            gx, gy = gx.ravel(), gy.ravel()
            step = max(1, 1500000 // len(gx))
            for s in range(0, len(ids), step):
                I = ids[s:s + step]
                px, py = x0[I, None] + gx, y0[I, None] + gy
                X, Y, A = x[I], y[I], area[I, None]
                cx, cy = px + .5, py + .5
                a = ((X[:, 1, None] - cx) * (Y[:, 2, None] - cy) - (X[:, 2, None] - cx) * (Y[:, 1, None] - cy)) / A
                c = ((X[:, 2, None] - cx) * (Y[:, 0, None] - cy) - (X[:, 0, None] - cx) * (Y[:, 2, None] - cy)) / A
                e = 1 - a - c
                i, j = np.nonzero((a >= 0) & (c >= 0) & (e >= 0))
                if not len(i):
                    continue
                t = I[i]; a, c, e = a[i, j], c[i, j], e[i, j]
                above = a * T[t, 0, 1] + c * T[t, 1, 1] + e * T[t, 2, 1] > floor
                at = (py[i, j] * W + px[i, j])[above]
                zz = (a * z[t, 0] + c * z[t, 1] + e * z[t, 2])[above].astype(np.float32)
                t = t[above]
                np.maximum.at(depth, at, zz)
                win = zz == depth[at]
                owner[at[win]] = t[win]
        score += np.bincount(owner[owner >= 0], minlength=len(T))
    return score >= min_pixels


def small_jpeg(raw, side):
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im.thumbnail((side, side), Image.LANCZOS)
    f = io.BytesIO(); im.save(f, 'JPEG', quality=72, optimize=True)
    return f.getvalue()


def write(path, prims, centre, side):
    span = max(np.abs(p['P'] - centre).max() for p in prims)
    pas = max(1, int(np.ceil(span * 100 / 32766)))   # au centimètre, ou à quelques-uns pour les très grands mondes
    js = dict(asset=dict(version='2.0', generator='make_neighbours.py'), scene=0, scenes=[dict(nodes=[0])],
              nodes=[dict(mesh=0, translation=centre.tolist(), scale=[0.01 * pas] * 3)], meshes=[dict(primitives=[])],
              extensionsUsed=['KHR_mesh_quantization'], extensionsRequired=['KHR_mesh_quantization'],
              accessors=[], bufferViews=[], materials=[], textures=[], images=[],
              samplers=[dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)])
    blob, seen = bytearray(), {}

    def view(data, **kw):
        blob.extend(b'\0' * (-len(blob) % 4))
        js['bufferViews'].append(dict(buffer=0, byteOffset=len(blob), byteLength=len(data), **kw))
        blob.extend(data)
        return len(js['bufferViews']) - 1

    def accessor(**kw):
        js['accessors'].append(kw)
        return len(js['accessors']) - 1

    for p in prims:
        q = np.round((p['P'] - centre) * 100 / pas)
        q = q.astype('<i2')
        pad = np.zeros((len(q), 4), '<i2'); pad[:, :3] = q       # 8 octets par sommet : glTF aligne sur 4
        at = dict(POSITION=accessor(bufferView=view(pad.tobytes(), byteStride=8, target=34962), componentType=5122,
                                    count=len(q), type='VEC3', min=q.min(0).tolist(), max=q.max(0).tolist()))
        src = p['mat'].get('pbrMetallicRoughness', {})
        pbr = dict(metallicFactor=0, roughnessFactor=src.get('roughnessFactor', 0.95))
        if 'baseColorFactor' in src:
            pbr['baseColorFactor'] = src['baseColorFactor']
        if p['img']:
            at['TEXCOORD_0'] = accessor(bufferView=view(p['uv'].tobytes(), target=34962), componentType=5126,
                                        count=len(q), type='VEC2')
            if p['img'] not in seen:
                js['images'].append(dict(bufferView=view(small_jpeg(p['img'], side)), mimeType='image/jpeg'))
                js['textures'].append(dict(source=len(js['images']) - 1, sampler=0))
                seen[p['img']] = len(js['textures']) - 1
            pbr['baseColorTexture'] = dict(index=seen[p['img']])
        short = len(q) < 65535
        F = p['F'].astype('<u2' if short else '<u4')
        idx = accessor(bufferView=view(F.tobytes(), target=34963), componentType=5123 if short else 5125,
                       count=F.size, type='SCALAR')
        mat = dict(name=p['mat']['name'], pbrMetallicRoughness=pbr, doubleSided=True)
        if p['mat'].get('alphaMode') == 'MASK':
            mat.update(alphaMode='MASK', alphaCutoff=p['mat'].get('alphaCutoff', 0.5))
        js['materials'].append(mat)
        js['meshes'][0]['primitives'].append(dict(attributes=at, indices=idx, material=len(js['materials']) - 1))
    blob.extend(b'\0' * (-len(blob) % 4))
    js['buffers'] = [dict(byteLength=len(blob))]
    head = json.dumps(js, separators=(',', ':')).encode()
    head += b' ' * (-len(head) % 4)
    with open(path, 'wb') as f:
        f.write(struct.pack('<III', 0x46546C67, 2, 28 + len(head) + len(blob)))
        f.write(struct.pack('<II', len(head), 0x4E4F534A) + head)
        f.write(struct.pack('<II', len(blob), 0x004E4942) + blob)


def build(site, zid):
    folder = os.path.join(site, 'tiles3d', zid)
    opt = dict(PIXEL=PIXEL, MIN_PIXELS=MIN_PIXELS, TEX_MAX=TEX_MAX)
    floor = SOUS_EAU
    if zid not in SURFACE:
        floor = -np.inf
        opt.update(FOND)
    prims = read(os.path.join(folder, 'scene.glb'), floor)
    T = np.concatenate([p['P'][p['F']] for p in prims])
    ok = visible(T, floor, opt['PIXEL'], opt['MIN_PIXELS'])
    at, kept = 0, []
    for p in prims:
        n = len(p['F']); F = p['F'][ok[at:at + n]]; at += n
        if not len(F):
            continue
        used, new = np.unique(F, return_inverse=True)
        kept.append(dict(p, P=p['P'][used], F=new.reshape(-1, 3), uv=None if p['uv'] is None else p['uv'][used]))
    allp = np.concatenate([p['P'] for p in kept])
    out = os.path.join(folder, 'voisin.glb')
    write(out, kept, np.round((allp.min(0) + allp.max(0)) / 2), opt['TEX_MAX'])
    print('%-16s %6d triangles sur %6d | %.2f Mo au lieu de %.1f Mo' % (
        zid, ok.sum(), len(T), os.path.getsize(out) / 1048576, os.path.getsize(os.path.join(folder, 'scene.glb')) / 1048576), flush=True)


if __name__ == '__main__':
    site = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'map3d', 'ovh')
    for z in (sys.argv[2:] or SURFACE + SOUTERRAIN):
        build(site, z)
