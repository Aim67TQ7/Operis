import { before, after, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { PGlite } from "@electric-sql/pglite";
const db = new PGlite();
const tenant = "10000000-0000-0000-0000-000000000001",
  other = "10000000-0000-0000-0000-000000000002";
const admin = "20000000-0000-0000-0000-000000000001",
  viewer = "20000000-0000-0000-0000-000000000002";
const company = "30000000-0000-0000-0000-000000000001",
  otherCompany = "30000000-0000-0000-0000-000000000002";
const scan = "40000000-0000-0000-0000-000000000001";
const key = "offline-only-capability-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";
const hash = createHash("sha256").update(key).digest("hex");
const payload = {
  tenant_id: tenant,
  company_id: company,
  company_code: "TEST",
  scan_id: scan,
  package_sha256: "a".repeat(64),
  scanner_version: "0.3.0",
  completed_at: "2026-09-07T10:00:00Z",
  summary: { preflight: "ok", measurements: [] },
  report: {
    coverage: { measured: 0, attempted: 11 },
    findings: [
      {
        category: "gap",
        subject: "Unknown coverage",
        evidence: "Offline test",
        score: 0,
        rationale: "Unknown is not healthy",
      },
    ],
    recommendations: [],
    limitations: ["Offline test"],
  },
};
before(async () => {
  await db.exec(
    `create role anon; create role authenticated; create schema auth; create table auth.users(id uuid primary key); create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$; grant usage on schema auth to authenticated,anon; grant execute on function auth.uid() to authenticated,anon;`,
  );
  for (const file of [
    "../schema.sql",
    "../discovery-foundation.sql",
    "../migrations/20260907111341_discovery_ingestion.sql",
  ])
    await db.exec(await readFile(new URL(file, import.meta.url), "utf8"));
  await db.exec(
    `insert into auth.users values('${admin}'),('${viewer}'); insert into public.operis_tenants(id,name) values('${tenant}','Test tenant'),('${other}','Other tenant'); insert into public.operis_memberships(tenant_id,user_id,role) values('${tenant}','${admin}','admin'),('${tenant}','${viewer}','viewer'); insert into public.operis_companies(id,tenant_id,code,name) values('${company}','${tenant}','TEST','Test company'),('${otherCompany}','${other}','OTHER','Other company');`,
  );
  await db.query(
    "insert into operis_private.discovery_ingest_config(key_sha256) values($1)",
    [hash],
  );
});
after(() => db.close());
async function asUser(
  user,
  run,
  { capability = key, role = "authenticated" } = {},
) {
  await db.exec("begin");
  try {
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [
      user,
    ]);
    await db.query("select set_config('request.headers',$1,true)", [
      JSON.stringify({
        "x-operis-ingest-key": capability,
        "x-request-id": "discovery-offline",
      }),
    ]);
    await db.exec(`set local role ${role}`);
    return await run();
  } finally {
    await db.exec("rollback");
  }
}
async function commit(p = payload) {
  return (
    await db.query("select public.operis_commit_discovery($1) as result", [p])
  ).rows[0].result;
}
test("backend validated ingestion is atomic, idempotent and audited", () =>
  asUser(admin, async () => {
    const first = await commit();
    assert.equal(first.duplicate, false);
    const repeat = await commit();
    assert.equal(repeat.duplicate, true);
    assert.equal(repeat.id, first.id);
    assert.equal(
      (await db.query("select count(*)::int as n from operis_discovery_runs"))
        .rows[0].n,
      1,
    );
    const audit = (
      await db.query("select * from operis_audit_events where record_id=$1", [
        first.id,
      ])
    ).rows;
    assert.equal(audit.length, 1);
    assert.equal(audit[0].actor_id, admin);
    assert.equal(audit[0].request_id, "discovery-offline");
    assert.equal(
      (
        await db.query(
          "select count(*)::int as n from operis_discovery_findings",
        )
      ).rows[0].n,
      1,
    );
  }));
