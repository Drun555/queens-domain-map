#!/usr/bin/env python3
"""Ajoute à chaque objet de data.json (champ 8) les clés qui permettent de le retrouver dans World0.sav :
   'G<hex>'  GUID de SavableActorStates (objet ramassé, coffre ouvert, mur cassé, boss vaincu…)
   'N<nom>'  entrée de NamedSaveData (défis réussis, pièces remises au scientifique)
   'O<nom>'  cristal de sauvegarde visité / téléporteur débloqué."""
import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
import json, glob, os, struct, re, collections
MAPS = ROOT + '/all/RuinsLevel/Maps/'
def g2hex(g): return b''.join(struct.pack('<I', int(x, 16)) for x in g.split('-')).hex()
lv = {}
for f in glob.glob(MAPS + '*.json'):
    try: L = json.load(open(f, encoding='utf-8-sig'))
    except Exception: continue
    if not isinstance(L, list): continue
    b = os.path.basename(f)[:-5]
    for o in L:
        if (o.get('Outer') or {}).get('ObjectName', '').endswith("PersistentLevel'"): lv[(b, o['Name'])] = o
# objets rangés dans un coffre : le jeu enregistre l'ouverture du coffre, pas le ramassage de l'objet
inchest = collections.defaultdict(list)
for (b, n), o in lv.items():
    pr = o.get('Properties') or {}
    for ref in pr.get('ActorsToActivateOnOpen') or []:
        if isinstance(ref, dict) and 'PersistentLevel.' in ref.get('ObjectName', ''):
            item = ref['ObjectName'].split('PersistentLevel.')[-1].rstrip("'")
            inchest[(b, item)] += ['G' + g2hex(g) for g in pr.get('GUIDs', [])]
# passages « activables » : ouverts par un autre acteur (mur, levier, interrupteur…) dont l'état est enregistré à leur place
refby = collections.defaultdict(set)
def _refs(v, out):
    if isinstance(v, dict):
        on = v.get('ObjectName', '')
        if 'PersistentLevel.' in on:
            nm = on.split('PersistentLevel.')[-1].rstrip("'")
            if '.' not in nm: out.add(nm)
        for x in v.values(): _refs(x, out)
    elif isinstance(v, list):
        for x in v: _refs(x, out)
for (b, n), o in lv.items():
    pr = o.get('Properties') or {}
    for k, v in pr.items():
        if not re.search(r'Activat|Target|Door|Open|Trigger', k): continue
        out = set(); _refs(v, out)
        for t in out:
            if t != n: refby[(b, t)].add(n)
def trigger_keys(b, n, depth=0):
    keys = []
    for src in refby.get((b, n), ()):
        so = lv.get((b, src))
        if not so: continue
        sp = so.get('Properties') or {}
        keys += ['G' + g2hex(g) for g in sp.get('GUIDs', [])]
        if depth < 3: keys += trigger_keys(b, src, depth + 1)
    return keys
# objets uniques : on regarde aussi l'inventaire (clés 'I<objet>'), certains ramassages ne sont pas enregistrés
ITEMS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'item_names.json')))
ITEM_FIX = {'Knifebelt': ['KnifeBelt_KeyItem'], 'Knight Rusty Sword Pickup': ['RustySword_Item', '!NRustySwordKnightGaveSword'],
            'Skullrod': ['SkullRod_Item'], 'Slashgun': ['SlashGun_ItemData'], 'Wing Crystal': []}
THROWN = re.compile(r'Dagger|Throwing|Spike Ball|Chakram|Needle', re.I)
_ST = {'pickup', 'item', 'data', 'bp', 'dans', 'un', 'coffre', 'the', 'of', '00', 'treasure', 'keyitem', 'key'}
def _toks(t):
    t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t); t = re.sub(r'(\d+)', r' \1 ', t).lower().replace('_', ' ')
    return [x for x in re.split(r'\W+', t) if x and x not in _ST]
