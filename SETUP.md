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

Until you make one, `portrait.svg` prints the word "arwin" in the ramp. To use
a photo:

```powershell
pip install pillow numpy opencv-python-headless rembg onnxruntime
python scripts/make_portrait.py me.jpg --preview
git pull
git add portrait.svg
git commit -m "portrait"
git push
```

The photo matters more than any setting:

- **Side light.** One window at about 45 degrees, every other light off.
- **Tight crop.** Chin to just above the hair. `--crop left,top,right,bottom`
  crops before anything else runs.
- **Big source.** 1200 px or more across. Small headshots lose glasses frames
  and brows when shrunk to 90 columns.
- **Plain background**, and nothing black against a dark wall.

Changed your mind about the placeholder word? `python scripts/make_portrait.py --text yourword`.

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
