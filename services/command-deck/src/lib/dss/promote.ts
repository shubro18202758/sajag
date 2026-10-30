/**
 * The officer-gated Promote action (plan X22, contract C-T) for OSINT
 * reports: turn an open-source report into a corridor event, keeping its
 * verification state, recorded with the officer's name. The action itself
 * never POSTs — it opens the confirmation Alert the inspector section hosts
 * (the dialog carries the kind, the kept label and the audit warning); the
 * writer fires only from that dialog's confirm. Hidden once
 * promoted_event_id is set (the section links the event instead); disabled
 * with its reason until a duty officer is named. A 409 comes back inline,
 * verbatim.
 */
import { ops } from '$lib/ops/store.svelte';
import { commandBar } from '$lib/shell/command-bar.svelte';
import { ACTION_ICON } from '$lib/design/icons';
import { t, kindLabel } from '$lib/i18n/strings';
import '$lib/i18n/packs.dss';
import { promoteOsintEvent } from '$lib/ops/client';
import { dssState } from '$lib/dss/dss-store.svelte';
import { verificationLabel } from '$lib/decisions/cards/meta';
import type { ObjectAction, ObjectRow } from '$lib/workspace/types';

/** The console's officer (the page's navbar control when it supplies one, else the ops store's). */
export function promoteOfficer(): string {
	return (commandBar.officer ? commandBar.officer.value : ops.dutyOfficer).trim();
}

/** The C-T promote verb for a report: the sajag kind when the oracle named one, else omitted (it derives). */
export function promoteKind(row: ObjectRow): string | undefined {
	const kind = row.props['sajag_event_kind'];
	if (typeof kind !== 'string' || kind === 'crime_incident' || kind === 'vehicle_pursuit') return undefined;
	return kind;
}

/** The Promote action (id `dss.promote`). Empty once promoted — the section links the event. */
export function promoteActions(row: ObjectRow): readonly ObjectAction[] {
	if (row.kind !== 'osint_event') return [];
	const promoted = row.props['promoted_event_id'];
	if (typeof promoted === 'string' && promoted) return [];
	const lang = ops.lang;
	const officer = promoteOfficer();
	return [
		{
			id: 'dss.promote',
			label: t(lang, 'dss_promote_label'),
			icon: ACTION_ICON.promote,
			disabled: !officer,
			disabledReason: officer ? undefined : t(lang, 'dss_promote_reason_officer'),
			run: () => {
				dssState.promoteUrn = row.urn;
			},
		},
	];
}

/** The dialog's confirm: ONE promote POST; the refusal (verbatim) lands in `dssState.refusals`. */
export async function runPromote(row: ObjectRow, note: string): Promise<boolean> {
	const officer = promoteOfficer();
	if (!officer) return false;
	const res = await promoteOsintEvent(row.id, { note: note || undefined, eventKind: promoteKind(row) }, officer);
	if (!res.ok) {
		dssState.refusals[`promote:${row.urn}`] = { refusal: res.refusal ?? 'refused', detail: res.detail };
		return false;
	}
	dssState.promoteUrn = null;
	return true;
}

/** The dialog copy: the kind and the kept verification label (X2 wording). */
export function promoteDialogCopy(row: ObjectRow, lang: string): string {
	const kind = promoteKind(row);
	return t(lang, 'dss_promote_dialog', kind ? kindLabel(lang, kind) : t(lang, 'kind_unknown'), verificationLabel(row.verification, lang));
}
