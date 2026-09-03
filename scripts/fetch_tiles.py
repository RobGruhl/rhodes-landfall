import math, os, time, urllib.request, json, sys
UA = "rhodes-tour-research/1.0 (personal walking tour; one-off fetch)"
def xy(lat, lon, z):
    n = 2**z
    x = int((lon+180)/360*n)
    y = int((1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n)
    return x, y
# (zoom, south, west, north, east)
AREAS = [
    (15, 36.425, 28.190, 36.472, 28.262),
    (16, 36.430, 28.195, 36.470, 28.256),
    (17, 36.4380, 28.2160, 36.4590, 28.2420),
]
out = "tiles"
manifest = {}
total = 0
for z, s, w, n, e in AREAS:
    x0, y1 = xy(s, w, z); x1, y0 = xy(n, e, z)
    tiles = [(x, y) for x in range(x0, x1+1) for y in range(y0, y1+1)]
    print(f"z{z}: x {x0}-{x1}, y {y0}-{y1} -> {len(tiles)} tiles", flush=True)
    for x, y in tiles:
        p = f"{out}/{z}_{x}_{y}.png"
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                open(p, "wb").write(data)
                total += len(data)
                break
            except Exception as ex:
                print("retry", z, x, y, ex, flush=True); time.sleep(2)
        time.sleep(0.15)
    manifest[z] = {"x0": x0, "x1": x1, "y0": y0, "y1": y1}
json.dump(manifest, open(f"{out}/manifest.json", "w"))
print("done, bytes fetched:", total, flush=True)
