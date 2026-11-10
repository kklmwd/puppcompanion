# Pupp Companion

A wrinkly Shar-Pei puppy that lives on your Windows or Mac desktop, drawn in chunky pixel art.

<img src="assets/icon.png" width="128" alt="Pupp Companion">

## What the puppy does

- **Wanders and naps** along the bottom of your screen, and dozes off when you step away.
- **Loves pets** – click or stroke it for hearts. Drag it to pick it up by the scruff and drop it somewhere else.
- **Follows your cursor** when it gets too far away.
- **Gentle reminders** – a speech bubble nudges you to drink water, stretch or rest your eyes.

Right-click the puppy (or its tray / menu-bar icon) for settings: follow on/off,
reminder interval, size, start at login, quit.

## Get it

**Download:** every push to `main` builds both apps. Open the repo's *Actions*
tab → latest *Build apps* run → download the artifact for your computer:

- **Windows** – `PuppCompanion-windows`: an installer and a portable `.exe`.
  Windows SmartScreen may warn because the app is unsigned: *More info* → *Run anyway*.
- **Mac** (Intel and Apple Silicon) – `PuppCompanion-mac`: a `.dmg`. Open it and
  drag *Pupp Companion* to *Applications*. The app is not notarized by Apple, so
  the first launch is blocked: open *System Settings → Privacy & Security*,
  scroll down and click **Open Anyway**. If macOS says the app is damaged, run
  this once in Terminal:

  ```bash
  xattr -dr com.apple.quarantine "/Applications/Pupp Companion.app"
  ```

**Run from source** (needs [Node.js](https://nodejs.org)):

```bash
npm install
npm start
```

**Build it yourself** (on the system you are building for):

```bash
npm run dist
```

## Changing the art

Green-screen renders live in `art/raw` (one pose per image) and
`art/raw/sheets` (animation sheets: 8-frame walk cycle, 4-frame fall and landing). After replacing one, regenerate the
pixel-art sprites in `assets/`:

```bash
pip install pillow numpy scipy
python tools/process_sprites.py
```
