import json, sys, time, urllib.parse, urllib.request
UA = "rhodes-tour-research/1.0 (personal walking tour)"
def geocode(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"format":"json","limit":3,"q":q, "viewbox":"28.18,36.48,28.28,36.40","bounded":0})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
names = [l.strip() for l in sys.stdin if l.strip()]
out = {}
for n in names:
    try:
        res = geocode(n + ", Rhodes, Greece")
        out[n] = [{"lat":float(x["lat"]),"lon":float(x["lon"]),"name":x.get("display_name","")[:90],"type":x.get("type")} for x in res]
    except Exception as e:
        out[n] = {"error": str(e)}
    time.sleep(1.1)
json.dump(out, open(sys.argv[1],"w"), indent=1, ensure_ascii=False)
for n,v in out.items():
    if isinstance(v, list) and v:
        print(f"{n:45s} {v[0]['lat']:.5f} {v[0]['lon']:.5f}  {v[0]['name'][:70]}")
    else:
        print(f"{n:45s} NO RESULT {v}")
