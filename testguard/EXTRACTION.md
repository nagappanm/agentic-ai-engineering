# Extraction plan — testguard → its own repo

Turn `testguard/` (a folder in the `agentic-ai-engineering` learning monorepo)
into a standalone, publishable OSS repo. This is a **distribution + identity**
step, not a technical one — do it when you're ready to put the tool in front of
people (the talk / a public post), because that's when the npm listing and
per-repo stars/issues start earning their keep.

## Already done (publish-prep, in this branch)
- `package.json` is release-ready: `version` bumped, `private` removed, npm
  metadata (repo/keywords/license), `bin → dist/cli.js`, `main`/`types`/
  `exports`/`files`, `prepublishOnly` build.
- **Build** via tsup: `npm run build` → `dist/` (ESM + `.d.ts`), `@playwright/test`
  marked external, shebang preserved on `dist/cli.js`. Verified: the compiled
  binary runs and gates.
- `@playwright/test` moved to **optionalDependencies** (dynamic mode is opt-in;
  the code already degrades gracefully without it).
- **Workflows** staged under `.github/workflows/` (`ci.yml`, `release.yml`) —
  ignored by the monorepo, they activate at the new repo root after the split.

So after the split you have a package that builds, tests, benchmarks, and
publishes — you only run steps 1–3 below.

## 1. Check the name first
```bash
npm view testguard   # exists ⇒ taken
```
If taken: `@nagappanm/testguard` (scoped), or `ai-testguard` / `testsentinel`.
Update `name` in package.json + the README/Action references before publishing.

## 2. Split out the history (keeps M0–M8 commits)
```bash
cd agentic-ai-engineering && git checkout main && git pull
git subtree split --prefix=testguard -b testguard-split
# create an empty repo nagappanm/testguard on GitHub, then:
git push git@github.com:nagappanm/testguard.git testguard-split:main
git clone git@github.com:nagappanm/testguard.git ../testguard && cd ../testguard
```

## 3. Publish
```bash
npm ci
npm run build       # sanity (prepublishOnly also runs it)
npm login
npm version 0.1.0   # if not already tagged
git push --tags     # release.yml publishes on the v* tag (needs NPM_TOKEN secret)
# ...or publish manually: npm publish --access public
```

## 4. Move the Action to the repo root (optional, for `uses: nagappanm/testguard@v1`)
`action/action.yml` currently gives `uses: nagappanm/testguard/action@v1`. To get
the root form, move it to `./action.yml`. Once published, simplify its run step to
`npx testguard@latest ...` instead of the `github.action_path` install.

## 5. Launch polish
- README badges (CI, npm, license); put the benchmark stat + a failing-report GIF
  up top.
- Change the README install line to `npm i -D testguard`.

## 6. Monorepo cutover
Replace `testguard/` in the monorepo with a short `README.md` pointer to the new
repo (or delete it) — a fresh branch/PR in the monorepo.

## Kill criteria (unchanged)
After the talk + a launch push, if stars/issues/installs stay near zero, stop.
This is a wedge, not a moat — don't invest months without demand signal.
