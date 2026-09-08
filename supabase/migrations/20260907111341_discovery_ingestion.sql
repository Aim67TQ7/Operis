-- Incremental, Operis-only hardening. Legacy discovery tables must already exist.
-- Never reapply the foundation to the shared ZODA project.
set local lock_timeout = '5s';
set local statement_timeout = '30s';

create table operis_private.discovery_ingest_config (
  singleton boolean primary key default true check (singleton),
  key_sha256 text not null check (key_sha256 ~ '^[a-f0-9]{64}$')
);
alter table operis_private.discovery_ingest_config enable row level security;
revoke all on operis_private.discovery_ingest_config from public, anon, authenticated;

-- RLS protects reads. Mutations are only via the bounded RPC below, with verified
-- user identity AND a backend-only capability header. No service-role key exists
-- in the application. Caller-supplied findings cannot bypass server validation.
revoke all on public.operis_discovery_runs, public.operis_discovery_findings,
  public.operis_module_recommendations from public, anon, authenticated;
grant select on public.operis_discovery_runs, public.operis_discovery_findings,
  public.operis_module_recommendations to authenticated;
drop policy if exists discovery_runs_insert on public.operis_discovery_runs;
drop policy if exists discovery_runs_update on public.operis_discovery_runs;
drop policy if exists discovery_findings_update on public.operis_discovery_findings;
drop policy if exists module_recommendations_update on public.operis_module_recommendations;

alter table public.operis_discovery_runs alter column storage_path drop not null;
alter table public.operis_discovery_runs add column scan_id uuid;
alter table public.operis_discovery_runs add constraint discovery_tenant_run_unique unique (tenant_id,id);
alter table public.operis_discovery_runs add constraint discovery_company_scope
  foreign key (tenant_id,company_id) references public.operis_companies(tenant_id,id);
alter table public.operis_discovery_runs add constraint discovery_package_unique unique (tenant_id,company_id,package_sha256);
alter table public.operis_discovery_runs add constraint discovery_scan_unique unique (tenant_id,company_id,scan_id);
alter table public.operis_discovery_findings add constraint findings_run_scope
  foreign key (tenant_id,run_id) references public.operis_discovery_runs(tenant_id,id);
alter table public.operis_module_recommendations add constraint recommendations_run_scope
  foreign key (tenant_id,run_id) references public.operis_discovery_runs(tenant_id,id);

create table public.operis_discovery_pilots (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.operis_tenants(id),
  run_id uuid not null,
  requested_by uuid not null references auth.users(id),
  status text not null default 'requested' check(status in ('requested','reviewing','closed')),
  created_at timestamptz not null default now(),
  foreign key(tenant_id,run_id) references public.operis_discovery_runs(tenant_id,id),
  unique(tenant_id,run_id)
);
alter table public.operis_discovery_pilots enable row level security;
revoke all on public.operis_discovery_pilots from public,anon,authenticated;
grant select on public.operis_discovery_pilots to authenticated;
create policy discovery_pilots_read on public.operis_discovery_pilots for select to authenticated
  using (operis_private.has_membership(tenant_id));
create trigger discovery_run_audit after insert on public.operis_discovery_runs
  for each row execute function operis_private.capture_change();
create trigger discovery_pilot_audit after insert or update on public.operis_discovery_pilots
  for each row execute function operis_private.capture_change();

