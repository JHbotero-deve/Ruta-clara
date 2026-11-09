create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) between 2 and 120),
  created_at timestamptz not null default now()
);
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  full_name text not null default '',
  created_at timestamptz not null default now()
);
create table if not exists public.memberships (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','admin','driver')),
  created_at timestamptz not null default now(),
  unique (organization_id,user_id)
);
create table if not exists public.deliveries (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  assigned_to uuid references auth.users(id) on delete set null,
  recipient_name text not null default '',
  unit_name text not null default '',
  address text not null,
  status text not null default 'pending' check (status in ('pending','completed','skipped','removed')),
  notes text not null default '',
  sort_order integer not null default 0,
  completed_at timestamptz,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists deliveries_org_status_idx on public.deliveries(organization_id,status);
create index if not exists deliveries_assigned_idx on public.deliveries(assigned_to,status);
create or replace function public.is_org_member(target_org uuid)
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from public.memberships m where m.organization_id = target_org and m.user_id = (select auth.uid())) $$;
create or replace function public.has_org_role(target_org uuid, allowed_roles text[])
returns boolean language sql stable security definer set search_path = public
as $$ select exists (select 1 from public.memberships m where m.organization_id = target_org and m.user_id = (select auth.uid()) and m.role = any(allowed_roles)) $$;
revoke all on function public.is_org_member(uuid) from public;
revoke all on function public.has_org_role(uuid,text[]) from public;
grant execute on function public.is_org_member(uuid) to authenticated;
grant execute on function public.has_org_role(uuid,text[]) to authenticated;
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
declare new_org uuid;
declare org_name text;
begin
  org_name := coalesce(nullif(trim(new.raw_user_meta_data->>'company_name'),''),'Empresa sin nombre');
  insert into public.organizations(name) values (org_name) returning id into new_org;
  insert into public.profiles(id,organization_id,full_name) values (new.id,new_org,coalesce(new.raw_user_meta_data->>'full_name',''));
  insert into public.memberships(organization_id,user_id,role) values (new_org,new.id,'owner');
  return new;
end;
$$;
drop trigger if exists on_auth_user_created_ruta_clara on auth.users;
create trigger on_auth_user_created_ruta_clara after insert on auth.users for each row execute procedure public.handle_new_user();
create or replace function public.set_delivery_updated_at()
returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
drop trigger if exists deliveries_updated_at on public.deliveries;
create trigger deliveries_updated_at before update on public.deliveries for each row execute procedure public.set_delivery_updated_at();
alter table public.organizations enable row level security;
alter table public.profiles enable row level security;
alter table public.memberships enable row level security;
alter table public.deliveries enable row level security;
revoke all on public.organizations,public.profiles,public.memberships,public.deliveries from anon;
grant select,update on public.organizations to authenticated;
grant select on public.profiles,public.memberships to authenticated;
grant select,insert,update,delete on public.deliveries to authenticated;
create policy "members read own organization" on public.organizations for select to authenticated using (public.is_org_member(id));
create policy "owners admins update organization" on public.organizations for update to authenticated using (public.has_org_role(id,array['owner','admin'])) with check (public.has_org_role(id,array['owner','admin']));
create policy "users read own profile" on public.profiles for select to authenticated using (id = (select auth.uid()));
create policy "members read organization memberships" on public.memberships for select to authenticated using (public.is_org_member(organization_id));
create policy "members read organization deliveries" on public.deliveries for select to authenticated using (public.is_org_member(organization_id));
create policy "admins manage deliveries" on public.deliveries for insert to authenticated with check (public.has_org_role(organization_id,array['owner','admin']) and created_by = (select auth.uid()));
create policy "admins update deliveries" on public.deliveries for update to authenticated using (public.has_org_role(organization_id,array['owner','admin'])) with check (public.has_org_role(organization_id,array['owner','admin']));
create policy "admins delete deliveries" on public.deliveries for delete to authenticated using (public.has_org_role(organization_id,array['owner','admin']));
create or replace function public.update_assigned_delivery_status(delivery_id uuid, new_status text)
returns public.deliveries language plpgsql security definer set search_path = public
as $$
declare updated public.deliveries;
begin
  if new_status not in ('pending','completed','skipped') then raise exception 'Estado no permitido'; end if;
  update public.deliveries d set status = new_status, completed_at = case when new_status = 'completed' then now() else null end
  where d.id = delivery_id and d.assigned_to = (select auth.uid()) and public.is_org_member(d.organization_id)
  returning d.* into updated;
  if updated.id is null then raise exception 'Entrega no encontrada o no asignada al usuario'; end if;
  return updated;
