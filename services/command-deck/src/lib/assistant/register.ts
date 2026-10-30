/**
 * The assistant's provider registration (plan X6, additive): the right
 * dock's Assistant tab on the workspace routes (SPEC §5.3, §6.2 — the
 * assistant is a link-only surface: it never decides). On `/chat` the page
 * mounts the same panel at full width (variant 'page').
 */
import { registerRightTab } from '$lib/workspace/registry';
// the tab's label renders before the panel mounts (t() is not reactive to a
// late pack), so this pack rides registration while the panel stays lazy
import '$lib/i18n/packs.assistant';
import LazyAssistantPanel from './LazyAssistantPanel.svelte';

export function register(): void {
	registerRightTab({
		id: 'assistant',
		label: 'asst_tab',
		icon: 'chat',
		component: LazyAssistantPanel,
		order: 40,
		when: (ctx) => ctx.route === '/' || ctx.route === '/gods-eye',
	});
}
