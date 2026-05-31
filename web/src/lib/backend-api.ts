import { getAuthToken } from "./auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_COMPANION_API_URL ?? "http://127.0.0.1:8000";

export type DraftObject = Record<string, unknown>;

export type DedupSuggestion = {
  persona_action?: "skip" | "merge" | "new" | "";
  persona_match?: string;
  family_actions?: {
    new_name: string;
    action: "skip" | "merge_into" | "new";
    target?: string;
  }[];
  memory_actions?: {
    new_content: string;
    action: "skip" | "new";
    target?: string;
  }[];
};

export type ParsedDraft = {
  persona: DraftObject;
  personas?: DraftObject[];
  elder_profile: DraftObject;
  elder_profiles?: DraftObject[];
  family_profiles: DraftObject[];
  memories: DraftObject[];
  dedup?: DedupSuggestion;
  merge_preview?: string[];
};

export type ImportResponse = {
  ok: boolean;
  imported: {
    persona: number;
    elder_profile: number;
    family_profiles: number;
    memories: number;
  };
};

export type ChatResponse = {
  text: string;
  audio_url?: string | null;
  debug: Record<string, unknown>;
};

export type ChatHistoryMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  text: string;
  audio_storage_path?: string;
  tts_provider?: string;
  persona_id?: string;
  voice_profile_id?: string;
  asr_provider?: string;
  created_at?: string;
};

export type ChatTurn = {
  id: string;
  session_id: string;
  elder_id?: string;
  elder_display_name?: string;
  persona_id?: string;
  persona_display_name?: string;
  voice_profile_id?: string;
  voice_display_name?: string;
  user_text: string;
  assistant_text: string;
  audio_url?: string;
  asr_provider?: string;
  tts_provider?: string;
  created_at?: string;
};

export type MemoryCandidateResponse = {
  candidate: {
    content?: string;
    memory_type?: string;
    subject?: string;
    family_members?: string[];
    emotion_tags?: string[];
    topic_tags?: string[];
    intimacy_weight?: number;
  };
  source: "parser" | "fallback" | string;
};

export type TextToSpeechResponse = {
  provider: string;
  audio_url: string;
};

export type FamilyContext = {
  family: {
    id: string;
    name: string;
    created_by?: string;
  };
  membership: {
    id: string;
    family_id: string;
    user_id: string;
    role: "owner" | "editor" | "viewer";
  };
};

export type CloudRecord = Record<string, unknown> & {
  id?: string;
  family_id?: string;
};

export type VoiceSample = CloudRecord & {
  id: string;
  storage_path: string;
  bucket?: string;
  sample_source: string;
  status: "pending_upload" | "ready" | "failed";
  created_by?: string;
  voice_profile_id?: string | null;
};

export type VoiceProfile = CloudRecord & {
  id: string;
  display_name: string;
  provider: string;
  provider_voice_id: string;
  status: "creating" | "ready" | "failed";
  consent_confirmed: boolean;
  demo_audio_url?: string;
  sample_source?: string;
  voice_type?: "preset" | "prepaid" | "postpaid";
  persona_id?: string;
};

export type VoiceStatusResponse = {
  profile_id: string;
  provider: string;
  provider_voice_id: string;
  voice_status: {
    code?: number;
    message?: string;
    available_training_times?: number;
    create_time?: number;
    language?: number;
    speaker_id?: string;
    status?: number;
    speaker_status?: {
      model_type?: number;
      demo_audio?: string;
    }[];
  };
};

