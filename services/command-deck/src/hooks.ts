/**
 * Universal hooks (server and browser). The V3 root flip (V3-SPEC §3.2, §10 P5): `/` shows Home and
 * `/analyst` shows the v2 workspace page. A reroute, not a file move — the workspace keeps its route node,
 * `data-template="convoy-command"`, its test ids and its operator (Cesium) CSP and gate, which
 * hooks.server.ts reads from the RESOLVED route id; only the URL changes. `/home` keeps answering.
 * The table lives in $lib/shell/root-flip.ts (tests/root-flip.unit.mjs holds it).
 */
import type { Reroute } from '@sveltejs/kit';
import { reroutePath } from './lib/shell/root-flip';

export const reroute: Reroute = ({ url }) => reroutePath(url.pathname);