def item_keys(label):
    lab = re.sub(r'\s*\(dans un coffre\)', '', label)
    if lab in ITEM_FIX: return [('N' + k[2:]) if k.startswith('!N') else 'I' + k for k in ITEM_FIX[lab]]
    if THROWN.search(lab): return []
    lt = set(_toks(lab))
    c = sorted([i for i in ITEMS if lt and lt <= set(_toks(i)) and not i.endswith('_C') and 'Shop' not in i],
               key=lambda i: (len(set(_toks(i)) - lt), len(i)))
    return ['I' + c[0]] if c else []
d = json.load(open('data.json', encoding='utf-8'))
c = collections.Counter()
for z in d['zones']:
    for p in z['pois']:
        if p[0] == 'bestiaire': continue                 # clés posées par add_bestiary.py
        del p[7:]
        if p[0] == 'enemy': continue                      # les ennemis réapparaissent : rien à cocher
        keys = []
        if p[0] == 'sci':
            k = re.search(r'Unlock_(\d+)', p[6]).group(1)
            keys = ['NWeaponUpgradeUnlock_%02d' % int(k)]     # compte comme fait une fois remise au scientifique
        elif p[0] == 'challenge':
            keys = ['N' + p[4].lower()]
        else:
            o = next((lv[(b, p[6])] for b in z['levels'] if (b, p[6]) in lv), None)
            pr = (o or {}).get('Properties') or {}
            if p[0] in ('save', 'tp'):
                ld = pr.get('LocationData')
                if isinstance(ld, dict): keys = ['O' + ld['ObjectName'].split("'")[1]]
            else:
                keys = ['G' + g2hex(g) for g in pr.get('GUIDs', [])]
                keys += next((inchest[(b, p[6])] for b in z['levels'] if (b, p[6]) in inchest), [])
                if p[0] == 'note' and pr.get('ImportKey'): keys.append('NReadNote_' + pr['ImportKey'])
                if p[0] == 'unique': keys += [k for k in item_keys(p[4]) if k not in keys]
                if p[0] in ('secret', 'mech') and (pr.get('ActivatableMode') or not keys):
                    bb = next(b for b in z['levels'] if (b, p[6]) in lv)
                    keys += [k for k in dict.fromkeys(trigger_keys(bb, p[6])) if k not in keys]
        if keys: p.append(keys); c[p[0]] += 1
        else: c[p[0] + ' (sans clé)'] += 1
# téléporteurs sans LocationData : les utiliser n'écrit rien dans la sauvegarde, on les déduit d'indices qui, eux, y sont
P = {(z['id'], p[6]): p for z in d['zones'] for p in z['pois']}
def ks(zid, *names): return [k for n in names for k in (P[(zid, n)][7] if len(P.get((zid, n), [])) > 7 else [])]
# mini-téléporteur entre le Jardin de pierre et la zone finale : fait dès qu'on est allé dans la zone finale,
# ou qu'on a ouvert le mur secret qui cache le pad du Jardin
fs_tp = ks('zone-finale', 'PigeonFossil_Pickup', 'SecretWall4_2', 'SkullKeyRelic_BP_2') + ks('jardin-de-pierre', 'SecretWall3')
TP_FIX = {('marchand', 'ShopTeleportDestination_2'): ['OGR_ShopIsland_Save', 'NShopUnlockFinished'],   # arrivée sur l'île du marchand
          ('jardin-de-pierre', 'MiniTeleporter2'): fs_tp, ('zone-finale', 'MiniTeleporter_2'): fs_tp}
for (zid, n), keys in TP_FIX.items():
    p = P.get((zid, n))
    if p is not None and keys and len(p) == 7:
        p.append(list(dict.fromkeys(keys))); c[p[0]] += 1; c[p[0] + ' (sans clé)'] -= 1
json.dump(d, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
for k, v in sorted(c.items()): print(k, v)
