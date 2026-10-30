/**
 * The ProposalCard bodies by decision kind (plan X9): the kind-specific
 * "Why", rule note and evidence of each card. The ProposalCard and the /ops
 * Decisions items render a unit's body through this map; a kind added later
 * (the DSS's `dss`, OS-DECK-B) adds its body here. The escort body is also
 * exported for UI-S6A's ConvoyCard.
 *
 * Every body takes `{unit}` (plus an optional `part`: 'why' | 'evidence',
 * `lang` and `now`, the host card's clock, so a countdown in the body
 * ticks with the card).
 */
import type { Component } from 'svelte';
import type { Unit } from '../units';
import StolenBody from './StolenBody.svelte';
import PursuitBody from './PursuitBody.svelte';
import EchallanBody from './EchallanBody.svelte';
import EscortBody from './EscortBody.svelte';
import CorridorBody from './CorridorBody.svelte';
import DssProposalBody from '$lib/dss/DssProposalBody.svelte';

/**
 * `now` (epoch ms) is the host card's clock; a body without one reads the
 * shell's 1 Hz clock. `reason` is the footer's reason field (a body whose
 * own verb needs the officer's note reads it — the dss Defer,
 * FIX-E-DSSCARD); bodies without one ignore it.
 */
/** Provenance a host already states in its own header (each tag reads ONCE per card). */
export type HostProvenance = { simulated?: boolean; gps?: boolean };
export const NO_HOST_PROVENANCE: HostProvenance = Object.freeze({});
export type CardBodyProps = { unit: Unit; part?: 'why' | 'evidence'; lang?: string; now?: number | null; reason?: string; hostProvenance?: HostProvenance };

export const CARD_BODIES: Record<string, Component<CardBodyProps>> = {
	'stolen-sighting': StolenBody as Component<CardBodyProps>,
	pursuit: PursuitBody as Component<CardBodyProps>,
	echallan: EchallanBody as Component<CardBodyProps>,
	'escort-proposal': EscortBody as Component<CardBodyProps>,
	'corridor-request': CorridorBody as Component<CardBodyProps>,
	// plan X22: the COA review body (the radios, the blocked best response, the why, the provenance)
	dss: DssProposalBody as Component<CardBodyProps>,
};

export { StolenBody, PursuitBody, EchallanBody, EscortBody, CorridorBody, DssProposalBody };
