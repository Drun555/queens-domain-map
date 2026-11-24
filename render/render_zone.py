#!/usr/bin/env python3
"""Rendu texturé, tranche par tranche, d'une zone de la carte.
Usage : python3 render_zone.py <zone> ; la configuration de chaque zone est dans ZONES ci-dessous."""
import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
import os, re, json, glob, sys, time, numpy as np
sys.path.insert(0, ROOT + '/render')
import glb, place
from PIL import Image
from scipy import ndimage

MAPS = ROOT + '/all/RuinsLevel/Maps/'
ROOTS = [ROOT + '/all/RuinsLevel', ROOT + '/meshes/ow2', ROOT + '/meshes/Library', ROOT + '/meshes/props', ROOT + '/meshes/extra']
EXS = r'(_HINT$|NoWalk|[Ss]ky|Aurora|IncenseRibbon|ScalerPlane|^Cube$|^Plane$|collider|_EW$)'
ZONES = {
  'ile': dict(levels=['100_GR', '110_GR_dungeon', '120_GR_goldenroom', '125_GR_CubeHall', '130_GR_outerisles', '070_UpperShell', '050_Ocean'],
              exclude=r'^(SZ_|M_Section|M_Memento|RuinsLevel_00_Part_02|Lib_|bloodlordarena|Ros_|RuinsLevel_00_Part_0[34]$)',
              px=20.0, samp=4.5, min_sep=1200, merge_gap=1500, start_all=True),
  'marchand': dict(levels=['140_GR_ShopIsleOnly', '070_UpperShell', '050_Ocean'],
              # l'île et la boutique sont posées dans le niveau du menu vidéo, lui-même décalé dans le monde
              extra_levels=[(ROOT + '/input/VideoConfigMap.json', (7199.0674, 36841.5, 0.0), r'^(VSI_00_SM|Shop_Interior_00_SM|Shop_DoorFrame_SM)$')],
              exclude=r'^(SZ_|M_Section|M_Memento|RuinsLevel_00_Part_0[0-4](?!_water)|Lib_|bloodlordarena|Ros_|RL_00_|WellRoof|KE_)',
              px=12.5, samp=3.0, min_sep=1200, merge_gap=1500, start_all=True),
  'aquatique': dict(levels=['200_AQ', '210_AQ_underground', '070_UpperShell', '050_Ocean'],
              exclude=r'^(SZ_|M_Section|M_Memento|RuinsLevel_00_Part_0[0-2]|Lib_|bloodlordarena|Ros_|RL_00_|WellRoof|KE_)',
              px=20.0, samp=4.5, min_sep=1200, merge_gap=1500, start_all=True),
  # le gros œuvre du mausolée (M_Section_*) est rangé dans 070_UpperShell : on ne garde que lui de ce niveau
  'mausolee': dict(levels=['400_MAUS_entrance', '420_MAUS_mid', '450_MAUS_darkmaze', '070_UpperShell'],
              level_filter={'070_UpperShell': r'^(M_Section|M_Shrine|M_ShipRoom)'},
              exclude=r'(_PPC|PPC$|NoWalk|EnemyPPC|_HINT$)',
              px=12.5, samp=3.0, min_sep=900, merge_gap=1200, start_all=False, cull_down=True),
  # --- zones secrètes et fins de jeu : le gros œuvre de la plupart est rangé dans 070_UpperShell ---
  'sz-ruines': dict(levels=['700_SZ_GR', '070_UpperShell'], level_filter={'070_UpperShell': r'^SZ_Part_01_00_SM$'},
              exclude=EXS, px=10.0, samp=2.5, min_sep=600, merge_gap=900, start_all=True),
  'sz-aquatique': dict(levels=['710_SZ_AQ', '070_UpperShell'], level_filter={'070_UpperShell': r'^SZ_Part_02_00_SM$'},
              exclude=EXS, px=10.0, samp=2.5, min_sep=600, merge_gap=900, start_all=True),
  'sz-tour': dict(levels=['720_SZ_LIB', '070_UpperShell'], level_filter={'070_UpperShell': r'^SZ_Part_03_00_SM$'},
              exclude=EXS, px=8.0, samp=2.0, min_sep=600, merge_gap=900, start_all=True),
  'hod': dict(levels=['730_HOD', '070_UpperShell'], level_filter={'070_UpperShell': r'^M_MementoTunnel_00_SM$'},
              exclude=EXS, px=8.0, samp=2.0, min_sep=600, merge_gap=900, start_all=True),
  'prison': dict(levels=['740_SZ_Prison', '070_UpperShell'], level_filter={'070_UpperShell': r'^(SZ_Part_04_00_SM|bloodlordarena_SM)$'},
              exclude=EXS, px=12.5, samp=3.0, min_sep=800, merge_gap=1000, start_all=True),
  'sz-mausolee': dict(levels=['750_SZ_MAUS2', '070_UpperShell'], level_filter={'070_UpperShell': r'^SZ_Part_S2_00_SM$'},
              exclude=EXS, px=10.0, samp=2.5, min_sep=700, merge_gap=1000, start_all=True),
  # Dekanima : la tour du Registre du péché avec, en plus, la zone bleue ; on reprend donc aussi le niveau de la tour,
  # et le bord de la forêt des profondeurs, qui touche le bas de la zone bleue (même hauteur, à une vingtaine de mètres)
  'dekanima': dict(levels=['760_Dekanima', '760_SZ_AUT', '780_SZ_Depths', '070_UpperShell'],
              level_filter={'070_UpperShell': r'^(Ros_Exterior_SM|SZ_Part_S1_00_SM)$'},
              exclude=EXS + r'|Grass|gd_grass|PPC|fog|SKYLIGHT', px=10.0, samp=2.5, min_sep=700, merge_gap=1000, start_all=True),
  'ros': dict(levels=['760_SZ_AUT', '070_UpperShell'], level_filter={'070_UpperShell': r'^Ros_Exterior_SM$'},
              exclude=EXS, px=15.0, samp=3.5, min_sep=900, merge_gap=1200, start_all=True),
  'marais': dict(levels=['770_SZ_Swamp', '070_UpperShell'], level_filter={'070_UpperShell': r'^(SZ_Part_S1_SwampZone_SM|SZ_Part_S1_SwampEntree_SM|SZ_Swamp_SipehaShrine_SM)$'},
              exclude=EXS, px=20.0, samp=4.5, min_sep=1000, merge_gap=1200, start_all=True,
              lava=r'^mpswamp_'),   # liquide en lave tant que la zone n'est pas nettoyée : l'eau et ces surfaces sont peintes en lave
  'jigeki': dict(levels=['775_JigekiTemple', '070_UpperShell'], level_filter={'070_UpperShell': r'^SZ_Part_S1_SwampZone_SM$'},
              exclude=EXS, px=8.0, samp=2.0, min_sep=600, merge_gap=900, start_all=True, pad=2500),
  'jardin-de-pierre': dict(levels=['790_SG'], exclude=EXS, px=15.0, samp=3.5, min_sep=800, merge_gap=1000, start_all=True),
  'zone-finale': dict(levels=['800_FinalZone'], exclude=EXS, px=12.5, samp=3.0, min_sep=800, merge_gap=1000, start_all=True),
  'sipeha': dict(levels=[], extra_levels=[(MAPS + '900_SipehaWorld.json', (28000.0, -35000.0, 20000.0), r'^(?!.*(Sky|collider|PPC|^Cube$)).*$')], box=((10600, -51800, -100000), (45500, -18200, 100000)),
              exclude=EXS, px=15.0, samp=3.0, min_sep=800, merge_gap=1000, start_all=True),
  # île d'automne et château : modèles du dossier OtherWorld
  'automne': dict(levels=['500_AUT', '510_AUT_droptunnel'], exclude=EXS + r'|Grass|gd_plant|FallenLeaves|gd_moss',
              px=36.0, samp=7.0, min_sep=1200, merge_gap=1500, start_all=True),
  'chateau': dict(levels=['600_Castle', '610_Castle_Ext'], exclude=EXS, px=12.5, samp=3.0, min_sep=800, merge_gap=1000, start_all=False),
  # Tour du Savoir (vue 3D) : le gros œuvre de la tour est dans 070_UpperShell ; les modèles de la bibliothèque exportés déjà placés sont ajoutés par build3d.py
  'tour-du-savoir': dict(levels=['300_LIB', '310_LIB_exterior', '320_LIB_basement', '070_UpperShell'],
              level_filter={'070_UpperShell': r'^(RuinsLevel_00_Part_02|Lib_)'}, world_meshes=ROOT + '/meshes/Library/',
              exclude=EXS, px=10.0, samp=2.5, min_sep=600, merge_gap=900, start_all=False),
  # forêt des profondeurs : le relief (SZ_Part_*) est rangé dans 070_UpperShell
  'foret': dict(levels=['780_SZ_Depths', '070_UpperShell'],
              level_filter={'070_UpperShell': r'^(SZ_Part_S1_00_SM|SZ_PuwemaTempleINT_SM|SZ_Part_S1_SwampInter_SM)$'},
              exclude=r'(Grass|gd_grass|PPC|fog|SKYLIGHT|_HINT$|NoWalk)',
              px=20.0, samp=4.5, min_sep=1200, merge_gap=1500, start_all=False, cull_down=True),
  # gros plan autour du dernier œuf (forêt des profondeurs) : cadre imposé, herbes et feuillages retirés
  'oeuf': dict(levels=['780_SZ_Depths', '070_UpperShell'],
              level_filter={'070_UpperShell': r'^SZ_'}, zone_pois='foret',
              box=((-12350 - 6000, 12662 - 6000, -30000), (-12350 + 6000, 12662 + 6000, 0)),
              exclude=r'(Grass|SONplant|gd_plant|gd_grass|PPC|fog|SKYLIGHT|gd_moss|Ordaplant|vine)',
              px=6.0, samp=1.6, min_sep=600, merge_gap=600, start_all=False),
}
WATERMAT = re.compile(r'water|ocean', re.I)
WATER_RGB = np.array([54, 93, 107], np.float32)      # teinte moyenne de RS_CalmWater1, la texture d'eau du jeu
# matériau par défaut d'Unreal : surfaces de blocage invisibles en jeu (ex. le mur courbe du cimetière de l'île)
TECHMAT = re.compile(r'WorldGridMaterial', re.I)
def lava_tex(S=256, seed=7):
    """Lave procédurale, même dessin que la vue 3D (viewer3d_site.html) : le jeu n'exporte pas de texture de lave."""
    st = [seed]
    def rnd():
        st[0] = st[0] * 16807 % 2147483647; return st[0] / 2147483647
    img = np.zeros((S, S, 3), np.float32); img[:] = (106, 21, 5)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    def blob(px, py, r, rgb, a0):
        dx = np.abs(xx - px); dx = np.minimum(dx, S - dx); dy = np.abs(yy - py); dy = np.minimum(dy, S - dy)
        a = np.clip(1 - np.sqrt(dx * dx + dy * dy) / r, 0, 1) * a0
        img[:] = img * (1 - a[..., None]) + np.array(rgb, np.float32) * a[..., None]
    for _ in range(160):
        px, py, r, hot = rnd() * S, rnd() * S, 8 + rnd() * 30, rnd()
        blob(px, py, r, (255, 220, 110) if hot > 0.7 else (255, 110, 20), 0.85 if hot > 0.7 else 0.7)
    for _ in range(70):
        px, py, r = rnd() * S, rnd() * S, 6 + rnd() * 20
        blob(px, py, r, (28, 6, 3), 0.6)
    return np.clip(img, 0, 255).astype(np.uint8)
