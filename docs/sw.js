// Rhodes Landfall service worker: keeps the pages, fonts and saved audio on the phone.
// Pages live in a versioned cache (build.py stamps VERSION); audio lives in its own
// unversioned cache so a page update never throws away 100+ MB of downloaded clips.
const VERSION = '97a090edf80c';
const SHELL = 'rhodes-shell-' + VERSION;
const AUDIO = 'rhodes-audio';
const FONTS = 'rhodes-fonts';
const SHELL_FILES = ['./', 'index.html', 'offline.html', 'read.html', 'save.html',
  'manifest.webmanifest', 'icon-180.png', 'icon-512.png', 'scripts-rob.pdf', 'scripts-jamie.pdf',
  'audio/rob/manifest.json', 'audio/jamie/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES.map(f => new Request(f, {cache: 'reload'})))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(k => k.startsWith('rhodes-shell-') && k !== SHELL).map(k => caches.delete(k))
  )).then(() => self.clients.claim()));
});

const scope = () => new URL(self.registration.scope);

// Safari asks for audio in byte ranges and will not play a plain 200 in reply,
// so cut the saved file to the requested range and answer 206.
async function ranged(req, res) {
  const range = req.headers.get('range');
  const blob = await res.blob();
  const type = res.headers.get('content-type') || 'audio/mpeg';
  const size = blob.size;
  if (!range) return new Response(blob, {status: 200, headers: {'Content-Type': type, 'Content-Length': String(size), 'Accept-Ranges': 'bytes'}});
  const m = /bytes=(\d*)-(\d*)/.exec(range);
  let start = m && m[1] !== '' ? parseInt(m[1], 10) : NaN;
  let end = m && m[2] !== '' ? parseInt(m[2], 10) : NaN;
  if (isNaN(start)) { start = Math.max(0, size - (isNaN(end) ? size : end)); end = size - 1; }
  if (isNaN(end) || end >= size) end = size - 1;
  if (start >= size || start > end) return new Response(null, {status: 416, headers: {'Content-Range': `bytes */${size}`}});
  return new Response(blob.slice(start, end + 1, type), {status: 206, headers: {
    'Content-Type': type, 'Content-Length': String(end - start + 1),
    'Content-Range': `bytes ${start}-${end}/${size}`, 'Accept-Ranges': 'bytes'}});
}

async function audio(req) {
  const hit = await caches.match(req.url, {cacheName: AUDIO, ignoreSearch: true});
  if (hit) return ranged(req, hit);
  return fetch(req);  // not saved yet: stream it
}

// Pages: answer from the phone at once, refresh the copy in the background when there is signal.
async function shell(req, event) {
  const cache = await caches.open(SHELL);
  const hit = await cache.match(req, {ignoreSearch: true});
  const refresh = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; });
  if (hit) { event.waitUntil(refresh.catch(() => {})); return hit; }
  return refresh;
}

async function fonts(req, event) {
  const cache = await caches.open(FONTS);
  const hit = await cache.match(req, {ignoreVary: true});
  const refresh = fetch(req).then(res => { if (res.ok || res.type === 'opaque') cache.put(req, res.clone()); return res; });
  if (hit) { event.waitUntil(refresh.catch(() => {})); return hit; }
  return refresh;
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') { e.respondWith(fonts(req, e)); return; }
  const base = scope();
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) return;
  const rel = url.pathname.slice(base.pathname.length);
  if (/^audio\/.+\.mp3$/.test(rel)) { e.respondWith(audio(req)); return; }
  // The phone map: index.html pulls live map tiles, offline.html carries its own,
  // so on a device with this worker the Map always opens the self-contained copy.
  if (rel === '' || rel === 'index.html') {
    e.respondWith(caches.open(SHELL).then(c => c.match(base.href + 'offline.html')).then(hit => hit || shell(req, e)));
    return;
  }
  e.respondWith(shell(req, e));
});
