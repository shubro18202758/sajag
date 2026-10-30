/**
 * A minimal DOM for `node tests/lib/queue.mjs --self-check` — enough of the
 * browser's element API to run the smokes' in-page helpers (the functions
 * they hand to page.evaluate) and their old-or-new selectors against markup
 * snippets in node, without a browser. Not a general HTML parser: it reads
 * the well-formed snippets the self-check carries (today's Svelte markup and
 * the redesign prototype's), nothing else.
 *
 *   const doc = parseHTML('<div data-testid="queue-card"><button>Approve</button></div>');
 *   doc.querySelector('[data-testid="queue-card"] button').textContent  // 'Approve'
 *
 * Selectors: comma lists; the descendant (' '), child ('>'), next-sibling
 * ('+') and sibling ('~') combinators; type, '*', #id, .class, [attr],
 * [attr=v], [attr~=v], [attr|=v], [attr^=v], [attr$=v], [attr*=v] (with an
 * optional ' i' flag); :not(list), :has(relative list), :scope,
 * :first-child, :last-child. Element API: tagName, localName, id,
 * className, classList.contains, dataset (read), attributes (get/has/set/
 * remove/toggle), hidden, children, firstElementChild, parentElement,
 * textContent (get/set), remove(), querySelector(All), matches, closest,
 * document.createElement, getClientRects (empty
 * inside a [hidden] subtree or under an inline display:none),
 * getBoundingClientRect (from the inline left/top/width/height px), click()
 * (runs the element's `onclick` hook, then bubbles to its ancestors').
 */

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);

class Node {
	constructor(type) {
		this.nodeType = type; // 1 element, 3 text, 9 document
		this.parentNode = null;
		this.childNodes = [];
	}
	appendChild(n) {
		n.parentNode = this;
		this.childNodes.push(n);
		return n;
	}
	get parentElement() {
		return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null;
	}
	get children() {
		return this.childNodes.filter((n) => n.nodeType === 1);
	}
	get firstElementChild() {
		return this.children[0] ?? null;
	}
	get textContent() {
		return this.childNodes.map((n) => (n.nodeType === 3 ? n.data : n.textContent)).join('');
	}
	set textContent(v) {
		for (const n of this.childNodes) n.parentNode = null;
		this.childNodes = [];
		if (v != null && v !== '') this.appendChild(new Text(String(v)));
	}
	remove() {
		const p = this.parentNode;
		if (!p) return;
		p.childNodes = p.childNodes.filter((n) => n !== this);
		this.parentNode = null;
	}
	querySelectorAll(sel) {
		const groups = parseSelector(sel);
		const out = [];
		const walk = (n) => {
			for (const c of n.children) {
				if (groups.some((g) => matchComplex(c, g, this))) out.push(c);
				walk(c);
			}
		};
		walk(this);
		return out;
	}
	querySelector(sel) {
		return this.querySelectorAll(sel)[0] ?? null;
	}
}

class Text extends Node {
	constructor(data) {
		super(3);
		this.data = data;
	}
}

