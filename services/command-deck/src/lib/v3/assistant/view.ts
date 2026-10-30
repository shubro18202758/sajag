/**
 * The V3 Assistant's view models — what one turn shows, built from the shared ChatSession's message and the
 * deck's stores by the page (AssistantPage), rendered by BotTurn / Thread / ContextPanel. Plain data only.
 */
import type { InsetVM, ThumbVM } from '../home/view';
import type { Segment } from './model';

export interface StepVM {
	label: string;
	state: 'pending' | 'running' | 'success' | 'error';
	simulated: boolean;
	summary: string | null;
}

export interface ProposalVM {
	key: string;
	kind: 'decision' | 'map';
	thumb: ThumbVM | null;
	/** V3-P7: the vehicle class's shot or the kind's key art over the map's corner. */
	inset?: InsetVM;
	tag: string;
	ai: boolean;
	timer: string | null;
	title: string;
	why: string;
	openHref: string | null;
	/** What "Show on map" selects (null: the map proposal itself waits on /map). */
	urn: string | null;
}

export interface CautionVM {
	key: string;
	text: string;
}

export interface TurnVM {
	id: number;
	role: 'user' | 'agent';
	/** The user's words, or the answer's prose split around cited objects. */
	text: string;
	segments: Segment[];
	at: string;
	working: boolean;
	steps: StepVM[];
	lookups: string | null;
	stepsSummary: string;
	noProse: boolean;
	error: string | null;
	grounding: string | null;
	cautions: CautionVM[];
	proposals: ProposalVM[];
}

export interface ContextItem {
	urn: string;
	label: string;
	meta: string;
	art: string;
	decide: boolean;
}
