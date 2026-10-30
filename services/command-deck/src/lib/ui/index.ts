/**
 * src/lib/ui — the Sajag primitive library (SPEC §5.1), Blueprint 6 based.
 *
 * Svelte 5 runes; styled only with var(--v-*); `...rest` on the root (or on
 * the native control for form fields); snippets for slots; no primitive
 * imports a store. One active-state rule: `.is-pressed` for controls,
 * `.is-selected` for data. Internal copy comes from i18n/packs.ui.ts in the
 * language provided by provideUiLang() (or a `lang` prop).
 *
 * This folder imports nothing from $lib/ops, $lib/gods-eye or
 * $lib/workspace (tests/design-tokens.mjs, rule R4).
 */
export { default as Alert } from './Alert.svelte';
export { default as Breadcrumbs } from './Breadcrumbs.svelte';
export { default as Button } from './Button.svelte';
export { default as ButtonGroup } from './ButtonGroup.svelte';
export { default as Callout } from './Callout.svelte';
export { default as Card } from './Card.svelte';
export { default as CardList } from './CardList.svelte';
export { default as Checkbox } from './Checkbox.svelte';
export { default as CompoundTag } from './CompoundTag.svelte';
export { default as DataTable } from './DataTable.svelte';
export { default as Dialog } from './Dialog.svelte';
export { default as Drawer } from './Drawer.svelte';
export { default as EntityTitle } from './EntityTitle.svelte';
export { default as EyeToggle } from './EyeToggle.svelte';
export { default as FormGroup } from './FormGroup.svelte';
export { default as HotkeysDialog } from './HotkeysDialog.svelte';
export { default as HTMLSelect } from './HTMLSelect.svelte';
export { default as Icon } from './Icon.svelte';
export { default as Input } from './Input.svelte';
export { default as Kbd } from './Kbd.svelte';
export { default as Menu } from './Menu.svelte';
export { default as MetricCard } from './MetricCard.svelte';
export { default as NonIdealState } from './NonIdealState.svelte';
export { default as Note } from './Note.svelte';
export { default as ObjectTag } from './ObjectTag.svelte';
export { default as Popover } from './Popover.svelte';
export { default as ProgressBar } from './ProgressBar.svelte';
export { default as PropertyTable } from './PropertyTable.svelte';
export { default as ProvenanceTag } from './ProvenanceTag.svelte';
export { default as Reason } from './Reason.svelte';
export { default as Section } from './Section.svelte';
export { default as SegmentedControl } from './SegmentedControl.svelte';
export { default as Skeleton } from './Skeleton.svelte';
export { default as Spinner } from './Spinner.svelte';
export { default as Splitter } from './Splitter.svelte';
export { default as Switch } from './Switch.svelte';
export { default as Tabs } from './Tabs.svelte';
export { default as Tag } from './Tag.svelte';
export { default as TimeField } from './TimeField.svelte';
export { default as Toaster } from './Toaster.svelte';
export { default as Tooltip } from './Tooltip.svelte';
export { default as Tree } from './Tree.svelte';

export { Coord, Id, Plate, Time, TimeRange } from './format';
export * from './format/format';
export { provideUiLang, uiLang, ut } from './lang';
export { openLayerCount, placeFloating, pushLayer } from './overlay';
export type * from './types';

/** Every primitive's data-ui name (the /design gallery and design-smoke assert each one mounts). */
export const UI_PRIMITIVES = [
	'icon',
	'button',
	'button-group',
	'segmented-control',
	'tag',
	'compound-tag',
	'provenance-tag',
	'object-tag',
	'id',
	'plate',
	'time',
	'time-range',
	'coord',
	'note',
	'reason',
	'callout',
	'eye-toggle',
	'input',
	'form-group',
	'html-select',
	'time-field',
	'switch',
	'checkbox',
	'tabs',
	'tree',
	'section',
	'card',
	'card-list',
	'menu',
	'popover',
	'tooltip',
	'dialog',
	'alert',
	'drawer',
	'toaster',
	'data-table',
	'property-table',
	'metric-card',
	'entity-title',
	'breadcrumbs',
	'non-ideal-state',
	'spinner',
	'skeleton',
	'progress-bar',
	'splitter',
	'hotkeys-dialog',
	'kbd'
] as const;
