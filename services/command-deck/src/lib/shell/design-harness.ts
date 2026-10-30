/**
 * Whether the /design/** harness pages are served (F-07): always under the
 * vite dev server; in a production build only when the server environment
 * carries SAJAG_DESIGN_HARNESS=1 exactly (the smokes' and the private
 * preview's opt-in). Pure — tests/deck-fixes.unit.mjs pins it.
 */
export function designHarnessOn(dev: boolean, flag: string | undefined | null): boolean {
	return dev || flag === '1';
}
