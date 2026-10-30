<script lang="ts">
	/**
	 * /design — the design system gallery (SPEC §6.7): every src/lib/ui
	 * primitive, in both themes side by side, plus the legacy primitives
	 * (every data-prim still mounts here: tests/design-smoke.mjs asserts
	 * against this page). Composites are verified on their own routes.
	 *
	 * Later slices copy this page as the visual reference, so every specimen
	 * keeps SPEC §2.4's colour roles: Reject, Dismiss and Cancel are default
	 * buttons to the left of the one primary; data states (Active, Planning)
	 * are neutral; red is only the watchlisted or stolen alert; green only
	 * "approved". The intent fills appear once, labelled by intent.
	 *
	 * Language: the shell's ONE switch. The page owns the language like
	 * every deck page (commandBar.onLangChange), and hands it to the
	 * primitives through provideUiLang; there is no second switch here.
	 *
	 * FICTIONAL DATA ONLY: masked marks such as MH01XX•••7, emulated camera
	 * ids, a fixed clock (24 Oct 2026, 03:18:38 IST). No real mark, person or
	 * record appears here, and nothing on this page calls an API.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n/strings';
	import type { Band } from '$lib/design/tokens';
	import {
		ACTION_ICON,
		ACTOR_ICON,
		EVENT_KIND_ICON,
		ICONS_16,
		INTENT_ICON,
		KIND_ICON,
		MODULE_ICON,
		PROVENANCE_ICON,
		kindIcon,
		eventKindIcon,
		type IconName
	} from '$lib/design/icons';
	import {
		Alert,
		Breadcrumbs,
		Button,
		ButtonGroup,
		Callout,
		Card,
		CardList,
		Checkbox,
		CompoundTag,
		DataTable,
		Dialog,
		Drawer,
		EntityTitle,
		EyeToggle,
		FormGroup,
		HotkeysDialog,
		HTMLSelect,
		Icon,
		Input,
		Kbd,
		Menu,
		MetricCard,
		NonIdealState,
		Note,
		ObjectTag,
		Popover,
		ProgressBar,
		PropertyTable,
		ProvenanceTag,
		Reason,
		Section,
		SegmentedControl,
		Skeleton,
		Spinner,
		Splitter,
		Switch,
		Tabs,
		Tag,
		TimeField,
		Toaster,
		Tooltip,
		Tree,
		UI_PRIMITIVES,
		provideUiLang
	} from '$lib/ui';
	import { Coord, Id, Plate, Time, TimeRange, colStamp } from '$lib/ui/format';
	import type { DataColumn, MenuItemSpec, PropertyGroup, ProvenanceSource, ToastSpec, TreeNode } from '$lib/ui/types';
	import Panel from '$lib/primitives/Panel.svelte';
	import PanelShell from '$lib/primitives/PanelShell.svelte';
	import Badge from '$lib/primitives/Badge.svelte';
	import BandChip from '$lib/primitives/BandChip.svelte';
	import LegacyButton from '$lib/primitives/Button.svelte';
	import DataTile from '$lib/primitives/DataTile.svelte';
	import FeedItem from '$lib/primitives/FeedItem.svelte';
	import AuditRow from '$lib/primitives/AuditRow.svelte';
	import MapLegend, { type LegendItem } from '$lib/primitives/MapLegend.svelte';
	import LayerRail from '$lib/primitives/LayerRail.svelte';
	import Modal from '$lib/primitives/Modal.svelte';
	import EmptyState from '$lib/primitives/EmptyState.svelte';
	import BandMasthead from '$lib/primitives/BandMasthead.svelte';
	import DecisionCard from '$lib/primitives/DecisionCard.svelte';
	import EventDossier from '$lib/primitives/EventDossier.svelte';
	import { toasts } from '$lib/shell/toast.svelte';
	import { commandBar } from '$lib/shell/command-bar.svelte';

	type Theme = 'command' | 'daylight';
	type ThemeMode = 'both' | Theme;

	// ── page controls ──────────────────────────────────────────────────────
	let themeMode = $state<ThemeMode>('both');
	// the language is the page's; the shell's switch hands every choice back
	// here, the chrome reads commandBar.lang and the primitives read uiLang()
	let lang = $state<string>('en');
	$effect(() => {
		commandBar.lang = lang;
		commandBar.onLangChange = (l: string) => (lang = l);
	});
	provideUiLang(() => lang);
	const themes = $derived<Theme[]>(themeMode === 'both' ? ['command', 'daylight'] : [themeMode]);
	const THEME_LABEL: Record<Theme, string> = { command: 'Command · operator', daylight: 'Daylight · public pages' };

	// ── fictional data (fixed clock: 24 Oct 2026, 03:18:38 IST) ───────────
	const NOW = Date.UTC(2026, 9, 23, 21, 48, 38);
	const MIN = 60_000;
	const PLATE = 'MH01XX•••7';
	const PLATE_2 = 'MH05XY•••2';

	const SECTIONS = [
		['foundations', 'Colour and type'],
		['icons', 'Icons'],
		['formatter', 'Formatter'],
		['buttons', 'Buttons'],
		['tags', 'Tags'],
		['notes', 'Notes and callouts'],
		['forms', 'Form controls'],
		['navigation', 'Navigation'],
		['containers', 'Containers'],
		['data', 'Data'],
		['overlays', 'Overlays'],
		['feedback', 'Feedback'],
		['layout', 'Layout'],
		['legacy', 'Legacy primitives']
	] as const;
	let currentSection = $state<string>('foundations');

	$effect(() => {
		const els = SECTIONS.map(([id]) => document.getElementById(id)).filter((e): e is HTMLElement => !!e);
		const io = new IntersectionObserver(
			(entries) => {
				const top = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
				if (top) currentSection = top.target.id;
			},
			{ rootMargin: '0px 0px -70% 0px' }
		);
		for (const el of els) io.observe(el);
		return () => io.disconnect();
	});

	// ── foundations ────────────────────────────────────────────────────────
	const SWATCHES: readonly { group: string; tokens: readonly string[] }[] = [
		{ group: 'Surfaces', tokens: ['--v-canvas', '--v-surface-1', '--v-surface-2', '--v-surface-3', '--v-surface-4', '--v-surface-sink'] },
		{ group: 'Ink', tokens: ['--v-ink-1', '--v-ink-2', '--v-ink-4', '--v-ink-disabled', '--v-line-2', '--v-line-strong'] },
		{ group: 'Intents', tokens: ['--v-primary', '--v-success', '--v-warning', '--v-danger', '--v-ai', '--v-act'] },
		{ group: 'Map roles', tokens: ['--v-map-select', '--v-map-decision', '--v-map-alert', '--v-map-route', '--v-map-event', '--v-map-marker'] }
	];
	const BANDS: readonly Band[] = ['GREEN', 'AMBER', 'RED', 'BLACK'];
	const BAND_WORD: Record<Band, string> = { GREEN: 'Green', AMBER: 'Amber', RED: 'Red', BLACK: 'Black' };
	const FLOW = [1, 2, 3, 4, 5] as const;
	const FLOW_WORD = ['Free', 'Light', 'Moderate', 'Heavy', 'Jammed'];
	// size / line height · weight as each theme renders the sample (command is
	// SPEC §3.2's operator scale; daylight keeps the public pages' larger type).
	// design-smoke checks every printed value against the computed style.
	const TYPE_SCALE: readonly { role: string; cls: string; sample: string; spec: Record<Theme, string> }[] = [
		{ role: 'H5 · object title', cls: 'ts-h5', sample: 'Authorise pursuit', spec: { command: '16 / 20 · 600', daylight: '16 / 20 · 600' } },
		{ role: 'H6 · section title', cls: 'ts-h6', sample: 'Corridor operations', spec: { command: '14 / 16 · 600', daylight: '16 / 18 · 600' } },
		{ role: 'Body', cls: 'ts-body', sample: 'Read by 6 cameras between 01:24 and 01:38', spec: { command: '14 / 18 · 400', daylight: '16 / 20 · 400' } },
		{
			role: 'Running text',
			cls: 'ts-run',
			sample: 'The engine proposes; a named officer decides every response.',
			spec: { command: '14 / 21 · 400', daylight: '16 / 24 · 400' }
		},
		{ role: 'Small', cls: 'ts-small', sample: 'Last read 01:38 IST at EM-CAM-03', spec: { command: '12 / 16 · 400', daylight: '13 / 17 · 400' } },
		{ role: 'Metric', cls: 'ts-metric', sample: '53.1', spec: { command: '22 / 28 · 600 tabular', daylight: '28 / 34 · 600 tabular' } }
	];

	// ── icons ──────────────────────────────────────────────────────────────
	const ICON_MAPS: readonly { title: string; map: Readonly<Record<string, IconName>> }[] = [
		{ title: 'Object kinds', map: KIND_ICON },
		{ title: 'Corridor-event kinds', map: EVENT_KIND_ICON },
		{ title: 'Actors', map: ACTOR_ICON },
		{ title: 'Actions', map: ACTION_ICON },
		{ title: 'Modules', map: MODULE_ICON },
		{ title: 'Intents', map: INTENT_ICON },
		{ title: 'Provenance', map: PROVENANCE_ICON }
	];
	const ALL_ICONS = Object.keys(ICONS_16) as IconName[];
	let showAllIcons = $state(false);

	// ── buttons, tags, forms ───────────────────────────────────────────────
	let view = $state<Record<Theme, string>>({ command: 'map', daylight: 'map' });
	let windowSel = $state<Record<Theme, string>>({ command: '6h', daylight: '6h' });
	let following = $state<Record<Theme, boolean>>({ command: true, daylight: true });
	let filters = $state(['Vehicles', 'Last 6 h', 'Watchlist']);
	// workspace filter chips: a removable CompoundTag per filter ("Kind │ Vehicles ✕")
	const FILTER_CHIPS: readonly { k: string; v: string }[] = [
		{ k: 'Kind', v: 'Vehicles' },
		{ k: 'Window', v: 'Last 6 h' },
		{ k: 'List', v: 'Watchlist' }
	];
	let chips = $state<Record<Theme, { k: string; v: string }[]>>({ command: [...FILTER_CHIPS], daylight: [...FILTER_CHIPS] });
	function resetFilters(th: Theme) {
		filters = ['Vehicles', 'Last 6 h', 'Watchlist'];
		chips[th] = [...FILTER_CHIPS];
	}
	let search = $state('');
	let officerName = $state('');
	let roadSel = $state('dh_road');
	let holdAt = $state<string | null>('01:38');
	let live = $state(true);
	let sims = $state(false);
	let checkA = $state(true);
	let checkB = $state(false);
	let eyeA = $state(true);
	let eyeB = $state(false);

	// ── navigation ─────────────────────────────────────────────────────────
	let tab = $state<Record<Theme, string>>({ command: 'inspector', daylight: 'inspector' });
	let treeSel = $state('cameras');
	const treeNodes = $derived<TreeNode[]>([
		{
			id: 'traffic',
			label: 'Traffic',
			expanded: true,
			childNodes: [
				{ id: 'flow', label: 'Flow', icon: KIND_ICON.segment, secondaryLabel: '49 roads', selected: treeSel === 'flow' },
				{ id: 'signals', label: 'Signal plans', icon: KIND_ICON.junction, secondaryLabel: '12', selected: treeSel === 'signals' }
			]
		},
		{
			id: 'enforcement',
			label: 'Enforcement',
			expanded: true,
			childNodes: [
				{ id: 'cameras', label: 'Cameras', icon: KIND_ICON.camera, secondaryLabel: '18', selected: treeSel === 'cameras' },
				{ id: 'sightings', label: 'Sightings', icon: KIND_ICON.sighting, dim: true, selected: treeSel === 'sightings' }
			]
		},
		{ id: 'response', label: 'Response', childNodes: [{ id: 'units', label: 'Units', icon: KIND_ICON.unit }] }
	]);
	const menuItems = $derived<MenuItemSpec[]>([
		{ id: 'h1', kind: 'header', label: 'Selection' },
		{ id: 'map', label: 'Show on map', icon: ACTION_ICON.show_on_map, rightLabel: 'F' },
		{ id: 'around', label: 'Search around', icon: ACTION_ICON.search_around, rightLabel: 'S' },
		{ id: 'graph', label: 'Add to graph', icon: ACTION_ICON.add_to_graph, rightLabel: 'G' },
		{ id: 'd1', kind: 'divider' },
		{ id: 'h2', kind: 'header', label: 'Window' },
		{ id: 'w6', label: 'Last 6 hours', selected: true },
		{ id: 'w24', label: 'Last 24 hours', selected: false },
		{ id: 'd2', kind: 'divider' },
		{ id: 'export', label: 'Export CSV (masked)', icon: 'export', disabled: true, disabledReason: 'Select rows to export.' },
		{ id: 'clear', label: 'Clear the selection', icon: 'cross' }
	]);

	// ── data ───────────────────────────────────────────────────────────────
	interface Sighting {
		id: string;
		camera: string;
		road: string;
		speed: number;
		t: number;
		emulated: boolean;
		state: 'pending' | 'approved' | 'rejected';
	}
	const SIGHTINGS: Sighting[] = [
		{ id: 's6', camera: 'EM-CAM-03', road: 'P D Mello Road', speed: 95, t: NOW - 100 * MIN, emulated: true, state: 'pending' },
		{ id: 's5', camera: 'EM-J05', road: 'Senapati Bapat Marg', speed: 102, t: NOW - 102 * MIN, emulated: true, state: 'pending' },
		{ id: 's4', camera: 'EM-CAM-01', road: 'Brabourne Road', speed: 115, t: NOW - 106 * MIN, emulated: true, state: 'approved' },
		{ id: 's3', camera: 'EM-CAM-04', road: 'Chittaranjan Avenue', speed: 103, t: NOW - 108 * MIN, emulated: false, state: 'pending' },
		{ id: 's2', camera: 'EM-CAM-02', road: 'Bandra–Worli Sea Link', speed: 110, t: NOW - 111 * MIN, emulated: true, state: 'rejected' },
		{ id: 's1', camera: 'EM-J01B', road: 'Grand Trunk Road', speed: 88, t: NOW - 114 * MIN, emulated: true, state: 'pending' }
	];
	const stamps = colStamp(
		SIGHTINGS.map((s) => s.t),
		NOW,
		{ seconds: false }
	);
	const STAMP = new Map(SIGHTINGS.map((s, i) => [s.id, stamps[i]]));
	let rowSel = $state<Record<Theme, string>>({ command: 's6', daylight: 's6' });
	let rowOpen = $state<Record<Theme, string[]>>({ command: ['s4'], daylight: ['s4'] });
	const STATE_TAG: Record<Sighting['state'], { label: string; intent: 'warning' | 'success' | 'none' }> = {
		pending: { label: 'Needs decision', intent: 'warning' },
		approved: { label: 'Approved', intent: 'success' },
		rejected: { label: 'Rejected', intent: 'none' }
	};

	const VIRTUAL_ROWS = Array.from({ length: 500 }, (_, i) => ({
		id: `v${i}`,
		camera: `EM-CAM-${String((i % 18) + 1).padStart(2, '0')}`,
		speed: 30 + ((i * 37) % 90),
		t: NOW - i * 2 * MIN
	}));
	let virtualSel = $state<string | null>(null);

	// the Read column is a DataTable time column: colStamp over the whole
	// column (IST, one format), sorted by the instant
	const SIGHTING_COLUMNS: DataColumn<Sighting>[] = [
		{ key: 'glyph', icon: true, render: glyphCell },
		{ key: 'camera', title: 'Camera', width: 136, sortable: true, render: cameraIdCell },
		{ key: 'road', title: 'Road', sortable: true, minWidth: 176 },
		{ key: 'speed', title: 'Speed', width: 84, num: true, sortable: true, render: speedCell },
		{ key: 't', title: 'Read (IST)', width: 84, num: true, sortable: true, time: { anchor: NOW } },
		{ key: 'state', title: 'State', width: 128, render: stateCell }
	];
	const TWO_LINE_COLUMNS: DataColumn<Sighting>[] = [
		{ key: 'glyph', icon: true, render: glyphCell },
		{ key: 'camera', title: 'Sighting', render: cameraIdCell, render2: roadLine2 },
		{ key: 'state', title: 'Decision', width: 136, render: stateCell, line2: (r) => `${STAMP.get(r.id)} · ${r.speed} km/h` }
	];
	type VirtualRow = (typeof VIRTUAL_ROWS)[number];
	const VIRTUAL_COLUMNS: DataColumn<VirtualRow>[] = [
		{ key: 'glyph', icon: true, render: vGlyph },
		{ key: 'camera', title: 'Camera', render: vCam },
		{ key: 'speed', title: 'km/h', width: 64, num: true },
		{ key: 't', title: 'Read (IST)', width: 112, num: true, time: { anchor: NOW } }
	];

	const propertyGroups = $derived<PropertyGroup[]>([
		{
			title: 'Identity',
			rows: [
				{ key: 'Registration mark', render: plateCell, hint: 'masked' },
				{ key: 'Class', value: 'Car' }
			]
		},
		{
			title: 'Lawful basis',
			rows: [
				{ key: 'Basis', value: 'Stolen vehicle (FIR)' },
				{ key: 'Reported', value: 'FIR 0001/2026, fictional police station' },
				{ key: 'Retention', render: retentionCell, hint: '30 days left' }
			]
		},
		{
			title: 'Last read',
			rows: [
				{ key: 'Camera', render: cameraCell },
				{ key: 'Speed, heading', value: '95 km/h · north-east' }
			]
		},
		{ title: 'Provenance', rows: [{ key: 'Source', render: provCell }] }
	]);

	// ── overlays ───────────────────────────────────────────────────────────
	let dialogOpen = $state<Record<Theme, boolean>>({ command: false, daylight: false });
	let alertOpen = $state<Record<Theme, boolean>>({ command: false, daylight: false });
	let drawerOpen = $state<Record<Theme, boolean>>({ command: false, daylight: false });
	let hotkeysOpen = $state<Record<Theme, boolean>>({ command: false, daylight: false });
	let toastSeq = 0;
	let liveToasts = $state<Record<Theme, ToastSpec[]>>({ command: [], daylight: [] });
	const STATIC_TOASTS: ToastSpec[] = [
		{ id: 'a', intent: 'success', message: 'Pursuit authorised for MH01XX•••7' },
		{ id: 'b', message: 'Share link copied (marks masked)', action: { label: 'Undo', onclick: () => {} } }
	];

	// a decision may be an approval or a rejection: its confirmation is neutral
	function pushToast(th: Theme) {
		const toast: ToastSpec = { id: `t${++toastSeq}`, message: 'Decision recorded with your name', timeout: 5000 };
		liveToasts[th] = [toast, ...liveToasts[th]].slice(0, 3);
	}

	// a popover opened from inside another (the navbar's More → Data pattern)
	const WINDOWS = [
		{ id: '1h', label: 'Last hour' },
		{ id: '6h', label: 'Last 6 hours' },
		{ id: '24h', label: 'Last 24 hours' }
	] as const;
	let nestedWindow = $state<Record<Theme, string>>({ command: '6h', daylight: '6h' });
	const windowItems = (th: Theme): MenuItemSpec[] =>
		WINDOWS.map((w) => ({ id: w.id, label: w.label, selected: nestedWindow[th] === w.id, attrs: { 'data-design-window': w.id } }));

	function dismissToast(th: Theme, id: ToastSpec['id']) {
		liveToasts[th] = liveToasts[th].filter((x) => x.id !== id);
	}

	// ── layout ─────────────────────────────────────────────────────────────
	let splitSize = $state<Record<Theme, number>>({ command: 200, daylight: 200 });

	// ── legacy primitives (data-prim, design-smoke) ─────────────────────────
	let demoBand = $state<Band>('GREEN');
	let dwell = $state(3);
	let modalOpen = $state(false);
	const legendItems: LegendItem[] = [
		{ id: 'corridor-events', label: 'Corridor events', colorToken: '--v-map-event', state: 'on', hint: 'live' },
		{ id: 'vehicle-traces', label: 'Vehicle traces', colorToken: '--v-map-select', state: 'on', hint: 'live' },
		{ id: 'signal-network', label: 'Signal network', colorToken: '--v-map-marker', state: 'off', hint: 'live' },
		{ id: 'agency-units', label: 'Agency units', colorToken: '--v-map-marker', state: 'on', hint: 'live' },
		{ id: 'cameras', label: 'Cameras', colorToken: '--v-ink-2', state: 'not-deployed', hint: 'not deployed (404)' }
	];
	let legendState = $state(legendItems);

	function fireToast(kind: 'info' | 'act' | 'error') {
		toasts.push({
			kind,
			title: kind === 'act' ? 'Decision approved' : kind === 'error' ? 'Held at baseline' : 'Share link copied',
			body: kind === 'error' ? 'Twin not calibrated' : `Sandbox officer · ${PLATE}`
		});
	}
</script>

<svelte:head><title>Design system · Sajag</title></svelte:head>

<!-- ── cells and snippets shared by the specimens ─────────────────────── -->

{#snippet plateCell()}<Plate mark={PLATE} masked />{/snippet}
{#snippet cameraCell()}<ObjectTag urn="camera:EM-CAM-03" kind="camera" label="EM-CAM-03" />{/snippet}
{#snippet retentionCell()}<Time value={NOW + 30 * 24 * 60 * MIN} anchor={NOW} suffix />{/snippet}
{#snippet provCell()}<ProvenanceTag source="emulated" />{/snippet}

{#snippet glyphCell(_r: Sighting)}<Icon name={kindIcon('sighting')} size={16} />{/snippet}
{#snippet cameraIdCell(r: Sighting)}<Id value={r.camera} />{#if r.emulated}<ProvenanceTag source="emulated" compact />{/if}{/snippet}
{#snippet speedCell(r: Sighting)}<span class="tn">{r.speed}</span><span class="unit">km/h</span>{/snippet}
{#snippet stateCell(r: Sighting)}<Tag intent={STATE_TAG[r.state].intent}>{STATE_TAG[r.state].label}</Tag>{/snippet}
{#snippet roadLine2(r: Sighting)}<span>{r.road}</span>{/snippet}

{#snippet sightingDetail(r: Sighting)}
	<div class="detail">
		<Note icon={ACTION_ICON.rule_no_fine} title="Evidence only.">
			No e-challan for a stolen vehicle's owner; one approval opens one pursuit.
		</Note>
		<div class="row">
			<CompoundTag left="Camera" value={r.camera} />
			<CompoundTag left="Read" value={STAMP.get(r.id) ?? '—'} />
			<CompoundTag left="Speed" value={`${r.speed} km/h`} />
		</div>
	</div>
{/snippet}

{#snippet vGlyph(_r: VirtualRow)}<Icon name={kindIcon('sighting')} size={16} />{/snippet}
{#snippet vCam(r: VirtualRow)}<Id value={r.camera} />{/snippet}

<!-- ── specimens (each rendered once per theme) ─────────────────────────── -->

{#snippet spFoundations(th: Theme)}
	<div class="swatch-groups">
		{#each SWATCHES as g (g.group)}
			<div class="sw-group">
				<div class="caption">{g.group}</div>
				<div class="swatches">
					{#each g.tokens as tok (tok)}
						<div class="swatch">
							<span class="chip" style:background="var({tok})"></span>
							<Id value={tok.replace('--v-', '')} />
						</div>
					{/each}
				</div>
			</div>
		{/each}
		<div class="sw-group">
			<div class="caption">Band ladder</div>
			<div class="swatches">
				{#each BANDS as b (b)}
					<div class="swatch">
						<span
							class={['chip', b === 'BLACK' && 'black']}
							style:background={b === 'BLACK' ? undefined : `var(--v-band-${b.toLowerCase()})`}
						></span>
						<span>{BAND_WORD[b]}</span>
					</div>
				{/each}
			</div>
		</div>
		<div class="sw-group">
			<div class="caption">Traffic flow, free to jammed</div>
			<div class="flow-rows">
				{#each FLOW as s, i (s)}
					<div class="flow-row">
						<svg class="flow" width="72" height="16" viewBox="0 0 72 16" aria-hidden="true">
							{#if s >= 3}<line x1="6" x2="66" y1="8" y2="8" class="casing" style:stroke-width="calc(var(--v-flow-width-{s}) + 2px)" />{/if}
							<line x1="6" x2="66" y1="8" y2="8" style:stroke="var(--v-flow-{s})" style:stroke-width="var(--v-flow-width-{s})" />
						</svg>
						<span>{FLOW_WORD[i]}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
	<div class="type-scale">
		{#each TYPE_SCALE as row (row.role)}
			<div class="ts-row">
				<span class="ts-role">{row.role}</span>
				<span class={row.cls} data-ts-sample={row.spec[th]}>{row.sample}</span>
				<span class="ts-spec">{row.spec[th]}</span>
			</div>
		{/each}
		<div class="ts-row">
			<span class="ts-role">Identifier</span>
			<span class="ts-body">Read at <Id value="EM-CAM-03" /> · mark <Plate mark={PLATE} /></span>
			<span class="ts-spec">mono, max(12px, 0.9em)</span>
		</div>
		<div class="ts-row">
			<span class="ts-role">हिंदी · मराठी</span>
			<span class="ts-body">सड़क बंद · रस्ता बंद</span>
			<span class="ts-spec">Noto Sans, self-hosted</span>
		</div>
	</div>
	<div class="elevations">
		{#each [0, 1, 2, 3, 4] as e (e)}
			<div class="elev" style:box-shadow="var(--v-elev-{e})"><span class="small">elev-{e}</span></div>
		{/each}
	</div>
{/snippet}

{#snippet spIcons(_th: Theme)}
	<div class="icon-maps">
		{#each ICON_MAPS as m (m.title)}
			<div class="icon-map">
				<div class="caption">{m.title}</div>
				<div class="icon-grid">
					{#each Object.entries(m.map) as [k, name] (k)}
						<Tooltip content={name}>
							<span class="icon-cell"><Icon {name} size={16} /><span class="ic-name">{k.replaceAll('_', ' ')}</span></span>
						</Tooltip>
					{/each}
				</div>
			</div>
		{/each}
	</div>
	<div class="row">
		<Icon name={kindIcon('vehicle')} size={20} />
		<Icon name={kindIcon('camera')} size={20} />
		<Icon name={eventKindIcon('procession')} size={20} />
		<Icon name={ACTOR_ICON.ai} size={20} intent="ai" />
		<Icon name={INTENT_ICON.warning} size={16} intent="warning" />
		<Icon name={INTENT_ICON.danger} size={16} intent="danger" />
		<Icon name={INTENT_ICON.success} size={16} intent="success" />
		<span class="small muted">20 px drawings for titles; 16 px in chrome; colour only through an intent</span>
	</div>
{/snippet}

{#snippet spFormatter(_th: Theme)}
	<PropertyTable
		groups={[
			{
				rows: [
					{ key: 'Id', render: fmtId },
					{ key: 'Plate (masked)', render: fmtPlate },
					{ key: 'Time', render: fmtTime },
					{ key: 'Time, other day', render: fmtTimeOther },
					{ key: 'Time, relative', render: fmtAgo },
					{ key: 'TimeRange', render: fmtRanges },
					{ key: 'Coord', render: fmtCoord }
				]
			}
		]}
	/>
	<div class="caption top">In a 12 px meta line (the suffix never drops under 12 px)</div>
	<div class="small muted" data-design="small-times">
		Last read <Time value={NOW - 100 * MIN} anchor={NOW} suffix /> · window <TimeRange
			start={NOW - 118 * MIN}
			end={NOW - 96 * MIN}
			anchor={NOW}
			suffix
		/>
	</div>
	<div class="caption top">One format per column (colStamp)</div>
	<table class="mini">
		<thead><tr><th>Same day</th><th>Mixed days</th></tr></thead>
		<tbody>
			{#each colStamp([NOW - 4 * MIN, NOW - 60 * MIN, NOW - 125 * MIN], NOW) as a, i (i)}
				{@const b = colStamp([NOW - 4 * MIN, NOW - 60 * MIN, NOW - 30 * 60 * MIN], NOW)[i]}
				<tr><td class="tn">{a}</td><td class="tn">{b}</td></tr>
			{/each}
		</tbody>
	</table>
{/snippet}
{#snippet fmtId()}<Id value="EM-CAM-03" /> <Id value="event:5f0c…e21" />{/snippet}
{#snippet fmtPlate()}<span data-design-plate><Plate mark={PLATE} masked /></span>{/snippet}
{#snippet fmtTime()}<Time value={NOW - 100 * MIN} anchor={NOW} suffix /> · <Time value={NOW - 100 * MIN} seconds />{/snippet}
{#snippet fmtTimeOther()}<Time value={NOW - 6 * 60 * MIN} anchor={NOW} />{/snippet}
{#snippet fmtAgo()}<Time value={NOW - 100 * MIN} ago now={NOW} />{/snippet}
{#snippet fmtRanges()}<TimeRange start={NOW - 118 * MIN} end={NOW - 96 * MIN} anchor={NOW} /> · <TimeRange
		start={NOW - 206 * MIN}
		end={NOW - 194 * MIN}
		anchor={NOW}
	/>{/snippet}
{#snippet fmtCoord()}<Coord lat={19.0049} lon={72.8424} />{/snippet}

{#snippet spButtons(th: Theme)}
	<div class="stack">
		<div class="caption">Decision row: Reject or Dismiss (default), then the one primary</div>
		<div class="row decision-row" data-design="decision-row">
			<Button minimal icon={ACTION_ICON.show_on_map} tooltip="Show the evidence on the map" />
			<span class="grow"></span>
			<Button data-design-decision="reject">Reject</Button>
			<Button intent="primary" icon="tick" data-design-decision="approve">Approve</Button>
		</div>
		<div class="row decision-row top-align" data-design="decision-row-locked">
			<Button minimal icon={ACTION_ICON.show_on_map} tooltip="Show the evidence on the map" />
			<span class="grow"></span>
			<Button disabled disabledReason="Name a duty officer and give a reason to dismiss.">Dismiss all 6…</Button>
			<Button
				intent="primary"
				icon={eventKindIcon('vehicle_pursuit')}
				disabled
				disabledReason="Name a duty officer to decide."
				reasonInline
			>
				Authorise pursuit
			</Button>
		</div>
		<div class="row">
			<Button minimal icon={ACTION_ICON.search_around}>Search around</Button>
			<Button minimal intent="primary">Open in workspace</Button>
			<Button outlined>Outlined</Button>
			<Button minimal icon="more" tooltip="More actions" />
			<Button icon="refresh" tooltip="Refresh" />
		</div>
		<div class="row">
			<Button small icon="plus">Request unit</Button>
			<Button>Regular</Button>
			<Button large intent="primary">Plan corridor</Button>
			<Button pressed={following[th]} icon="locate" onclick={() => (following[th] = !following[th])}>Follow</Button>
			<Button loading>Saving</Button>
			<Button disabled>Disabled</Button>
		</div>
		<div class="caption">Intent fills (API reference; SPEC §2.4 decides where each may appear)</div>
		<div class="row" data-design="button-intents">
			<Button>Default</Button>
			<Button intent="primary">Primary</Button>
			<Button intent="success">Success</Button>
			<Button intent="warning">Warning</Button>
			<Button intent="danger">Danger</Button>
		</div>
		<div class="row">
			<Button icon={ACTION_ICON.inbox} intent="warning" data-design="inbox-decision">Inbox 1</Button>
			<Button icon={ACTION_ICON.inbox} intent="danger" data-design="inbox-watchlist">Inbox 1</Button>
			<span class="small muted">The Inbox button: a decision waits; an unread watchlist read</span>
		</div>
		<div class="row">
			<ButtonGroup>
				<Button icon="map" pressed={view[th] === 'map'} onclick={() => (view[th] = 'map')}>Map</Button>
				<Button icon="graph" pressed={view[th] === 'graph'} onclick={() => (view[th] = 'graph')}>Graph</Button>
				<Button icon="th" pressed={view[th] === 'table'} onclick={() => (view[th] = 'table')}>Table</Button>
			</ButtonGroup>
			<ButtonGroup minimal>
				<Button minimal icon="zoom-in" tooltip="Zoom in" />
				<Button minimal icon="zoom-out" tooltip="Zoom out" />
				<Button minimal icon="zoom-to-fit" tooltip="Zoom to fit" />
			</ButtonGroup>
			<SegmentedControl
				label="Window"
				bind:value={windowSel[th]}
				options={[
					{ value: '1h', label: '1 h' },
					{ value: '6h', label: '6 h' },
					{ value: '24h', label: '24 h' },
					{ value: '7d', label: '7 d' }
				]}
			/>
		</div>
		<Button fill alignText="left" icon={MODULE_ICON.corridor} rightIcon="chevron-right">Corridor workspace</Button>
	</div>
{/snippet}

{#snippet spTags(th: Theme)}
	<div class="stack">
		<div class="row" data-design="tag-roles">
			<Tag>Car</Tag>
			<Tag data-design-tag="active">Active</Tag>
			<Tag intent="success">Approved</Tag>
			<Tag intent="warning">Needs decision</Tag>
			<Tag intent="danger" icon="flag">Watchlist</Tag>
			<Tag intent="danger" icon={INTENT_ICON.danger}>Reported stolen</Tag>
			<Tag intent="ai" icon={ACTOR_ICON.ai}>Proposed by Sajag AI</Tag>
			<Tag intent="primary" icon="selection">+3 selected</Tag>
		</div>
		<div class="small muted">
			States are neutral; orange waits for a decision, red is a watchlisted or stolen vehicle, green is approved, blue is the
			selection, indigo is AI
		</div>
		<div class="row">
			<Tag round>6</Tag>
			<Tag round intent="warning">1</Tag>
			{#each filters as f (f)}
				<Tag removable onremove={() => (filters = filters.filter((x) => x !== f))}>{f}</Tag>
			{/each}
		</div>
		<div class="row">
			<CompoundTag left="Needs decision" value="6" intent="warning" icon={ACTION_ICON.inbox} />
			<CompoundTag left="Writer" value="Off" />
			<CompoundTag left="Window" value="01:20–01:42" />
		</div>
		<div class="row" data-design="filter-chips">
			{#each chips[th] as c (c.k)}
				<CompoundTag left={c.k} value={c.v} removable onremove={() => (chips[th] = chips[th].filter((x) => x.k !== c.k))} data-design-chip={c.k} />
			{/each}
			<Tag interactive icon="filter" onclick={() => resetFilters(th)} data-design="reset-filters">Reset filters</Tag>
			<span class="small muted">Workspace filters: a removable CompoundTag</span>
		</div>
		<div class="row" data-design="provenance">
			<ProvenanceTag source="emulated" />
			<ProvenanceTag source="simulated" />
			<ProvenanceTag source="test" />
			<ProvenanceTag source="osint" />
			<ProvenanceTag source="osint" verification="UNVERIFIED-OSINT" />
			<ProvenanceTag source="osint" verification="NEWS-REPORTED" />
			<ProvenanceTag source="osint" verification="OFFICIAL-VERIFIED" />
			<ProvenanceTag source="osint" verification="CONFIRMED" />
		</div>
		<div class="row">
			<span class="small muted">Compact (mixed lists):</span>
			<ProvenanceTag source="emulated" compact data-design="prov-compact" />
			<ProvenanceTag source="simulated" compact />
			<ProvenanceTag source="test" compact />
			<ProvenanceTag source="osint" verification="NEWS-REPORTED" compact />
		</div>
		<div class="row" data-design="prov-fallbacks">
			<span class="small muted">A source the console does not know says so; a live row is unmarked:</span>
			<ProvenanceTag source={'fixture' as ProvenanceSource} data-design="prov-unknown" />
			<span class="small muted" data-design="prov-live">source live: no tag<ProvenanceTag source={'live' as ProvenanceSource} /></span>
		</div>
		<div class="row">
			<ObjectTag urn="vehicle:demo-1" kind="vehicle" label={PLATE} masked onselect={() => {}} />
			<ObjectTag urn="camera:EM-CAM-03" kind="camera" label="EM-CAM-03" onselect={() => {}} />
			<ObjectTag urn="junction:105" kind="junction" label="Hindmata junction" />
			<ObjectTag urn="event:demo-2" kind="event" eventKind="procession" label="Visarjan procession" />
			<ObjectTag urn="recommendation:demo-3" kind="recommendation" label="Stolen-vehicle sighting" />
			<ObjectTag urn="osint_event:demo-4" kind="osint_event" label="Road accident · BKC connector" />
			<ObjectTag urn="place:bkc_connector" kind="place" label="BKC connector" />
		</div>
	</div>
{/snippet}

{#snippet spNotes(_th: Theme)}
	<div class="stack">
		<Note icon={ACTION_ICON.rule_no_fine} title="Evidence only.">
			No e-challan for a stolen vehicle's owner; a sighting can only authorise one pursuit.
		</Note>
		<Reason text="Name a duty officer to decide." />
		<Callout title="Sample answer">The assistant is offline; this is a recorded example, not a live answer.</Callout>
		<Callout icon={ACTION_ICON.emulated} title="Exercise data" data-design-callout="exercise">
			Feeds are simulated or emulated. Every advisory draft says so in its text.
		</Callout>
		<Callout icon="offline" title="Feed lost" data-design-callout="feed-lost">Signal ingress has not answered for 2 min.</Callout>
		<Callout intent="warning" title="Decision waiting">An escort proposal expires in 0:47.</Callout>
		<Callout intent="success" compact>Pursuit authorised. Opening the pursuit is a separate decision.</Callout>
	</div>
{/snippet}

{#snippet spForms(th: Theme)}
	<div class="form-grid">
		<FormGroup label="Search" labelFor="d-search-{th}" helperText="Objects, marks, roads and commands">
			<Input id="d-search-{th}" bind:value={search} leftIcon="search" placeholder="Search objects, plates, roads…" clearable>
				{#snippet rightElement()}<Kbd keys={['Ctrl', 'K']} />{/snippet}
			</Input>
		</FormGroup>
		<FormGroup
			label="Duty officer"
			labelFor="d-officer-{th}"
			helperText="Shows full registration marks on this console and records the name with your decision. Attribution, not sign-in."
		>
			<Input id="d-officer-{th}" bind:value={officerName} leftIcon={ACTOR_ICON.officer} placeholder="Name as on the duty roster" />
		</FormGroup>
		<FormGroup label="Reason" labelFor="d-reason-{th}" labelInfo="(required to dismiss)" helperText="Write why, in a few words.">
			<Input id="d-reason-{th}" placeholder="e.g. duplicate read" />
		</FormGroup>
		<FormGroup label="Read-only" labelFor="d-ro-{th}">
			<Input id="d-ro-{th}" value="EM-CAM-03" readonly />
		</FormGroup>
		<FormGroup label="Road" labelFor="d-road-{th}">
			<HTMLSelect
				id="d-road-{th}"
				bind:value={roadSel}
				fill
				options={[
					{ value: 'dh_road', label: 'Diamond Harbour Road' },
					{ value: 'khudiram', label: 'Annie Besant Road' },
					{ value: 'strand', label: 'P D Mello Road' }
				]}
			/>
		</FormGroup>
		<FormGroup label="Hold point" labelFor="d-time-{th}" helperText="Typed as hh:mm; ↑ and ↓ step a minute">
			<TimeField id="d-time-{th}" bind:value={holdAt} />
		</FormGroup>
		<div class="stack">
			<Switch bind:checked={live} label="Live" />
			<Switch bind:checked={sims} label="Show simulated feed" />
			<Switch checked disabled label="Writer (policy)" />
		</div>
		<div class="stack">
			<Checkbox bind:checked={checkA} label="Vehicles" />
			<Checkbox bind:checked={checkB} label="Units" />
			<Checkbox indeterminate label="Some layers" />
			<Checkbox disabled label="Lab layers (off by policy)" />
		</div>
		<div class="stack">
			<span class="eye-row"><span>Cameras</span><EyeToggle bind:visible={eyeA} label="Cameras" /></span>
			<span class="eye-row"><span>Signal plans</span><EyeToggle bind:visible={eyeB} label="Signal plans" /></span>
			<span class="eye-row dimmed"><span>Sightings</span><EyeToggle visible empty label="Sightings" /></span>
		</div>
	</div>
{/snippet}

{#snippet spNavigation(th: Theme)}
	<div class="stack">
		<Tabs
			bind:value={tab[th]}
			items={[
				{ id: 'inspector', label: 'Inspector', icon: 'properties' },
				{ id: 'inbox', label: 'Inbox', icon: ACTION_ICON.inbox, count: 2, countIntent: 'warning' },
				{ id: 'links', label: 'Links', count: 51 },
				{ id: 'assistant', label: 'Assistant', icon: ACTOR_ICON.ai }
			]}
		/>
		<Breadcrumbs items={[{ label: 'Haji Ali · stolen vehicle', onclick: () => {} }, { label: 'Vehicles', onclick: () => {} }, { label: PLATE }]}>
			{#snippet current()}<Plate mark={PLATE} />{/snippet}
		</Breadcrumbs>
		<div class="nav-grid">
			<div class="framed">
				<Tree nodes={treeNodes} label="Layers" onnodeclick={(n) => (treeSel = n.id)}>
					{#snippet end(n)}
						{#if n.icon}<EyeToggle visible={n.id !== 'signals'} empty={n.dim} label={n.label} />{/if}
					{/snippet}
				</Tree>
			</div>
			<div class="framed menu-box">
				<Menu items={menuItems} label="Selection actions" />
			</div>
		</div>
	</div>
{/snippet}

{#snippet spContainers(th: Theme)}
	<div class="stack">
		<div class="framed">
			<Section title="Decisions" icon={ACTION_ICON.inbox} sub="1 waiting">
				{#snippet right()}<Button minimal small icon="filter-list" tooltip="Filter" />{/snippet}
				<div class="pad">
					<EntityTitle icon={kindIcon('vehicle')} alert subtitle="Vehicle · Car · last read 01:38 IST at EM-CAM-03">
						{#snippet title()}<Plate mark={PLATE} />{/snippet}
						{#snippet tags()}
							<Tag intent="danger" icon="flag">Watchlist</Tag>
							<Tag intent="danger" icon={INTENT_ICON.danger}>Reported stolen</Tag>
							<ProvenanceTag source="emulated" />
						{/snippet}
					</EntityTitle>
				</div>
			</Section>
			<Section title="City signal plans" icon={KIND_ICON.junction} collapsible open={th === 'command'}>
				{#snippet right()}<Tag icon={ACTION_ICON.masked}>Writer off</Tag>{/snippet}
				<div class="pad small muted">Four plans, one per band. The writer is off by policy.</div>
			</Section>
		</div>
		<div class="row top-align">
			<Card interactive selected style="width: 180px">
				<div class="h6">Corridor A</div>
				<div class="small muted">Selected card</div>
			</Card>
			<Card elevation={2} style="width: 180px">
				<div class="h6">Elevation 2</div>
				<div class="small muted">A floating card</div>
			</Card>
		</div>
		<CardList>
			<Card interactive compact>
				<div class="row"><Icon name={eventKindIcon('procession')} /><span>Visarjan procession</span><span class="grow"></span><TimeRange start={NOW - 66 * MIN} end={NOW} anchor={NOW} /></div>
			</Card>
			<Card interactive compact>
				<div class="row"><Icon name={eventKindIcon('work_zone')} /><span>Metro work zone</span><span class="grow"></span><Tag>Active</Tag></div>
			</Card>
			<Card interactive compact>
				<div class="row"><Icon name={eventKindIcon('protected_movement')} /><span>Protected movement</span><span class="grow"></span><Tag>Planning</Tag></div>
			</Card>
		</CardList>
	</div>
{/snippet}

{#snippet spData(th: Theme)}
	<div class="stack">
		<div class="metrics framed">
			<MetricCard caption="Open events" value={0} sub="39 in history" />
			<MetricCard caption="Decisions waiting" value={1} intent="warning" sub="6 sightings · waiting 1 h 40 min" />
			<MetricCard caption="Corridor speed" value="53.1" unit="km/h" sub="Simulated · last hour" spark={[48, 51, 50, 46, 44, 49, 53, 52, 55, 53]} />
			<MetricCard caption="Watchlist reads" value={19} unit="24 h" sub="1 vehicle · last 01:38" spark={[0, 0, 1, 0, 0, 2, 1, 0, 3, 12]} />
		</div>
		<div class="caption">A zero recedes to ink-2 at 400, whatever its intent</div>
		<div class="metrics framed" data-design="metric-zeros">
			<MetricCard caption="Decisions waiting" value={0} intent="warning" sub="Nothing waits for a decision" data-design-metric="zero-warning" />
			<MetricCard caption="Watchlist alerts" value={0} intent="danger" sub="None unread in 24 h" data-design-metric="zero-danger" />
		</div>
		<div class="framed table-box" data-design="sightings-table">
			<DataTable
				columns={SIGHTING_COLUMNS}
				rows={SIGHTINGS}
				rowKey={(r) => r.id}
				selected={rowSel[th]}
				onselect={(k) => (rowSel[th] = k)}
				bind:expanded={rowOpen[th]}
				expandable={sightingDetail}
				dim={(r) => r.state === 'rejected'}
				caption="Sightings"
			/>
		</div>
		<div class="framed table-box" data-design="two-line-table">
			<DataTable columns={TWO_LINE_COLUMNS} rows={SIGHTINGS.slice(0, 3)} rowKey={(r) => r.id} density="two-line" caption="Decided items" />
		</div>
		<div class="framed" data-design="virtual-table">
			<DataTable
				columns={VIRTUAL_COLUMNS}
				rows={VIRTUAL_ROWS}
				rowKey={(r) => r.id}
				height="224px"
				selected={virtualSel}
				onselect={(k) => (virtualSel = k)}
				caption="500 reads (virtualised)"
			/>
		</div>
		<div class="framed pad">
			<PropertyTable groups={propertyGroups} />
		</div>
	</div>
{/snippet}

{#snippet spOverlays(th: Theme)}
	<div class="stack">
		<div class="row">
			<Button icon="link" onclick={() => (dialogOpen[th] = true)} data-design-open="dialog">Share view</Button>
			<Button onclick={() => (alertOpen[th] = true)} data-design-open="alert">Cancel event</Button>
			<Button icon="drawer-right" onclick={() => (drawerOpen[th] = true)} data-design-open="drawer">Open drawer</Button>
			<Button icon="key-command" onclick={() => (hotkeysOpen[th] = true)} data-design-open="hotkeys">Shortcuts</Button>
			<Popover placement="bottom-start" data-design-popover>
				<Button rightIcon="caret-down" data-design-open="popover">Actions</Button>
				{#snippet content({ close })}
					<Menu items={menuItems} onselect={close} label="Actions" autofocus />
				{/snippet}
			</Popover>
			<Popover placement="bottom-start" data-design-popover="parent">
				<Button icon="filter" rightIcon="caret-down" data-design-open="nested">Filters</Button>
				{#snippet content()}
					<div class="pop-body">
						<div class="caption">Time window</div>
						<Popover placement="right-start" data-design-popover="child">
							<Button small fill alignText="left" rightIcon="caret-right" data-design-open="nested-child">
								{WINDOWS.find((w) => w.id === nestedWindow[th])?.label}
							</Button>
							{#snippet content({ close })}
								<Menu
									items={windowItems(th)}
									onselect={(item) => {
										nestedWindow[th] = item.id;
										close();
									}}
									label="Time window"
									autofocus
								/>
							{/snippet}
						</Popover>
						<span class="small muted">A popover opened from inside this one keeps it open</span>
					</div>
				{/snippet}
			</Popover>
		</div>
		<div class="row">
			<Tooltip content="Inverted tooltip: 12 px, no arrow">
				<Button minimal icon="help" data-design-tooltip>Hover for a tooltip</Button>
			</Tooltip>
			<Button onclick={() => pushToast(th)} data-design-open="toast">Show toast</Button>
			<span class="small muted">Keys: <Kbd keys={['Ctrl', 'K']} /> <Kbd>?</Kbd> <Kbd>Esc</Kbd></span>
		</div>
		<div class="toast-box">
			<Toaster toasts={STATIC_TOASTS} position="inline" />
		</div>
		<Toaster toasts={liveToasts[th]} ondismiss={(id) => dismissToast(th, id)} position="top" />
		<Dialog bind:open={dialogOpen[th]} title="Share this view" icon="link">
			<p class="body-text">The link carries the map, the selection and the time window. Registration marks stay masked in the link.</p>
			<Input value="https://sajag.local/#v=2&sel=camera:EM-CAM-03" readonly fill />
			{#snippet footer()}
				<Button onclick={() => (dialogOpen[th] = false)}>Close</Button>
				<Button intent="primary" icon="duplicate" onclick={() => (dialogOpen[th] = false)}>Copy link</Button>
			{/snippet}
		</Dialog>
		<Alert bind:open={alertOpen[th]} confirmLabel="Cancel the event" cancelLabel="Keep it" onconfirm={() => (alertOpen[th] = false)}>
			<p>Cancel <b>Metro work zone</b>? Its closures lift and citizens see the change.</p>
		</Alert>
		<Drawer bind:open={drawerOpen[th]} title="Sighting detail" icon={kindIcon('sighting')} size="360px">
			<PropertyTable groups={propertyGroups} />
		</Drawer>
		<HotkeysDialog bind:open={hotkeysOpen[th]} />
	</div>
{/snippet}

{#snippet spFeedback(_th: Theme)}
	<div class="stack">
		<div class="framed">
			<NonIdealState icon="search" title="No matching objects" description="Try a road name, a camera id or part of a registration mark." iconSize={32}>
				{#snippet action()}<Button small>Clear the search</Button>{/snippet}
			</NonIdealState>
		</div>
		<div class="row">
			<Spinner size={16} />
			<Spinner size={20} />
			<Spinner size={50} value={0.62} />
			<span class="small muted">Spinners: 16, 20 and a determinate 50</span>
		</div>
		<Skeleton lines={3} />
		<div class="stack tight">
			<span class="small muted">Expiry of an escort proposal</span>
			<ProgressBar value={0.72} intent="warning" label="Time left" />
			<span class="small muted">Loading the history</span>
			<ProgressBar label="Loading" />
		</div>
	</div>
{/snippet}

{#snippet spLayout(th: Theme)}
	<div class="split-demo framed">
		<div class="pane" style:width="{splitSize[th]}px">
			<div class="pane-head">Explorer</div>
			<div class="small muted pad">{splitSize[th]} px — drag the divider or use the arrow keys</div>
		</div>
		<Splitter bind:size={splitSize[th]} min={120} max={320} label="Resize the explorer" />
		<div class="pane grow">
			<div class="pane-head">Map</div>
		</div>
	</div>
{/snippet}

<!-- ── the page ───────────────────────────────────────────────────────── -->

<div class="gallery" data-design="gallery" data-ui-primitives={UI_PRIMITIVES.length}>
	<nav class="toc" aria-label="Sections">
		<div class="toc-title">Design system</div>
		<ul>
			{#each SECTIONS as [id, label] (id)}
				<li><a href="#{id}" class={['toc-link', currentSection === id && 'is-selected']}>{label}</a></li>
			{/each}
		</ul>
	</nav>

	<div class="content">
		<header class="page-head">
			<EntityTitle
				icon={MODULE_ICON.city}
				title="Design system"
				subtitle={`${UI_PRIMITIVES.length} primitives from src/lib/ui on Blueprint 6 tokens · fictional data only`}
				level={1}
			/>
			<div class="controls">
				<SegmentedControl
					label="Theme"
					bind:value={themeMode}
					options={[
						{ value: 'both', label: 'Both themes' },
						{ value: 'command', label: 'Command' },
						{ value: 'daylight', label: 'Daylight' }
					]}
				/>
				<span class="small muted">Language: the switch in the top bar</span>
			</div>
		</header>

		{#snippet section(id: string, title: string, sub: string, body: Snippet<[Theme]>, previews = false)}
			<section {id} class="sec" data-design-section={id}>
				<header class="sec-head">
					<h2>{title}</h2>
					<span class="sec-sub">{sub}</span>
				</header>
				<div class={['specimens', themes.length === 1 && 'single']}>
					{#each themes as th (th)}
						<div class="specimen" data-theme={th} data-specimen-theme={th} data-theme-preview={previews ? th : undefined}>
							<div class="sp-label">{THEME_LABEL[th]}</div>
							{@render body(th)}
						</div>
					{/each}
				</div>
			</section>
		{/snippet}

		{@render section('foundations', 'Colour and type', 'tokens.css · Inter and JetBrains Mono, self-hosted', spFoundations, true)}
		{@render section('icons', 'Icons', 'Blueprint 6.14 glyphs through the frozen maps · no person glyph', spIcons)}
		{@render section('formatter', 'Formatter', 'Id · Plate · Time · TimeRange · Coord — IST, one format per column', spFormatter)}
		{@render section('buttons', 'Buttons', 'Button · ButtonGroup · SegmentedControl', spButtons)}
		{@render section('tags', 'Tags', 'Tag · CompoundTag · ProvenanceTag · ObjectTag', spTags)}
		{@render section('notes', 'Notes and callouts', 'Note (the rule note) · Reason · Callout', spNotes)}
		{@render section('forms', 'Form controls', 'Input · FormGroup · HTMLSelect · TimeField · Switch · Checkbox · EyeToggle', spForms)}
		{@render section('navigation', 'Navigation', 'Tabs · Breadcrumbs · Tree · Menu', spNavigation)}
		{@render section('containers', 'Containers', 'Section · EntityTitle · Card · CardList', spContainers)}
		{@render section('data', 'Data', 'MetricCard · DataTable (two-line, expandable, virtualised) · PropertyTable', spData)}
		{@render section('overlays', 'Overlays', 'Popover · Menu · Tooltip · Dialog · Alert · Drawer · Toaster · HotkeysDialog · Kbd', spOverlays)}
		{@render section('feedback', 'Feedback', 'NonIdealState · Spinner · Skeleton · ProgressBar', spFeedback)}
		{@render section('layout', 'Layout', 'Splitter', spLayout)}

		<section id="all-icons" class="sec">
			<Section title="All glyphs" sub={`${ALL_ICONS.length} on the 16 px grid`} collapsible bind:open={showAllIcons} variant="card">
				<div class="all-icons">
					{#each ALL_ICONS as name (name)}
						<span class="glyph-cell"><Icon {name} size={16} /><span class="ic-name">{name}</span></span>
					{/each}
				</div>
			</Section>
		</section>

		<!-- ── legacy primitives: every data-prim stays mounted (design-smoke) ── -->
		<section id="legacy" class="sec legacy" data-design-section="legacy">
			<header class="sec-head">
				<h2>Legacy primitives</h2>
				<span class="sec-sub">src/lib/primitives on the new token values; the shell slice rebuilds them on src/lib/ui</span>
			</header>

			<div class="legacy-grid">
				<div class="legacy-block wide">
					<div class="caption">Band masthead: hysteresis dwell, then the 600 ms wipe</div>
					<BandMasthead
						band={demoBand}
						posture="{BAND_WORD[demoBand]}: posture sentence for the city, one line"
						candidate={{ band: 'RED', ticks: dwell, required: 4 }}
						bandSource="situation_log"
						{lang}
					/>
					<div class="row">
						<SegmentedControl
							label="Band"
							bind:value={demoBand}
							options={BANDS.map((b) => ({ value: b, label: BAND_WORD[b], attrs: { 'data-band-cycle': b } }))}
						/>
						<Button small onclick={() => (dwell = (dwell % 4) + 1)}>Tick {dwell}/4</Button>
						<span class="small muted">Black: a dark fill with a red hairline; the hairline breathes only where motion is on</span>
					</div>
				</div>

				<div class="legacy-block wide">
					<div class="caption">Counters (DataTile)</div>
					<div class="tiles">
						<DataTile label="Active events" value="3" source={{ variant: 'live', label: 'live' }} />
						<DataTile label="Pending decisions" value="2" source={{ variant: 'act', label: 'pending' }} />
						<DataTile label="Units dispatched" value="5" unit="units" source={{ variant: 'fixture', label: 'mixed' }} />
						<DataTile label="Ambulance windows" value="1" source={{ variant: 'emulated', label: 'emulated' }} />
					</div>
				</div>

				<div class="legacy-block">
					<div class="caption">Panel, PanelShell, Badge, EmptyState</div>
					<Panel title="Panel" sub="renders only what it is given" status={{ state: 'live', updatedAt: Date.now() }} {lang}>
						<div class="row wrap">
							<Badge variant="live" />
							<Badge variant="offline" />
							<Badge variant="fixture" />
							<Badge variant="emulated" />
							<Badge variant="not-deployed" />
							<Badge variant="stale" />
							<Badge variant="pending" />
							<Badge variant="approved" />
							<Badge variant="rejected" />
							<Badge variant="deferred" />
							<Badge variant="act" />
							<Badge variant="neutral" label="neutral" />
							<Badge variant="band" band="GREEN" />
							<Badge variant="band" band="BLACK" />
						</div>
					</Panel>
					<PanelShell title="PanelShell" variant="raised" {lang}>
						<p class="small muted">PanelShell is an alias of Panel.</p>
					</PanelShell>
					<EmptyState title="Nothing here yet" hint="Every fixture-fed surface says so." />
				</div>

				<div class="legacy-block">
					<div class="caption">Button (actor gate) and BandChip</div>
					<div class="row wrap">
						<LegacyButton variant="primary" size="sm">Commit (locked)</LegacyButton>
						<LegacyButton variant="primary" size="sm" actor="Sandbox officer">Commit</LegacyButton>
						<LegacyButton variant="secondary" size="sm">Secondary</LegacyButton>
						<LegacyButton variant="ghost" size="sm">Ghost</LegacyButton>
						<LegacyButton variant="danger-outline" size="sm">Reject</LegacyButton>
						<LegacyButton variant="secondary" size="sm" busy>Busy</LegacyButton>
					</div>
					<div class="row wrap">
						<BandChip band="GREEN" />
						<BandChip band="AMBER" />
						<BandChip band="RED" />
						<BandChip band="BLACK" />
						<BandChip band="RED" hollow />
					</div>
					<div class="caption top">Audit rows (FeedItem, AuditRow)</div>
					<div class="feed">
						<FeedItem ts={NOW - 4000} actor="Sandbox officer" actorKind="human" level="decision" text="Approved an e-challan for {PLATE_2}: 112 km/h in a 60 segment" {lang} />
						<AuditRow ts={NOW - 9000} actor="adaptive" actorKind="machine" level="band" text="Band green → amber, hysteresis n=4" source="audit-poll" {lang} />
						<AuditRow ts={NOW - 15000} actor="interception plan" actorKind="machine" level="tool" text="Ranked chokes 1 → 3" source="ndjson-chat" {lang} />
						<FeedItem ts={NOW - 30000} actor="signals" actorKind="machine" level="error" text="Apply refused: twin not calibrated, held at baseline" source="audit-poll" {lang} />
					</div>
				</div>

				<div class="legacy-block">
					<div class="caption">LayerRail and MapLegend</div>
					<LayerRail
						items={legendState}
						onToggle={(id) =>
							(legendState = legendState.map((i) =>
								i.id === id && i.state !== 'not-deployed' ? { ...i, state: i.state === 'on' ? 'off' : 'on' } : i
							))}
						{lang}
					/>
					<MapLegend items={legendState} {lang} />
				</div>

				<div class="legacy-block">
					<div class="caption">DecisionCard</div>
					<DecisionCard
						kind="echallan"
						title="{PLATE_2} · 112 km/h in a 60 segment"
						deadline="retention 09:42"
						namedActor={null}
						actions={[
							{ id: 'approve', label: 'approve', kind: 'commit' },
							{ id: 'reject', label: 'reject', kind: 'reject' },
							{ id: 'defer', label: 'defer', kind: 'defer' }
						]}
						onaction={(id) => fireToast(id === 'approve' ? 'act' : 'info')}
						{lang}
					>
						<p class="small">Rule: speeding on a segment. Sighting emulated.</p>
						{#snippet evidence()}
							<p class="small muted">Mark {PLATE_2} · source emulated ANPR · window 09:42–10:00</p>
						{/snippet}
					</DecisionCard>
					<DecisionCard
						kind="corridor-request"
						title="108 · cardiac · BKC"
						deadline="golden hour 00:14"
						namedActor="Sandbox officer"
						actions={[
							{ id: 'approve', label: 'approve window', kind: 'commit' },
							{ id: 'defer', label: 'defer', kind: 'defer' }
						]}
						onaction={() => fireToast('act')}
						{lang}
					/>
				</div>

				<div class="legacy-block">
					<div class="caption">EventDossier</div>
					<EventDossier event={{ eventId: 'EV-DEMO-0001', name: 'Visarjan corridor', band: 'AMBER', state: 'active' }} {lang}>
						{#snippet meta()}<p class="small muted">Procession · crowd extreme · spine Bandra–Worli Sea Link</p>{/snippet}
						{#snippet phases()}<p class="small muted">Planned 05:30 → active 07:10 → complete</p>{/snippet}
						{#snippet audit()}
							<FeedItem ts={NOW - 60000} actor="operator" actorKind="human" level="decision" text="Corridor opened for the procession" {lang} />
						{/snippet}
						{#snippet advisory()}<p class="small muted">EN / हिंदी / मराठी: one fact, three languages</p>{/snippet}
					</EventDossier>
				</div>

				<div class="legacy-block">
					<div class="caption">Modal and toasts (feedback, never refusals)</div>
					<div class="row wrap">
						<Button small onclick={() => (modalOpen = true)} data-design-legacy="modal">Open evidence modal</Button>
						<Button small onclick={() => fireToast('info')} data-design-legacy="toast-info">Toast · info</Button>
						<Button small onclick={() => fireToast('act')} data-design-legacy="toast-act">Toast · act</Button>
						<Button small onclick={() => fireToast('error')} data-design-legacy="toast-error">Toast · error</Button>
					</div>
					<Modal open={modalOpen} title="Evidence · {PLATE_2}" onClose={() => (modalOpen = false)}>
						<p class="small">Rule: speeding on a segment · 112 km/h · limit 60 · source emulated ANPR</p>
						<p class="small muted">{t(lang, 'veil_close')}.</p>
					</Modal>
				</div>
			</div>
		</section>
	</div>
</div>

<style>
	.gallery {
		display: grid;
		flex: 0 0 auto;
		grid-template-columns: 184px minmax(0, 1fr);
		min-height: 100%;
		background: var(--v-canvas);
		color: var(--v-ink-1);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	@media (max-width: 1499px) {
		.gallery {
			grid-template-columns: minmax(0, 1fr);
		}

		.toc {
			display: none;
		}
	}

	/* ── table of contents ── */
	.toc {
		position: sticky;
		top: 0;
		align-self: start;
		max-height: 100vh;
		padding: 16px 8px 16px 16px;
		overflow: auto;
		border-right: 1px solid var(--v-line-1);
	}

	.toc-title {
		padding: 0 8px 8px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
	}

	.toc ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.toc-link {
		display: block;
		padding: 4px 8px;
		border-radius: var(--v-radius-btn);
		color: var(--v-ink-2);
		font-size: var(--v-text-base);
		text-decoration: none;
	}

	.toc-link:hover {
		background: var(--v-minimal-hover);
		color: var(--v-ink-1);
	}

	.toc-link.is-selected {
		color: var(--v-ink-1);
	}

	/* ── content ── */
	.content {
		display: flex;
		flex-direction: column;
		gap: 32px;
		min-width: 0;
		padding: 20px 24px 64px;
	}

	.page-head {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		padding-bottom: 16px;
		border-bottom: 1px solid var(--v-line-2);
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}

	.sec {
		display: flex;
		flex-direction: column;
		gap: 12px;
		scroll-margin-top: 16px;
	}

	.sec-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 4px 12px;
	}

	.sec-head h2 {
		margin: 0;
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
	}

	.sec-sub {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
	}

	.specimens {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.specimens.single {
		grid-template-columns: minmax(0, 1fr);
	}

	.specimen {
		position: relative;
		min-width: 0;
		padding: 36px 16px 16px;
		border-radius: var(--v-radius-panel);
		background: var(--v-canvas);
		color: var(--v-ink-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.sp-label {
		position: absolute;
		top: 10px;
		left: 16px;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
	}

	/* ── helpers ── */
	.stack {
		display: flex;
		flex-direction: column;
		gap: 12px;
		min-width: 0;
	}

	.stack.tight {
		gap: 4px;
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.row.top-align {
		align-items: flex-start;
	}

	.grow {
		flex: 1 1 auto;
	}

	.small {
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.muted {
		color: var(--v-ink-2);
	}

	.h6 {
		font-weight: 600;
	}

	.caption {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		font-weight: 600;
		line-height: 16px;
	}

	.caption.top {
		margin-top: 12px;
	}

	.framed {
		min-width: 0;
		overflow: hidden;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.pad {
		padding: 12px 16px;
	}

	.tn {
		font-variant-numeric: tabular-nums;
	}

	.unit {
		color: var(--v-ink-2);
	}

	.body-text {
		margin: 0 0 12px;
	}

	/* ── foundations ── */
	.swatch-groups {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 16px;
	}

	.sw-group {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.swatches {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 4px 8px;
	}

	.swatch {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		font-size: var(--v-text-xs);
	}

	.chip {
		width: 20px;
		height: 20px;
		flex: 0 0 auto;
		border-radius: var(--v-radius-chip);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.chip.black {
		background: var(--v-band-black-fill);
		box-shadow: inset 0 0 0 1px var(--v-band-black-hairline);
	}

	.flow-rows {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: var(--v-text-xs);
	}

	.flow-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.flow {
		flex: 0 0 auto;
		border-radius: var(--v-radius-chip);
		background: var(--v-surface-sink);
	}

	.flow line {
		stroke-linecap: round;
	}

	.flow .casing {
		stroke: var(--v-map-casing);
	}

	.type-scale {
		display: flex;
		flex-direction: column;
		margin-top: 16px;
		border-top: 1px solid var(--v-line-1);
	}

	.ts-row {
		display: grid;
		grid-template-columns: 128px minmax(0, 1fr) auto;
		align-items: baseline;
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--v-line-1);
	}

	.ts-role,
	.ts-spec {
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		white-space: nowrap;
	}

	.ts-h5 {
		font-size: var(--v-text-md);
		font-weight: 600;
		line-height: calc(var(--v-text-md) + 4px);
	}

	.ts-h6 {
		font-size: var(--v-text-base);
		font-weight: 600;
		line-height: calc(var(--v-text-base) + 2px);
	}

	.ts-body {
		font-size: var(--v-text-base);
		line-height: calc(var(--v-text-base) + 4px);
	}

	.ts-run {
		font-size: var(--v-text-base);
		line-height: 1.5;
	}

	.ts-small {
		font-size: var(--v-text-xs);
		line-height: calc(var(--v-text-xs) + 4px);
	}

	.ts-metric {
		font-size: var(--v-text-xl);
		font-weight: 600;
		line-height: calc(var(--v-text-xl) + 6px);
		font-variant-numeric: tabular-nums;
	}

	.elevations {
		display: flex;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 16px;
	}

	.elev {
		display: flex;
		align-items: flex-end;
		width: 72px;
		height: 48px;
		padding: 4px 8px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		color: var(--v-ink-2);
	}

	/* ── icons ── */
	/* a map is at least 300 px, so its two columns hold the longest single
	   word ("recommendation") in either theme without breaking it */
	.icon-maps {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
		gap: 16px;
		margin-bottom: 12px;
	}

	.icon-map {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.icon-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 4px 8px;
	}

	/* the reference must read in full: a long name wraps under itself, the
	   glyph stays on the first line */
	.icon-cell,
	.glyph-cell {
		display: inline-flex;
		align-items: flex-start;
		gap: 8px;
		min-width: 0;
		color: var(--v-ink-1);
	}

	.icon-cell :global([data-ui='icon']),
	.glyph-cell :global([data-ui='icon']) {
		flex: 0 0 auto;
	}

	.ic-name {
		min-width: 0;
		color: var(--v-ink-2);
		font-size: var(--v-text-xs);
		line-height: 16px;
		overflow-wrap: anywhere;
	}

	.all-icons {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 8px 12px;
		padding: 12px 16px 16px;
	}

	/* ── formatter ── */
	.mini {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--v-text-xs);
	}

	.mini th {
		padding: 4px 8px 4px 0;
		border-bottom: 1px solid var(--v-line-2);
		color: var(--v-ink-2);
		font-weight: 400;
		text-align: left;
	}

	.mini td {
		padding: 4px 8px 4px 0;
		border-bottom: 1px solid var(--v-line-1);
	}

	/* ── forms ── */
	.form-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 4px 16px;
		align-items: start;
	}

	.eye-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		max-width: 240px;
		font-size: var(--v-text-base);
	}

	.eye-row.dimmed > span:first-child {
		color: var(--v-ink-disabled);
	}

	/* ── navigation ── */
	.nav-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 12px;
		align-items: start;
	}

	.menu-box {
		background: var(--v-surface-2);
	}

	/* ── data ── */
	.metrics {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
	}

	.metrics > :global(* + *) {
		box-shadow: inset 1px 0 0 var(--v-line-1);
	}

	.table-box {
		max-height: 360px;
		overflow: auto;
	}

	.detail {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 16px 12px 36px;
	}

	/* ── buttons ── */
	/* a decision card's footer: the evidence action, then Reject or Dismiss, then the one primary */
	.decision-row {
		max-width: 480px;
		padding: 8px 12px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-1);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	/* ── overlays ── */
	.pop-body {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 8px;
		width: 240px;
		padding: 12px;
	}

	.toast-box {
		padding: 12px;
		border-radius: var(--v-radius-panel);
		background: var(--v-surface-sink);
	}

	/* ── layout ── */
	.split-demo {
		display: flex;
		height: 160px;
	}

	.pane {
		display: flex;
		flex-direction: column;
		min-width: 0;
		background: var(--v-surface-1);
	}

	.pane.grow {
		flex: 1 1 auto;
		background: var(--v-surface-sink);
	}

	.pane-head {
		display: flex;
		align-items: center;
		height: 40px;
		padding: 0 16px;
		border-bottom: 1px solid var(--v-line-2);
		font-weight: 600;
	}

	/* ── legacy ── */
	.legacy-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	@media (max-width: 1279px) {
		.legacy-grid,
		.specimens {
			grid-template-columns: minmax(0, 1fr);
		}
	}

	.legacy-block {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
		padding: 16px;
		border-radius: var(--v-radius-panel);
		box-shadow: inset 0 0 0 1px var(--v-line-1);
	}

	.legacy-block.wide {
		grid-column: 1 / -1;
	}

	.row.wrap {
		flex-wrap: wrap;
	}

	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 8px;
	}

	.feed {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
</style>
