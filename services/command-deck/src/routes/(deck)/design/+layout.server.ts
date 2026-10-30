/**
 * The /design/** harness pages are developer surfaces: fictional fixture data
 * (masked demo marks, fixture officers) rendered inside the real navbar and
 * LiveStrip. They never ship to an operator (F-07): a production server
 * answers 404 for every /design route — server render AND client navigation
 * (the route's data request runs this load too) — unless the server was
 * started with SAJAG_DESIGN_HARNESS=1, which the smokes and the private
 * gate-off preview of scripts/verify_all.sh set. `vite dev` always serves
 * them (dev is true there).
 */
import { error } from '@sveltejs/kit';
import { dev } from '$app/environment';
import { env } from '$env/dynamic/private';
import { designHarnessOn } from '$lib/shell/design-harness';

export const load = () => {
	if (!designHarnessOn(dev, env.SAJAG_DESIGN_HARNESS)) error(404, 'Not found');
	return {};
};
