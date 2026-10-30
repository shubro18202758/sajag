<script lang="ts">
	/**
	 * Feeds and services (SPEC §6.3 col 3): every source behind the wall with
	 * its volume, one status and its age. Provenance is a status of its own
	 * (Simulated, Emulated), never a fault; the note behind a degraded or
	 * down source is the row's tooltip, verbatim. The rows are the ones the
	 * navbar's Data popover lists (feeds.ts), so the two agree.
	 */
	import { ProvenanceTag, Section, Tag, Tooltip } from '$lib/ui';
	import { fmtDuration } from '$lib/ui/format/format';
	import { t } from '$lib/i18n/strings';
	import '$lib/i18n/packs.wall';
	import { statusWord, type WallFeedRow } from './feeds';

	interface Props {
		rows: readonly WallFeedRow[];
		lang: string;
	}

	let { rows, lang }: Props = $props();

	const L = (key: string, ...args: unknown[]) => t(lang, key, ...args);
	const answering = $derived(rows.filter((r) => r.status !== 'down' && r.status !== 'waiting').length);
</script>

<Section title={L('wall_feeds')} icon="data-connection" level={2} sub={L('wall_feeds_count', answering, rows.length)} data-prim="panel" data-wall="feeds">
	<table class="wdt">
		<colgroup><col /><col style:width="112px" /><col style:width="104px" /><col style:width="64px" /></colgroup>
		<thead>
			<tr>
				<th scope="col">{L('wall_feeds_col_source')}</th>
				<th scope="col">{L('wall_feeds_col_volume')}</th>
				<th scope="col">{L('wall_feeds_col_status')}</th>
				<th scope="col" class="num">{L('wall_feeds_col_age')}</th>
			</tr>
		</thead>
		<tbody>
			{#each rows as r (r.id)}
				<tr data-feed={r.id} data-status={r.status}>
					<td><div class="c"><span class="ell">{r.name}</span></div></td>
					<td><div class="c"><span class="ell muted tn">{r.volume ?? '—'}</span></div></td>
					<td>
						<div class="c">
							<Tooltip content={r.note}>
								<span class="st">
									{#if r.status === 'simulated' || r.status === 'emulated'}
										<ProvenanceTag source={r.status} {lang} />
									{:else if r.status === 'ok'}
										<Tag intent="success">{statusWord(lang, r.status)}</Tag>
									{:else if r.status === 'down'}
										<Tag icon="offline">{statusWord(lang, r.status)}</Tag>
									{:else}
										<Tag>{statusWord(lang, r.status)}</Tag>
									{/if}
								</span>
							</Tooltip>
						</div>
					</td>
					<td class="num"><div class="c"><span class="muted tn">{r.ageSec != null ? fmtDuration(r.ageSec, lang) : '—'}</span></div></td>
				</tr>
			{/each}
		</tbody>
	</table>
</Section>

<style>
	.st {
		display: inline-flex;
	}
</style>
