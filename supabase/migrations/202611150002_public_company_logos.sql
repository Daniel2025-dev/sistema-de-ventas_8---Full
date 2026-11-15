begin;

-- Los logos institucionales deben poder mostrarse antes y después de iniciar sesión.
update storage.buckets
set public = true
where id = 'imagenes';

commit;
