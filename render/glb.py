import json,struct,numpy as np
CT={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
NC={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def load(path):
    b=open(path,'rb').read()
    assert b[:4]==b'glTF'
    off=12; js=None; bn=None
    while off<len(b):
        ln,ty=struct.unpack_from('<II',b,off); off+=8
        if ty==0x4E4F534A: js=json.loads(b[off:off+ln])
        elif ty==0x004E4942: bn=b[off:off+ln]
        off+=ln
    def acc(i):
        a=js['accessors'][i]; bv=js['bufferViews'][a['bufferView']]
        dt=np.dtype(CT[a['componentType']]); n=NC[a['type']]
        o=bv.get('byteOffset',0)+a.get('byteOffset',0); st=bv.get('byteStride')
        if st and st!=dt.itemsize*n:
            arr=np.ndarray((a['count'],n),dtype=dt,buffer=bn,offset=o,strides=(st,dt.itemsize))
        else:
            arr=np.frombuffer(bn,dtype=dt,count=a['count']*n,offset=o).reshape(a['count'],n)
        return np.array(arr)
    V=[];F=[];base=0
    for m in js.get('meshes',[]):
        for p in m['primitives']:
            if p.get('mode',4)!=4: continue
            v=acc(p['attributes']['POSITION']).astype(np.float64)
            f=acc(p['indices']).reshape(-1,3).astype(np.int64) if 'indices' in p else np.arange(len(v)).reshape(-1,3)
            V.append(v);F.append(f+base);base+=len(v)
    if not V: return None,None,js
    return np.vstack(V),np.vstack(F),js
if __name__=='__main__':
    import sys
    for p in sys.argv[1:]:
        V,F,js=load(p)
        print(p.split('/')[-1],'verts',len(V),'tris',len(F),'min',V.min(0).round(1),'max',V.max(0).round(1))
        print('  nodes',json.dumps(js.get('nodes'))[:300],'asset',js.get('asset'),'scenes',js.get('scenes'))

def load_prims(path):
    """Renvoie une liste de primitives : positions (cm, repère Unreal), indices, UV, nom du matériau."""
    b = open(path, 'rb').read()
    assert b[:4] == b'glTF'
    off = 12; js = None; bn = None
    while off < len(b):
        ln, ty = struct.unpack_from('<II', b, off); off += 8
        if ty == 0x4E4F534A: js = json.loads(b[off:off + ln])
        elif ty == 0x004E4942: bn = b[off:off + ln]
        off += ln
    def acc(i):
        a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
        dt = np.dtype(CT[a['componentType']]); n = NC[a['type']]
        o = bv.get('byteOffset', 0) + a.get('byteOffset', 0); st = bv.get('byteStride')
        if st and st != dt.itemsize * n:
            arr = np.ndarray((a['count'], n), dtype=dt, buffer=bn, offset=o, strides=(st, dt.itemsize))
        else:
            arr = np.frombuffer(bn, dtype=dt, count=a['count'] * n, offset=o).reshape(a['count'], n)
        return np.array(arr)
    names = [m.get('name', '') for m in js.get('materials', [])]
    out = []
    for m in js.get('meshes', []):
        for p in m['primitives']:
            if p.get('mode', 4) != 4: continue
            v = acc(p['attributes']['POSITION']).astype(np.float64)
            pos = np.stack([v[:, 0] * 100, v[:, 2] * 100, v[:, 1] * 100], 1)   # glTF (m, Y haut) -> Unreal (cm, Z haut)
            f = acc(p['indices']).reshape(-1, 3).astype(np.int64) if 'indices' in p else np.arange(len(v)).reshape(-1, 3)
            uv = acc(p['attributes']['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in p['attributes'] else np.zeros((len(v), 2))
            out.append({'pos': pos, 'idx': f, 'uv': uv, 'mat': names[p['material']] if 'material' in p and names else ''})
    return out