end;
$$;
revoke all on function public.update_assigned_delivery_status(uuid,text) from public;
grant execute on function public.update_assigned_delivery_status(uuid,text) to authenticated;

alter table public.profiles add column if not exists email text not null default '';
alter table public.deliveries add column if not exists sort_order integer not null default 0;
create table if not exists public.organization_invites (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  token_hash text not null unique,
  role text not null check (role in ('admin','driver')),
  created_by uuid not null references auth.users(id),
  expires_at timestamptz not null default now() + interval '7 days',
  used_at timestamptz,
  used_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
alter table public.organization_invites enable row level security;
revoke all on public.organization_invites from anon,authenticated;
create or replace function public.create_organization_invite(target_role text)
returns text language plpgsql security definer set search_path = public
as $$
declare current_org uuid;
declare invite_code text;
begin
  if target_role not in ('admin','driver') then raise exception 'Rol de invitación no permitido'; end if;
  select organization_id into current_org from public.profiles where id = (select auth.uid());
  if current_org is null or not public.has_org_role(current_org,array['owner','admin']) then raise exception 'No tienes permiso para invitar miembros'; end if;
  invite_code := replace(gen_random_uuid()::text || gen_random_uuid()::text,'-','');
  insert into public.organization_invites(organization_id,token_hash,role,created_by)
  values (current_org,md5(invite_code),target_role,(select auth.uid()));
  return invite_code;
end;
$$;
revoke all on function public.create_organization_invite(text) from public;
grant execute on function public.create_organization_invite(text) to authenticated;
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
declare new_org uuid;
declare org_name text;
declare invite_code text;
declare invite_row public.organization_invites;
declare new_role text;
begin
  invite_code := nullif(trim(new.raw_user_meta_data->>'invite_code'),'');
  if invite_code is not null then
    select * into invite_row from public.organization_invites
    where token_hash = md5(invite_code) and used_at is null and expires_at > now()
    for update;
    if invite_row.id is null then raise exception 'Código de invitación inválido o vencido'; end if;
    new_org := invite_row.organization_id;
    new_role := invite_row.role;
    update public.organization_invites set used_at = now(), used_by = new.id where id = invite_row.id;
  else
    org_name := coalesce(nullif(trim(new.raw_user_meta_data->>'company_name'),''),'Empresa sin nombre');
    insert into public.organizations(name) values (org_name) returning id into new_org;
    new_role := 'owner';
  end if;
  insert into public.profiles(id,organization_id,full_name,email)
  values (new.id,new_org,coalesce(new.raw_user_meta_data->>'full_name',''),coalesce(new.email,''));
  insert into public.memberships(organization_id,user_id,role) values (new_org,new.id,new_role);
  return new;
end;
$$;
drop policy if exists "users read own profile" on public.profiles;
create policy "members read organization profiles" on public.profiles for select to authenticated
using (public.is_org_member(organization_id));

create or replace function public.validate_delivery_assignee()
returns trigger language plpgsql set search_path = public
as $$
begin
  if new.assigned_to is not null and not exists (
    select 1 from public.memberships m
    where m.organization_id = new.organization_id and m.user_id = new.assigned_to
  ) then
    raise exception 'El repartidor asignado no pertenece a esta empresa';
  end if;
  return new;
end;
$$;
drop trigger if exists validate_delivery_assignee_trigger on public.deliveries;
create trigger validate_delivery_assignee_trigger before insert or update of assigned_to,organization_id
on public.deliveries for each row execute procedure public.validate_delivery_assignee();
