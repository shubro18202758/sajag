<script lang="ts" module>
	export type BadgeVariant =
		| 'live'
		| 'offline'
		| 'fixture'
		| 'emulated'
		| 'not-deployed'
		| 'stale'
		| 'pending'
		| 'approved'
		| 'rejected'
		| 'deferred'
		| 'act'
		| 'neutral'
		| 'band';
</script>

<script lang="ts">
	/**
	 * Badge — the legacy status pill, rebuilt on src/lib/ui's Tag (SPEC §5.2).
	 * The thirteen variants collapse into the colour roles (SPEC §2.4) and the
	 * provenance glyphs:
	 *   live, approved           → success (healthy, approved)
	 *   act, with its own label  → warning: the "Needs decision" tag (a
	 *                              decision waits), the one orange use
	 *   act with a caller's label, pending → neutral: callers use them for
	 *                              rule notes and states ("No fine · evidence
	 *                              only", "Human confirms", "Commits locked …"),
	 *                              and orange never marks a rule note
	 *   emulated                 → the emulated provenance glyph, quiet ink
	 *   fixture                  → the test glyph, quiet ink
	 *   offline, not-deployed, stale, rejected, deferred, neutral → neutral
	 *   band                     → BandChip (BLACK's fill-and-hairline rule)
	 * Text is sentence case: the label as given, its first letter capitalised
	 * (HI and MR are untouched). `data-prim="badge"`, `data-variant` and the
	 * `badge` class stay on the root.
	 */
	import type { Band } from '$lib/design/tokens';
	import { PROVENANCE_ICON, type IconName } from '$lib/design/icons';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs';
	import Tag from '$lib/ui/Tag.svelte';
	import { uiLang } from '$lib/ui/lang';
	import type { TagIntent } from '$lib/ui/types';
	import BandChip from './BandChip.svelte';
	import { sentenceStart } from './text';

	interface Props {
		variant: BadgeVariant;
		/** Required for variant="band"; ignored otherwise. */
		band?: Band | null;
		label?: string;
		title?: string;
		lang?: string;
	}

	let { variant, band = null, label, title, lang }: Props = $props();

	const ctxLang = uiLang();
	const L = $derived(lang ?? ctxLang());

	const INTENT: Partial<Record<BadgeVariant, TagIntent>> = {
		live: 'success',
		approved: 'success'
	};
	/** Orange only for the "Needs decision" tag itself (no caller label): SPEC §2.4. */
	const intent = $derived<TagIntent>(variant === 'act' && label == null ? 'warning' : (INTENT[variant] ?? 'none'));
	const ICON: Partial<Record<BadgeVariant, IconName>> = {
		emulated: PROVENANCE_ICON.emulated,
		fixture: PROVENANCE_ICON.test
	};

	const text = $derived(sentenceStart(label ?? t(L, `badge_${variant}`)));
	const quiet = $derived(variant === 'emulated' || variant === 'fixture' || variant === 'stale' || variant === 'not-deployed' || variant === 'offline');
</script>

{#if variant === 'band'}
	<BandChip band={(band ?? 'GREEN') as Band} {label} size="sm" />
{:else}
	<Tag
		{intent}
		icon={ICON[variant]}
		tooltip={title ?? null}
		class={['badge', quiet && 'quiet']}
		data-prim="badge"
		data-variant={variant}>{text}</Tag
	>
{/if}

<style>
	/* provenance and absent states read quietly (ink-2), never as a colour */
	:global(.tag[data-prim='badge'].quiet) {
		color: var(--v-ink-2);
	}
</style>