LAVA_TEX = lava_tex()
TECH = re.compile(r'(AudioOcclusion|ShadowBox|FogCard|^Cylinder$|decalPlane|NoWalk|WorldGrid|Blocker|_PPC_?\d*$|PPC$|Volume)', re.I)

zid = sys.argv[1]; Z = ZONES[zid]
OUTDIR = ROOT + '/render/tiles_tex/' + zid; os.makedirs(OUTDIR, exist_ok=True)
exclude = re.compile(Z['exclude']) if Z.get('exclude') else None
rng = np.random.default_rng(11)
log = lambda *a: print(*a, flush=True)

mesh_file, png, mats = {}, {}, {}
for R in ROOTS:
    for f in glob.glob(R + '/**/*.glb', recursive=True): mesh_file.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    for p in glob.glob(R + '/**/*.png', recursive=True): png.setdefault(os.path.splitext(os.path.basename(p))[0], p)
    for f in glob.glob(R + '/**/*.json', recursive=True):
        if '/Maps/' in f: continue
        try: d = json.load(open(f, encoding='utf-8-sig'))
        except Exception: continue
        if isinstance(d, dict) and 'Textures' in d: mats.setdefault(os.path.splitext(os.path.basename(f))[0], d['Textures'])
tcache = {}
def texture(mat):
    if Z.get('lava') and re.search(Z['lava'], mat): return LAVA_TEX
    if mat in tcache: return tcache[mat]
    img = None; T = mats.get(mat)
    if T:
        for k in ('Texture_Main', 'Texture_Diffuse', 'Texture_Base', 'Texture_Alternate', 'Texture_Trim'):
            if k in T:
                p = png.get(T[k]['ObjectName'].split("'")[1])
                if p:
                    im = Image.open(p).convert('RGB')
                    if max(im.size) > 1024: im = im.resize((min(1024, im.size[0]), min(1024, im.size[1])))
                    img = np.asarray(im, dtype=np.uint8)
                break
    tcache[mat] = img
    return img
