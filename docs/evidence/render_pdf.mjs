// Render the evidence HTML to an A4 PDF.
//   node docs/evidence/render_pdf.mjs [in.html] [out.pdf]
// Defaults: docs/evidence/evidence.html -> docs/evidence/Sajag_Evidence.pdf.
// Puppeteer is resolved from PUPPETEER_FROM (a package.json whose node_modules holds puppeteer) or ../../frontend.
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
const require = createRequire(process.env.PUPPETEER_FROM ?? new URL('../../frontend/package.json', import.meta.url));
const puppeteer = require('puppeteer');
const here = fileURLToPath(new URL('.', import.meta.url));
const input = resolve(process.argv[2] ?? resolve(here, 'evidence.html'));
const output = resolve(process.argv[3] ?? resolve(here, 'Sajag_Evidence.pdf'));
const browser = await puppeteer.launch({ headless: 'new', executablePath: process.env.CHROME ?? `${process.env.HOME}/.cache/puppeteer/chrome/linux_arm-153.0.8010.36/chrome-linux-arm64/chrome`, args: ['--no-sandbox', '--allow-file-access-from-files'] });
const page = await browser.newPage();
await page.goto(pathToFileURL(input).href, { waitUntil: 'networkidle0' });
await page.pdf({ path: output, format: 'A4', printBackground: true, preferCSSPageSize: true });
await browser.close();
console.log('wrote', output);
