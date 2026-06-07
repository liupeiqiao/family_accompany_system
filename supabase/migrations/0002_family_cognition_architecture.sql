-- Family Cognition Architecture.
-- Adds graph-centered people, relationships, structured memory events, and conversation state.

create table if not exists public.persons (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  kind text not null default 'family',
  full_name text not null default '',
  nicknames jsonb not null default '[]'::jsonb,
  gender text not null default '',
  birth_date text not null default '',
  address_terms jsonb not null default '{}'::jsonb,
  traits jsonb not null default '[]'::jsonb,
  speech_style jsonb not null default '[]'::jsonb,
  habits jsonb not null default '[]'::jsonb,
  interests jsonb not null default '[]'::jsonb,
  life_experiences jsonb not null default '[]'::jsonb,
  work_experiences jsonb not null default '[]'::jsonb,
  family_experiences jsonb not null default '[]'::jsonb,
  knowledge_boundaries jsonb not null default '{}'::jsonb,
  topic_boundaries jsonb not null default '{}'::jsonb,
  legacy_family_profile_id text not null default '',
  legacy_persona_id text not null default '',
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relationships (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  from_person_id uuid not null references public.persons(id) on delete cascade,
  to_person_id uuid not null references public.persons(id) on delete cascade,
  relation_type text not null default '',
  display_label text not null default '',
  inverse_relation_type text not null default '',
  inverse_display_label text not null default '',
  confidence numeric not null default 1.0,
  source text not null default '',
  notes text not null default '',
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.persona_roles (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  person_id uuid not null references public.persons(id) on delete cascade,
  role_label text not null default '',
  appellation_to_elder text not null default '',
  can_speak_as_person boolean not null default true,
  voice_profile_id uuid references public.voice_profiles(id) on delete set null,
  comfort_style jsonb not null default '[]'::jsonb,
  mood_preference jsonb not null default '{}'::jsonb,
  sensitivity_map jsonb not null default '{}'::jsonb,
  legacy_persona_id text not null default '',
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.memory_events (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  title text not null default '',
  summary text not null default '',
  event_time_text text not null default '',
  event_start_at timestamptz,
  event_end_at timestamptz,
  location text not null default '',
  emotion_tags jsonb not null default '[]'::jsonb,
  topic_tags jsonb not null default '[]'::jsonb,
  source_type text not null default '',
  source_person_id uuid references public.persons(id) on delete set null,
  truth_status text not null default 'uncertain',
  sensitivity_level integer not null default 0,
  updated_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.memory_event_participants (
  event_id uuid not null references public.memory_events(id) on delete cascade,
  person_id uuid not null references public.persons(id) on delete cascade,
  role_in_event text not null default '',
  perspective text not null default 'heard_about',
  can_use_first_person boolean not null default false,
  can_mention boolean not null default true,
  primary key (event_id, person_id)
);

create table if not exists public.conversation_states (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families(id) on delete cascade,
  session_id uuid references public.chat_sessions(id) on delete cascade,
  elder_person_id uuid references public.persons(id) on delete set null,
  current_persona_role_id uuid references public.persona_roles(id) on delete set null,
  recent_person_ids jsonb not null default '[]'::jsonb,
  recent_event_ids jsonb not null default '[]'::jsonb,
  elder_emotion text not null default '',
  ongoing_topic text not null default '',
  unfinished_topics jsonb not null default '[]'::jsonb,
  relationship_focus jsonb not null default '{}'::jsonb,
  last_intent text not null default '',
  summary text not null default '',
  updated_at timestamptz not null default now()
);

create index if not exists idx_persons_family on public.persons(family_id);
create index if not exists idx_relationships_family on public.relationships(family_id);
create index if not exists idx_relationships_from on public.relationships(from_person_id);
create index if not exists idx_relationships_to on public.relationships(to_person_id);
create index if not exists idx_persona_roles_family on public.persona_roles(family_id);
create index if not exists idx_memory_events_family on public.memory_events(family_id);
create index if not exists idx_memory_event_participants_person on public.memory_event_participants(person_id);
create index if not exists idx_conversation_states_family on public.conversation_states(family_id);

alter table public.persons enable row level security;
alter table public.relationships enable row level security;
alter table public.persona_roles enable row level security;
alter table public.memory_events enable row level security;
alter table public.memory_event_participants enable row level security;
alter table public.conversation_states enable row level security;

create policy persons_select_member on public.persons
  for select using (public.is_family_member(family_id));
create policy persons_insert_editor on public.persons
  for insert with check (public.is_family_editor(family_id));
create policy persons_update_editor on public.persons
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy relationships_select_member on public.relationships
  for select using (public.is_family_member(family_id));
create policy relationships_insert_editor on public.relationships
  for insert with check (public.is_family_editor(family_id));
create policy relationships_update_editor on public.relationships
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy persona_roles_select_member on public.persona_roles
  for select using (public.is_family_member(family_id));
create policy persona_roles_insert_editor on public.persona_roles
  for insert with check (public.is_family_editor(family_id));
create policy persona_roles_update_editor on public.persona_roles
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy memory_events_select_member on public.memory_events
  for select using (public.is_family_member(family_id));
create policy memory_events_insert_editor on public.memory_events
  for insert with check (public.is_family_editor(family_id));
create policy memory_events_update_editor on public.memory_events
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));

create policy memory_event_participants_select_member on public.memory_event_participants
  for select using (
    exists (
      select 1 from public.memory_events me
      where me.id = event_id and public.is_family_member(me.family_id)
    )
  );
create policy memory_event_participants_insert_editor on public.memory_event_participants
  for insert with check (
    exists (
      select 1 from public.memory_events me
      where me.id = event_id and public.is_family_editor(me.family_id)
    )
  );
create policy memory_event_participants_update_editor on public.memory_event_participants
  for update using (
    exists (
      select 1 from public.memory_events me
      where me.id = event_id and public.is_family_editor(me.family_id)
    )
  );

create policy conversation_states_select_member on public.conversation_states
  for select using (public.is_family_member(family_id));
create policy conversation_states_insert_editor on public.conversation_states
  for insert with check (public.is_family_editor(family_id));
create policy conversation_states_update_editor on public.conversation_states
  for update using (public.is_family_editor(family_id))
  with check (public.is_family_editor(family_id));
