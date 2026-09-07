import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

// Real PostgreSQL policy/trigger execution in WebAssembly. The auth schema below
// stands in only for Supabase's auth.uid() and user records; no network / live data.
const db = new PGlite();
const a = "10000000-0000-0000-0000-000000000001",
  b = "10000000-0000-0000-0000-000000000002";
const admin = "20000000-0000-0000-0000-000000000001",
  outsider = "20000000-0000-0000-0000-000000000002",
  viewer = "20000000-0000-0000-0000-000000000003";
const companyB = "30000000-0000-0000-0000-000000000002";
before(async () => {
  await db.exec(`create role anon; create role authenticated; create schema auth;
    create table auth.users(id uuid primary key);
    create function auth.uid() returns uuid language sql stable as $$
      select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
    grant usage on schema auth to authenticated,anon;
    grant execute on function auth.uid() to authenticated,anon;`);
  await db.exec(
    await readFile(new URL("../schema.sql", import.meta.url), "utf8"),
  );
  await db.exec(`insert into auth.users values ('${admin}'),('${outsider}'),('${viewer}');
    insert into public.operis_tenants(id,name) values ('${a}','Tenant A'),('${b}','Tenant B');
    insert into public.operis_memberships(tenant_id,user_id,role) values
      ('${a}','${admin}','admin'),('${a}','${viewer}','viewer'),('${b}','${outsider}','admin');
    insert into public.operis_companies(id,tenant_id,code,name) values ('${companyB}','${b}','B','Company B');`);
});
after(async () => db.close());

async function asUser(id, run, role = "authenticated") {
  await db.exec("begin");
  try {
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [id]);
    await db.exec(`set local role ${role}`);
    return await run();
  } finally {
    await db.exec("rollback");
  }
}

test("member only sees own tenant and memberships", async () =>
  asUser(admin, async () => {
    assert.deepEqual((await db.query("select id from operis_tenants")).rows, [
      { id: a },
    ]);
    assert.equal(
      (await db.query("select * from operis_memberships")).rows.length,
      2,
    );
    assert.equal(
      (await db.query("select * from operis_companies")).rows.length,
      0,
    );
  }));
test("anonymous role sees zero tenants", async () =>
  asUser(
    "",
    async () => {
      assert.equal(
        (await db.query("select * from operis_tenants")).rows.length,
        0,
      );
    },
    "anon",
  ));
test("authenticated role without identity has no access", async () =>
  asUser("", async () => {
    assert.equal(
      (await db.query("select * from operis_tenants")).rows.length,
      0,
    );
  }));
test("administrator creates own company with atomic audit evidence", async () =>
  asUser(admin, async () => {
    await db.query("select set_config('request.headers',$1,true)", [
      JSON.stringify({ "x-request-id": "test-request" }),
    ]);
    const company = (
      await db.query(
        "insert into operis_companies(tenant_id,code,name) values ($1,'A','Company A') returning id",
        [a],
      )
    ).rows[0];
    const event = (
      await db.query("select * from operis_audit_events where record_id=$1", [
        company.id,
      ])
    ).rows[0];
    assert.equal(event.tenant_id, a);
    assert.equal(event.actor_id, admin);
    assert.equal(event.action, "INSERT");
    assert.equal(event.before, null);
    assert.equal(event.after.name, "Company A");
    assert.equal(event.request_id, "test-request");
  }));
test("administrator cannot insert into another tenant", async () => {
  await assert.rejects(
    asUser(admin, () =>
      db.query(
        "insert into operis_companies(tenant_id,code,name) values ($1,'X','Wrong tenant')",
        [b],
      ),
    ),
    /row-level security/,
  );
});
test("viewer cannot create companies", async () => {
  await assert.rejects(
    asUser(viewer, () =>
      db.query(
        "insert into operis_companies(tenant_id,code,name) values ($1,'X','Wrong role')",
        [a],
      ),
    ),
    /row-level security/,
  );
});
test("viewer cannot rename tenant", async () =>
  asUser(viewer, async () => {
    assert.equal(
      (
        await db.query(
          "update operis_tenants set name='Changed' where id=$1 returning id",
          [a],
        )
      ).rows.length,
      0,
    );
  }));
test("administrator rename records before and after", async () =>
  asUser(admin, async () => {
    await db.query(
      "update operis_tenants set name='Renamed tenant' where id=$1",
      [a],
    );
    const event = (
      await db.query(
        "select * from operis_audit_events where action='UPDATE' and record_id=$1",
        [a],
      )
    ).rows[0];
    assert.equal(event.before.name, "Tenant A");
    assert.equal(event.after.name, "Renamed tenant");
  }));