test("browser cannot forge normalized reports through exposed RPC", async () => {
  for (const capability of ["", "wrong-capability"])
    await assert.rejects(
      asUser(admin, () => commit(), { capability }),
      /Validated ingestion required/,
    );
});
test("viewer cannot ingest even with backend capability", async () => {
  await assert.rejects(
    asUser(viewer, () => commit()),
    /Discovery write access required/,
  );
});
test("membership and company ownership enforced independently", async () => {
  await assert.rejects(
    asUser(admin, () =>
      commit({
        ...payload,
        tenant_id: other,
        company_id: otherCompany,
        company_code: "OTHER",
      }),
    ),
    /Discovery write access required/,
  );
  await assert.rejects(
    asUser(admin, () => commit({ ...payload, company_id: otherCompany })),
    /Company binding rejected/,
  );
  await assert.rejects(
    asUser(admin, () => commit({ ...payload, company_code: "MISMATCH" })),
    /Company binding rejected/,
  );
});
test("different bytes under same scan rejected without replacing original", () =>
  asUser(admin, async () => {
    await commit();
    await db.exec("savepoint retry");
    await assert.rejects(
      commit({ ...payload, package_sha256: "b".repeat(64) }),
      /different content/,
    );
    await db.exec("rollback to savepoint retry");
    assert.equal(
      (await db.query("select package_sha256 from operis_discovery_runs"))
        .rows[0].package_sha256,
      "a".repeat(64),
    );
  }));
test("direct writes and private capability reads are denied", async () => {
  for (const sql of [
    "select * from operis_private.discovery_ingest_config",
    "update operis_discovery_runs set status='complete'",
    "delete from operis_discovery_runs",
    "update operis_discovery_findings set score=5",
    "update operis_module_recommendations set fit_score=100",
    "insert into operis_discovery_runs(tenant_id) values(null)",
    "update operis_discovery_pilots set status='closed'",
  ]) {
    await assert.rejects(
      asUser(admin, () => db.exec(sql)),
      /permission denied/,
    );
  }
});
test("pilot request persists once with actor audit and rejects cross-tenant calls", () =>
  asUser(admin, async () => {
    const run = await commit();
    const call = () =>
      db.query(
        "select public.operis_request_discovery_pilot($1,$2) as result",
        [tenant, run.id],
      );
    const first = (await call()).rows[0].result,
      second = (await call()).rows[0].result;
    assert.equal(first.id, second.id);
    assert.equal(first.requested_by, admin);
    assert.equal(
      (
        await db.query(
          "select count(*)::int as n from operis_audit_events where record_id=$1",
          [first.id],
        )
      ).rows[0].n,
      1,
    );
    await db.exec("savepoint scope_check");
    await assert.rejects(
      db.query("select public.operis_request_discovery_pilot($1,$2)", [
        other,
        run.id,
      ]),
      /Discovery write access required/,
    );
    await db.exec("rollback to savepoint scope_check");
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [
      viewer,
    ]);
    await assert.rejects(call(), /Discovery write access required/);
  }));
test("anonymous cannot call either RPC", async () => {
  await assert.rejects(
    asUser("", () => commit(), { role: "anon" }),
    /permission denied/,
  );
  await assert.rejects(
    asUser(
      "",
      () =>
        db.query("select public.operis_request_discovery_pilot($1,$2)", [
          tenant,
          scan,
        ]),
      { role: "anon" },
    ),
    /permission denied/,
  );
});
test("persisted report is invisible after membership removal and to outsiders", async () => {
  await db.exec("begin");
  try {
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [
      admin,
    ]);
    await db.query("select set_config('request.headers',$1,true)", [
      JSON.stringify({ "x-operis-ingest-key": key }),
    ]);
    await db.exec("set local role authenticated");
    await commit();
    await db.exec("reset role");
    await db.query("delete from public.operis_memberships where user_id=$1", [
      admin,
    ]);
    await db.exec("set local role authenticated");
    assert.equal(
      (await db.query("select * from operis_discovery_runs")).rows.length,
      0,
    );
    assert.equal(
      (await db.query("select * from operis_discovery_findings")).rows.length,
      0,
    );
    await assert.rejects(commit(), /Discovery write access required/);
  } finally {
    await db.exec("rollback");
  }
});