export type ElderVoiceChatResponse = {
  recognized_text: string;
  reply_text: string;
  audio_url?: string | null;
  session_id: string;
  message_id?: string;
  matched_persona: {
    persona_id: string;
    display_name: string;
    confidence: number;
  };
  status: "ok" | "asr_empty" | "context_error" | string;
  debug: Record<string, unknown>;
};

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const bodyText = await response.text();
    let detail = bodyText;
    try {
      const parsed = JSON.parse(bodyText) as { detail?: unknown };
      detail = typeof parsed.detail === "string" ? parsed.detail : bodyText;
    } catch {
      detail = bodyText;
    }
    throw new Error(detail || `Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function withUser(init?: RequestInit): RequestInit {
  const token = getAuthToken();
  return {
    ...init,
    headers: {
      ...(token ? { "X-User-Token": token } : {}),
      ...init?.headers,
    },
  };
}

export function fetchCurrentFamily(): Promise<FamilyContext> {
  return requestJson<FamilyContext>("/api/family/current", withUser());
}

export function createFamily(payload: { name: string }): Promise<FamilyContext> {
  return requestJson<FamilyContext>(
    "/api/family",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function fetchCloudElder(familyId: string): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    `/api/elders/current?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function saveCloudElder(payload: CloudRecord & { family_id: string }): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    "/api/elders/current",
    withUser({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export function fetchCloudFamilyProfiles(familyId: string): Promise<CloudRecord[]> {
  return requestJson<CloudRecord[]>(
    `/api/family-profiles?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function createCloudFamilyProfile(payload: CloudRecord & { family_id: string }): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    "/api/family-profiles",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function updateCloudFamilyProfile(
  profileId: string,
  payload: CloudRecord & { family_id: string },
): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    `/api/family-profiles/${encodeURIComponent(profileId)}`,
    withUser({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export function deleteCloudFamilyProfile(profileId: string, familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/family-profiles/${encodeURIComponent(profileId)}?family_id=${encodeURIComponent(familyId)}`,
    withUser({
      method: "DELETE",
    }),
  );
}

export function fetchCloudMemories(familyId: string): Promise<CloudRecord[]> {
  return requestJson<CloudRecord[]>(
    `/api/memories?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function createCloudMemory(payload: CloudRecord & { family_id: string }): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    "/api/memories",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function updateCloudMemory(
  memoryId: string,
  payload: CloudRecord & { family_id: string },
): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    `/api/memories/${encodeURIComponent(memoryId)}`,
    withUser({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export function deleteCloudMemory(memoryId: string, familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/memories/${encodeURIComponent(memoryId)}?family_id=${encodeURIComponent(familyId)}`,
    withUser({
      method: "DELETE",
    }),
  );
}

export function fetchCloudPersonas(familyId: string): Promise<CloudRecord[]> {
  return requestJson<CloudRecord[]>(
    `/api/personas?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function createCloudPersona(payload: CloudRecord & { family_id: string }): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    "/api/personas",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function updateCloudPersona(
  personaId: string,
  payload: CloudRecord & { family_id: string },
): Promise<CloudRecord> {
  return requestJson<CloudRecord>(
    `/api/personas/${encodeURIComponent(personaId)}`,
    withUser({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export function deleteCloudPersona(personaId: string, familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/personas/${encodeURIComponent(personaId)}?family_id=${encodeURIComponent(familyId)}`,
    withUser({
      method: "DELETE",
    }),
  );
}

export function deleteCloudElder(familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/elders/current?family_id=${encodeURIComponent(familyId)}`,
    withUser({
      method: "DELETE",
    }),
  );
}

export function createVoiceUploadIntent(payload: {
  family_id: string;
  filename: string;
  sample_source: "upload" | "recording";
}): Promise<VoiceSample> {
  return requestJson<VoiceSample>(
    "/api/voices/upload-intent",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function fetchVoiceSamples(familyId: string): Promise<VoiceSample[]> {
  return requestJson<VoiceSample[]>(
    `/api/voices/samples?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function fetchVoiceProfiles(familyId: string): Promise<VoiceProfile[]> {
  return requestJson<VoiceProfile[]>(
    `/api/voices/profiles?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function updateVoiceProfile(
  profileId: string,
  payload: {
    family_id: string;
    persona_id: string;
  },
): Promise<VoiceProfile> {
  return requestJson<VoiceProfile>(
    `/api/voices/profiles/${encodeURIComponent(profileId)}`,
    withUser({
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
}

export function parseProfileText(payload: {
  family_id: string;
  text: string;
  perspective: "family" | "elder";
}): Promise<ParsedDraft> {
  return requestJson<ParsedDraft>("/api/parse", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importParsedData(payload: ParsedDraft & { family_id: string }): Promise<ImportResponse> {
  return requestJson<ImportResponse>("/api/import", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchRecords(): Promise<ParsedDraft> {
  return requestJson<ParsedDraft>("/api/records");
}

export function deleteMemory(memoryId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/memories/${encodeURIComponent(memoryId)}`, {
    method: "DELETE",
  });
}

export function deleteFamilyProfile(name: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/family-profiles/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
}

export function deleteElderProfile(fullName: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/elders/${encodeURIComponent(fullName)}`, {
    method: "DELETE",
  });
}

export function deletePersona(roleLabel: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/personas/${encodeURIComponent(roleLabel)}`, {
    method: "DELETE",
  });
}

export function sendChat(payload: {
  family_id: string;
  elder_id: string;
  persona_id: string;
  text: string;
  voice_profile_id?: string;
}): Promise<ChatResponse> {
  return requestJson<ChatResponse>(
    "/api/chat",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function fetchChatHistory(familyId: string): Promise<ChatHistoryMessage[]> {
  return requestJson<ChatHistoryMessage[]>(
    `/api/chat/history?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function fetchChatTurns(familyId: string): Promise<ChatTurn[]> {
  return requestJson<ChatTurn[]>(
    `/api/chat/turns?family_id=${encodeURIComponent(familyId)}`,
    withUser(),
  );
}

export function generateMemoryCandidate(payload: {
  family_id: string;
  user_text: string;
  assistant_text: string;
  persona_display_name?: string;
  elder_display_name?: string;
}): Promise<MemoryCandidateResponse> {
  return requestJson<MemoryCandidateResponse>(
    "/api/chat/memory-candidate",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export async function sendElderVoiceChat(payload: {
  family_id: string;
  elder_id?: string;
  persona_id?: string;
  voice_profile_id?: string;
  client_session_id?: string;
  audio_format: string;
  audio_file: Blob;
}): Promise<ElderVoiceChatResponse> {
  const formData = new FormData();
  formData.set("family_id", payload.family_id);
  formData.set("elder_id", payload.elder_id ?? "");
  formData.set("persona_id", payload.persona_id ?? "");
  formData.set("voice_profile_id", payload.voice_profile_id ?? "");
  formData.set("client_session_id", payload.client_session_id ?? "");
  formData.set("audio_format", payload.audio_format);
  formData.set("audio_file", payload.audio_file, `elder-speech.${payload.audio_format}`);

  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/elder/voice-chat`, {
    method: "POST",
    headers: {
      ...(token ? { "X-User-Token": token } : {}),
    },
    body: formData,
  });

  if (!response.ok) {
    const bodyText = await response.text();
    throw new Error(bodyText || `Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<ElderVoiceChatResponse>;
}

export function cloneVoice(payload: {
  family_id: string;
  display_name: string;
  sample_ids: string[];
  consent_confirmed: boolean;
  sample_source?: "upload" | "recording" | "preset" | "prepaid";
  audio_data_base64?: string;
  audio_format?: string;
  speaker_id?: string;
  custom_speaker_id?: string;
  prompt_text?: string;
  language?: number;
  demo_text?: string;
  enable_audio_denoise?: boolean;
  voice_type?: "preset" | "prepaid" | "postpaid";
}): Promise<VoiceProfile> {
  return requestJson<VoiceProfile>(
    "/api/voices/clone",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function queryVoiceStatus(payload: {
  family_id: string;
  voice_profile_id: string;
}): Promise<VoiceStatusResponse> {
  return requestJson<VoiceStatusResponse>(
    "/api/voices/status",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function upgradeVoice(payload: {
  family_id: string;
  voice_profile_id: string;
}): Promise<VoiceStatusResponse> {
  return requestJson<VoiceStatusResponse>(
    "/api/voices/upgrade",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}

export function deleteVoiceProfile(profileId: string, familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/voices/profiles/${encodeURIComponent(profileId)}?family_id=${encodeURIComponent(familyId)}`,
    withUser({
      method: "DELETE",
    }),
  );
}

export function synthesizeSpeech(payload: {
  family_id: string;
  voice_profile_id: string;
  text: string;
}): Promise<TextToSpeechResponse> {
  return requestJson<TextToSpeechResponse>(
    "/api/tts",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}
