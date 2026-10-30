/**
 * The registry's one reactive dependency: bumped on every registration, read
 * by every registry read, so a tab, section, action or source registered
 * after a view mounted still appears in it (registry.ts is plain TypeScript
 * and holds its entries outside Svelte's reactivity).
 */
class RegistryClock {
	value = $state(0);

	bump() {
		this.value++;
	}
}

export const registryClock = new RegistryClock();
