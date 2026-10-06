# Setting up and maintaining this profile

`README.md` is the profile page itself, so the notes live here.

## First time

1. On GitHub, create a **public** repo named exactly `arwin-tech`, without a README.
2. From this folder, in PowerShell:

   ```powershell
   git init -b main
   git add .
   git commit -m "profile readme"
   git remote add origin https://github.com/arwin-tech/arwin-tech.git
   git push -u origin main
   ```

3. **Actions** tab → **refresh stats** → **Run workflow**, once. After that it
   runs by itself every morning at 09:17 Dubai time.
4. Set your display name, bio and pinned repos by hand on your profile. GitHub
   has no API for any of the three.

If the README doesn't show on your profile, edit it once in GitHub's web editor;
new profile READMEs are sometimes cached.

## The portrait

`portrait.svg` is a photo of you drawn in text, with your name typed under it.
To make a new one, put the photo in this folder and run:

```powershell
pip install pillow numpy opencv-python-headless rembg onnxruntime
python scripts/make_portrait.py me.jpg --name arwin --preview
git pull
git add portrait.svg
git commit -m "portrait"
git push
```

The first run downloads a 170 MB model, once. `--preview` also prints the
characters in the terminal so you can judge before pushing.

Two flags frame the shot. Both take `left,top,right,bottom` in the photo's own
pixels (Paint shows the pixel position under the cursor, bottom left):

- `--crop` is a wide box around you, shoulders included. The background remover
  needs that context; a tight crop leaves a smear of wall behind the head.
- `--focus` zooms to the head and collar inside it, so the whole 90-character
  grid is spent on the face.

The current portrait used `--crop 60,65,250,310 --focus 102,65,243,226`.

If the result looks wrong:

- Face too dark and flat: raise `--midpoint` a little (`0.45`).
- Face washed out: lower it (`0.35`).
- Features look mushy: `--contrast 8`. Too noisy: `--sharpen 0.8`.
- Want only the portrait: leave `--name` off. Different name: `--name yourword`.

What matters more than any flag is the photo:

- **Side light.** One window at about 45 degrees, every other light off.
- **Resolution.** 1200 px or more across. A small photo is enlarged
  automatically, but that can't add detail, so eyes and brows stay soft.
- **Plain background**, and nothing black against a dark wall.

No photo handy? `python scripts/make_portrait.py --text yourword` prints just a word.

## Day to day

- The action commits the stat SVGs itself, so run `git pull` before you edit
  anything locally. Don't regenerate them on your machine: your token and the
  action's can bucket a day differently, which means merge conflicts.
- Section headings are drawn by `generate_stats.py`. Rename or add them in its
  `HEADINGS` dict (lowercase a-z, spaces and hyphens), then reference the new
  `hd-<slug>.svg` in the README.
- Colours live in `scripts/profile_style.py`.
- Test markdown changes before pushing: GitHub strips `<style>`, `class`,
  `style` and inline `<svg>` from READMEs, but keeps `<img>`, `<samp>`,
  `<sub>`, `<sup>`, `<details>`, `<picture>` and `align`/`width` attributes.

## Credit

The approach comes from andriidrok1's guide and profile,
github.com/andriidrok1/andriidrok1. The code here was written fresh for this
profile; JetBrains Mono is under the SIL OFL (`scripts/fonts/OFL.txt`).