pcache = {}
def prims(name):
    if name not in pcache:
        f = mesh_file.get(name); pcache[name] = glb.load_prims(f) if f else []
    return pcache[name]

# --- 1. objets posés dans les niveaux de la zone ---
pl = []
for lv in Z['levels']:
    js = MAPS + lv + '.json'
    keep = re.compile(Z.get('level_filter', {}).get(lv, '.'))
    pl += [(n, M, T, 'c') for n, M, T in place.placements(js) if keep.search(n)]
    acts, _ = place.actor_placements(js, set(mesh_file))
    pl += [(n, M, T, 'a') for n, M, T in acts if keep.search(n)]
for js, off, inc in Z.get('extra_levels', []):
    rx = re.compile(inc); off = np.array(off)
    pl += [(n, M, T + off, 'c') for n, M, T in place.placements(js) if rx.search(n)]
log(len(pl), 'objets posés dans', len(Z['levels']) + len(Z.get('extra_levels', [])), 'niveaux')

# cadre de la zone : marqueurs de la carte (1er-99e centile) + marge
dd = json.load(open(ROOT + '/map/data.json'))
zp = np.array([[p[1], p[2], p[3]] for p in [z for z in dd['zones'] if z['id'] == Z.get('zone_pois', zid)][0]['pois']])
PAD = Z.get('pad', 8000); lo = np.percentile(zp, 0.5, axis=0) - PAD; hi = np.percentile(zp, 99.5, axis=0) + PAD   # boîte large de recherche
if 'box' in Z: lo, hi = np.array(Z['box'][0], float), np.array(Z['box'][1], float)

