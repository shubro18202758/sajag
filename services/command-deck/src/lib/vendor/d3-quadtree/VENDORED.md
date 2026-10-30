# d3-quadtree 3.0.1 (vendored)

- **Package**: `d3-quadtree` **3.0.1**, ISC licence, Copyright 2010-2021 Mike Bostock (`LICENSE`, unchanged).
- **Tarball**: https://registry.npmjs.org/d3-quadtree/-/d3-quadtree-3.0.1.tgz
- **Tarball sha256**: `d4145e9cecca8a6077e1099de96375ec9923b0de0df4004bd98aafa17c2d557f`
- **Vendored**: 2026-10-25 by UI-S4 (Sajag v2, SPEC §13.9) — no npm dependency, no lockfile change.

## What was copied

Only `package/src/**` (into `src/`) and `package/LICENSE`, byte for byte, with exactly two edits per file:

1. a first line `// @ts-nocheck` (the deck's tsconfig has `checkJs`; upstream ships untyped JavaScript);
2. no import rewrite: the package has no bare import (its files import each other relatively).

Nothing else differs from the tarball. To verify, re-download the tarball, check the sha256 above, and compare each
`src/*.js` with `package/src/*.js` after dropping the first line and undoing the import rewrite.

Typed access for the deck lives in `src/lib/analysis/graph/force.ts`; nothing outside `src/lib/analysis` imports
this folder.