create function operis_private.commit_discovery(p_payload jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  actor uuid := auth.uid();
  target uuid := (p_payload->>'tenant_id')::uuid;
  company uuid := (p_payload->>'company_id')::uuid;
  scan uuid := (p_payload->>'scan_id')::uuid;
  digest text := p_payload->>'package_sha256';
  run uuid;
  existing_digest text;
  item jsonb;
  key_header text := coalesce(nullif(current_setting('request.headers',true),'')::jsonb->>'x-operis-ingest-key','');
begin
  if actor is null or length(key_header)<32 or not exists (
    select 1 from operis_private.discovery_ingest_config where singleton
      and key_sha256=encode(sha256(convert_to(key_header,'UTF8')),'hex')
  ) then raise insufficient_privilege using message='Validated ingestion required'; end if;
  perform 1 from public.operis_memberships where tenant_id=target and user_id=actor
    and role in ('admin','operator') for share;
  if not found then raise insufficient_privilege using message='Discovery write access required'; end if;
  perform 1 from public.operis_companies where tenant_id=target and id=company
    and code=p_payload->>'company_code' for share;
  if not found then raise insufficient_privilege using message='Company binding rejected'; end if;
  if scan is null or digest is null or digest !~ '^[a-f0-9]{64}$'
    or p_payload->>'scanner_version' is distinct from '0.3.0'
    or jsonb_typeof(p_payload->'summary') is distinct from 'object'
    or jsonb_typeof(p_payload->'report') is distinct from 'object'
    or octet_length(p_payload::text)>131072 then
    raise check_violation using message='Invalid normalized assessment';
  end if;
  -- Serialize the scan key before checking idempotency. Retried uploads return
  -- the original immutable report; different bytes under one scan are rejected.
  perform pg_advisory_xact_lock(hashtextextended(target::text||company::text||scan::text,0));
  select id,package_sha256 into run,existing_digest from public.operis_discovery_runs
    where tenant_id=target and company_id=company and scan_id=scan;
  if found then
    if existing_digest<>digest then raise unique_violation using message='Scan already committed with different content'; end if;
    return jsonb_build_object('id',run,'duplicate',true);
  end if;
  insert into public.operis_discovery_runs(tenant_id,company_id,scan_id,uploaded_by,
    scanner_version,package_schema_version,original_filename,storage_path,package_sha256,
    status,scan_mode,completed_at,summary,self_evaluation,limitations)
  values(target,company,scan,actor,'0.3.0','1','aggregate-discovery.zip',null,digest,
    'complete','metadata_only',(p_payload->>'completed_at')::timestamptz,
    p_payload->'summary',p_payload->'report',p_payload->'report'->'limitations') returning id into run;
  for item in select value from jsonb_array_elements(p_payload->'report'->'findings') loop
    insert into public.operis_discovery_findings(tenant_id,run_id,category,subject,evidence,score,rationale)
      values(target,run,item->>'category',item->>'subject',item->>'evidence',0,item->>'rationale');
  end loop;
  for item in select value from jsonb_array_elements(p_payload->'report'->'recommendations') loop
    insert into public.operis_module_recommendations(tenant_id,run_id,module_code,module_name,rank,fit_score,evidence,expected_value)
      values(target,run,item->>'module_code',item->>'module_name',(item->>'rank')::int,0,item->'evidence',
        jsonb_build_object('rationale',item->>'rationale','measured_value',null));
  end loop;
  return jsonb_build_object('id',run,'duplicate',false);
end;
$$;
revoke all on function operis_private.commit_discovery(jsonb) from public,anon,authenticated;
grant execute on function operis_private.commit_discovery(jsonb) to authenticated;
create function public.operis_commit_discovery(p_payload jsonb) returns jsonb
language sql security invoker set search_path='' as $$
  select operis_private.commit_discovery(p_payload);
$$;
revoke all on function public.operis_commit_discovery(jsonb) from public,anon,authenticated;
grant execute on function public.operis_commit_discovery(jsonb) to authenticated;

create function operis_private.request_discovery_pilot(p_tenant uuid,p_run uuid) returns jsonb
language plpgsql security definer set search_path='' as $$
declare actor uuid:=auth.uid(); result public.operis_discovery_pilots;
begin
  if actor is null then raise insufficient_privilege using message='Verified identity required'; end if;
  perform 1 from public.operis_memberships where tenant_id=p_tenant and user_id=actor
    and role in ('admin','operator') for share;
  if not found then raise insufficient_privilege using message='Discovery write access required'; end if;
  perform 1 from public.operis_discovery_runs where tenant_id=p_tenant and id=p_run
    and status='complete' for share;
  if not found then raise insufficient_privilege using message='Assessment not found'; end if;
  perform pg_advisory_xact_lock(hashtextextended('pilot:'||p_run::text,0));
  select * into result from public.operis_discovery_pilots where tenant_id=p_tenant and run_id=p_run;
  if found then return to_jsonb(result); end if;
  insert into public.operis_discovery_pilots(tenant_id,run_id,requested_by)
    values(p_tenant,p_run,actor) returning * into result;
  return to_jsonb(result);
end;
$$;
revoke all on function operis_private.request_discovery_pilot(uuid,uuid) from public,anon,authenticated;
grant execute on function operis_private.request_discovery_pilot(uuid,uuid) to authenticated;
create function public.operis_request_discovery_pilot(p_tenant uuid,p_run uuid) returns jsonb
language sql security invoker set search_path='' as $$
  select operis_private.request_discovery_pilot(p_tenant,p_run);
$$;
revoke all on function public.operis_request_discovery_pilot(uuid,uuid) from public,anon,authenticated;
grant execute on function public.operis_request_discovery_pilot(uuid,uuid) to authenticated;

-- This release retains normalized aggregates only. Disable the legacy raw ZIP
-- insert path; leave existing private objects and read access untouched.
do $$ begin
  if to_regclass('storage.objects') is not null then
    execute 'drop policy if exists operis_discovery_upload on storage.objects';
  end if;
end $$;
