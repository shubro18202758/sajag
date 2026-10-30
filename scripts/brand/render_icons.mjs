/**
 * Raster icons from the brand SVGs (static/brand): the PWA icons, the Apple touch icon, the legacy favicon.png, and the
 * PNG exports for documents and decks (the mark at 512 px on transparent, the horizontal lockup at 2× on transparent).
 * Needs a headless Chrome through puppeteer (PUPPETEER_FROM: a folder whose node_modules holds puppeteer; CHROME: the
 * browser binary). Deterministic for one Chrome build.
 *   PUPPETEER_FROM=… CHROME=… node scripts/brand/render_icons.mjs
 */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATIC = path.resolve(HERE, '../../services/command-deck/static');
const require = createRequire(path.join(process.env.PUPPETEER_FROM ?? path.resolve(HERE, '../../frontend'), 'package.json'));
const puppeteer = require('puppeteer');
const CHROME = process.env.CHROME ?? `${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`;

// [source svg, output png, size (or [w, h]), full-bleed tile colour (maskable icons need a full square) or null]
const JOBS = [
	['brand/favicon.svg', 'favicon.png', 32, null],
	['brand/sajag-app-icon.svg', 'brand/icon-192.png', 192, null],
	['brand/sajag-app-icon.svg', 'brand/icon-512.png', 512, null],
	['brand/sajag-mark.svg', 'brand/icon-maskable-512.png', 512, '#000000'],
	['brand/sajag-mark.svg', 'brand/apple-touch-icon.png', 180, '#000000'],
	['brand/sajag-mark.svg', 'brand/sajag-mark-512.png', 512, null],
	['brand/sajag-lockup.svg', 'brand/sajag-lockup.png', 'lockup', null],
	['brand/sajag-lockup-day.svg', 'brand/sajag-lockup-day.png', 'lockup', null],
];

const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox'] });
try {
	const page = await browser.newPage();
	for (const [src, out, sz, tile] of JOBS) {
		const svg = readFileSync(path.join(STATIC, src), 'utf8');
		if (sz === 'lockup') {
			// a lockup at 2× its own height (128 px), its width from the SVG's viewBox
			const vb = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
			const h = 128;
			const w = Math.ceil((Number(vb[1]) / Number(vb[2])) * h);
			await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 });
			await page.setContent(`<html><body style="margin:0;background:transparent"><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="width:${w}px;height:${h}px;display:block"></body></html>`);
			await page.screenshot({ path: path.join(STATIC, out), omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
			console.log('ok', out);
			continue;
		}
		const size = sz;
		// a maskable icon keeps its art inside the central 80 % safe zone, on a full-bleed tile
		const inner = tile ? `<div style="width:${size}px;height:${size}px;background:${tile};display:grid;place-items:center"><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="width:${size * 0.62}px;height:${size * 0.62}px"></div>`
			: `<img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="width:${size}px;height:${size}px;display:block">`;
		await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 });
		await page.setContent(`<html><body style="margin:0;background:transparent">${inner}</body></html>`);
		await page.screenshot({ path: path.join(STATIC, out), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
		console.log('ok', out);
	}
} finally {
	await browser.close();
}
