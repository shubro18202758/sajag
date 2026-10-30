/// <reference types="vite/client" />
/**
 * registerProviders() — the one call a route page makes to register every
 * workspace provider (plan R9): Vite eagerly imports each
 * `src/lib/<provider>/register.ts` and this calls its `register()`. A
 * provider merged later (osint, dss, assistant …) appears without any
 * route-page edit; before it has merged, its tab simply does not appear.
 *
 * Idempotent: every register* call is keyed by id and replaces its own
 * entry (plan R27), so a second call (HMR, a second page) changes nothing.
 *
 * Kept out of every unit-test bundle: esbuild has no import.meta.glob. The
 * unit tests call a provider's register() directly.
 */
type ProviderModule = { register?: () => void };

export function registerProviders(): void {
	const modules = import.meta.glob<ProviderModule>('../*/register.ts', { eager: true });
	for (const path of Object.keys(modules).sort()) {
		const register = modules[path]?.register;
		if (typeof register === 'function') register();
	}
}
