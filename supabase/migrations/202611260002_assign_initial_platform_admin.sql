begin;

insert into public.platform_admins(auth_user_id)
select id
from auth.users
where lower(email) = lower('floresdaniel.g@gmail.com')
on conflict (auth_user_id) do nothing;

do $$
begin
  if not exists (
    select 1
    from public.platform_admins pa
    join auth.users au on au.id = pa.auth_user_id
    where lower(au.email) = lower('floresdaniel.g@gmail.com')
  ) then
    raise exception 'No existe la cuenta Auth floresdaniel.g@gmail.com; cree o confirme la cuenta antes de desplegar';
  end if;
end $$;

commit;