raw, skipped = [], 0
for n, M, T, kind in pl:
    if TECH.search(n) or (exclude and exclude.search(n)): skipped += 1; continue
    for pr in prims(n):
        if kind == 'a' and texture(pr['mat']) is None: continue      # meubles sans texture : ignorés
        if TECHMAT.search(pr['mat']): continue
        V = (pr['pos'] @ M.T + T).astype(np.float32)
        vmin, vmax = V.min(0), V.max(0)
        if vmax[0] < lo[0] or vmin[0] > hi[0] or vmax[1] < lo[1] or vmin[1] > hi[1]: continue
        raw.append((V, pr['idx'], pr['uv'].astype(np.float32), pr['mat']))
log(len(raw), 'primitives dans le cadre |', skipped, 'objets techniques ou hors zone écartés')
# cadre serré sur le décor réellement présent
allv = np.vstack([V[::max(1, len(V) // 2000)] for V, _, _, mat in raw if not WATERMAT.search(mat)])
flo = np.maximum(np.percentile(allv, 0.05, axis=0) - 1000, lo); fhi = np.minimum(np.percentile(allv, 99.95, axis=0) + 1000, hi)
X0, Y0 = float(np.floor(flo[0] / 100) * 100), float(np.floor(flo[1] / 100) * 100)
PXF = Z['px']; WF = int(np.ceil((fhi[0] - X0) / PXF)); HF = int(np.ceil((fhi[1] - Y0) / PXF))
SS = 2; PX = PXF / SS; W, H = WF * SS, HF * SS
log('cadre', X0, Y0, '->', round(fhi[0]), round(fhi[1]), '| image', WF, 'x', HF)

groups = []; water = []; hist = np.zeros(6000); HB = 100.0; HZ0 = -300000.0
for V, Fi, UV, mat in raw:
    a, b, c = V[Fi[:, 0]], V[Fi[:, 1]], V[Fi[:, 2]]
    if WATERMAT.search(mat):
        water.append(np.stack([a, b, c], 1)); continue
    n = np.cross(b - a, c - a); ar = np.linalg.norm(n, axis=1) / 2; ok = ar > 1e-3
    if Z.get('cull_down', True):      # plafonds de grotte : faces tournées vers le bas, invisibles depuis le dessus
        ok &= (-n[:, 2]) > -0.2 * 2 * np.maximum(ar, 1e-9)
    if not ok.any(): continue
    a, b, c, n, ar = a[ok], b[ok], c[ok], n[ok], ar[ok]
    nu = (-n / (2 * ar)[:, None]).astype(np.float32)
    proj = np.abs(nu[:, 2]) * ar
    up = nu[:, 2] > 0.85
    zc = (a[:, 2] + b[:, 2] + c[:, 2]) / 3
    bi = ((zc - HZ0) / HB).astype(int); m = up & (bi >= 0) & (bi < 6000)
    np.add.at(hist, bi[m], ar[m])
    cnt = np.minimum(np.ceil((proj + 0.15 * ar) / (Z['samp'] ** 2)).astype(np.int64) + 1, 300000)
    groups.append(dict(a=a, b=b, c=c, nu=nu, cnt=cnt, ua=UV[Fi[ok, 0]], ub=UV[Fi[ok, 1]], uc=UV[Fi[ok, 2]],
                       zlo=np.minimum.reduce([a[:, 2], b[:, 2], c[:, 2]]), zhi=np.maximum.reduce([a[:, 2], b[:, 2], c[:, 2]]),
                       tex=texture(mat)))
ntex = sum(1 for g in groups if g['tex'] is not None)
# --- eau : rasterisée une seule fois sur toute la grille (hauteur de la surface d'eau la plus haute) ---
wz = np.full((H, W), -1e9, np.float32)
wtris = np.concatenate(water) if water else np.zeros((0, 3, 3), np.float32)
for t in wtris:
    xs = (t[:, 0] - X0) / PX; ys = (t[:, 1] - Y0) / PX
    x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), W - 1)
    y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), H - 1)
    if x0 > x1 or y0 > y1: continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if abs(d) < 1e-9: continue
    l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
    l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
    l2 = 1 - l0 - l1
    inside = (l0 >= -1e-4) & (l1 >= -1e-4) & (l2 >= -1e-4)
    zz = l0 * t[0, 2] + l1 * t[1, 2] + l2 * t[2, 2]
    sub = wz[y0:y1 + 1, x0:x1 + 1]
    np.copyto(sub, np.maximum(sub, np.where(inside, zz, -1e9)).astype(np.float32))
