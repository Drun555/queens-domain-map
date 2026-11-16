#!/usr/bin/env python3
"""Catégories « Bestiaire » (un repère par créature et par zone) et « Cellules d'énergie ».
Clés de sauvegarde du bestiaire : 'K<nom de la fiche>' (KilledEnemyCounts) + GUID du point d'apparition."""
import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
import json, glob, os, re, struct, collections
MAPS = ROOT + '/all/RuinsLevel/Maps/'
def g2hex(g): return b''.join(struct.pack('<I', int(x, 16)) for x in g.split('-')).hex()
killed_names = json.load(open(ROOT + '/input/enemy_names.json'))
STOP = {'data', 'default', 'base', 'regular', '00', 'defaultdata', 'spawner', 'bp', 'c', 'the', '01'}
def toks(s):
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s).lower().replace('_', ' ')
    return [t for t in re.split(r'\W+', s) if t and t not in STOP]
FIX = {  # étiquette du point d'apparition -> fiche du bestiaire (vérifié à la main)
 'Boner Shrineboss Demo': 'Boner_Shrineboss_Grave_Data', 'Book Bug Big': 'BookBug_Base_Data', 'Book Bug Small': 'BookBug_Popcorn_Data',
 'Crawler No Candles': 'Crawler_Base_Data', 'Crawler Rotten No Candles': 'Crawler_Rotten_Data', 'Fish Maner No Element': 'Fishman_NonPoison_Data',
 'Fisher Small': 'Fisher_01_Data', 'Rattybugger Gold': 'RattyBugger_Gold', 'Rattybugger Regular': 'RattyBugger_00_Base',
 'Sea Slug Base': 'Seaslug_Base_Data', 'Sea Slug SZ': 'Seaslug_SZ_Data', 'Sparklebugger': 'SparkleBugger_Data', 'Stoner Boner': 'Boner_Stone_Archer_Data',
 'Golem': 'Golem_Default_Data', 'Looker Disguised': 'Looker_Default_Data',
 # fiches dont le nom interne est inconnu : on s'appuie sur l'état du point d'apparition (boss uniques)
 'Bone Machine': None, 'King Fishman': None, 'Book Bug Albino': None, 'Legally Distinct Green Skeleton': None, 'Sipeha': None,
}
for i in range(1, 8): FIX['Potion Lizer %02d' % i] = 'Potion_Lizer_%d' % i
def fiche(label):
    if label in FIX: return FIX[label]
    lt = set(toks(label))
    return sorted(killed_names, key=lambda nm: (-len(lt & set(toks(nm))), len(set(toks(nm)) - lt)))[0]
NICE = {'Golem_Mossy_Data': 'Golem Mossy'}
lv = {}
d = json.load(open('data.json', encoding='utf-8'))
for z in d['zones']:
    for b in z['levels']:
        if b in lv: continue
        L = json.load(open(MAPS + b + '.json', encoding='utf-8-sig'))
        lv[b] = {o['Name']: o for o in L if (o.get('Outer') or {}).get('ObjectName', '').endswith("PersistentLevel'")}
cats = [c for c in d['cats'] if c['id'] not in ('bestiaire', 'energy')]
i = [c['id'] for c in cats].index('collect') + 1
cats[i:i] = [{'id': 'energy', 'label': "Cellules d'énergie", 'color': '#22d3ee', 'on': 1},
             {'id': 'bestiaire', 'label': 'Bestiaire (1 par créature)', 'color': '#a78bfa', 'on': 0}]
d['cats'] = cats
nb = collections.Counter(); seen_types = set()
for z in d['zones']:
    z['pois'] = [p for p in z['pois'] if p[0] != 'bestiaire']
    for p in z['pois']:
        if re.search(r'EnergyCell', p[6]) or 'Energy Cell' in p[4] and p[0] != 'chest': p[0] = 'energy'; nb['energy'] += 1
    first = {}
    for p in z['pois']:
        if p[0] not in ('enemy', 'boss') or 'piège' in p[4]: continue
        o = lv[z['levels'][p[5]]].get(p[6]) or {}
        pr = o.get('Properties') or {}
        ed = pr.get('EnemyData')
        f = ed['ObjectName'].split("'")[1] if isinstance(ed, dict) and 'Group' not in ed['ObjectName'] and 'Team' not in ed['ObjectName'] and 'Duo' not in ed['ObjectName'] else fiche(p[4])
        k = f or ('?' + p[4])
        if k in first: continue
        keys = (['K' + f] if f else []) + ['G' + g2hex(g) for g in pr.get('GUIDs', [])] if (not f or p[0] == 'boss') else ['K' + f]
        name = NICE.get(f, p[4])
        if p[0] == 'boss' and f and len(p) > 7 and 'K' + f not in p[7]: p[7].append('K' + f)
        first[k] = ['bestiaire', p[1], p[2], p[3], name, p[5], p[6], keys]
        seen_types.add(k)
    z['pois'] += list(first.values()); nb['bestiaire'] += len(first)
json.dump(d, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(dict(nb), '| fiches différentes :', len(seen_types))
