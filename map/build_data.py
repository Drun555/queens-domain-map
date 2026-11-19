import os as _os
ROOT = _os.environ.get('QD_ROOT', _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # dossier du dépôt
DEV_LEFTOVERS = {('210_AQ_underground','TeleporterFragment_Pickup_BP2'),('500_AUT','EnergyDagger_Pickup2'),('500_AUT','Vampire_Dagger_Pickup2'),('600_Castle','Chicken_Upgrade_Pickup_2'),('600_Castle','Fish_UpgradePickup_2'),('600_Castle','TeleporterFragment_Pickup_BP_2'),('780_SZ_Depths','CrystalFragment_Pickup_BP2_2')}
import json,re,collections,math
d=json.load(open(ROOT + '/input/queens-domain-actors.json'))
ZONES=[ # id, label, sous-titre, niveaux
 ('ile','Île de Neasied','Ruines vertes, camp, îles extérieures',['100_GR','110_GR_dungeon','120_GR_goldenroom','125_GR_CubeHall','130_GR_outerisles']),
 ('marchand','Île du marchand','140_GR_ShopIsleOnly',['140_GR_ShopIsleOnly']),
 ('aquatique',"Temple d'Obmuer",'200_AQ, 210_AQ_underground',['200_AQ','210_AQ_underground']),
 ('tour-du-savoir','Tour du savoir','300_LIB, extérieur, sous-sol',['300_LIB','310_LIB_exterior','320_LIB_basement']),
 ('mausolee','Mausolée de Deimpo','400, 420, 450_MAUS',['400_MAUS_entrance','420_MAUS_mid','450_MAUS_darkmaze']),
 ('automne','Île d\'automne','500_AUT, tunnel',['500_AUT','510_AUT_droptunnel']),
 ('chateau','Château de Siraatsu','600_Castle, extérieur',['600_Castle','610_Castle_Ext']),
 ('sz-ruines','Zone secrète des ruines','700_SZ_GR',['700_SZ_GR']),
 ('sz-aquatique','Zone secrète aquatique','710_SZ_AQ',['710_SZ_AQ']),
 ('sz-tour','Zone secrète de la Tour','720_SZ_LIB',['720_SZ_LIB']),
 ('hod','HOD','730_HOD',['730_HOD']),
 ('prison','Prison','740_SZ_Prison',['740_SZ_Prison']),
 ('sz-mausolee','Mausolée profond','750_SZ_MAUS2',['750_SZ_MAUS2']),
 ('dekanima','Dekanima','760_Dekanima',['760_Dekanima']),
 ('ros','Registre du péché','760_SZ_AUT',['760_SZ_AUT']),
 ('marais','Caverne pourrissante','770_SZ_Swamp',['770_SZ_Swamp']),
 ('jigeki','Temple de Jigeki','775_JigekiTemple',['775_JigekiTemple']),
 ('foret','Val verdoyant','780_SZ_Depths',['780_SZ_Depths']),
 ('jardin-de-pierre','Jardin pétrifié','790_SG',['790_SG']),
 ('zone-finale','Zone finale','800_FinalZone',['800_FinalZone']),
 ('sipeha','Monde de Sipeha','900_SipehaWorld',['900_SipehaWorld']),
]
OFFSET={'900_SipehaWorld':(28000,-35000,20000)}
CATS=[ # id,label,color,default
 ('save','Cristaux de sauvegarde','#7fe3ff',1),('tp','Téléporteurs','#b79bff',1),('chest','Coffres','#ffc24a',1),
 ('unique','Armes et objets uniques','#ff7a59',1),('key','Clés et livres','#f2e36b',1),('sci','Pièces du scientifique','#4f8cff',1),('upgrade','Améliorations','#6fe08c',1),
 ('skull','Crânes argentés (Skull Key Relic)','#c9d2de',1),('collect','Collectibles','#ff9ad5',1),('egg','Œufs','#ffb38a',1),('npc','PNJ','#ffffff',1),('note','Notes et tablettes','#c9b48a',1),
 ('flesh','Murs de chair','#e0527a',1),('secret','Murs secrets','#5fd0b8',0),('boss','Boss et ennemis uniques','#ff3b3b',0),
 ('challenge','Zones de défi','#9fb4ff',0),('consum','Consommables et pièces','#b8a24a',0),
 ('enemy','Ennemis','#a05a5a',0),
]
tc=collections.Counter(a['t'] for l in d['levels'] for a in l['actors'])
FX=re.compile(r'CeilingDust|UnstableCeilingFX|RandomSparks|BloodPool|EnemySpawner_C$')
def cat(t,p):
    if t=='Checkpoint_C': return 'save'
    if t in('Teleporter_C','MiniTeleporter_C'): return 'tp'
    if re.search(r'(^|_)Chest(_|$)',t) and 'Charm' not in t: return 'chest'
    if t=='NecroWall_Manager_BP_C': return 'flesh'
    if t in('SecretWall_C','ScienceSecretWall_C') or re.search(r'SecretZoneDoor|SecretSkull|SecretTeleporter',t): return 'secret'
    if t=='ChallengeCompleteVolume_C': return 'challenge'
    if re.search(r'Oldnotes|SmallTablet|^Note$',t): return 'note'
    if re.search(r'NPC|Shopkeeper',t) and 'Collision' not in t: return 'npc'
    if t.endswith('Spawner_C') or t.endswith('Spawner_BP_C') or t.endswith('Spawner_Default_C') or 'TrapDecoy' in t or t.startswith('Potion_Lizer'):
        if FX.search(t): return None
        if re.search(r'Boss|Miniboss',t) or (tc[t]==1 and 'TrapDecoy' not in t): return 'boss'
        return 'enemy'
    if re.search(r'Coin|Herb_Item|HealingPotion|Cure_Pickup|Fruit_Pickup|Panacea|WeaponXPPotion|RejuvenatingPotion|IronPotion|BerserkPotion',t): return 'consum'
    if 'WeaponUpgradeUnlock' in t: return 'sci'
    if re.search(r'Upgrade_?Pedestal|UpgradePedestal|Upgrade_?Pickup|UpgradePickup|WeaponUpgradeUnlock|FlyingSwordChargeRelic|FlyingSwordUltraMoveRelic|HPIncreaseNecklace|WeaponUpgradeMachine',t): return 'upgrade'
    if 'SkullKeyRelic' in t: return 'skull'
    if 'FishWife_Egg' in t: return 'egg'          # œufs de la femme-poisson : catégorie à part
    if re.search(r'SkullKeyRelic|CrystalFragment|TeleporterFragment|EnergyCell|RaiderNecklace',t): return 'collect'
    if re.search(r'BookKey|Key_|_key_|KeyTrident|DoorKey|KnightsKey|SwordShrineKey|TowerDoor_Key',t) and not re.search(r'Recepticle|Receptacle|Slot',t): return 'key'
    if re.search(r'Pickup|SecretSword_Item|Dek_Egg',t): return 'unique'
    return None
# objets retirés de la carte : rien à trouver pour le joueur (zone, nom interne)
EXCLURE={('jardin-de-pierre','SecretTeleporterDestination2_2')}
def pretty(t):
    s=re.sub(r'_C$','',t); s=re.sub(r'(_BP\d*|_Bp|_PickupBP|_Pickup\d*|_ItemBP|_Item_BP|_Item_Bp|_Item|_Spawner_BP|_Spawner|_NPC|_Data|_Inspect)(?=_|$)','',s)
    s=re.sub(r'_BP\d*$','',s); s=s.replace('_',' ')
    s=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',s); s=re.sub(r'\s+',' ',s).strip()
    return s
def refname(v): return v.split("'")[-1] if "'" in v else v.split(':')[-1]
def label(a,c):
    t=a['t']; p=a.get('p',{})
    if c in('save','tp'):
        v=p.get('LocationData') or p.get('LocationDA'); return pretty(refname(v)) if v else pretty(t)
    if c=='chest':
        items=[pretty(x.split(':')[0]) for x in p.get('ActorsToActivateOnOpen',[]) if isinstance(x,str) and re.search(r'Pickup|Item|Key|Relic|Fragment|Upgrade',x)]
        return 'Coffre'+(' : '+', '.join(items) if items else '')
    if c=='challenge': return str(p.get('ChallengeToComplete'))
    if c=='flesh': return 'Mur de chair ('+', '.join(x for x in p.get('NamedSaveDataToIncrement',[]) if x!='NecroWallsDestroyed')+')'
    if c=='note':
        ti=p.get('Title'); return (ti.get('SourceString') if isinstance(ti,dict) else None) or 'Note'
    if c=='npc':
        n=p.get('name'); base=(n.get('SourceString') if isinstance(n,dict) else None) or pretty(t)
        return base+(' (fantôme)' if 'Ghost' in t and 'fant' not in base else '')
    if c=='secret': return 'Mur secret' if 'Wall' in t else pretty(t)
    s=pretty(t)
    if 'TrapDecoy' in t: s+=' (piège)'
    return s
lv={l['level']:l for l in d['levels']}
out={'cats':[dict(id=c[0],label=c[1],color=c[2],on=c[3]) for c in CATS],'zones':[]}
tot=collections.Counter(); 
for zid,zl,zs,levels in ZONES:
    pois=[];bg=set()
    for li,ln in enumerate(levels):
        acts=lv[ln]['actors']; byn={a['n']:a for a in acts}
        ox,oy,oz=OFFSET.get(ln,(0,0,0))
        inchest=set(x.split(':',1)[1] for a in acts for x in a.get('p',{}).get('ActorsToActivateOnOpen',[]) if isinstance(x,str) and ':' in x)
        for a in acts:
            if 'x' not in a: continue
            x,y,z=a['x'],a['y'],a['z']
            cur=a; ok=True; depth=0
            while 'attach' in cur and depth<6:
                par=byn.get(cur['attach'])
                if not par or 'x' not in par: ok=False; break
                yaw=math.radians(par.get('yaw',0)); cs,sn=math.cos(yaw),math.sin(yaw)
                x,y=par['x']+x*cs-y*sn, par['y']+x*sn+y*cs; z+=par['z']
                cur=par; depth+=1
            if not ok: continue
            if x==0 and y==0: continue
            x+=ox;y+=oy;z+=oz
            c=cat(a['t'],a.get('p',{}))
            if (zid,a['n']) in EXCLURE: continue
            if c:
                lab=label(a,c)
                if a['n'] in inchest and c!='chest': lab+=' (dans un coffre)'
                # copies inutilisées laissées par les développeurs : jamais ramassables (absentes d'une sauvegarde à 100 %)
                if c in ('unique','upgrade','collect') and (ln, a['n']) in DEV_LEFTOVERS: continue
                pois.append([c,round(x),round(y),round(z),lab,li,a['n']]); tot[c]+=1
            bg.add((round(x/150),round(y/150),round(z/300)))
    # clip outliers for bg using percentiles
    xs=sorted(b[0] for b in bg); ys=sorted(b[1] for b in bg); zs_=sorted(b[2] for b in bg)
    def rng(v): n=len(v); lo,hi=v[int(n*0.01)],v[min(n-1,int(n*0.99))]; pad=(hi-lo)*0.6+20; return lo-pad,hi+pad
    (x0,x1),(y0,y1),(z0,z1)=rng(xs),rng(ys),rng(zs_)
    bgl=[b for b in bg if x0<=b[0]<=x1 and y0<=b[1]<=y1 and z0<=b[2]<=z1]
    pois=[p for p in pois if x0*150<=p[1]<=x1*150 and y0*150<=p[2]<=y1*150]
    flat=[v for b in sorted(bgl) for v in b]
    out['zones'].append(dict(id=zid,label=zl,sub=zs,levels=levels,pois=pois,bg=flat))
    print(zid,len(pois),'pois',len(bgl),'bg')
print(tot, sum(tot.values()))
s=json.dumps(out,ensure_ascii=False,separators=(',',':'))
open('data.json','w').write(s); print(len(s)/1e6,'MB')
# sanity
z=next(z for z in out['zones'] if z['id']=='tour-du-savoir')
for p in z['pois']:
    if p[0] in('flesh','save','tp') or 'Skullrod' in p[6]: print(p)
import random; random.seed(1)
allp=[p for z in out['zones'] for p in z['pois']]
for c in [c[0] for c in CATS]:
    ex=[p[4] for p in allp if p[0]==c]; print(c,len(ex),random.sample(ex,min(6,len(ex))))
