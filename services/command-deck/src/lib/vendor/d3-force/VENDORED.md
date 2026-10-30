# d3-force 3.0.0 (vendored)

- **Package**: `d3-force` **3.0.0**, ISC licence, Copyright 2010-2021 Mike Bostock (`LICENSE`, unchanged).
- **Tarball**: https://registry.npmjs.org/d3-force/-/d3-force-3.0.0.tgz
- **Tarball sha256**: `deacfa7ecb466f88717fe1863347dd65e5a5422d9f8c893d771cb2a7f987fa15`
- **Vendored**: 2026-10-25 by UI-S4 (Sajag v2, SPEC §13.9) — no npm dependency, no lockfile change.

## What was copied

Only `package/src/**` (into `src/`) and `package/LICENSE`, byte for byte, with exactly two edits per file:

1. a first line `// @ts-nocheck` (the deck's tsconfig has `checkJs`; upstream ships untyped JavaScript);
2. the bare imports `d3-dispatch`, `d3-timer` and `d3-quadtree` rewritten to the relative paths `../../d3-dispatch/src/index.js`, `../../d3-timer/src/index.js` and `../../d3-quadtree/src/index.js` (`simulation.js`, `collide.js`, `manyBody.js`); the other files have no bare import.

Nothing else differs from the tarball. To verify, re-download the tarball, check the sha256 above, and compare each
`src/*.js` with `package/src/*.js` after dropping the first line and undoing the import rewrite.

Typed access for the deck lives in `src/lib/analysis/graph/force.ts`; nothing outside `src/lib/analysis` imports
this folder.
