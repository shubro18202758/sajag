/**
 * The shell's glyphs, named once (SPEC §4.2): every one comes from a frozen
 * map in $lib/design/icons where the map has the meaning, so the navbar, the
 * LiveStrip and the popovers draw the same glyph for the same thing as every
 * other surface (the glyph lint forbids kind glyphs as literals).
 */
import {
	ACTION_ICON,
	ACTOR_ICON,
	MODULE_ICON,
	PROVENANCE_ICON,
	eventKindIcon,
	kindIcon,
	type IconName
} from '$lib/design/icons';

/** The product mark (the City module's globe). */
export const MARK_ICON: IconName = MODULE_ICON.city;
/** The band tag's key glyph (the Situation module: the city's posture). */
export const DASHBOARD_ICON: IconName = MODULE_ICON.situation;
export const SIMULATED_ICON: IconName = PROVENANCE_ICON.simulated;
export const EMULATED_ICON: IconName = PROVENANCE_ICON.emulated;
export const DATA_ICON: IconName = 'data-connection';
export const POLICIES_ICON: IconName = ACTION_ICON.policies;
export const INBOX_ICON: IconName = ACTION_ICON.inbox;
export const OFFICER_ICON: IconName = ACTOR_ICON.officer;
export const MASKED_ICON: IconName = ACTION_ICON.masked;
export const SYSTEM_ICON: IconName = ACTOR_ICON.system;
export const NO_FINE_ICON: IconName = ACTION_ICON.rule_no_fine;
export const PURSUIT_ICON: IconName = eventKindIcon('vehicle_pursuit');
/** A decision unit (the soonest decision on the LiveStrip). */
export const DECISION_ICON: IconName = kindIcon('recommendation');
export const MORE_ICON: IconName = 'more';
export const SEARCH_ICON: IconName = 'search';
export const SHORTCUTS_ICON: IconName = 'key-command';
/** The public views (Citizen, Driver): their alerts. Not `globe`, the OSINT provenance glyph (X1/X2). */
export const PUBLIC_ICON: IconName = 'notifications';
export const LANGUAGE_ICON: IconName = 'translate';
export const SHARE_ICON: IconName = 'share';
export const HISTORY_ICON: IconName = 'history';
export const FEED_LOSS_ICON: IconName = 'offline';
export const DESIGN_ICON: IconName = 'applications';
export const CLEAR_ICON: IconName = 'small-cross';
export const MENU_ICON: IconName = 'menu';