class Element extends Node {
	constructor(tag, attrs) {
		super(1);
		this.localName = tag.toLowerCase();
		this.attrs = new Map(attrs);
		this.onclick = null;
	}
	get tagName() {
		return this.localName.toUpperCase();
	}
	getAttribute(n) {
		return this.attrs.has(n) ? this.attrs.get(n) : null;
	}
	hasAttribute(n) {
		return this.attrs.has(n);
	}
	setAttribute(n, v) {
		this.attrs.set(n, String(v));
	}
	removeAttribute(n) {
		this.attrs.delete(n);
	}
	toggleAttribute(n, force) {
		const on = force ?? !this.attrs.has(n);
		if (on) this.attrs.set(n, '');
		else this.attrs.delete(n);
		return on;
	}
	get id() {
		return this.getAttribute('id') ?? '';
	}
	get className() {
		return this.getAttribute('class') ?? '';
	}
	get classList() {
		const list = this.className.split(/\s+/).filter(Boolean);
		return { contains: (c) => list.includes(c), length: list.length, [Symbol.iterator]: () => list[Symbol.iterator]() };
	}
	get dataset() {
		const out = {};
		for (const [k, v] of this.attrs) {
			if (k.startsWith('data-')) out[k.slice(5).replace(/-([a-z])/g, (_m, c) => c.toUpperCase())] = v;
		}
		return out;
	}
	get hidden() {
		return this.attrs.has('hidden');
	}
	set hidden(v) {
		this.toggleAttribute('hidden', !!v);
	}
	get value() {
		return this.getAttribute('value') ?? '';
	}
	set value(v) {
		this.setAttribute('value', v);
	}
	matches(sel) {
		return parseSelector(sel).some((g) => matchComplex(this, g, null));
	}
	closest(sel) {
		for (let n = this; n && n.nodeType === 1; n = n.parentElement) if (n.matches(sel)) return n;
		return null;
	}
	/** Laid out unless it sits in a [hidden] subtree or under an inline display:none. */
	getClientRects() {
		for (let n = this; n && n.nodeType === 1; n = n.parentElement) {
			if (n.hasAttribute('hidden')) return [];
			if (/display\s*:\s*none/.test(n.getAttribute('style') ?? '')) return [];
		}
		return [{ width: 1, height: 1 }];
	}
	/**
	 * The element's box from its INLINE geometry — `left`, `top`, `width`,
	 * `height` in px, read as client coordinates (the self-check lays its
	 * snippets out absolutely); a zero box when it is not laid out
	 * (getClientRects) or carries no geometry.
	 */
	getBoundingClientRect() {
		const style = this.getClientRects().length ? (this.getAttribute('style') ?? '') : '';
		const px = (k) => {
			const m = new RegExp(`(?:^|;)\\s*${k}\\s*:\\s*(-?[\\d.]+)px`).exec(style);
			return m ? Number(m[1]) : 0;
		};
		const [left, top, width, height] = ['left', 'top', 'width', 'height'].map(px);
		return { x: left, y: top, left, top, right: left + width, bottom: top + height, width, height };
	}
	click() {
		for (let n = this; n && n.nodeType === 1; n = n.parentElement) if (typeof n.onclick === 'function') n.onclick.call(n, { target: this });
	}
}

class Document extends Node {
	constructor() {
		super(9);
	}
	createElement(tag) {
		return new Element(tag, []);
	}
	get body() {
		return this;
	}
	get documentElement() {
		return this.firstElementChild;
	}
}

