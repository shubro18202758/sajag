/**
 * /welcome — the reader's language for the server render (the sajag_lang cookie, read by the same pure parser the
 * browser and hooks.server.ts use). With no choice made it speaks English (the product's default everywhere);
 * मराठी and हिंदी are one press away and the choice is remembered.
 * Nothing else is loaded: the page is static.
 */
import type { PageServerLoad } from './$types';
import { langFromCookieHeader } from '$lib/i18n/lang-cookie';

export const load: PageServerLoad = ({ request }) => ({
	lang: langFromCookieHeader(request.headers.get('cookie')) ?? 'en',
});
