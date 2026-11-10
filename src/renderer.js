const PIXEL = 3;   // screen pixels per sprite pixel
const seq = (name, n) => Array.from({ length: n }, (_, i) => name + (i + 1));

// frames per state: [frame names, milliseconds per frame]
const ANIMS = {
  sit: [['sit'], 0],
  happy: [['happy'], 0],
  held: [['held'], 0],
  walk: [seq('walk', 8), 95],
  fall: [['fall1', 'fall2'], 100],
  sleep: [['sleep1', 'sleep1', 'sleep2', 'sleep3', 'sleep3', 'sleep2'], 520],
};
// played once after hitting the ground: [frame, milliseconds]
const LANDING = [['splat', 520], ['dazed', 750]];
const POSES = [...new Set([...Object.values(ANIMS).flatMap(([f]) => f), ...LANDING.map(([f]) => f), 'blink'])];

const stage = document.getElementById('stage');
const flip = document.getElementById('flip');
const sprite = document.getElementById('sprite');
const bubble = document.getElementById('bubble');
const fx = document.getElementById('fx');

// preload sprites + alpha masks for pixel-accurate clicking
const images = {}, masks = {};
for (const name of POSES) {
  const img = new Image();
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    masks[name] = ctx.getImageData(0, 0, c.width, c.height);
    if (name === pose) show(name);
  };
  img.src = `../assets/${name}.png`;
  images[name] = img;
}

let state = 'sit', pose = 'sit', dir = -1;

function show(name) {
  pose = name;
  const img = images[name];
  sprite.src = img.src;
  if (img.naturalWidth) sprite.style.width = img.naturalWidth * PIXEL + 'px';
}

function particle(cls, text) {
  const r = sprite.getBoundingClientRect(), s = stage.getBoundingClientRect();
  const el = document.createElement('span');
  el.className = 'particle ' + cls;
  el.textContent = text;
  el.style.left = (r.left - s.left + r.width * (0.25 + Math.random() * 0.5)) + 'px';
  el.style.top = (r.top - s.top + r.height * 0.15) + 'px';
  el.style.setProperty('--dx', (Math.random() * 50 - 25) + 'px');
  fx.appendChild(el);
  el.addEventListener('animationend', () => el.remove());
}

// ---------- frame animation ----------
let animTimer, landing = false;
function play(name) {
  clearTimeout(animTimer);
  landing = name === 'landing';
  if (landing) {
    let i = 0;
    const step = () => {
      if (i === LANDING.length) { landing = false; return play(state); }
      const [frame, ms] = LANDING[i++];
      show(frame);
      animTimer = setTimeout(step, ms);
    };
    return step();
  }
  const [frames, ms] = ANIMS[name];
  let i = 0;
  const step = () => {
    show(frames[i++ % frames.length]);
    if (frames.length > 1) animTimer = setTimeout(step, ms);
  };
  step();
}

let bubbleTimer;
function say(text) {
  bubble.textContent = text;
  bubble.hidden = false;
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => { bubble.hidden = true; }, 8000);
}

window.pup.onUpdate((d) => {
  dir = d.dir;
  flip.classList.toggle('right', dir === 1);
  if (d.state !== state || !sprite.src) {
    state = d.state;
    stage.className = state;
    play(d.land ? 'landing' : state);
  }
  if (d.hearts) for (let i = 0; i < 5; i++) setTimeout(() => particle('heart', '♥'), i * 160);
  if (d.bubble) say(d.bubble);
});

// idle life: blinks while sitting, z's while sleeping
setInterval(() => {
  if (state === 'sit' && pose === 'sit' && Math.random() < 0.3) {
    show('blink');
    setTimeout(() => { if (pose === 'blink') show('sit'); }, 190);
  }
}, 1000);
setInterval(() => { if (state === 'sleep') particle('zed', 'z'); }, 1400);

// ---------- mouse: click-through on transparent pixels, pet, drag ----------
function overPuppy(e) {
  const m = masks[pose];
  if (!m) return false;
  const r = sprite.getBoundingClientRect();
  let u = (e.clientX - r.left) / r.width, v = (e.clientY - r.top) / r.height;
  if (u < 0 || u >= 1 || v < 0 || v >= 1) return false;
  if (dir === 1) u = 1 - u;
  const x = Math.floor(u * m.width), y = Math.floor(v * m.height);
  return m.data[(y * m.width + x) * 4 + 3] > 40;
}

let ignoring = true, down = null, dragging = false, stroke = 0, strokeAt = 0;

window.addEventListener('mousemove', (e) => {
  if (dragging) return;
  const over = overPuppy(e);
  if (over === ignoring) { ignoring = !over; window.pup.ignoreMouse(ignoring); }
  if (down && Math.hypot(e.screenX - down.x, e.screenY - down.y) > 6) {
    dragging = true;
    window.pup.dragStart();
    return;
  }
  if (over && !down) {            // stroking the puppy counts as petting
    const t = performance.now();
    if (t - strokeAt > 1500) stroke = 0;
    stroke += Math.hypot(e.movementX, e.movementY);
    strokeAt = t;
    if (stroke > 320) { stroke = 0; window.pup.pet(); }
  }
});
window.addEventListener('mousedown', (e) => {
  if (e.button === 0 && overPuppy(e)) down = { x: e.screenX, y: e.screenY };
});
window.addEventListener('mouseup', (e) => {
  if (e.button !== 0) return;
  if (dragging) window.pup.dragEnd();
  else if (down) window.pup.pet();
  down = null; dragging = false;
});
window.addEventListener('contextmenu', (e) => {
  e.preventDefault();
  if (overPuppy(e)) window.pup.menu();
});
