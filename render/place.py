import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
"""Résout la position dans le monde de chaque maillage posé dans un niveau Unreal exporté."""
import json, math, numpy as np

def _rot(r):
    if not r: return np.eye(3)
    p = math.radians(r.get('Pitch', 0.0)); y = math.radians(r.get('Yaw', 0.0)); ro = math.radians(r.get('Roll', 0.0))
    cy, sy = math.cos(y), math.sin(y); cp, sp = math.cos(p), math.sin(p); cr, sr = math.cos(ro), math.sin(ro)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx                      # ordre Unreal : roulis, puis tangage, puis lacet

def _vec(v, d=0.0):
    return np.array([v.get('X', d), v.get('Y', d), v.get('Z', d)]) if v else np.array([d, d, d])


def _ref(ref):
    """(acteur, composant) depuis une référence Unreal 'Classe\'Niveau:PersistentLevel.Acteur.Composant\''."""
    if not ref: return (None, None)
    n = ref['ObjectName']
    body = n.split("'")[1] if "'" in n else n
    body = body.split('PersistentLevel.')[-1]
    parts = body.split('.')
    return (parts[-2] if len(parts) > 1 else None, parts[-1])

def placements(level_json):
    """[(nom du maillage, matrice 3x3, translation)] pour chaque StaticMeshComponent du niveau."""
    objs = json.load(open(level_json, encoding='utf-8-sig'))
    def short(ref):
        return ref['ObjectName'].split('.')[-1].rstrip("'") if ref else None
    by = {}
    for o in objs:
        outer = o.get('Outer')
        key = (short(outer) if outer else None, o['Name'])
        by[key] = o
    def world(o, actor, depth=0):
        """Transforme locale -> monde en remontant la chaîne d'attache."""
        p = o.get('Properties') or {}
        R = _rot(p.get('RelativeRotation')); T = _vec(p.get('RelativeLocation')); S = _vec(p.get('RelativeScale3D'), 1.0)
        par = p.get('AttachParent')
        if par is not None and depth < 12:
            pa, pc = _ref(par)
            pо = by.get((actor, pc)) or by.get((pa, pc))
            if pо is not None:
                PR, PT, PS = world(pо, pa or actor, depth + 1)
                return PR @ R, PT + PR @ (PS * T), PS * S
        return R, T, S
    out = []
    for o in objs:
        if o['Type'] not in ('StaticMeshComponent', 'InstancedStaticMeshComponent'): continue
        p = o.get('Properties') or {}
        sm = p.get('StaticMesh')
        if not isinstance(sm, dict): continue
        name = sm['ObjectName'].split("'")[1] if "'" in sm['ObjectName'] else sm['ObjectName']
        actor = (o.get('Outer') or {}).get('ObjectName', '')
        actor = actor.split('.')[-1].rstrip("'") if actor else None
        R, T, S = world(o, actor)
        out.append((name, R * S, T))          # l'échelle est absorbée dans les colonnes de R
    return out

if __name__ == '__main__':
    import sys, glob, os, collections
    pl = placements(sys.argv[1])
    have = {}
    for r in (ROOT + '/meshes/Library', ROOT + '/meshes/props'):
        for f in glob.glob(r + '/**/*.glb', recursive=True):
            have.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    miss = collections.Counter(n for n, _, _ in pl if n not in have)
    print(len(pl), 'maillages posés |', sum(1 for n, _, _ in pl if n in have), 'disponibles')
    print('manquants :', miss.most_common(12))

def actor_placements(level_json, mesh_names):
    """Place les acteurs Blueprint (meubles, livres…) en reliant leur classe au modèle de même nom."""
    import re
    norm = {}
    for m in mesh_names:
        norm.setdefault(re.sub(r'_(sm|mesh)$', '', m.lower()), m)
    objs = json.load(open(level_json, encoding='utf-8-sig'))
    def short(ref): return ref['ObjectName'].split('.')[-1].rstrip("'") if ref else None
    by = {}
    for o in objs:
        outer = o.get('Outer')
        by[(short(outer) if outer else None, o['Name'])] = o
    def world(o, actor, depth=0):
        p = o.get('Properties') or {}
        R = _rot(p.get('RelativeRotation')); T = _vec(p.get('RelativeLocation')); S = _vec(p.get('RelativeScale3D'), 1.0)
        par = p.get('AttachParent')
        if par is not None and depth < 12:
            pa, pc = _ref(par)
            q = by.get((actor, pc)) or by.get((pa, pc))
            if q is not None:
                PR, PT, PS = world(q, pa or actor, depth + 1)
                return PR @ R, PT + PR @ (PS * T), PS * S
        return R, T, S
    out, unmatched = [], {}
    for o in objs:
        outer = (o.get('Outer') or {}).get('ObjectName', '')
        if not outer.startswith("Level'"): continue          # acteurs posés directement dans le niveau
        cls = o['Type']
        if not cls.endswith('_C'): continue
        base = re.sub(r'_+$', '', re.sub(r'_?BP\d*', '', cls[:-2], flags=re.I)).lower()
        mesh = norm.get(base) or norm.get(base + '_sm') or norm.get(re.sub(r'_\d+$', '', base))
        if not mesh:
            unmatched[cls] = unmatched.get(cls, 0) + 1
            continue
        p = o.get('Properties') or {}
        rc = p.get('RootComponent')
        comp = by.get((o['Name'], short(rc))) if rc else None
        if comp is None: continue
        R, T, S = world(comp, o['Name'])
        out.append((mesh, R * S, T))
    return out, unmatched

if __name__ == '__main__' and len(sys.argv) > 2 if 'sys' in dir() else False:
    pass