/** Parse a snippet into a Document (attributes keep their raw text; entities &amp; &lt; &gt; &quot; &#39; decoded). */
export function parseHTML(html) {
	const doc = new Document();
	const stack = [doc];
	const top = () => stack[stack.length - 1];
	const decode = (s) => s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
	const re = /<!--[\s\S]*?-->|<\/([a-zA-Z][\w:-]*)\s*>|<([a-zA-Z][\w:-]*)((?:\s+[^\s"'>/=]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'>]+))?)*)\s*(\/?)>|([^<]+)/g;
	let m;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('<!--')) continue;
		if (m[1]) {
			const tag = m[1].toLowerCase();
			for (let i = stack.length - 1; i > 0; i--) {
				if (stack[i].localName === tag) {
					stack.length = i;
					break;
				}
			}
			continue;
		}
		if (m[2]) {
			const attrs = [];
			const ar = /([^\s"'>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;
			let a;
			while ((a = ar.exec(m[3] ?? ''))) attrs.push([a[1].toLowerCase(), decode(a[2] ?? a[3] ?? a[4] ?? '')]);
			const el = new Element(m[2], attrs);
			top().appendChild(el);
			if (!m[4] && !VOID.has(el.localName)) stack.push(el);
			continue;
		}
		if (m[5]) top().appendChild(new Text(decode(m[5])));
	}
	return doc;
}

// ─── selectors ──────────────────────────────────────────────────────────────

/** Split at top-level commas (outside brackets, parentheses and quotes). */
function splitTop(s, sep) {
	const out = [];
	let depth = 0;
	let quote = null;
	let cur = '';
	for (const ch of s) {
		if (quote) {
			cur += ch;
			if (ch === quote) quote = null;
			continue;
		}
		if (ch === '"' || ch === "'") quote = ch;
		else if (ch === '(' || ch === '[') depth++;
		else if (ch === ')' || ch === ']') depth--;
		if (ch === sep && depth === 0) {
			out.push(cur);
			cur = '';
			continue;
		}
		cur += ch;
	}
	out.push(cur);
	return out.map((x) => x.trim()).filter((x) => x.length);
}

const cache = new Map();
/** sel → [complex] where complex = [{combinator, compound}] read right to left. */
export function parseSelector(sel) {
	if (cache.has(sel)) return cache.get(sel);
	const groups = splitTop(sel, ',').map(parseComplex);
	cache.set(sel, groups);
	return groups;
}

function parseComplex(s) {
	const parts = [];
	let i = 0;
	let comb = null;
	while (i < s.length) {
		if (/\s/.test(s[i])) {
			while (i < s.length && /\s/.test(s[i])) i++;
			if (comb == null && parts.length && !'>+~'.includes(s[i] ?? '')) comb = ' ';
			continue;
		}
		if ('>+~'.includes(s[i])) {
			comb = s[i];
			i++;
			continue;
		}
		let j = i;
		let depth = 0;
		let quote = null;
		while (j < s.length) {
			const ch = s[j];
			if (quote) {
				if (ch === quote) quote = null;
			} else if (ch === '"' || ch === "'") quote = ch;
			else if (ch === '(' || ch === '[') depth++;
			else if (ch === ')' || ch === ']') depth--;
			else if (depth === 0 && (/\s/.test(ch) || '>+~'.includes(ch))) break;
			j++;
		}
		parts.push({ comb: parts.length ? comb ?? ' ' : null, compound: parseCompound(s.slice(i, j)) });
		comb = null;
		i = j;
	}
	return parts;
}

function parseCompound(s) {
	const out = { tag: null, ids: [], classes: [], attrs: [], pseudos: [] };
	let i = 0;
	const ident = () => {
		const m = /^-?[_a-zA-Z0-9\u00a0-\uffff-]+/.exec(s.slice(i));
		if (!m) throw new Error(`minidom: cannot parse selector '${s}' at ${i}`);
		i += m[0].length;
		return m[0];
	};
	if (s[i] === '*') i++;
	else if (/[a-zA-Z]/.test(s[i] ?? '')) out.tag = ident().toLowerCase();
	while (i < s.length) {
		const ch = s[i];
		if (ch === '#') {
			i++;
			out.ids.push(ident());
		} else if (ch === '.') {
			i++;
			out.classes.push(ident());
		} else if (ch === '[') {
			const end = findClose(s, i, '[', ']');
			const body = s.slice(i + 1, end).trim();
			const m = /^([^\s~|^$*!=]+)\s*(?:([~|^$*]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))\s*(i)?)?$/.exec(body);
			if (!m) throw new Error(`minidom: cannot parse attribute selector [${body}]`);
			out.attrs.push({ name: m[1].toLowerCase(), op: m[2] ?? null, value: m[3] ?? m[4] ?? m[5] ?? null, ci: !!m[6] });
			i = end + 1;
		} else if (ch === ':') {
			i++;
			const name = ident();
			let arg = null;
			if (s[i] === '(') {
				const end = findClose(s, i, '(', ')');
				arg = s.slice(i + 1, end);
				i = end + 1;
			}
			out.pseudos.push({ name, arg });
		} else throw new Error(`minidom: unexpected '${ch}' in selector '${s}'`);
	}
	return out;
}

function findClose(s, from, open, close) {
	let depth = 0;
	let quote = null;
	for (let i = from; i < s.length; i++) {
		const ch = s[i];
		if (quote) {
			if (ch === quote) quote = null;
			continue;
		}
		if (ch === '"' || ch === "'") quote = ch;
		else if (ch === open) depth++;
		else if (ch === close && --depth === 0) return i;
	}
	throw new Error(`minidom: unbalanced '${open}' in '${s}'`);
}

function attrMatch(el, a) {
	if (!el.hasAttribute(a.name)) return false;
	if (a.op == null) return true;
	let v = el.getAttribute(a.name);
	let want = a.value ?? '';
	if (a.ci) {
		v = v.toLowerCase();
		want = want.toLowerCase();
	}
	switch (a.op) {
		case '=':
			return v === want;
		case '~=':
			return v.split(/\s+/).includes(want);
		case '|=':
			return v === want || v.startsWith(`${want}-`);
		case '^=':
			return want !== '' && v.startsWith(want);
		case '$=':
			return want !== '' && v.endsWith(want);
		case '*=':
			return want !== '' && v.includes(want);
		default:
			return false;
	}
}

function siblingsBefore(el) {
	const p = el.parentNode;
	if (!p) return [];
	const kids = p.children;
	return kids.slice(0, kids.indexOf(el));
}

function matchCompound(el, c, scope) {
	if (el.nodeType !== 1) return false;
	if (c.tag && el.localName !== c.tag) return false;
	if (c.ids.some((id) => el.id !== id)) return false;
	if (c.classes.some((k) => !el.classList.contains(k))) return false;
	if (c.attrs.some((a) => !attrMatch(el, a))) return false;
	for (const p of c.pseudos) {
		if (p.name === 'not') {
			if (parseSelector(p.arg).some((g) => matchComplex(el, g, scope))) return false;
		} else if (p.name === 'has') {
			// relative selectors (simple right-hand side): a leading combinator
			// binds to the element (children / next / later siblings), else descendants
			const ok = splitTop(p.arg, ',').some((rel) => {
				const r = rel.trim();
				const lead = '>+~'.includes(r[0]) ? r[0] : ' ';
				const groups = parseSelector(lead === ' ' ? r : r.slice(1).trim());
				const sibs = el.parentNode ? el.parentNode.children : [];
				const at = sibs.indexOf(el);
				const pool =
					lead === ' ' ? el.querySelectorAll('*') : lead === '>' ? el.children : lead === '+' ? sibs.slice(at + 1, at + 2) : sibs.slice(at + 1);
				return pool.some((x) => groups.some((g) => matchComplex(x, g, el)));
			});
			if (!ok) return false;
		} else if (p.name === 'scope') {
			if (scope ? el !== scope : el.parentNode?.nodeType !== 9) return false;
		} else if (p.name === 'first-child') {
			if (siblingsBefore(el).length !== 0) return false;
		} else if (p.name === 'last-child') {
			const kids = el.parentNode?.children ?? [];
			if (kids.at(-1) !== el) return false;
		} else throw new Error(`minidom: unsupported pseudo-class :${p.name}`);
	}
	return true;
}

/** Right-to-left match of one complex selector; `scope` bounds :scope and relative :has. */
function matchComplex(el, parts, scope) {
	const step = (node, k) => {
		if (!matchCompound(node, parts[k].compound, scope)) return false;
		if (k === 0) return true;
		const comb = parts[k].comb;
		if (comb === '>') return !!node.parentElement && step(node.parentElement, k - 1);
		if (comb === ' ') {
			for (let a = node.parentElement; a; a = a.parentElement) if (step(a, k - 1)) return true;
			return false;
		}
		const before = siblingsBefore(node);
		if (comb === '+') return before.length > 0 && step(before.at(-1), k - 1);
		return before.some((b) => step(b, k - 1));
	};
	return step(el, parts.length - 1);
}
