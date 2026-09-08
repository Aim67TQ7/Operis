-- Operator-only; run with psql variables tenant_name and admin_user_id.
-- admin_user_id must identify an already verified, non-anonymous provider user.
-- Run only on the approved Operis target.
-- Touch only Operis records; preserve shared provider settings. This is not payment verification.
\set ON_ERROR_STOP on
begin;
create temporary table provisioning_input as
  select :'tenant_name'::text as name, :'admin_user_id'::uuid as user_id;
do $$
begin
  if not exists(select 1 from auth.users u join provisioning_input p on p.user_id=u.id
    where u.email_confirmed_at is not null and not coalesce(u.is_anonymous,false)) then
    raise exception 'A verified non-anonymous administrator is required';
  end if;
end;
$$;
with tenant as (
  insert into public.operis_tenants(name) select name from provisioning_input returning id
)
insert into public.operis_memberships(tenant_id,user_id,role)
select t.id,p.user_id,'admin' from tenant t cross join provisioning_input p
returning tenant_id,user_id,role;
drop table provisioning_input;
commit;
