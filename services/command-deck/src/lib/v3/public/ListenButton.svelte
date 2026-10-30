<script lang="ts" module>
	/** Advisories already voiced on this page view (text + language → wav), so a second press plays at once. Memory only. */
	const voiced = new Map<string, Blob>();
</script>

<script lang="ts">
	/**
	 * "ऐका / Listen" (PLAN §2.4 C): reads an advisory aloud in the page's language through the on-premises speech
	 * service (POST /api/speech/speak — the one speech call a public page may make, ≤ 400 characters, rate-limited by the
	 * deck). The voice is synthetic and says so. Nothing about the listener is sent or kept; the audio lives in memory.
	 */
	import { onDestroy } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import '$lib/v3/field/packs.field';
	import { FieldApiError, speak } from '$lib/v3/field/api';
	import { speakable, speakLang } from '$lib/v3/field/model';

	let { text, lang, compact = false }: { text: string; lang: string; compact?: boolean } = $props();
	const L = (key: string) => t(lang, key);

	let phase = $state<'idle' | 'loading' | 'playing' | 'error'>('idle');
	let problem = $state<string | null>(null);
	let audio: HTMLAudioElement | null = null;
	let url: string | null = null;
	let ctl: AbortController | null = null;
	const uid = $props.id();

	function stop() {
		ctl?.abort();
		audio?.pause();
		audio = null;
		if (url) URL.revokeObjectURL(url);
		url = null;
		if (phase !== 'error') phase = 'idle';
	}

	async function press() {
		if (phase === 'loading' || phase === 'playing') return stop();
		const body = speakable(text);
		if (!body) return;
		const code = speakLang(lang);
		const key = `${code}\u0000${body}`;
		problem = null;
		phase = 'loading';
		ctl = new AbortController();
		try {
			let wav = voiced.get(key);
			if (!wav) {
				wav = await speak(body, code, ctl.signal);
				voiced.set(key, wav);
			}
			url = URL.createObjectURL(wav);
			audio = new Audio(url);
			audio.onended = () => stop();
			audio.onerror = () => {
				phase = 'error';
				problem = L('fld_listen_failed');
			};
			await audio.play();
			phase = 'playing';
		} catch (err) {
			if (err instanceof DOMException && err.name === 'AbortError') return;
			phase = 'error';
			problem = err instanceof FieldApiError && err.kind === 'rate' ? L('fld_listen_busy') : L('fld_listen_failed');
		}
	}

	// a new text (another road, another language) stops the old voice
	$effect(() => {
		void text;
		void lang;
		return () => stop();
	});
	onDestroy(stop);
</script>

<span class={['listen', compact && 'compact']} data-testid="listen" data-state={phase}>
	<button type="button" class={['lb', phase === 'playing' && 'is-pressed']} aria-pressed={phase === 'playing'} aria-describedby={`ls-${uid}`} onclick={() => void press()} disabled={!text.trim()}>
		{#if phase === 'loading'}
			<span class="spin" aria-hidden="true"></span>
		{:else if phase === 'playing'}
			<span class="eq" aria-hidden="true"><i></i><i></i><i></i></span>
		{:else}
			<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10v4a1 1 0 0 0 1 1h2.5l5 4V5l-5 4H5a1 1 0 0 0-1 1zM16.5 9a4 4 0 0 1 0 6M19 6.5a7.5 7.5 0 0 1 0 11" /></svg>
		{/if}
		<span>{phase === 'loading' ? L('fld_listen_loading') : phase === 'playing' ? L('fld_listen_stop') : L('fld_listen')}</span>
	</button>
	<span class="note" id={`ls-${uid}`}>{problem ?? L('fld_listen_voice')}</span>
</span>

<style>
	.listen {
		display: inline-flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 6px 10px;
	}

	.lb {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 44px;
		padding: 0 18px 0 14px;
		border: 1px solid var(--v3-line-3);
		border-radius: 22px;
		background: var(--v3-s1);
		color: var(--v3-t1);
		font: inherit;
		font-size: 16px;
		font-weight: 650;
		cursor: pointer;
		transition: background var(--v3-dur-1) var(--v3-ease), border-color var(--v3-dur-1) var(--v3-ease);
	}

	.compact .lb {
		min-height: 40px;
		font-size: 15px;
	}

	.lb:hover:not(:disabled) {
		border-color: var(--v3-brand);
		background: var(--v3-s2);
	}

	.lb.is-pressed {
		border-color: var(--v3-brand);
		background: var(--v3-brand-veil);
	}

	.lb:focus-visible {
		outline: 2px solid var(--v3-brand);
		outline-offset: 2px;
	}

	.lb:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.ico {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: var(--v3-brand-text);
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.spin {
		width: 18px;
		height: 18px;
		border: 2px solid var(--v3-line-3);
		border-top-color: var(--v3-brand);
		border-radius: 50%;
		animation: spin 0.9s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.eq {
		display: inline-flex;
		align-items: flex-end;
		gap: 2px;
		width: 20px;
		height: 18px;
	}

	.eq i {
		flex: 1;
		height: 40%;
		border-radius: 1px;
		background: var(--v3-brand);
		animation: eq 0.8s ease-in-out infinite alternate;
	}

	.eq i:nth-child(2) {
		animation-delay: 0.2s;
	}

	.eq i:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes eq {
		to {
			height: 100%;
		}
	}

	.note {
		color: var(--v3-t3);
		font-size: 13px;
	}

	@media (prefers-reduced-motion: reduce) {
		.spin,
		.eq i {
			animation: none;
		}
	}
</style>
