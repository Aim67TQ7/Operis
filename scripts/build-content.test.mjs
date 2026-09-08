import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, readFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {settings, build, escape} from './build-content.mjs';

test('production opt-in refuses staging and preview origins', () => {
  assert.equal(settings({}).enabled, false);
  for (const env of [
    {SEO_INDEXABLE:'true'},
    {SEO_INDEXABLE:'true', SITE_URL:'https://operis-staging.netlify.app'},
    {SEO_INDEXABLE:'true', SITE_URL:'https://example.com', CONTEXT:'deploy-preview'},
    {SEO_INDEXABLE:'true', SITE_URL:'https://example.com', URL:'https://other.example.com'},
    {SITE_URL:'https://example.com/other/'},
  ]) assert.throws(()=>settings(env));
  assert.equal(escape('<script>"&'), '&lt;script&gt;&quot;&amp;');
});
test('static content is readable without JS and drafts never enter sitemap or feed', async () => {
  const out=await mkdtemp(join(tmpdir(),'operis-seo-'));
  try {
    await build({},out);
    assert.match(await readFile(join(out,'_headers'),'utf8'), /X-Robots-Tag: noindex/);
    assert.doesNotMatch(await readFile(join(out,'sitemap.xml'),'utf8'), /<url>/);
    await build({SEO_INDEXABLE:'true',SITE_URL:'https://example.com'},out);
    const html=await readFile(join(out,'resources/epicor/index.html'),'utf8');
    assert.match(html, /<h1[^>]*>Understand your Epicor/);
    assert.match(html, /href="\/resources\/discovery-readiness\/">Review discovery readiness/);
    assert.doesNotMatch(html, /<form|contact|lead capture|downloadable customer scanner/i);
    assert.match(html, /content="index, follow"/);
    assert.doesNotMatch(html, /<script/);
    const syteline=await readFile(join(out,'resources/syteline/index.html'),'utf8');
    assert.match(syteline, /Infor SyteLine and CloudSuite Industrial/);
    assert.match(syteline, /not a compatibility certification/);
    const sitemap=await readFile(join(out,'sitemap.xml'),'utf8');
    assert.match(sitemap,/https:\/\/example.com\/resources\/epicor\//);
    assert.doesNotMatch(sitemap,/dependency-inventory/);
    assert.doesNotMatch(await readFile(join(out,'resources/feed.xml'),'utf8'),/<item>/);
    const draft=await readFile(join(out,'resources/blog/epicor-on-premises-dependency-inventory/index.html'),'utf8');
    assert.match(draft,/noindex, follow/);
    assert.match(draft,/Editorial review pending/);
    assert.doesNotMatch(await readFile(join(out,'resources/blog/index.html'),'utf8'),/dependency-inventory/);
  } finally {await rm(out,{recursive:true,force:true});}
});
