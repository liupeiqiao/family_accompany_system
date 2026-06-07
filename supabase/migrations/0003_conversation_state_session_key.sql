alter table public.conversation_states
  drop constraint if exists conversation_states_session_id_fkey,
  drop constraint if exists conversation_states_elder_person_id_fkey,
  drop constraint if exists conversation_states_current_persona_role_id_fkey,
  alter column session_id type text using coalesce(session_id::text, 'default'),
  alter column session_id set default 'default',
  alter column session_id set not null,
  alter column elder_person_id type text using coalesce(elder_person_id::text, ''),
  alter column elder_person_id set default '',
  alter column elder_person_id set not null,
  alter column current_persona_role_id type text using coalesce(current_persona_role_id::text, ''),
  alter column current_persona_role_id set default '',
  alter column current_persona_role_id set not null;

create unique index if not exists idx_conversation_states_family_session
  on public.conversation_states(family_id, session_id);
