/**
 * The primitives' language — a Svelte context, never a store (SPEC §5:
 * no primitive imports a store). The shell or a page provides a getter
 * once, high in the tree:
 *
 *   provideUiLang(() => commandBar.lang);
 *
 * and every primitive below reads it through uiLang(). A primitive with
 * internal copy also takes an explicit `lang` prop, which wins. Without a
 * provider the language is English.
 *
 * ut() resolves a `ui_*` key from packs.ui.ts (EN/HI/MR) through the core
 * t() fallback chain (lang → en → key).
 */
import { getContext, setContext } from 'svelte';
import { t } from '$lib/i18n/strings';
import '$lib/i18n/packs.ui';
import type { UiKey } from '$lib/i18n/packs.ui';

const LANG_KEY = Symbol.for('sajag.ui.lang');

export type LangGetter = () => string;

/** Provide the UI language to every primitive below this component. */
export function provideUiLang(getter: LangGetter): void {
	setContext(LANG_KEY, getter);
}

/** Inside a component's initialisation: the language getter in scope ('en' without a provider). */
export function uiLang(): LangGetter {
	return getContext<LangGetter | undefined>(LANG_KEY) ?? (() => 'en');
}

/** The primitives' copy: a `ui_*` key in `lang`, with arguments for template keys. */
export function ut(lang: string, key: UiKey, ...args: unknown[]): string {
	return t(lang, key, ...args);
}
