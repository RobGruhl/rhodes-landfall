import json, math, heapq, sys
def hav(a, b):
    R=6371000.0
    la1,lo1=math.radians(a[0]),math.radians(a[1]); la2,lo2=math.radians(b[0]),math.radians(b[1])
    d=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(d))
ways=json.load(open('data/ways.json'))['elements']
pos={}; adj={}
BAD={'motorway','trunk'}
for w in ways:
    t=w.get('tags',{})
    if t.get('highway') in BAD: continue
    if t.get('access') in ('private','no') and t.get('foot') not in ('yes','designated'): continue
    if t.get('foot')=='no': continue
    factor=1.0
    if t.get('highway') in ('primary','secondary','primary_link','secondary_link'): factor=1.15
    if t.get('highway')=='steps': factor=1.3
    if t.get('highway') in ('service','track'): factor=1.05
    geo=w.get('geometry') or []
    ids=[(round(g['lat'],7),round(g['lon'],7)) for g in geo]
    for i,nid in enumerate(ids):
        pos[nid]=(geo[i]['lat'],geo[i]['lon'])
    for i in range(len(ids)-1):
        a,b=ids[i],ids[i+1]
        d=hav(pos[a],pos[b])*factor
        adj.setdefault(a,[]).append((b,d)); adj.setdefault(b,[]).append((a,d))
def nearest(pt):
    return min(pos, key=lambda n: hav(pos[n],pt))
def dijkstra(s,t):
    dist={s:0}; prev={}; pq=[(0,s)]
    while pq:
        d,u=heapq.heappop(pq)
        if u==t: break
        if d>dist.get(u,1e18): continue
        for v,w in adj.get(u,[]):
            nd=d+w
            if nd<dist.get(v,1e18):
                dist[v]=nd; prev[v]=u; heapq.heappush(pq,(nd,v))
    if t not in dist: return None, None
    path=[t]
    while path[-1]!=s: path.append(prev[path[-1]])
    return list(reversed(path)), dist[t]
def route(waypoints):
    coords=[]; legs=[]
    for i in range(len(waypoints)-1):
        a=nearest(waypoints[i][1]); b=nearest(waypoints[i+1][1])
        path,d=dijkstra(a,b)
        if path is None:
            print('NO PATH', waypoints[i][0], '->', waypoints[i+1][0], file=sys.stderr); continue
        pts=[pos[n] for n in path]
        real=sum(hav(pts[k],pts[k+1]) for k in range(len(pts)-1))
        legs.append({'from':waypoints[i][0],'to':waypoints[i+1][0],'m':round(real),'min':round(real/75,1)})
        if coords and coords[-1]==pts[0]: pts=pts[1:]
        coords.extend(pts)
    return coords, legs
if __name__=='__main__':
    wp=json.load(open(sys.argv[1]))
    coords,legs=route([(w['name'],(w['lat'],w['lon'])) for w in wp])
    total=sum(l['m'] for l in legs)
    json.dump({'coords':[[round(a,6),round(b,6)] for a,b in coords],'legs':legs,'total_m':total}, open(sys.argv[2],'w'))
    for l in legs: print(f"{l['from']:28s} -> {l['to']:28s} {l['m']:5d} m  {l['min']:4.1f} min")
    print('TOTAL', total, 'm', round(total/75), 'min at 4.5 km/h; points', len(coords))