# léger motif de vagues tiré de la texture du jeu, répété tous les 12 m
wt = png.get('RS_CalmWater1') or png.get('RS_CalmWater')
if wt:
    tw = np.asarray(Image.open(wt).convert('L'), np.float32); tw = tw / tw.mean()
    gx = ((np.arange(W) * PX + X0) / 1200.0 * tw.shape[1]).astype(np.int64) % tw.shape[1]
    gy = ((np.arange(H) * PX + Y0) / 1200.0 * tw.shape[0]).astype(np.int64) % tw.shape[0]
    ripple = np.clip(0.85 + 0.15 * tw[gy[:, None], gx[None, :]], 0.7, 1.25)
else:
    ripple = np.ones((H, W), np.float32)
if Z.get('lava'):   # lave à la place de l'eau, calée sur les coordonnées du monde ; deux échelles mélangées pour casser la répétition
    def _lava(m_per_tile, ox, oy):
        gx = ((np.arange(W) * PX + X0) / m_per_tile * 256 + ox).astype(np.int64) % 256
        gy = ((np.arange(H) * PX + Y0) / m_per_tile * 256 + oy).astype(np.int64) % 256
        return LAVA_TEX[gy[:, None], gx[None, :]].astype(np.float32)
    LAVA_W = _lava(1400.0, 0, 0) * 0.6 + _lava(2300.0, 97, 41) * 0.4