test("company/site relationship cannot cross tenants", async () => {
  await assert.rejects(
    asUser(admin, () =>
      db.query(
        "insert into operis_sites(tenant_id,company_id,code,name) values ($1,$2,'X','Cross tenant')",
        [a, companyB],
      ),
    ),
    /foreign key/,
  );
});
test("audit evidence cannot be forged by a tenant administrator", async () => {
  await assert.rejects(
    asUser(admin, () =>
      db.query(
        "insert into operis_audit_events(tenant_id,action,table_name,record_id) values ($1,'INSERT','fake','fake')",
        [a],
      ),
    ),
    /permission denied/,
  );
});
test("audit evidence cannot be edited or deleted", async () => {
  for (const sql of [
    "update operis_audit_events set action='DELETE'",
    "delete from operis_audit_events",
  ]) {
    await assert.rejects(
      asUser(admin, () => db.exec(sql)),
      /permission denied/,
    );
  }
});
test("membership cannot be self-elevated", async () => {
  await assert.rejects(
    asUser(viewer, () => db.exec("update operis_memberships set role='admin'")),
    /permission denied/,
  );
});
test("tenant identifiers are immutable for the authenticated role", async () => {
  await assert.rejects(
    asUser(admin, () =>
      db.query("update operis_tenants set id=$1 where id=$2", [b, a]),
    ),
    /permission denied/,
  );
});
test("audit reads remain tenant scoped", async () =>
  asUser(admin, async () => {
    assert.ok(
      (await db.query("select tenant_id from operis_audit_events")).rows.every(
        (row) => row.tenant_id === a,
      ),
    );
  }));
test("removing membership immediately removes access", async () => {
  await db.exec("begin");
  try {
    await db.query("delete from operis_memberships where user_id=$1", [admin]);
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [
      admin,
    ]);
    await db.exec("set local role authenticated");
    assert.equal(
      (await db.query("select * from operis_tenants")).rows.length,
      0,
    );
  } finally {
    await db.exec("rollback");
  }
});

// Commit writes, then read in a separate authenticated transaction. This is
// persisted PostgreSQL evidence, unlike a mock response or same-transaction echo.
test("company and site persist with complete actor and request audit evidence", async () => {
  let company, site;
  await db.exec("begin");
  try {
    await db.query("select set_config('request.jwt.claim.sub',$1,true)", [
      admin,
    ]);
    await db.exec("set local role authenticated");
    await db.query("select set_config('request.headers',$1,true)", [
      JSON.stringify({ "x-request-id": "persist-company" }),
    ]);
    company = (
      await db.query(
        "insert into operis_companies(tenant_id,code,name) values ($1,'PERSIST','Persisted company') returning *",
        [a],
      )
    ).rows[0];
    await db.query("select set_config('request.headers',$1,true)", [
      JSON.stringify({ "x-request-id": "persist-site" }),
    ]);
    site = (
      await db.query(
        "insert into operis_sites(tenant_id,company_id,code,name) values ($1,$2,'PERSIST','Persisted site') returning *",
        [a, company.id],
      )
    ).rows[0];
    await db.exec("commit");
  } catch (error) {
    await db.exec("rollback");
    throw error;
  }
  await asUser(admin, async () => {
    for (const [table, row, request] of [
      ["operis_companies", company, "persist-company"],
      ["operis_sites", site, "persist-site"],
    ]) {
      assert.deepEqual(
        (await db.query(`select * from ${table} where id=$1`, [row.id])).rows,
        [row],
      );
      const events = (
        await db.query("select * from operis_audit_events where record_id=$1", [
          row.id,
        ])
      ).rows;
      assert.equal(events.length, 1);
      const event = events[0];
      assert.equal(event.tenant_id, a);
      assert.equal(event.actor_id, admin);
      assert.equal(event.action, "INSERT");
      assert.equal(event.table_name, table);
      assert.equal(event.before, null);
      assert.deepEqual(
        {
          ...event.after,
          created_at: new Date(event.after.created_at).toISOString(),
        },
        JSON.parse(JSON.stringify(row)),
      );
      assert.equal(event.request_id, request);
      assert.ok(event.created_at);
    }
  });
  await asUser(outsider, async () => {
    assert.equal(
      (await db.query("select * from operis_sites where id=$1", [site.id])).rows
        .length,
      0,
    );
    assert.equal(
      (
        await db.query("select * from operis_audit_events where record_id=$1", [
          site.id,
        ])
      ).rows.length,
      0,
    );
  });
});

test("viewer cannot create sites or leave audit evidence for rejected writes", async () => {
  const before = (await db.query("select count(*) from operis_audit_events"))
    .rows;
  await assert.rejects(
    asUser(viewer, () =>
      db.query(
        "insert into operis_sites(tenant_id,company_id,code,name) values ($1,$2,'DENIED','Denied site')",
        [a, companyB],
      ),
    ),
    /row-level security/,
  );
  assert.deepEqual(
    (await db.query("select count(*) from operis_audit_events")).rows,
    before,
  );
});
