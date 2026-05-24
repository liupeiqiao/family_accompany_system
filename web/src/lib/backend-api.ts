const API_BASE_URL =
  process.env.NEXT_PUBLIC_COMPANION_API_URL ?? "http://127.0.0.1:8000";

export type DraftObject = Record<string, unknown>;

export type ParsedDraft = {
  persona: DraftObject;
  personas?: DraftObject[];
  elder_profile: DraftObject;
  elder_profiles?: DraftObject[];
  family_profiles: DraftObject[];
  memories: DraftObject[];
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
