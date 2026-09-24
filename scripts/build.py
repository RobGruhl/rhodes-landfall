import json, sys, re
sys.path.insert(0,'.')
import router
QUAY=(36.44511,28.23313)
pins=json.load(open('data/pins.json'))
qn=router.nearest(QUAY)
for p in pins:
    n=router.nearest((p['lat'],p['lon']))
    path,d=router.dijkstra(qn,n)
    if router.hav(router.pos[n],(p['lat'],p['lon']))>300: path=None
    if path:
        pts=[router.pos[k] for k in path]
        real=sum(router.hav(pts[i],pts[i+1]) for i in range(len(pts)-1))
        p['walk']=max(1,round(real/75))
    else:
        p['walk']=None
route=json.load(open('data/route.json'))

# splice the rampart walk (real wall geometry) into the route between the walls-walk start and end pins
import os
if os.path.exists('data/wallwalk.json'):
    wall=json.load(open('data/wallwalk.json'))
    coords=route['coords']
    def idx_near(p): return min(range(len(coords)), key=lambda i:router.hav(coords[i],p))
    a=idx_near((36.44532,28.22348)); b=idx_near((36.44002,28.22843))
    if a<b:
        route['coords']=coords[:a+1]+wall+coords[b:]
        for l in route['legs']:
            if l['from'].startswith('Walls walk'): l['m']=1100; l['min']=60.0; l['note']='rampart walk'
day=json.load(open('data/day.json'))
tpl=open('template.html').read()
tpl=tpl.replace('/*__LEAFLET_CSS__*/',open('data/leaflet.min.css').read())
tpl=tpl.replace('/*__TILES__*/',open('data/tiles.js').read())
tpl=tpl.replace('/*__ROUTE__*/[]',json.dumps(route['coords'],separators=(',',':')))
tpl=tpl.replace('/*__PINS__*/[]',json.dumps(pins,ensure_ascii=False,separators=(',',':')))
tpl=tpl.replace('/*__DAY__*/[]',json.dumps(day,ensure_ascii=False,separators=(',',':')))
import os as _os
# audio: one manifest per narration set (docs/audio/<set>/manifest.json), merged as {slug: {set: clips}}
aud={}
import glob as _glob
_repo=_os.environ.get('RHODES_REPO','/Users/robgruhl/Projects/rhodes')
for mp in sorted(_glob.glob(_os.path.join(_repo,'docs','audio','*','manifest.json'))):
    m=json.load(open(mp)); st=m.get('set') or _os.path.basename(_os.path.dirname(mp))
    for slug,clips in m.get('clips',{}).items():
        aud.setdefault(slug,{})[st]=clips
tpl=tpl.replace('/*__AUDIO__*/{}',json.dumps(aud,separators=(',',':')))
PAGES='https://robgruhl.github.io/rhodes-landfall/'
tpl=tpl.replace("/*__AUDIO_BASE__*/''",json.dumps(PAGES)).replace('/*__LIVE__*/false','false')
tpl=tpl.replace('<!--__CONTENT__-->',open('data/content.html').read())
ROOT=_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
DOCS=_os.path.join(ROOT,'docs'); _os.makedirs(DOCS,exist_ok=True)
# phone app: manifest, icon, service worker (see scripts/sw.js and save.html)
PWA_HEAD='''<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Rhodes">
<script>if('serviceWorker' in navigator&&(location.protocol==='https:'||location.hostname==='localhost'))navigator.serviceWorker.register('sw.js').catch(function(){});</script>'''
tpl=tpl.replace('<!--__PWA_HEAD__-->',PWA_HEAD)
# Leaflet inline, so the map draws with no network at all
tpl=tpl.replace('/*__LEAFLET_JS__*/',open('data/leaflet.min.js').read().replace('//# sourceMappingURL=leaflet.js.map',''))
open(_os.path.join(DOCS,'offline.html'),'w').write(tpl)
# GitHub Pages variant: live OpenStreetMap tiles instead of the embedded bundle
live=tpl.replace(open('data/tiles.js').read(),'')
live=live.replace("const Local=L.TileLayer.extend({getTileUrl:function(c){return (typeof TILES!=='undefined'&&TILES[c.z+'/'+c.x+'/'+c.y])||BLANK;}});\n  new Local('',{minZoom:15,maxZoom:19,minNativeZoom:15,maxNativeZoom:17,tileSize:256,attribution:'&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'}).addTo(map);",
 "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{minZoom:13,maxZoom:19,attribution:'&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'}).addTo(map);")
