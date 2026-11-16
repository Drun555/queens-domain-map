#!/usr/bin/env python3
"""Assemble site/index.html : template.html + data.json + le plan de chaque zone (site/tiles/<zone>/meta.json)."""
import json, os, sys
MIN_GAP = 900.0   # deux sols à moins de 9 m l'un de l'autre = paliers d'un même étage

def merge_floors(floors, gap=MIN_GAP):
    out = []
    for f in floors:
        lv = f['lvl'] if f['lvl'] is not None else f['z0']
        if out:
            p = out[-1]
            plv = p['lvl'] if p['lvl'] is not None else p['z0']
            if lv - plv < gap:
                p['z1'] = f['z1']
                if p['lvl'] is None:
                    p['lvl'] = f['lvl']
                continue
        out.append(dict(f))
    return out

def main():
    d = json.load(open('data.json', encoding='utf-8'))
    for z in d['zones']:
        p = 'site/tiles/%s/meta.json' % z['id']
        if not os.path.exists(p):
            continue
        meta = json.load(open(p))
        n = len(meta['floors'])
        meta['floors'] = merge_floors(meta['floors'], meta.get('mergeGap', MIN_GAP))
        meta['dir'] = 'tiles/%s/' % z['id']
        z['plan'] = meta
        print('%-18s %d étages (%d avant fusion), %d images' % (z['id'], len(meta['floors']), n, len(meta['bands'])))
    t = open('template.html', encoding='utf-8').read()
    s = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    from collections import Counter
    import html as _h
    cnt = Counter(p[0] for z in d['zones'] for p in z['pois'])
    skip = {'enemy', 'consum', 'npc'}
    zl = ''.join('<li>%s (%d objets)</li>' % (_h.escape(z['label']), sum(1 for p in z['pois'] if p[0] not in skip)) for z in d['zones'])
    cl = ''.join('<li>%s : %d</li>' % (_h.escape(c['label']), cnt[c['id']]) for c in d['cats'] if c['id'] not in skip and cnt[c['id']])
    t = t.replace('__SEO_ZONES__', zl).replace('__SEO_CATS__', cl)
    html = t.replace('__DATA__', s)
    open('site/index.html', 'w', encoding='utf-8').write(html)
    open('_check.js', 'w').write(html[html.rindex('<script>') + 8:html.rindex('</script>')])
    print('site/index.html %.2f Mo' % (len(html) / 1e6))

if __name__ == '__main__':
    main()
