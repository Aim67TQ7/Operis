-- Approved ZODA staging only. All synthetic fixtures and capability changes roll back.
-- No Auth users created, no email sent, no ERP access, no customer data returned.
begin;
set local lock_timeout='5s';
set local statement_timeout='30s';
do $$
declare
  users uuid[]; actor uuid; viewer uuid; target uuid:=gen_random_uuid(); outside uuid:=gen_random_uuid();
  company uuid:=gen_random_uuid(); other_company uuid:=gen_random_uuid(); scan uuid:=gen_random_uuid();
  payload jsonb; first_result jsonb; result jsonb; run uuid; pilot uuid; n int; denied boolean;
  test_key text:='rollback-only-discovery-capability-xxxxxxxxxxxxxxxxxxxxxxxxxxxx';
begin
  select array_agg(id) into users from (select id from auth.users where email_confirmed_at is not null and not coalesce(is_anonymous,false) order by id limit 2) u;
  if coalesce(array_length(users,1),0)<2 then raise exception 'Two existing verified identities are required'; end if;
  actor:=users[1]; viewer:=users[2];
  update operis_private.discovery_ingest_config set key_sha256=encode(sha256(convert_to(test_key,'UTF8')),'hex') where singleton;
  if not found then raise exception 'Discovery capability configuration missing'; end if;
  insert into public.operis_tenants(id,name) values(target,'Discovery rollback QA'),(outside,'Discovery rollback outsider');
  insert into public.operis_companies(id,tenant_id,code,name) values(company,target,'TEST','Discovery rollback company'),(other_company,outside,'OTHER','Discovery rollback other');
  insert into public.operis_memberships(tenant_id,user_id,role) values(target,actor,'admin'),(target,viewer,'viewer');
  payload:=jsonb_build_object('tenant_id',target,'company_id',company,'company_code','TEST','scan_id',scan,
    'package_sha256',repeat('a',64),'scanner_version','0.3.0','completed_at',now(),
    'summary',jsonb_build_object('preflight','ok','measurements','[]'::jsonb),
    'report',jsonb_build_object('findings',jsonb_build_array(jsonb_build_object('category','gap','subject','Synthetic coverage gap','evidence','Offline fixture','rationale','Unknown')),'recommendations','[]'::jsonb,'limitations',jsonb_build_array('Rollback test')));
  perform set_config('request.jwt.claim.sub',actor::text,true);
  perform set_config('request.headers',jsonb_build_object('x-operis-ingest-key',test_key,'x-request-id','discovery-rollback')::text,true);
  execute 'set local role authenticated';
  first_result:=public.operis_commit_discovery(payload); run:=(first_result->>'id')::uuid;
  result:=public.operis_commit_discovery(payload);
  if result->>'id'<>run::text or not (result->>'duplicate')::boolean then raise exception 'Idempotency failed'; end if;
  select count(*) into n from public.operis_audit_events where record_id=run::text and actor_id=actor and request_id='discovery-rollback';
  if n<>1 then raise exception 'Atomic run audit failed'; end if;
  select count(*) into n from public.operis_discovery_findings where run_id=run and tenant_id=target;
  if n<>1 then raise exception 'Findings persistence failed'; end if;
  denied:=false;
  begin perform public.operis_commit_discovery(payload||jsonb_build_object('package_sha256',repeat('b',64)));
  exception when unique_violation then denied:=true; end;
  if not denied then raise exception 'Different bytes replaced saved scan'; end if;
  denied:=false;
  begin perform public.operis_commit_discovery(payload||jsonb_build_object('company_id',other_company));
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Cross-company commit accepted'; end if;
  denied:=false;
  begin update public.operis_discovery_runs set summary='{}'::jsonb where id=run;
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Direct browser mutation accepted'; end if;
  result:=public.operis_request_discovery_pilot(target,run); pilot:=(result->>'id')::uuid;
  result:=public.operis_request_discovery_pilot(target,run);
  if result->>'id'<>pilot::text then raise exception 'Duplicate pilot request'; end if;
  select count(*) into n from public.operis_audit_events where record_id=pilot::text and actor_id=actor;
  if n<>1 then raise exception 'Pilot audit failed'; end if;
  perform set_config('request.headers','{}',true);
  denied:=false;
  begin perform public.operis_commit_discovery(payload);
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Missing backend capability accepted'; end if;
  perform set_config('request.headers',jsonb_build_object('x-operis-ingest-key',test_key)::text,true);
  perform set_config('request.jwt.claim.sub',viewer::text,true);
  denied:=false;
  begin perform public.operis_commit_discovery(payload);
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Viewer ingestion accepted'; end if;
  denied:=false;
  begin perform public.operis_request_discovery_pilot(target,run);
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Viewer pilot accepted'; end if;
  execute 'reset role';
  delete from public.operis_memberships where tenant_id=target and user_id=viewer;
  execute 'set local role authenticated';
  select count(*) into n from public.operis_discovery_runs where id=run;
  if n<>0 then raise exception 'Membership removal did not hide report'; end if;
  select count(*) into n from public.operis_discovery_pilots where id=pilot;
  if n<>0 then raise exception 'Outsider can read pilot'; end if;
  execute 'reset role';
  perform set_config('request.jwt.claim.sub','',true);
  execute 'set local role anon';
  denied:=false;
  begin perform public.operis_commit_discovery(payload);
  exception when insufficient_privilege then denied:=true; end;
  if not denied then raise exception 'Anonymous RPC accepted'; end if;
  execute 'reset role';
end $$;
rollback;
select 'Discovery live database boundaries passed; all fixtures and test settings rolled back' as result;