live=live.replace("minZoom:15,maxZoom:19,zoomSnap:.5","minZoom:13,maxZoom:19,zoomSnap:.5")
live=live.replace('const AUDIO_BASE = '+json.dumps(PAGES)+';',"const AUDIO_BASE = '';").replace('const LIVE = false;','const LIVE = true;')
live=live.replace("Tiles cached for offline viewing on 2 September 2026.","Map tiles load live from OpenStreetMap; the offline copy embeds them.")
open(_os.path.join(DOCS,'index.html'),'w').write(live)
# reader page: both narration sets, the merged audio map, pin names by slug
import glob as _g2
_stops={}
for _set in ('rob','jamie'):
    _l=[]
    for _f in sorted(_g2.glob(_os.path.join(_repo,'narration',_set+'-*.json'))): _l+=json.load(open(_f))
    _l.sort(key=lambda x:x['n']); _stops[_set]=[{k:x[k] for k in ('n','slug','title','short','long')} for x in _l]
_places={p['aud']:p['name'] for p in pins if p.get('aud')}
rd=open('reader.html').read()
rd=rd.replace('/*__STOPS__*/{}',json.dumps(_stops,ensure_ascii=False,separators=(',',':')))
rd=rd.replace('/*__AUDIO__*/{}',json.dumps(aud,separators=(',',':')))
rd=rd.replace('/*__PLACES__*/{}',json.dumps(_places,ensure_ascii=False,separators=(',',':')))
rd=rd.replace("/*__AUDIO_BASE__*/''","''")
rd=rd.replace('<!--__PWA_HEAD__-->',PWA_HEAD)
open(_os.path.join(DOCS,'read.html'),'w').write(rd)
# save page: every clip with its size, per narrator
_files={}
for _set in ('rob','jamie'):
    _m=json.load(open(_os.path.join(DOCS,'audio',_set,'manifest.json')))
    _files[_set]=[{'file':c[k]['file'],'bytes':_os.path.getsize(_os.path.join(DOCS,c[k]['file']))} for c in _m['clips'].values() for k in ('short','long') if k in c]
sv=open('save.html').read().replace('<!--__PWA_HEAD__-->',PWA_HEAD).replace('/*__FILES__*/{}',json.dumps(_files,separators=(',',':')))
open(_os.path.join(DOCS,'save.html'),'w').write(sv)
open(_os.path.join(DOCS,'manifest.webmanifest'),'w').write(json.dumps({
    'name':'Rhodes Landfall','short_name':'Rhodes','display':'standalone','scope':'./',
    'background_color':'#FAF8F3','theme_color':'#8B3A2F',
    'icons':[{'src':'icon-180.png','sizes':'180x180','type':'image/png'},{'src':'icon-512.png','sizes':'512x512','type':'image/png'}]},indent=1))
# the worker's cache name changes whenever any page or manifest does, so phones pick up rebuilds
import hashlib as _h
_v=_h.sha256()
for _f in ('index.html','offline.html','read.html','save.html','manifest.webmanifest','audio/rob/manifest.json','audio/jamie/manifest.json'):
    _v.update(open(_os.path.join(DOCS,_f),'rb').read())
open(_os.path.join(DOCS,'sw.js'),'w').write(open('sw.js').read().replace('__VERSION__',_v.hexdigest()[:12]))
print('reader bytes',len(rd),'stops',{k:len(v) for k,v in _stops.items()})
print('live variant bytes',len(live), 'tile layer replaced:', "tile.openstreetmap.org/{z}" in live)
print('pins',len(pins),'html bytes',len(tpl))
for p in pins: print(f"{p['cat']:9s} {p.get('n','') or '':>2} {p['walk']!s:>4} min  {p['name']}")
