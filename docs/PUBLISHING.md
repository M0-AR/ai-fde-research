# Publishing the Lifecycle Lab

**Live site:** <https://m0-ar.github.io/ai-fde-research/> · [Full lab](https://m0-ar.github.io/ai-fde-research/preview.html) · [Docs mirror](https://m0-ar.github.io/ai-fde-research/docs/preview.html)

This repository ships as a static site: no build step, no server, and no application secrets. The same files work from a local folder, a project GitHub Pages URL, or a custom domain.

## Before anything goes public

Run the local checks:

```bash
make test
make verify
```

Then inspect:

- `git status` — stage only the intended files.
- `README.md` — the exact beginner anchor resolves and every relative link is valid.
- `preview.html` — the page works without a server-specific rewrite.
- `assets/social-preview.png` — 1280×640 and under 1 MB.
- Secrets — no `.env`, tokens, private hostnames, or customer identifiers.

The preview is static, but it is still public. Treat every screenshot, dataset row, and example as publishable.

## GitHub Pages: current deployment

This repository is published from `main` with **Settings → Pages → Source: Deploy from a branch**, branch `main`, folder `/ (root)`. Pushing to `main` triggers GitHub's **pages build and deployment** workflow. No custom Actions workflow is required.

The root `index.html` is a copy of `preview.html`; both open the full lab. After editing `preview.html`, run `cp preview.html index.html`. The root `.nojekyll` keeps the site static. `404.html` is the custom 404. `docs/preview.html` is a small compatibility redirect so `/docs/preview.html` opens the same lab; it is not the canonical page.

Do not switch the Pages source to `/docs` unless you move the canonical page and its relative assets there. This repository's source is `/ (root)`.

### Project-site paths

A project site is served under `https://OWNER.github.io/REPO/`. Use **relative** links:

```text
./preview.html
./assets/demo.gif
./figures/fig_benchmark_resolve.png
```

Do not hard-code `/preview.html`; that points at the domain root, not the project. The README uses absolute project URLs so GitHub renders clickable links. The site HTML itself uses relative paths.

### Custom 404

`404.html` is included. GitHub Pages serves it for unknown paths. Keep it at the repository root so it is copied to the site root.

### Custom domain (optional)

If you add a custom domain:

1. Configure the DNS records GitHub documents for Pages.
2. Enter the domain under **Settings → Pages → Custom domain**.
3. Enable **Enforce HTTPS** after the certificate is issued.
4. Add a `CNAME` file only if you are intentionally using a custom domain.

Do not add a `CNAME` for a `github.io` project URL.

## Social preview

Upload `assets/social-preview.png` under **Settings → General → Social preview**. GitHub recommends a 1280×640 image under 1 MB. The supplied file is sized for that slot.

## Release sequence

```bash
# 0. Keep the root entry point in sync with the full preview
cp preview.html index.html

# 1. Confirm the evidence still verifies
make test
make verify

# 2. Inspect what will be published
git status
git diff --stat

# 3. Stage deliberately; never commit local secrets or scratch files
git add README.md preview.html index.html 404.html .nojekyll \
  PROTOCOL.md RUN_MANIFEST.md CITATION.cff LICENSE LICENSE-DATA \
  .github docs assets figures results data src tests config paper \
  requirements.txt pyproject.toml Makefile Dockerfile docker-compose.yml .gitignore

# 4. Commit and push only when the release is approved
git commit -m "Publish FDE Lifecycle Lab research preview"
git push -u origin main
```

The remote for this repository is `git@github.com:M0-AR/ai-fde-research.git`. For a fresh checkout:

```bash
git remote add origin git@github.com:M0-AR/ai-fde-research.git
git branch -M main
git push -u origin main
```

The live URL is `https://m0-ar.github.io/ai-fde-research/`. Keep the README live links and `docs/preview.html` in sync if the repository is renamed.

## Post-deploy checks

Probe the three published paths:

```bash
BASE="https://m0-ar.github.io/ai-fde-research"
for p in "" "preview.html" "docs/preview.html"; do
  printf "%s -> " "/$p"
  curl -s -o /dev/null -w "%{http_code}\n" "$BASE/$p"
done
```

Expected: `200` for `/`, `/preview.html`, and `/docs/preview.html`. The last path is a compatibility redirect that opens the same lab.

- Open the [live site](https://m0-ar.github.io/ai-fde-research/) in a private window; confirm the page does not depend on local storage or a previous session.
- Check the root URL, `/preview.html`, `/docs/preview.html`, a deep link (`preview.html#evidence`), and a deliberately missing page.
- Test at 390 px and 1440 px widths.
- Confirm figures load after switching evidence tabs.
- Open the README on the repository home page and click the live links and the beginner anchor.
- Confirm the social preview in a link unfurl.
- Verify the Pages deployment is public and the repository license is visible.

## If the site does not appear

| Symptom | Check |
|---|---|
| 404 at the project root | `index.html` is at the branch root; Pages source is `/ (root)` |
| `/preview.html` 404 | `preview.html` is at the branch root; Pages source is `/ (root)` |
| `/docs/preview.html` 404 | `docs/preview.html` is committed; Pages source is `/ (root)` |
| Styles or figures missing | Asset links are relative and the `assets/` and `figures/` folders were committed |
| Old content after a push | The Pages deployment finished; hard-refresh the browser |
| Custom 404 not used | `404.html` is at the site root, not inside `docs/` |
| Jekyll error | `.nojekyll` exists at the branch root |
| Actions job fails before starting | Check the account's Actions billing/runner status; branch Pages builds are separate |

The site is deliberately dependency-free. If a future change adds a build step, document it here and update the Pages source before merging.
