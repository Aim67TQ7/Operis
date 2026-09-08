-- Historical discovery foundation retrieved from the applied migration.
-- Local reproducibility only. Already applied on ZODA; do not reapply there.
create table if not exists public.operis_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.operis_tenants(id) on delete cascade,
  company_id uuid references public.operis_companies(id) on delete set null,
  uploaded_by uuid not null default auth.uid() references auth.users(id) on delete restrict,
  source_erp text not null default 'epicor_kinetic',
  scanner_version text,
  package_schema_version text,
  original_filename text not null,
  storage_path text not null unique,
  package_sha256 text,
  status text not null default 'uploaded' check (status in ('uploaded','validating','analyzing','complete','failed')),
  scan_mode text check (scan_mode in ('metadata_only','definition_enhanced')),
  started_at timestamptz,
  completed_at timestamptz,
  summary jsonb not null default '{}'::jsonb,
  self_evaluation jsonb not null default '{}'::jsonb,
  limitations jsonb not null default '[]'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.operis_discovery_findings (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.operis_discovery_runs(id) on delete cascade,
  tenant_id uuid not null references public.operis_tenants(id) on delete cascade,
  category text not null check (category in ('externalize','agent','interface','retire','risk','gap','coverage')),
  subject text not null,
  evidence text,
  score integer not null default 0 check (score between 0 and 5),
  horizon text,
  rationale text,
  validation_status text not null default 'unreviewed' check (validation_status in ('unreviewed','confirmed','rejected','needs_information')),
  created_at timestamptz not null default now()
);

create table if not exists public.operis_module_recommendations (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.operis_discovery_runs(id) on delete cascade,
  tenant_id uuid not null references public.operis_tenants(id) on delete cascade,
  module_code text not null,
  module_name text not null,
  rank integer not null check (rank > 0),
  fit_score numeric(5,2) not null check (fit_score between 0 and 100),
  evidence jsonb not null default '[]'::jsonb,
  expected_value jsonb not null default '{}'::jsonb,
  implementation_horizon text,
  status text not null default 'recommended' check (status in ('recommended','selected','deferred','rejected')),
  created_at timestamptz not null default now(),
  unique (run_id, module_code)
);

create index if not exists operis_discovery_runs_tenant_created_idx
  on public.operis_discovery_runs (tenant_id, created_at desc);
create index if not exists operis_discovery_findings_run_score_idx
  on public.operis_discovery_findings (run_id, score desc);
create index if not exists operis_module_recommendations_run_rank_idx
  on public.operis_module_recommendations (run_id, rank);

alter table public.operis_discovery_runs enable row level security;
alter table public.operis_discovery_findings enable row level security;
alter table public.operis_module_recommendations enable row level security;

create policy "discovery_runs_read" on public.operis_discovery_runs
  for select to authenticated using (operis_private.has_membership(tenant_id));
create policy "discovery_runs_insert" on public.operis_discovery_runs
  for insert to authenticated with check (
    uploaded_by = (select auth.uid()) and operis_private.has_membership(tenant_id)
  );
create policy "discovery_runs_update" on public.operis_discovery_runs
  for update to authenticated using (operis_private.has_membership(tenant_id))
  with check (operis_private.has_membership(tenant_id));

create policy "discovery_findings_read" on public.operis_discovery_findings
  for select to authenticated using (operis_private.has_membership(tenant_id));
create policy "discovery_findings_update" on public.operis_discovery_findings
  for update to authenticated using (operis_private.has_membership(tenant_id))
  with check (operis_private.has_membership(tenant_id));

create policy "module_recommendations_read" on public.operis_module_recommendations
  for select to authenticated using (operis_private.has_membership(tenant_id));
create policy "module_recommendations_update" on public.operis_module_recommendations
  for update to authenticated using (operis_private.has_membership(tenant_id))
  with check (operis_private.has_membership(tenant_id));

revoke all on public.operis_discovery_runs from anon;
revoke all on public.operis_discovery_findings from anon;
revoke all on public.operis_module_recommendations from anon;
grant select, insert, update on public.operis_discovery_runs to authenticated;
grant select, update on public.operis_discovery_findings to authenticated;
grant select, update on public.operis_module_recommendations to authenticated;


