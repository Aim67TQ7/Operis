-- Reviewed initial schema. Convert to a CLI-generated migration before deployment.
-- Applies only to a dedicated Operis database, once. Never run against legacy databases.
begin;
create schema if not exists operis_private;
revoke all on schema operis_private from public, anon, authenticated;
grant usage on schema operis_private to authenticated;

create table public.operis_tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 2 and 100),
  created_at timestamptz not null default now()
);
create table public.operis_memberships (
  tenant_id uuid not null references public.operis_tenants(id),
  user_id uuid not null references auth.users(id),
  role text not null check (role in ('admin','operator','viewer')),
  created_at timestamptz not null default now(),
  primary key (tenant_id,user_id)
);
create index operis_memberships_user_idx on public.operis_memberships(user_id,tenant_id);
create table public.operis_companies (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.operis_tenants(id),
  code text not null check (code ~ '^[A-Za-z0-9_-]{1,24}$'),
  name text not null check (char_length(btrim(name)) between 2 and 100),
  created_at timestamptz not null default now(),
  unique (tenant_id,id), unique (tenant_id,code)
);
create table public.operis_sites (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.operis_tenants(id),
  company_id uuid not null,
  code text not null check (code ~ '^[A-Za-z0-9_-]{1,24}$'),
  name text not null check (char_length(btrim(name)) between 2 and 100),
  created_at timestamptz not null default now(),
  foreign key (tenant_id,company_id) references public.operis_companies(tenant_id,id),
  unique (tenant_id,company_id,code)
);
create index operis_sites_tenant_company_idx on public.operis_sites(tenant_id,company_id);
create table public.operis_audit_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.operis_tenants(id),
  actor_id uuid,
  action text not null check (action in ('INSERT','UPDATE','DELETE')),
  table_name text not null,
  record_id text not null,
  before jsonb,
  after jsonb,
  request_id text,
  created_at timestamptz not null default now()
);
create index operis_audit_tenant_time_idx on public.operis_audit_events(tenant_id,created_at desc);

-- Private, fixed-search-path membership lookup avoids recursive membership RLS.
-- It accepts no user ID: identity is always the verified request's auth.uid().
create function operis_private.has_membership(target uuid, require_admin boolean default false)
returns boolean language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and exists (
    select 1 from public.operis_memberships m
    where m.tenant_id = target and m.user_id = (select auth.uid())
      and (not require_admin or m.role = 'admin')
  );
$$;
revoke all on function operis_private.has_membership(uuid,boolean) from public,anon,authenticated;
grant execute on function operis_private.has_membership(uuid,boolean) to authenticated;

alter table public.operis_tenants enable row level security;
alter table public.operis_memberships enable row level security;
alter table public.operis_companies enable row level security;
alter table public.operis_sites enable row level security;
alter table public.operis_audit_events enable row level security;
revoke all on public.operis_tenants, public.operis_memberships, public.operis_companies,
  public.operis_sites, public.operis_audit_events from public,anon,authenticated;
grant select on public.operis_tenants, public.operis_memberships, public.operis_companies,
  public.operis_sites, public.operis_audit_events to authenticated;
-- Readiness probes have a SELECT privilege but no anon policy, hence zero visible rows.
grant select on public.operis_tenants to anon;
grant update(name) on public.operis_tenants to authenticated;
grant insert(tenant_id,code,name) on public.operis_companies to authenticated;
grant insert(tenant_id,company_id,code,name) on public.operis_sites to authenticated;

create policy tenants_read on public.operis_tenants for select to authenticated
  using (operis_private.has_membership(id));
create policy tenants_update on public.operis_tenants for update to authenticated
  using (operis_private.has_membership(id,true)) with check (operis_private.has_membership(id,true));
create policy memberships_read on public.operis_memberships for select to authenticated
  using (operis_private.has_membership(tenant_id));
create policy companies_read on public.operis_companies for select to authenticated
  using (operis_private.has_membership(tenant_id));
create policy companies_insert on public.operis_companies for insert to authenticated
  with check (operis_private.has_membership(tenant_id,true));
create policy sites_read on public.operis_sites for select to authenticated
  using (operis_private.has_membership(tenant_id));
create policy sites_insert on public.operis_sites for insert to authenticated
  with check (operis_private.has_membership(tenant_id,true));
create policy audit_read on public.operis_audit_events for select to authenticated
  using (operis_private.has_membership(tenant_id));

-- Trigger-only privileged audit writer. No client can invoke it, insert an event,
-- or update/delete history. The mutation and evidence commit in one transaction.
create function operis_private.capture_change() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  old_data jsonb; new_data jsonb; source_data jsonb; scope uuid; record_key text;
begin
  if tg_op <> 'INSERT' then old_data := to_jsonb(old); end if;
  if tg_op <> 'DELETE' then new_data := to_jsonb(new); end if;
  if tg_op = 'UPDATE' and old_data = new_data then return new; end if;
  source_data := coalesce(new_data,old_data);
  if tg_table_name = 'operis_tenants' then scope := (source_data->>'id')::uuid;
  else scope := (source_data->>'tenant_id')::uuid; end if;
  record_key := coalesce(source_data->>'id',source_data->>'user_id');
  insert into public.operis_audit_events(tenant_id,actor_id,action,table_name,record_id,before,after,request_id)
    values(scope,auth.uid(),tg_op,tg_table_name,record_key,old_data,new_data,
      left(nullif(current_setting('request.headers',true),'')::jsonb->>'x-request-id',100));
  return coalesce(new,old);
end;
$$;
revoke all on function operis_private.capture_change() from public,anon,authenticated;
create trigger tenant_audit after insert or update on public.operis_tenants
  for each row execute function operis_private.capture_change();
create trigger company_audit after insert or update or delete on public.operis_companies
  for each row execute function operis_private.capture_change();
create trigger site_audit after insert or update or delete on public.operis_sites
  for each row execute function operis_private.capture_change();
create trigger membership_audit after insert or update or delete on public.operis_memberships
  for each row execute function operis_private.capture_change();
commit;