log(len(wtris), "triangles d'eau,", int((wz > -1e8).sum() // (SS * SS)), 'pixels couverts')
log(len(groups), 'groupes,', sum(len(g['a']) for g in groups), 'triangles,', ntex, 'groupes texturés')

# --- 2. étages : hauteurs où se concentre la surface de sol ---
allz = np.concatenate([np.r_[g['zlo'], g['zhi']] for g in groups] + ([wtris[:, :, 2].ravel()] if len(wtris) else []))
zlo_all = float(np.floor(np.percentile(allz, 0.2) / 100) * 100 - 200); zhi_all = float(np.ceil(np.percentile(allz, 99.8) / 100) * 100 + 200)
sm = hist + np.r_[hist[1:], 0]
levels = []
for i in np.argsort(sm)[::-1]:
    if sm[i] < 0.10 * sm.max(): break
    zl = HZ0 + i * HB + (HB if hist[min(i + 1, 5999)] > hist[i] else 0)
    if zlo_all < zl < zhi_all and all(abs(zl - l) >= Z['min_sep'] for l in levels): levels.append(float(zl))
levels.sort(); log('sols détectés (m) :', [round(l / 100) for l in levels])
cuts = [zlo_all] + [l - 150 for l in levels if l - 150 > zlo_all + 300] + [zhi_all]
floors = []
for i in range(len(cuts) - 1):
    lv = [l for l in levels if cuts[i] <= l < cuts[i + 1]]
    floors.append({'z0': cuts[i], 'z1': cuts[i + 1], 'lvl': lv[0] if lv else None})
edges = []
for f in floors:
    nb = max(1, int(np.ceil((f['z1'] - f['z0']) / 400)))
    edges += list(np.linspace(f['z0'], f['z1'], nb + 1)[:-1])
edges.append(zhi_all)
log(len(floors), 'étages,', len(edges) - 1, 'tranches')

# --- 3. rendu de chaque tranche ---
light = np.array([-0.45, -0.45, 0.77], np.float32); light /= np.linalg.norm(light)
k3 = np.ones((3, 3), np.float32)
bands = []; t0 = time.time()
for bi in range(len(edges) - 1):
    Z0, Z1 = edges[bi], edges[bi + 1]
    zb = np.full(H * W, -1e9, np.float32); col = np.zeros((H * W, 3), np.uint8); shd = np.zeros(H * W, np.float32)
    for g in groups:
        sel = np.nonzero((g['zhi'] > Z0) & (g['zlo'] < Z1))[0]
        if not len(sel): continue
        idx = np.repeat(sel, g['cnt'][sel])
        for s in range(0, len(idx), 4_000_000):
            i = idx[s:s + 4_000_000]
            r1 = np.sqrt(rng.random(len(i), dtype=np.float32)); r2 = rng.random(len(i), dtype=np.float32)
            w0, w1, w2 = (1 - r1)[:, None], (r1 * (1 - r2))[:, None], (r1 * r2)[:, None]
            P = w0 * g['a'][i] + w1 * g['b'][i] + w2 * g['c'][i]
            px = ((P[:, 0] - X0) / PX).astype(np.int64); py = ((P[:, 1] - Y0) / PX).astype(np.int64)
            m = (P[:, 2] > Z0) & (P[:, 2] < Z1) & (px >= 0) & (px < W) & (py >= 0) & (py < H)
            if not m.any(): continue
            px, py, z, i2 = px[m], py[m], P[m, 2], i[m]
            tex = g['tex']
            if tex is not None:
                uv = w0[m] * g['ua'][i2] + w1[m] * g['ub'][i2] + w2[m] * g['uc'][i2]
                th, tw = tex.shape[:2]
                rgb = tex[np.mod((uv[:, 1] * th).astype(np.int64), th), np.mod((uv[:, 0] * tw).astype(np.int64), tw)]
            else:
                rgb = np.full((len(px), 3), 118, np.uint8)
            k = py * W + px
            o = np.lexsort((z, k)); k, z, rgb, i2 = k[o], z[o], rgb[o], i2[o]
            last = np.r_[k[1:] != k[:-1], True]
            k, z, rgb, i2 = k[last], z[last], rgb[last], i2[last]
            up = z > zb[k]; kk = k[up]
            zb[kk] = z[up]; col[kk] = rgb[up]
            shd[kk] = 0.52 + 0.48 * np.clip(g['nu'][i2[up]] @ light, 0, 1)
    cov = (zb > -1e8).reshape(H, W)
    wmask = (wz > Z0) & (wz <= Z1)
    if cov.sum() < 200 and wmask.sum() < 200: continue
    C = col.reshape(H, W, 3).astype(np.float32); S = shd.reshape(H, W); Zb = zb.reshape(H, W)
    for _ in range(2):
        cnt = ndimage.convolve(cov.astype(np.float32), k3, mode='constant')
        hole = (~cov) & (cnt >= 5)
        if not hole.any(): break
        d = np.maximum(cnt, 1)
        for ch in range(3):
            f = ndimage.convolve(np.where(cov, C[..., ch], 0), k3, mode='constant') / d; C[..., ch][hole] = f[hole]
        f = ndimage.convolve(np.where(cov, S, 0), k3, mode='constant') / d; S[hole] = f[hole]
        f = ndimage.convolve(np.where(cov, Zb, 0), k3, mode='constant') / d; Zb[hole] = f[hole]
        cov = cov | hole
    Zc = np.where(cov, Zb, Z0)
    gr = np.maximum(np.abs(np.gradient(Zc, axis=1)), np.abs(np.gradient(Zc, axis=0)))
    S = S * (1 - 0.55 * np.clip((gr - 12) / 120, 0, 1) * cov)
    out = C * S[..., None]
    alpha = np.where(cov, 255.0, 0.0)
    wcol = LAVA_W if Z.get('lava') else WATER_RGB[None, None, :] * ripple[..., None]
    under = wmask & cov & (Zb < wz - 3)                     # fond visible sous l'eau
    deep = wmask & ~cov                                     # eau sans fond dans cette tranche
    if Z.get('lava'):                                       # la lave est opaque
        out[under] = wcol[under]; out[deep] = wcol[deep]; alpha[deep] = 255
    else:
        out[under] = out[under] * 0.4 + wcol[under] * 0.6
        out[deep] = wcol[deep]; alpha[deep] = 215
    img = np.zeros((H, W, 4), np.uint8)
    img[..., :3] = np.clip(out, 0, 255); img[..., 3] = alpha.astype(np.uint8)
    fn = 'b%03d.webp' % bi
    Image.fromarray(img, 'RGBA').resize((WF, HF), Image.BOX).save(os.path.join(OUTDIR, fn), 'WEBP', quality=80, method=5)
    bands.append({'f': fn, 'z': float(Z0), 'z1': float(Z1)})
    log('tranche %d/%d  %.0f m  %ds' % (bi + 1, len(edges) - 1, Z0 / 100, time.time() - t0))

meta = {'x0': X0, 'y0': Y0, 'px': PXF, 'w': WF, 'h': HF, 'bands': bands, 'floors': floors,
        'mergeGap': Z['merge_gap'], 'startAll': bool(Z.get('start_all'))}
json.dump(meta, open(os.path.join(OUTDIR, 'meta.json'), 'w'))
tot = sum(os.path.getsize(os.path.join(OUTDIR, b['f'])) for b in bands)
log('TERMINÉ', len(bands), 'tranches,', round(tot / 1e6, 1), 'Mo')
