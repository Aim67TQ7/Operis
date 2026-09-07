import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

export const escape = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function settings(env) {
  const enabled = env.SEO_INDEXABLE === 'true';
  const site = new URL(env.SITE_URL || 'https://operis-staging.netlify.app');
  if (site.protocol !== 'https:' || site.pathname !== '/' || site.search || site.hash || site.username || site.password) throw new Error('SITE_URL must be an HTTPS origin');
  if (enabled && (!env.SITE_URL || /localhost|staging|preview|--/.test(site.hostname) || (env.CONTEXT && env.CONTEXT !== 'production'))) throw new Error('Indexing requires a confirmed public SITE_URL and production context');
  // A Netlify preview must never index, even if it inherits production variables.
  if (enabled && env.URL && new URL(env.URL).origin !== site.origin) throw new Error('SITE_URL must match the Netlify primary URL');
  return { origin: site.origin, enabled };
}
export async function build(env = process.env, out = resolve('dist')) {
  const {origin, enabled} = settings(env);
  const data = JSON.parse(await readFile('content/pages.json', 'utf8'));
  const slugs = new Set();
  for (const p of data) {
    if (!/^\/resources\/(?:[a-z0-9-]+\/)*$/.test(p.path) || slugs.has(p.path)) throw new Error('Invalid or duplicate content path');
    if (!p.title || !p.description || !p.h1 || !p.sections?.length) throw new Error('Incomplete page');
    if (p.kind === 'article' && (!p.date || !['draft','published'].includes(p.status))) throw new Error('Article needs date and status');
    for (const s of p.sources || []) if (new URL(s.url).protocol !== 'https:') throw new Error('Sources must use HTTPS');
    slugs.add(p.path);
  }
  const published = p => p.kind !== 'article' || (p.status === 'published' && p.date <= new Date().toISOString().slice(0,10));
  const nav = '<a href="/resources/">OPERIS <small>FIELD NOTES</small></a><nav aria-label="Main"><a href="/resources/epicor/">Epicor</a><a href="/resources/syteline/">SyteLine</a><a href="/resources/on-premises-erp/">On-premises</a><a href="/resources/blog/">Journal</a><a href="/">Workspace</a></nav>';
  const page = (p) => {
    const index = enabled && published(p);
    const article = p.kind === 'article';
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${escape(p.title)}</title><meta name="description" content="${escape(p.description)}"><meta name="robots" content="${index?'index, follow':'noindex, follow'}"><link rel="canonical" href="${origin}${p.path}"><meta property="og:title" content="${escape(p.title)}"><meta property="og:description" content="${escape(p.description)}"><meta property="og:url" content="${origin}${p.path}"><meta property="og:type" content="${article?'article':'website'}"><meta property="og:site_name" content="OPERIS"><meta name="twitter:card" content="summary"><link rel="stylesheet" href="/resources/content.css"><link rel="alternate" type="application/rss+xml" title="OPERIS Journal" href="/resources/feed.xml"></head><body><a class="skip" href="#main">Skip to content</a><header>${nav}</header><main id="main"><div class="crumb"><a href="/resources/">Resources</a> / ${escape(p.label)}</div><article ${article?'itemscope itemtype="https://schema.org/BlogPosting"':''}><p class="eyebrow">${escape(p.label)}</p><h1 ${article?'itemprop="headline"':''}>${escape(p.h1)}</h1><p class="intro" ${article?'itemprop="description"':''}>${escape(p.description)}</p>${article?`<p class="byline">By <span itemprop="author" itemscope itemtype="https://schema.org/Organization"><span itemprop="name">OPERIS</span></span> · ${published(p)?`<time itemprop="datePublished" datetime="${p.date}">${p.date}</time>`:`Draft prepared ${escape(p.date)} · Editorial review pending`}</p>`:''}<div ${article?'itemprop="articleBody"':''}>${p.sections.map(s=>`<section><h2>${escape(s.heading)}</h2>${(s.paragraphs||[]).map(t=>`<p>${escape(t)}</p>`).join('')}${s.items?`<ul>${s.items.map(i=>`<li>${escape(i)}</li>`).join('')}</ul>`:''}</section>`).join('')}</div>${p.kind==='hub'?`<div class="grid">${data.filter(x=>x.path!==p.path && (p.path.endsWith('/blog/') ? x.kind==='article' : x.kind!=='article') && (!enabled || published(x))).map(x=>`<a class="card" href="${x.path}"><h2>${escape(x.h1)}</h2><p>${escape(x.description)}</p></a>`).join('')}</div>`:''}${p.sources?.length?`<section><h2>Sources and further reading</h2><ul>${p.sources.map(s=>`<li><a href="${escape(s.url)}">${escape(s.label)}</a></li>`).join('')}</ul><p class="byline">Sources checked September 6, 2026. Verify current vendor guidance for your version and agreement.</p></section>`:''}</article><aside class="cta"><h2>Start with what you can verify.</h2><p>Use the readiness checklist to document your ERP, access boundaries, and first workflow.</p><a class="button" href="/resources/discovery-readiness/">Review discovery readiness →</a></aside></main><footer><p>OPERIS · An intelligence layer for existing business systems.</p><p>Epicor and Infor product names belong to their respective owners. OPERIS is independent; no vendor affiliation or certification is implied.</p><a href="/resources/">All resources</a></footer></body></html>`;
  };
  await mkdir(out, {recursive:true});
  for (const p of data) {
    const dest = resolve(out, '.'+p.path, 'index.html');
    await mkdir(dirname(dest), {recursive:true});
    await writeFile(dest, page(p));
  }
  await copyFile('content/content.css', resolve(out,'resources/content.css'));
  await writeFile(resolve(out,'404.html'), '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Page not found | OPERIS</title><meta name="robots" content="noindex"><link rel="stylesheet" href="/resources/content.css"></head><body><main><h1>Page not found</h1><p><a href="/resources/">Explore OPERIS resources</a></p></main></body></html>');
  const discoverable = enabled ? data.filter(published) : [];
  await writeFile(resolve(out,'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${discoverable.map(p=>`<url><loc>${origin}${p.path}</loc></url>`).join('')}</urlset>`);
  await writeFile(resolve(out,'robots.txt'), `User-agent: *\nAllow: /\n${enabled?`Sitemap: ${origin}/sitemap.xml\n`:''}`);
  // Crawlers may fetch pages to see noindex; robots.txt is not access control.
  await writeFile(resolve(out,'_headers'), enabled ? '/404.html\n  X-Robots-Tag: noindex\n' : '/*\n  X-Robots-Tag: noindex\n');
  await writeFile(resolve(out,'resources/feed.xml'), `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>OPERIS Journal</title><link>${origin}/resources/blog/</link><description>Practical ERP discovery and control.</description>${discoverable.filter(p=>p.kind==='article').map(p=>`<item><title>${escape(p.h1)}</title><link>${origin}${p.path}</link><guid>${origin}${p.path}</guid><pubDate>${new Date(p.date).toUTCString()}</pubDate><description>${escape(p.description)}</description></item>`).join('')}</channel></rss>`);
  console.log(`Built ${data.length} resource pages; ${discoverable.length} sitemap entries; indexing ${enabled?'enabled':'disabled'}`);
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) await build();
