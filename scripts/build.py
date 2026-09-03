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
aud={}
mp=_os.path.join(_os.environ.get('RHODES_REPO','/Users/robgruhl/Projects/rhodes'),'docs','audio','manifest.json')
if _os.path.exists(mp):
    aud=json.load(open(mp)).get('clips',{})
tpl=tpl.replace('/*__AUDIO__*/{}',json.dumps(aud,separators=(',',':')))
PAGES='https://robgruhl.github.io/rhodes-landfall/'
tpl=tpl.replace("/*__AUDIO_BASE__*/''",json.dumps(PAGES)).replace('/*__LIVE__*/false','false')
tpl=tpl.replace('<!--__CONTENT__-->',open('data/content.html').read())
open('rhodes-landfall.html','w').write(tpl)
# GitHub Pages variant: live OpenStreetMap tiles instead of the embedded bundle
live=tpl.replace(open('data/tiles.js').read(),'')
live=live.replace("const Local=L.TileLayer.extend({getTileUrl:function(c){return (typeof TILES!=='undefined'&&TILES[c.z+'/'+c.x+'/'+c.y])||BLANK;}});\n  new Local('',{minZoom:15,maxZoom:19,minNativeZoom:15,maxNativeZoom:17,tileSize:256,attribution:'&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'}).addTo(map);",
 "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{minZoom:13,maxZoom:19,attribution:'&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors'}).addTo(map);")
live=live.replace("minZoom:15,maxZoom:19,zoomSnap:.5","minZoom:13,maxZoom:19,zoomSnap:.5")
live=live.replace('const AUDIO_BASE = '+json.dumps(PAGES)+';',"const AUDIO_BASE = '';").replace('const LIVE = false;','const LIVE = true;')
live=live.replace("Tiles cached for offline viewing on 2 September 2026.","Map tiles load live from OpenStreetMap; the offline copy embeds them.")
import os; os.makedirs('docs',exist_ok=True)
open('docs/index.html','w').write(live)
print('live variant bytes',len(live), 'tile layer replaced:', "tile.openstreetmap.org/{z}" in live)
print('pins',len(pins),'html bytes',len(tpl))
for p in pins: print(f"{p['cat']:9s} {p.get('n','') or '':>2} {p['walk']!s:>4} min  {p['name']}")
