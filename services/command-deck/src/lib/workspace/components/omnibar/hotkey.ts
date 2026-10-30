/**
 * One ⌘K / Ctrl+K handler per page (plan R30/X25): the first mounted
 * Omnibar claims this module-level slot and installs the handler; a second
 * mounted instance claims nothing, registers no handler, and warns in dev.
 */
let owner: symbol | null = null;

/** Claim the page's omnibar hotkey; false when another instance holds it. */
export function claimHotkey(id: symbol): boolean {
	if (owner && owner !== id) return false;
	owner = id;
	return true;
}

/** Release the slot (only its holder can). */
export function releaseHotkey(id: symbol): void {
	if (owner === id) owner = null;
}

/** True while some Omnibar holds the slot. */
export function hotkeyClaimed(): boolean {
	return owner !== null;
}

/** True when the key event was typed into a field (the field owns it). */
export function typingIn(e: KeyboardEvent): boolean {
	const t = e.target as HTMLElement | null;
	return !!t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
}
