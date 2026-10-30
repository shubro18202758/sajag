/**
 * The pack registry's reactive marker (FIX-E-PERF2 scope 2).
 *
 * Language chunks now arrive asynchronously in the browser: the console's
 * current language loads eagerly (lib/i18n/load.ts) and the other two load on
 * first switch. A late registration is invisible to Svelte unless something
 * re-reads the packs — so this module wires BOTH ends of the signal: the
 * version reader the core resolvers touch (`setPackVersionReader`), and the
 * post-registration bump (`setPacksRegisteredHook` → `ensureLang`). Every
 * `$derived` or template resolving copy through `t()`/`tOps()`/`citizenT()`
 * re-runs once a chunk lands, in the new language, with no raw key ever
 * showing (the EN fallback covers the gap).
 *
 * This module is RUNES territory and is imported only from the app's runes
 * contexts (the shells, the ops store); load.ts and
 * strings.ts stay rune-free so the node test harness can bundle them.
 */
import { setPackVersionReader } from './strings';
import { setPacksRegisteredHook } from './load';

export const packRegistry = $state({ version: 0, loaded: [] as string[] });

setPackVersionReader(() => packRegistry.version);
setPacksRegisteredHook((lang) => {
	packRegistry.loaded = [...packRegistry.loaded, lang];
	packRegistry.version++;
});
