-- Runs only against an approved project with the Operis foundation installed.
-- Uses two existing verified users; creates no Auth users and sends no email.
-- All test tenant/company/membership/audit records roll back in this transaction.
begin;
set local lock_timeout = '5s';
set local statement_timeout = '20s';
do $$
declare
  users uuid[]; actor uuid; viewer uuid;
  tenant_a uuid := gen_random_uuid(); tenant_b uuid := gen_random_uuid();
  company_a uuid; company_b uuid; denied boolean; actual integer;
begin
  select array_agg(id) into users from (
    select id from auth.users where email_confirmed_at is not null
      and not coalesce(is_anonymous,false) order by id limit 2
  ) verified;
  if coalesce(array_length(users,1),0) < 2 then
    raise exception 'Live test requires two existing verified users; no users were created';
  end if;
  actor := users[1]; viewer := users[2];
  insert into public.operis_tenants(id,name) values (tenant_a,'Operis rollback test A'),(tenant_b,'Operis rollback test B');
  insert into public.operis_memberships(tenant_id,user_id,role) values
    (tenant_a,actor,'admin'),(tenant_a,viewer,'viewer'),(tenant_b,viewer,'admin');
  insert into public.operis_companies(tenant_id,code,name) values (tenant_b,'TEST-B','Rollback test B') returning id into company_b;

  perform set_config('request.jwt.claim.sub',actor::text,true);
  perform set_config('request.jwt.claims',jsonb_build_object('sub',actor,'role','authenticated')::text,true);
  execute 'set local role authenticated';
  select count(*) into actual from public.operis_tenants where id in (tenant_a,tenant_b);
  if actual <> 1 then raise exception 'Tenant isolation failed'; end if;
  insert into public.operis_companies(tenant_id,code,name) values (tenant_a,'TEST-A','Rollback test A') returning id into company_a;
  select count(*) into actual from public.operis_audit_events where record_id=company_a::text and actor_id=actor;
  if actual <> 1 then raise exception 'Atomic actor audit failed'; end if;

  denied := false;
  begin
    insert into public.operis_companies(tenant_id,code,name) values (tenant_b,'DENIED','Denied cross-tenant company');
  exception when insufficient_privilege then denied := true;
  end;
  if not denied then raise exception 'Cross-tenant insert unexpectedly succeeded'; end if;
  denied := false;
  begin
    insert into public.operis_sites(tenant_id,company_id,code,name) values (tenant_a,company_b,'DENIED','Denied cross-tenant site');
  exception when foreign_key_violation then denied := true;
  end;
  if not denied then raise exception 'Cross-tenant company relation unexpectedly succeeded'; end if;
  denied := false;
  begin
    update public.operis_audit_events set action='DELETE' where tenant_id=tenant_a;
  exception when insufficient_privilege then denied := true;
  end;
  if not denied then raise exception 'Audit edit unexpectedly succeeded'; end if;

  execute 'reset role';
  perform set_config('request.jwt.claim.sub',viewer::text,true);
  perform set_config('request.jwt.claims',jsonb_build_object('sub',viewer,'role','authenticated')::text,true);
  execute 'set local role authenticated';
  denied := false;
  begin
    insert into public.operis_companies(tenant_id,code,name) values (tenant_a,'DENIED','Denied viewer company');
  exception when insufficient_privilege then denied := true;
  end;
  if not denied then raise exception 'Viewer write unexpectedly succeeded'; end if;
  denied := false;
  begin
    update public.operis_memberships set role='admin' where tenant_id=tenant_a and user_id=viewer;
  exception when insufficient_privilege then denied := true;
  end;
  if not denied then raise exception 'Self-escalation unexpectedly succeeded'; end if;
  execute 'reset role';
  perform set_config('request.jwt.claim.sub','',true);
  perform set_config('request.jwt.claims','{}',true);
  execute 'set local role anon';
  select count(*) into actual from public.operis_tenants;
  if actual <> 0 then raise exception 'Anonymous tenant visibility failed'; end if;
  execute 'reset role';
end;
$$;
rollback;
select 'Eight live access/audit checks passed; all test changes rolled back' as result;
