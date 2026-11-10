const { app, BrowserWindow, Tray, Menu, screen, ipcMain, powerMonitor, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

const MAC = process.platform === 'darwin';
const ASSETS = path.join(__dirname, '..', 'assets');
const BASE_W = 300, BASE_H = 330;      // window size at 100% scale
const TICK_MS = 33;
const REMINDERS = [
  'Time for some water? 💧',
  'Stretch break! Paws up 🐾',
  'Rest your eyes — look far away for 20 seconds 👀',
  'Stand up and wiggle a little!',
  'Deep breath in… and out 🌿',
  'Snack time? Asking for a friend 🦴',
];

// ---------- settings ----------
const settingsFile = () => path.join(app.getPath('userData'), 'settings.json');
let settings = { follow: true, reminderMinutes: 45, size: 1 };
function loadSettings() {
  try { Object.assign(settings, JSON.parse(fs.readFileSync(settingsFile(), 'utf8'))); } catch {}
}
function saveSettings() {
  try { fs.writeFileSync(settingsFile(), JSON.stringify(settings, null, 2)); } catch {}
}

// ---------- puppy brain ----------
let win, tray, timer;
const pup = {
  state: 'sit',     // sit | walk | sleep | happy | held | fall
  x: 0, y: 0,       // x = centre of puppy, y = feet (screen px)
  vy: 0, dir: -1,   // dir: -1 facing left, 1 facing right
  until: 0,         // time the current state ends
  target: null, following: false,
  grab: { dx: 0, dy: 0 },
};
let nextReminder = 0, reminderIndex = 0, lastSent = '', lastBounds = '';

const now = () => Date.now();
const rand = (a, b) => a + Math.random() * (b - a);
const area = () => screen.getDisplayNearestPoint({ x: Math.round(pup.x), y: Math.round(pup.y) - 20 }).workArea;
const ground = () => { const a = area(); return a.y + a.height; };

function enter(state, ms) {
  pup.state = state;
  pup.until = ms ? now() + ms : Infinity;
  if (state !== 'walk') { pup.target = null; pup.following = false; }
}
function sit() { enter('sit', rand(3000, 8000)); }
function nap() { enter('sleep', rand(40000, 120000)); }

function scheduleReminder() {
  nextReminder = settings.reminderMinutes > 0 ? now() + settings.reminderMinutes * 60000 : Infinity;
}

function decide() {
  const a = area();
  const cursor = screen.getCursorScreenPoint();
  const idle = powerMonitor.getSystemIdleTime();
  if (idle > 120) return nap();                        // you're away: nap time
  if (settings.follow && idle < 15 && Math.abs(cursor.x - pup.x) > 220 * settings.size) {
    pup.following = true;
    return enter('walk', 20000);
  }
  const r = Math.random();
  if (r < 0.45) {
    const half = 90 * settings.size;
    pup.target = rand(a.x + half, a.x + a.width - half);
    return enter('walk', 20000);
  }
  if (r < 0.62) return nap();
  sit();
}

function tick() {
  if (!win || win.isDestroyed()) return;
  const dt = TICK_MS / 1000, t = now(), s = settings.size;
  const a = area(), half = 90 * s;

  if (pup.state === 'held') {
    const c = screen.getCursorScreenPoint();
    pup.x = c.x + pup.grab.dx; pup.y = c.y + pup.grab.dy;
  } else if (pup.state === 'fall') {
    pup.vy += 2600 * dt; pup.y += pup.vy * dt;
    if (pup.y >= ground()) { pup.y = ground(); enter('sit', rand(4000, 8000)); send({ land: true }); }
  } else {
    pup.y = ground();
    if (pup.state === 'walk') {
      if (pup.following) pup.target = screen.getCursorScreenPoint().x;
      const d = pup.target - pup.x;
      const reach = pup.following ? 120 * s : 4;
      if (Math.abs(d) <= reach || t > pup.until) sit();
      else { pup.dir = d < 0 ? -1 : 1; pup.x += pup.dir * 75 * s * dt; }
    } else if (t > pup.until) {
      pup.state === 'sit' ? decide() : sit();
    }
    pup.x = Math.min(Math.max(pup.x, a.x + half), a.x + a.width - half);
  }

  if (t > nextReminder && pup.state !== 'held' && pup.state !== 'fall') {
    scheduleReminder();
    enter('sit', 9000);
    send({ bubble: REMINDERS[reminderIndex++ % REMINDERS.length] });
  }

  const W = Math.round(BASE_W * s), H = Math.round(BASE_H * s);
  const b = { x: Math.round(pup.x - W / 2), y: Math.round(pup.y - H), width: W, height: H };
  const key = `${b.x},${b.y},${W},${H}`;
  if (key !== lastBounds) {
    lastBounds = key;
    if (win.webContents.getZoomFactor() !== s) win.webContents.setZoomFactor(s);
    win.setBounds(b);
  }
  send();
}

function send(extra) {
  const base = { state: pup.state, dir: pup.dir };
  const key = JSON.stringify(base);
  if (!extra && key === lastSent) return;
  lastSent = key;
  win.webContents.send('pup', { ...base, ...extra });
}

// ---------- menu ----------
function buildMenu() {
  const radio = (label, key, value) => ({
    label, type: 'radio', checked: settings[key] === value,
    click: () => { settings[key] = value; saveSettings(); if (key === 'reminderMinutes') scheduleReminder(); refreshMenu(); },
  });
  return Menu.buildFromTemplate([
    { label: 'Pet the puppy', click: () => pet() },
    { label: 'Nap now', click: () => nap() },
    { label: 'Wake up', click: () => sit() },
    { type: 'separator' },
    { label: 'Follow my cursor', type: 'checkbox', checked: settings.follow,
      click: (i) => { settings.follow = i.checked; saveSettings(); refreshMenu(); } },
    { label: 'Gentle reminders', submenu: [
      radio('Off', 'reminderMinutes', 0), radio('Every 20 minutes', 'reminderMinutes', 20),
      radio('Every 45 minutes', 'reminderMinutes', 45), radio('Every 60 minutes', 'reminderMinutes', 60),
      { type: 'separator' },
      { label: 'Show one now', click: () => { nextReminder = 0; } },
    ] },
    { label: 'Size', submenu: [radio('Small', 'size', 0.7), radio('Medium', 'size', 1), radio('Large', 'size', 1.4)] },
    { label: MAC ? 'Start at login' : 'Start with Windows', type: 'checkbox', checked: app.getLoginItemSettings().openAtLogin,
      click: (i) => app.setLoginItemSettings({ openAtLogin: i.checked }) },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
}
function refreshMenu() { if (tray) tray.setContextMenu(buildMenu()); }

function pet() {
  if (pup.state === 'held' || pup.state === 'fall') return;
  enter('happy', 2400);
  send({ hearts: true });
}

// ---------- app ----------
if (!app.requestSingleInstanceLock()) app.quit();

app.whenReady().then(() => {
  loadSettings();
  const wa = screen.getPrimaryDisplay().workArea;
  pup.x = wa.x + wa.width - 260; pup.y = wa.y + wa.height;

  win = new BrowserWindow({
    width: BASE_W, height: BASE_H, x: Math.round(pup.x - BASE_W / 2), y: pup.y - BASE_H,
    transparent: true, frame: false, resizable: false, movable: false,
    skipTaskbar: true, hasShadow: false, focusable: false, alwaysOnTop: true, show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js') },
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  // macOS: no Dock icon (LSUIElement), and stay with you across Spaces and fullscreen apps
  if (MAC) win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile(path.join(__dirname, 'index.html'));
  win.once('ready-to-show', () => {
    win.showInactive();
    sit(); scheduleReminder();
    timer = setInterval(tick, TICK_MS);
    setTimeout(() => send({ bubble: 'Woof! I live here now 🐶' }), 800);
  });

  // macOS menu bar wants a small icon; tray-mac.png has an @2x sibling for Retina
  tray = new Tray(nativeImage.createFromPath(path.join(ASSETS, MAC ? 'tray-mac.png' : 'tray.png')));
  tray.setToolTip('Pupp Companion');
  refreshMenu();
  if (!MAC) tray.on('click', () => pet());   // on macOS a click opens the menu

  ipcMain.on('ignore-mouse', (_e, ignore) => {
    if (pup.state === 'held') return;
    win.setIgnoreMouseEvents(ignore, { forward: true });
  });
  ipcMain.on('pet', pet);
  ipcMain.on('menu', () => buildMenu().popup({ window: win }));
  ipcMain.on('drag-start', () => {
    const c = screen.getCursorScreenPoint();
    // hang from the cursor by the scruff: cursor sits near the top of the sprite
    pup.grab = { dx: 0, dy: Math.round(215 * settings.size) };
    pup.x = c.x; pup.y = c.y + pup.grab.dy;
    win.setIgnoreMouseEvents(false);
    enter('held');
  });
  ipcMain.on('drag-end', () => {
    if (pup.state !== 'held') return;
    pup.vy = 0; enter('fall');
  });
});

app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => clearInterval(timer));
