<script lang="ts">
	/**
	 * The city's emergency numbers on the public pages (City Pack `emergency` and agency names): 112, ambulance (108),
	 * fire, police and — where the city has one — the civic disaster control line (Mumbai: BMC 1916). Plain tel: links;
	 * Sajag takes no calls and says so. The digits stay Western in every language (a number to dial).
	 */
	import { t } from '$lib/i18n/strings';
	import { AGENCIES, EMERGENCY, agencyName } from '$lib/city';
	import '$lib/v3/packs.city';

	let { lang }: { lang: string } = $props();

	/** "Ambulance (108)" → "Ambulance": the number is printed beside the name already. */
	const bare = (s: string | null) => (s ?? '').replace(/\s*\((?:\d+|[०-९]+)\)\s*$/, '').trim();

	/** The pack's agency for a number: one whose EN name carries the number ("BMC Disaster Management (1916)"), else the first of its kind. */
	function agencyFor(n: string, kind: string): string | null {
		const byNumber = AGENCIES.find((a) => a.en.includes(`(${n})`));
		return (byNumber ?? AGENCIES.find((a) => a.kind === kind))?.id ?? null;
	}

	const rows = $derived(
		[
			{ n: EMERGENCY.unified, kind: 'emergency' },
			{ n: EMERGENCY.ambulance, kind: 'ambulance' },
			{ n: EMERGENCY.civic_disaster, kind: 'disaster' },
			{ n: EMERGENCY.fire, kind: 'fire' },
			{ n: EMERGENCY.police, kind: 'police' },
		]
			.filter((r): r is { n: string; kind: string } => !!r.n)
			.map((r) => {
				const id = agencyFor(r.n, r.kind);
				return { n: r.n, name: bare(id ? agencyName(id, lang) : null) || r.n };
			}),
	);
</script>

<section class="sos" data-testid="pub-emergency" aria-labelledby="pub-emergency-title">
	<h2 id="pub-emergency-title">{t(lang, 'city_emergency_title')}</h2>
	<ul>
		{#each rows as r (r.n)}
			<li>
				<a href={`tel:${r.n}`} aria-label={`${t(lang, 'city_emergency_call', r.n)} · ${r.name}`}>
					<span class="num" lang="en">{r.n}</span>
					<span class="name">{r.name}</span>
				</a>
			</li>
		{/each}
	</ul>
	<p class="note">{t(lang, 'city_emergency_note')}</p>
</section>

<style>
	.sos {
		width: min(100% - 32px, 688px);
		margin: 16px auto 0;
		padding: 16px;
		border: 1px solid var(--v3-line-1);
		border-radius: var(--v3-radius-l);
		background: var(--v3-s1);
	}

	.sos h2 {
		margin: 0 0 12px;
		font-size: var(--v3-text-body);
		font-weight: 600;
		color: var(--v3-t1);
	}

	.sos ul {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.sos a {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-height: 48px;
		padding: 8px 12px;
		border-radius: var(--v3-radius-m);
		background: var(--v3-s2);
		color: var(--v3-t1);
		text-decoration: none;
	}

	.sos a:focus-visible {
		outline: 2px solid var(--v3-brand-strong);
		outline-offset: 2px;
	}

	.num {
		font-size: var(--v3-text-title);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.name {
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		color: var(--v3-t2);
	}

	.note {
		margin: 8px 0 0;
		font-size: var(--v3-text-micro);
		line-height: var(--v3-lh-micro);
		color: var(--v3-t3);
	}
</style>
