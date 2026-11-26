-- =====================================================================
-- PeRC – cơ sở dữ liệu người dùng trên Supabase
-- Chạy 1 lần trong Supabase: SQL Editor -> New query -> dán toàn bộ -> Run
-- =====================================================================

-- Email quản trị (chủ app). Đổi nếu cần.
create or replace function public.perc_admin_email() returns text
language sql immutable as $$ select 'nganthuylien@gmail.com' $$;

-- ---------------------------------------------------------------- bảng
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  full_name   text,
  created_at  timestamptz not null default now(),
  last_seen   timestamptz,
  daily_quota int  not null default 500,      -- điểm mỗi ngày
  banned      boolean not null default false,
  is_admin    boolean not null default false
);

create table if not exists public.usage (
  id       bigserial primary key,
  user_id  uuid not null references auth.users(id) on delete cascade,
  at       timestamptz not null default now(),
  task     text not null,
  cost     int  not null
);
create index if not exists usage_user_at on public.usage(user_id, at);

-- Bật RLS: người dùng chỉ đọc được dữ liệu của chính mình, không tự ghi/sửa được.
alter table public.profiles enable row level security;
alter table public.usage    enable row level security;
drop policy if exists "doc ho so cua minh" on public.profiles;
create policy "doc ho so cua minh" on public.profiles for select using (id = auth.uid());
drop policy if exists "doc luot dung cua minh" on public.usage;
create policy "doc luot dung cua minh" on public.usage for select using (user_id = auth.uid());

-- ---------------------------------------------------------------- tự tạo hồ sơ khi đăng ký (tự động duyệt)
create or replace function public.perc_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name, is_admin)
  values (new.id, new.email,
          coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
          lower(new.email) = lower(public.perc_admin_email()))
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists perc_on_auth_user_created on auth.users;
create trigger perc_on_auth_user_created after insert on auth.users
  for each row execute function public.perc_new_user();

-- ---------------------------------------------------------------- điểm đã dùng hôm nay (theo giờ Việt Nam)
create or replace function public.perc_used_today(uid uuid) returns int
language sql stable security definer set search_path = public as $$
  select coalesce(sum(cost), 0)::int from public.usage
  where user_id = uid
    and (at at time zone 'Asia/Ho_Chi_Minh')::date = (now() at time zone 'Asia/Ho_Chi_Minh')::date
$$;

-- ---------------------------------------------------------------- trạng thái của tôi
create or replace function public.my_status() returns json
language plpgsql security definer set search_path = public as $$
declare p public.profiles;
begin
  select * into p from public.profiles where id = auth.uid();
  if p.id is null then
    return json_build_object('ok', false, 'error', 'Chưa có hồ sơ');
  end if;
  update public.profiles set last_seen = now() where id = p.id;
  return json_build_object('ok', true, 'email', p.email, 'name', p.full_name,
    'quota', p.daily_quota, 'used', public.perc_used_today(p.id),
    'banned', p.banned, 'is_admin', p.is_admin);
end $$;

-- ---------------------------------------------------------------- trừ điểm khi chạy tác vụ (chạy trên máy chủ -> không gian lận được)
create or replace function public.consume(task text, cost int) returns json
language plpgsql security definer set search_path = public as $$
declare p public.profiles; used int;
begin
  select * into p from public.profiles where id = auth.uid();
  if p.id is null then return json_build_object('ok', false, 'error', 'Chưa đăng nhập'); end if;
  if p.banned then return json_build_object('ok', false, 'error', 'Tài khoản đã bị khoá'); end if;
  if cost < 0 or cost > 1000 then return json_build_object('ok', false, 'error', 'Điểm không hợp lệ'); end if;
  used := public.perc_used_today(p.id);
  if used + cost > p.daily_quota then
    return json_build_object('ok', false, 'used', used, 'quota', p.daily_quota,
      'error', format('Hết hạn mức hôm nay (%s/%s điểm). Hạn mức làm mới lúc 0h.', used, p.daily_quota));
  end if;
  insert into public.usage (user_id, task, cost) values (p.id, task, cost);
  update public.profiles set last_seen = now() where id = p.id;
  return json_build_object('ok', true, 'used', used + cost, 'quota', p.daily_quota);
end $$;

-- ---------------------------------------------------------------- xoá dữ liệu của tôi (xoá tài khoản + hồ sơ + lịch sử)
create or replace function public.delete_my_data() returns json
language plpgsql security definer set search_path = public, auth as $$
begin
  if auth.uid() is null then return json_build_object('ok', false); end if;
  delete from auth.users where id = auth.uid();          -- cascade xoá profiles, usage
  return json_build_object('ok', true);
end $$;

-- ---------------------------------------------------------------- quản trị (chỉ admin)
create or replace function public.admin_list_users() returns table (
  id uuid, email text, full_name text, created_at timestamptz, last_seen timestamptz,
  daily_quota int, banned boolean, is_admin boolean, used_today int, used_total bigint)
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.profiles pr where pr.id = auth.uid() and pr.is_admin) then
    raise exception 'Chỉ quản trị viên';
  end if;
  return query
    select p.id, p.email, p.full_name, p.created_at, p.last_seen, p.daily_quota, p.banned, p.is_admin,
           public.perc_used_today(p.id),
           (select coalesce(sum(u.cost), 0) from public.usage u where u.user_id = p.id)
    from public.profiles p order by p.last_seen desc nulls last;
end $$;

create or replace function public.admin_set_user(uid uuid, quota int, is_banned boolean) returns json
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from public.profiles pr where pr.id = auth.uid() and pr.is_admin) then
    raise exception 'Chỉ quản trị viên';
  end if;
  update public.profiles set daily_quota = greatest(quota, 0), banned = is_banned where id = uid;
  return json_build_object('ok', true);
end $$;

create or replace function public.admin_delete_user(uid uuid) returns json
language plpgsql security definer set search_path = public, auth as $$
begin
  if not exists (select 1 from public.profiles pr where pr.id = auth.uid() and pr.is_admin) then
    raise exception 'Chỉ quản trị viên';
  end if;
  if uid = auth.uid() then raise exception 'Không tự xoá tài khoản quản trị'; end if;
  delete from auth.users where id = uid;
  return json_build_object('ok', true);
end $$;

-- Chỉ người đã đăng nhập mới gọi được các hàm
revoke all on function public.my_status(), public.consume(text, int), public.delete_my_data(),
  public.admin_list_users(), public.admin_set_user(uuid, int, boolean), public.admin_delete_user(uuid)
  from public, anon;
grant execute on function public.my_status(), public.consume(text, int), public.delete_my_data(),
  public.admin_list_users(), public.admin_set_user(uuid, int, boolean), public.admin_delete_user(uuid)
  to authenticated;
