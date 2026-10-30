/**
 * Hold-to-record (the voice report sheet): the browser's MediaRecorder on the microphone, a live level for the
 * waveform, a 60 s ceiling. The recording lives only in memory: the blob goes once to /api/speech/report and is
 * dropped; nothing is written to storage. The microphone is released the moment the recording stops.
 *
 *   recorder.start()   asks for the microphone (the browser's own permission prompt) and starts recording
 *   recorder.stop()    resolves the recording (null when it was too short or failed)
 *   recorder.cancel()  stops and discards
 */

export type RecState = 'idle' | 'arming' | 'recording' | 'error';
export type RecError = 'denied' | 'unsupported' | 'short' | 'failed' | null;

const MAX_MS = 60_000;
const MIN_MS = 700;
const BARS = 40;

/** The best recording type this browser offers (Opus in WebM first: what the speech service decodes over ffmpeg). */
export function pickMime(isSupported: (t: string) => boolean): string | null {
	for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']) if (isSupported(t)) return t;
	return null;
}

export class Recorder {
	state = $state<RecState>('idle');
	error = $state<RecError>(null);
	/** Milliseconds since the recording began. */
	elapsed = $state(0);
	/** The last BARS input levels, 0..1 (the waveform). */
	bars = $state<number[]>(Array(BARS).fill(0));

	#stream: MediaStream | null = null;
	#rec: MediaRecorder | null = null;
	#chunks: Blob[] = [];
	#ctx: AudioContext | null = null;
	#raf = 0;
	#t0 = 0;
	#timer: ReturnType<typeof setTimeout> | null = null;
	#done: ((b: Blob | null) => void) | null = null;
	#wantStop = false;

	get supported(): boolean {
		return typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined';
	}

	async start(): Promise<void> {
		if (this.state === 'arming' || this.state === 'recording') return;
		this.error = null;
		this.#wantStop = false;
		if (!this.supported) {
			this.state = 'error';
			this.error = 'unsupported';
			return;
		}
		this.state = 'arming';
		try {
			// the browser's noise suppression smears consonants the Marathi ASR needs (place names); Whisper copes with noise
			this.#stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: true, channelCount: 1 } });
		} catch (err) {
			this.state = 'error';
			this.error = err instanceof DOMException && (err.name === 'NotAllowedError' || err.name === 'SecurityError') ? 'denied' : 'unsupported';
			return;
		}
		// let go before the browser answered: nothing to record
		if (this.#wantStop) {
			this.#release();
			this.state = 'error';
			this.error = 'short';
			return;
		}
		const mime = pickMime((t) => MediaRecorder.isTypeSupported(t));
		try {
			this.#rec = new MediaRecorder(this.#stream, mime ? { mimeType: mime, audioBitsPerSecond: 96_000 } : undefined);
		} catch {
			this.#release();
			this.state = 'error';
			this.error = 'unsupported';
			return;
		}
		this.#chunks = [];
		this.#rec.ondataavailable = (e) => {
			if (e.data && e.data.size) this.#chunks.push(e.data);
		};
		this.#rec.onstop = () => this.#finish();
		this.#rec.start(250);
		this.#t0 = performance.now();
		this.elapsed = 0;
		this.state = 'recording';
		this.#meter();
		this.#timer = setTimeout(() => void this.stop(), MAX_MS);
	}

	/** Stop and hand back the recording (null when too short, cancelled or failed). */
	stop(): Promise<Blob | null> {
		if (this.state === 'arming') {
			this.#wantStop = true;
			return Promise.resolve(null);
		}
		if (this.state !== 'recording' || !this.#rec) return Promise.resolve(null);
		return new Promise((resolve) => {
			this.#done = resolve;
			try {
				this.#rec?.stop();
			} catch {
				this.#finish();
			}
		});
	}

	cancel(): void {
		this.#done = null;
		this.#wantStop = true;
		try {
			if (this.#rec && this.#rec.state !== 'inactive') this.#rec.stop();
		} catch {
			/* already stopped */
		}
		this.#release();
		this.#chunks = [];
		this.state = 'idle';
		this.error = null;
	}

	#finish() {
		const ms = performance.now() - this.#t0;
		const type = this.#rec?.mimeType || 'audio/webm';
		const blob = this.#chunks.length ? new Blob(this.#chunks, { type }) : null;
		this.#chunks = [];
		this.#release();
		const done = this.#done;
		this.#done = null;
		if (!blob || ms < MIN_MS) {
			this.state = 'error';
			this.error = blob ? 'short' : 'failed';
			done?.(null);
			return;
		}
		this.state = 'idle';
		done?.(blob);
	}

	#meter() {
		if (!this.#stream) return;
		try {
			const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
			if (!Ctx) return;
			this.#ctx = new Ctx();
			const src = this.#ctx.createMediaStreamSource(this.#stream);
			const an = this.#ctx.createAnalyser();
			an.fftSize = 512;
			src.connect(an);
			const buf = new Uint8Array(an.fftSize);
			let lastPush = 0;
			const tick = (t: number) => {
				if (this.state !== 'recording') return;
				this.elapsed = performance.now() - this.#t0;
				an.getByteTimeDomainData(buf);
				let peak = 0;
				for (const v of buf) peak = Math.max(peak, Math.abs(v - 128) / 128);
				if (t - lastPush > 70) {
					lastPush = t;
					this.bars = [...this.bars.slice(1), Math.min(1, Math.sqrt(peak) * 1.15)];
				}
				this.#raf = requestAnimationFrame(tick);
			};
			this.#raf = requestAnimationFrame(tick);
		} catch {
			/* the level is decoration: recording goes on without it */
		}
	}

	#release() {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		cancelAnimationFrame(this.#raf);
		for (const tr of this.#stream?.getTracks() ?? []) tr.stop();
		this.#stream = null;
		this.#rec = null;
		void this.#ctx?.close().catch(() => undefined);
		this.#ctx = null;
		this.bars = Array(BARS).fill(0);
	}
}
