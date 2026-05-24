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

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`Backend request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function withUser(init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      "X-User-Id": "demo-user",
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
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function cloneVoice(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/voices/clone", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function synthesizeSpeech(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/tts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
