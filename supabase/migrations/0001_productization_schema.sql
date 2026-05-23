-- Productization schema for the family companion app.
-- Families isolate all user-submitted profiles, memories, voice assets, and chats.

create extension if not exists "pgcrypto";

create table if not exists public.families (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_by uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.family_memberships (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'editor', 'viewer')),
  created_at timestamptz not null default now(),
  unique (family_id, user_id)
);

create table if not exists public.elders (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  full_name text not null default '',
  gender text not null default '',
  personality jsonb not null default '[]'::jsonb,
  preferences jsonb not null default '[]'::jsonb,
  habits jsonb not null default '[]'::jsonb,
  health_notes jsonb not null default '[]'::jsonb,
  speech_traits jsonb not null default '[]'::jsonb,
  life_experiences jsonb not null default '[]'::jsonb,
  important_memories jsonb not null default '[]'::jsonb,
  notes text not null default '',
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.personas (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  role_label text not null,
  relation text not null default '',
  appellation text not null default '',
  personality jsonb not null default '[]'::jsonb,
  speech_style jsonb not null default '[]'::jsonb,
  comfort_style jsonb not null default '[]'::jsonb,
  mood_preference jsonb not null default '{}'::jsonb,
  topic_affinity jsonb not null default '{}'::jsonb,
  sensitivity_map jsonb not null default '{}'::jsonb,
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (family_id, role_label)
);

create table if not exists public.family_profiles (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  name text not null,
  relation text not null default '',
  personality jsonb not null default '[]'::jsonb,
  preferences jsonb not null default '[]'::jsonb,
  habits jsonb not null default '[]'::jsonb,
  relations jsonb not null default '[]'::jsonb,
  notes text not null default '',
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (family_id, name)
);

create table if not exists public.memories (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  content text not null,
  memory_type text not null default '',
  subject text not null default '',
  family_members jsonb not null default '[]'::jsonb,
  emotion_tags jsonb not null default '[]'::jsonb,
  topic_tags jsonb not null default '[]'::jsonb,
  intimacy_weight numeric not null default 0.5,
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.voice_profiles (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  display_name text not null,
  provider text not null,
  provider_voice_id text not null,
  status text not null default 'ready',
  created_by uuid not null references auth.users(id),
  consent_confirmed boolean not null default false,
  sample_source text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.voice_samples (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  voice_profile_id uuid references public.voice_profiles(id) on delete cascade,
  storage_path text not null,
  sample_source text not null,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table if not exists public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  elder_id uuid references public.elders(id) on delete set null,
  persona_id uuid references public.personas(id) on delete set null,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  chat_session_id uuid not null references public.chat_sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system')),
  content text not null,
  audio_storage_path text,
  debug jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.is_family_member(target_family_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.family_memberships fm
    where fm.family_id = target_family_id
      and fm.user_id = auth.uid()
  );
$$;

create or replace function public.is_family_editor(target_family_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.family_memberships fm
    where fm.family_id = target_family_id
      and fm.user_id = auth.uid()
      and fm.role in ('owner', 'editor')
  );
$$;

create or replace function public.is_family_owner(target_family_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.family_memberships fm
    where fm.family_id = target_family_id
      and fm.user_id = auth.uid()
      and fm.role = 'owner'
  );
$$;

alter table public.families enable row level security;
alter table public.family_memberships enable row level security;
alter table public.elders enable row level security;
alter table public.personas enable row level security;
alter table public.family_profiles enable row level security;
alter table public.memories enable row level security;
alter table public.voice_profiles enable row level security;
alter table public.voice_samples enable row level security;
alter table public.chat_sessions enable row level security;
alter table public.chat_messages enable row level security;

create policy families_select_member on public.families
  for select using (public.is_family_member(id));
create policy families_insert_authenticated on public.families
  for insert with check (created_by = auth.uid());
create policy families_update_owner on public.families
  for update using (public.is_family_owner(id));

create policy family_memberships_select_member on public.family_memberships
  for select using (public.is_family_member(family_id));
create policy family_memberships_insert_owner on public.family_memberships
  for insert with check (public.is_family_owner(family_id));
create policy family_memberships_update_owner on public.family_memberships
  for update using (public.is_family_owner(family_id));
create policy family_memberships_delete_owner on public.family_memberships
  for delete using (public.is_family_owner(family_id));

create policy elders_select_member on public.elders
  for select using (public.is_family_member(family_id));
create policy elders_insert_editor on public.elders
  for insert with check (public.is_family_editor(family_id));
create policy elders_update_editor on public.elders
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy personas_select_member on public.personas
  for select using (public.is_family_member(family_id));
create policy personas_insert_editor on public.personas
  for insert with check (public.is_family_editor(family_id));
create policy personas_update_editor on public.personas
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy family_profiles_select_member on public.family_profiles
  for select using (public.is_family_member(family_id));
create policy family_profiles_insert_editor on public.family_profiles
  for insert with check (public.is_family_editor(family_id));
create policy family_profiles_update_editor on public.family_profiles
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy memories_select_member on public.memories
  for select using (public.is_family_member(family_id));
create policy memories_insert_editor on public.memories
  for insert with check (public.is_family_editor(family_id));
create policy memories_update_editor on public.memories
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy voice_profiles_select_member on public.voice_profiles
  for select using (public.is_family_member(family_id));
create policy voice_profiles_insert_editor on public.voice_profiles
  for insert with check (public.is_family_editor(family_id));
create policy voice_profiles_update_editor on public.voice_profiles
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy voice_samples_select_member on public.voice_samples
  for select using (public.is_family_member(family_id));
create policy voice_samples_insert_editor on public.voice_samples
  for insert with check (public.is_family_editor(family_id));

create policy chat_sessions_select_member on public.chat_sessions
  for select using (public.is_family_member(family_id));
create policy chat_sessions_insert_editor on public.chat_sessions
  for insert with check (public.is_family_editor(family_id));
create policy chat_sessions_update_editor on public.chat_sessions
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy chat_messages_select_member on public.chat_messages
  for select using (public.is_family_member(family_id));
create policy chat_messages_insert_editor on public.chat_messages
  for insert with check (public.is_family_editor(family_id));

insert into storage.buckets (id, name, public)
values
  ('voice-samples', 'voice-samples', false),
  ('generated-audio', 'generated-audio', false)
on conflict (id) do nothing;

create policy voice_samples_storage_select_member on storage.objects
  for select using (
    bucket_id = 'voice-samples'
    and public.is_family_member((storage.foldername(name))[1]::uuid)
  );

create policy voice_samples_storage_insert_editor on storage.objects
  for insert with check (
    bucket_id = 'voice-samples'
    and public.is_family_editor((storage.foldername(name))[1]::uuid)
  );

create policy generated_audio_storage_select_member on storage.objects
  for select using (
    bucket_id = 'generated-audio'
    and public.is_family_member((storage.foldername(name))[1]::uuid)
  );

create policy generated_audio_storage_insert_editor on storage.objects
  for insert with check (
    bucket_id = 'generated-audio'
    and public.is_family_editor((storage.foldername(name))[1]::uuid)
  );
