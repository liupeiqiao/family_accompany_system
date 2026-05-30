# Voice UI Redesign & Voice Type Differentiation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the voice management page from a single flat technical layout into a SaaS-style sidebar navigation with three focused views (family voice library, import, create clone), add explicit `voice_type` differentiation, and implement type-aware delete behavior.

**Architecture:** Backend adds `voice_type` field to VoiceProfile data model and a unified `delete_voice_profile` CloudRepository method that switches between hard-delete (preset/prepaid) and soft-delete (postpaid) based on type. Frontend restructures `page.tsx` into a sidebar-layout shell with three content panels rendered conditionally via state toggle.

**Tech Stack:** Python/FastAPI backend, React/Next.js frontend with TypeScript, existing InMemoryCloudRepository + SupabaseCloudRepository patterns.

---

### Task 1: Add `voice_type` to the request schema and handler

**Files:**
- Modify: `api/schemas.py:74-87`
- Modify: `api/handlers.py:345-400`

- [ ] **Step 1: Add `voice_type` field to `VoiceCloneCreateRequest`**

In `api/schemas.py`, add the field after `enable_audio_denoise`:

```python
class VoiceCloneCreateRequest(BaseModel):
    family_id: str
    display_name: str = "My voice"
    sample_ids: list[str] = Field(default_factory=list)
    consent_confirmed: bool = False
    sample_source: str = "upload"  # upload / recording / preset
    audio_data_base64: str = ""
    audio_format: str = "wav"
    speaker_id: str = ""
    custom_speaker_id: str = ""
    prompt_text: str = ""
    language: int = 0
    demo_text: str = ""
    enable_audio_denoise: bool | None = None
    voice_type: str = ""  # "preset" | "prepaid" | "postpaid"
```

- [ ] **Step 2: Pass `voice_type` through `handle_clone_voice`**

In `api/handlers.py`, find the `handle_clone_voice` function. In the `create_voice_profile` call inside `operation()`, add `voice_type` to the payload dict:

```python
profile = repo.create_voice_profile(
    family_id=request.family_id,
    user_id=user_id,
    payload={
        "display_name": request.display_name,
        "provider": clone_result.provider,
        "provider_voice_id": clone_result.provider_voice_id,
        "status": "ready",
        "consent_confirmed": request.consent_confirmed,
        "sample_source": sample_source,
        "sample_ids": request.sample_ids,
        "demo_audio_url": clone_result.demo_audio_url,
        "voice_type": request.voice_type or _derive_voice_type(request, sample_source),
    },
)
```

Add the helper function after `_is_cloned_voice_profile`:

```python
def _derive_voice_type(request: VoiceCloneCreateRequest, sample_source: str) -> str:
    if sample_source == "preset" and not request.audio_data_base64:
        return "preset"
    if request.speaker_id and not request.custom_speaker_id:
        if request.speaker_id.startswith("S_") or request.speaker_id.startswith("icl_"):
            return "prepaid"
    if request.custom_speaker_id:
        return "postpaid"
    if request.audio_data_base64:
        return "postpaid"
    return "prepaid"
```

- [ ] **Step 3: Run existing voice tests to ensure nothing broke**

```bash
python -m pytest tests/test_voice_phase3.py -v
```

Expected: All 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/schemas.py api/handlers.py
git commit -m "feat(voice): add voice_type field to clone request schema and handler"
```

---

### Task 2: Write test for voice_type derivation logic

**Files:**
- Modify: `tests/test_voice_phase3.py`

- [ ] **Step 1: Add a test for `_derive_voice_type`**

Add to `tests/test_voice_phase3.py`:

```python
def test_derive_voice_type_correctly_classifies_requests():
    from api.handlers import _derive_voice_type
    from api.schemas import VoiceCloneCreateRequest

    preset = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="preset",
        audio_data_base64="",
        speaker_id="",
        custom_speaker_id="",
    )
    assert _derive_voice_type(preset, "preset") == "preset"

    prepaid = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="upload",
        audio_data_base64="ZmFrZQ==",
        speaker_id="S_test_001",
        custom_speaker_id="",
    )
    assert _derive_voice_type(prepaid, "upload") == "prepaid"

    postpaid = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="upload",
        audio_data_base64="ZmFrZQ==",
        speaker_id="custom_speaker_id",
        custom_speaker_id="my_custom_voice_001",
    )
    assert _derive_voice_type(postpaid, "upload") == "postpaid"
```

- [ ] **Step 2: Run the test**

```bash
python -m pytest tests/test_voice_phase3.py::test_derive_voice_type_correctly_classifies_requests -v
```

Expected: FAIL (function not defined) → then add it in Task 1 Step 2, or PASS if already added.

- [ ] **Step 3: Commit**

```bash
git add tests/test_voice_phase3.py
git commit -m "test(voice): add voice_type derivation unit test"
```

---

### Task 3: Add `delete_voice_profile` to CloudRepository interface and InMemory impl

**Files:**
- Modify: `productization/cloud_repository.py:100-101` (interface)
- Modify: `productization/cloud_repository.py:301-305` (InMemory impl)

- [ ] **Step 1: Add abstract method to `CloudRepository` interface**

After `hide_voice_profile` in the abstract class, add:

```python
def delete_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
    ...
```

- [ ] **Step 2: Implement in `InMemoryCloudRepository`**

Replace the existing `hide_voice_profile` method body, adding a new `delete_voice_profile` alongside it:

```python
def delete_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
    self._require_editor(family_id, user_id)
    profile = self._get_family_record(self._voice_profiles, family_id, profile_id)
    voice_type = profile.get("voice_type", "")
    if voice_type in ("preset", "prepaid"):
        # Hard delete: remove profile + cascade delete linked samples
        sample_ids_to_delete = [
            sid for sid, s in self._voice_samples.items()
            if s.get("voice_profile_id") == profile_id
        ]
        for sid in sample_ids_to_delete:
            del self._voice_samples[sid]
        del self._voice_profiles[profile_id]
    else:
        # Soft delete (postpaid): hide from list
        profile["status"] = "hidden"
        profile["updated_by"] = user_id
```

Keep `hide_voice_profile` as-is (it will be removed later).

- [ ] **Step 3: Run existing tests**

```bash
python -m pytest tests/test_voice_phase3.py -v
```

Expected: All tests pass (existing hide behavior preserved).

- [ ] **Step 4: Commit**

```bash
git add productization/cloud_repository.py
git commit -m "feat(voice): add delete_voice_profile to CloudRepository with type-aware logic"
```

---

### Task 4: Add test for delete_voice_profile and implement handler

**Files:**
- Modify: `tests/test_voice_phase3.py`
- Modify: `api/handlers.py:569-576`
- Modify: `api/main.py:284-290`

- [ ] **Step 1: Add test for hard-delete vs soft-delete behavior**

Add to `tests/test_voice_phase3.py`:

```python
def test_delete_voice_profile_hard_deletes_preset_and_prepaid(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Test", user_id="owner")

    # Create a sample first
    sample = repo.create_voice_sample_upload_intent(
        family_id=family["id"], user_id="owner", filename="test.wav", sample_source="upload"
    )

    # Create preset profile linked to sample
    preset = repo.create_voice_profile(
        family_id=family["id"], user_id="owner",
        payload={
            "display_name": "Preset Voice", "provider": "doubao",
            "provider_voice_id": "BV001", "status": "ready",
            "consent_confirmed": True, "sample_source": "preset",
            "sample_ids": [sample["id"]], "voice_type": "preset",
        },
    )
    # Create prepaid profile
    prepaid = repo.create_voice_profile(
        family_id=family["id"], user_id="owner",
        payload={
            "display_name": "Prepaid Voice", "provider": "doubao",
            "provider_voice_id": "S_test_001", "status": "ready",
            "consent_confirmed": True, "sample_source": "upload",
            "sample_ids": [], "voice_type": "prepaid",
        },
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    client = TestClient(app)

    # Hard delete presets
    resp = client.delete(
        f"/api/voices/profiles/{preset['id']}?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert resp.status_code == 200
    profiles_after = client.get(
        f"/api/voices/profiles?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    profile_ids = [p["id"] for p in profiles_after.json()]
    assert preset["id"] not in profile_ids
    # Linked sample should be cascade-deleted
    samples = repo.list_voice_samples(family_id=family["id"], user_id="owner")
    sample_ids = [s["id"] for s in samples]
    assert sample["id"] not in sample_ids

    # Hard delete prepaid
    resp2 = client.delete(
        f"/api/voices/profiles/{prepaid['id']}?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert resp2.status_code == 200
    profiles_final = client.get(
        f"/api/voices/profiles?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert prepaid["id"] not in [p["id"] for p in profiles_final.json()]


def test_delete_voice_profile_soft_deletes_postpaid(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Test", user_id="owner")
    postpaid = repo.create_voice_profile(
        family_id=family["id"], user_id="owner",
        payload={
            "display_name": "Postpaid Voice", "provider": "doubao",
            "provider_voice_id": "custom_voice_001", "status": "ready",
            "consent_confirmed": True, "sample_source": "upload",
            "sample_ids": [], "voice_type": "postpaid",
        },
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    client = TestClient(app)

    resp = client.delete(
        f"/api/voices/profiles/{postpaid['id']}?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert resp.status_code == 200
    # Profile should be hidden (filtered from list)
    profiles = client.get(
        f"/api/voices/profiles?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert profiles.json() == []
    # But still exists in repo with status "hidden"
    all_profiles = repo._voice_profiles
    assert postpaid["id"] in all_profiles
    assert all_profiles[postpaid["id"]]["status"] == "hidden"
```

- [ ] **Step 2: Replace `handle_hide_voice_profile` with `handle_delete_voice_profile` in handlers.py**

```python
def handle_delete_voice_profile(profile_id: str, family_id: str, user_id: str) -> DeleteResponse:
    _call_cloud(
        lambda: get_cloud_repository().delete_voice_profile(
            family_id=family_id,
            user_id=user_id,
            profile_id=profile_id,
        )
    )
    return DeleteResponse(ok=True)
```

- [ ] **Step 3: Update route in `api/main.py`**

Change the existing import and route:

```python
# Replace handle_hide_voice_profile import with handle_delete_voice_profile
from .handlers import (
    ...
    handle_delete_voice_profile,  # was handle_hide_voice_profile
    ...
)

# Update the endpoint
@app.delete("/api/voices/profiles/{profile_id}", response_model=DeleteResponse)
def delete_voice_profile_endpoint(
    profile_id: str,
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> DeleteResponse:
    return handle_delete_voice_profile(profile_id, family_id, x_user_id)
```

- [ ] **Step 4: Run the new tests**

```bash
python -m pytest tests/test_voice_phase3.py::test_delete_voice_profile_hard_deletes_preset_and_prepaid tests/test_voice_phase3.py::test_delete_voice_profile_soft_deletes_postpaid -v
```

Expected: Both PASS.

- [ ] **Step 5: Run all voice tests**

```bash
python -m pytest tests/test_voice_phase3.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_voice_phase3.py api/handlers.py api/main.py
git commit -m "feat(voice): replace hide with type-aware delete endpoint"
```

---

### Task 5: Add `delete_voice_profile` to SupabaseCloudRepository

**Files:**
- Modify: `productization/cloud_repository.py` (SupabaseCloudRepository class)

- [ ] **Step 1: Implement `delete_voice_profile` in `SupabaseCloudRepository`**

Find the `SupabaseCloudRepository` class and add the new method after `hide_voice_profile`:

```python
def delete_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
    self._require_editor(family_id, user_id)
    profile = self._get_family_record(self._voice_profiles_table_name(), family_id, profile_id)
    voice_type = str(profile.get("voice_type", ""))
    if voice_type in ("preset", "prepaid"):
        # Hard delete: remove linked samples first, then profile
        self._request(
            f"voice_samples?voice_profile_id=eq.{profile_id}",
            method="DELETE",
        )
        self._request(
            f"{self._voice_profiles_table_name()}?id=eq.{profile_id}&family_id=eq.{family_id}",
            method="DELETE",
        )
    else:
        # Soft delete (postpaid)
        self._request(
            f"{self._voice_profiles_table_name()}?id=eq.{profile_id}&family_id=eq.{family_id}",
            method="PATCH",
            payload={"status": "hidden", "updated_by": user_id},
        )
```

Note: Add a helper `_voice_profiles_table_name()` if not already present (check existing pattern — if the table name is `voice_profiles`, use it directly).

- [ ] **Step 2: Commit**

```bash
git add productization/cloud_repository.py
git commit -m "feat(voice): add delete_voice_profile to SupabaseCloudRepository"
```

---

### Task 6: Update frontend API layer

**Files:**
- Modify: `web/src/lib/backend-api.ts`

- [ ] **Step 1: Add `voice_type` to `VoiceProfile` type**

```typescript
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
};
```

- [ ] **Step 2: Add `deleteVoiceProfile` function, update `cloneVoice`**

```typescript
export function deleteVoiceProfile(profileId: string, familyId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/voices/profiles/${encodeURIComponent(profileId)}?family_id=${encodeURIComponent(familyId)}`,
    withUser({ method: "DELETE" }),
  );
}
```

Update `cloneVoice` params to include `voice_type`:

```typescript
export function cloneVoice(payload: {
  family_id: string;
  display_name: string;
  sample_ids: string[];
  consent_confirmed: boolean;
  sample_source?: "upload" | "recording" | "preset";
  audio_data_base64?: string;
  audio_format?: string;
  speaker_id?: string;
  custom_speaker_id?: string;
  prompt_text?: string;
  language?: number;
  demo_text?: string;
  enable_audio_denoise?: boolean;
  voice_type?: "preset" | "prepaid" | "postpaid";  // new
}): Promise<VoiceProfile> {
  return requestJson<VoiceProfile>(
    "/api/voices/clone",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}
```

- [ ] **Step 3: Remove `hideVoiceProfile` export (replaced by `deleteVoiceProfile`)**

Remove the existing `hideVoiceProfile` function.

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/backend-api.ts
git commit -m "feat(web): add voice_type, deleteVoiceProfile API, update cloneVoice"
```

---

### Task 7: Build page shell — layout, nav, and top banner

**Files:**
- Modify: `web/src/app/voices/page.tsx`

- [ ] **Step 1: Replace the entire page with the new shell structure**

Rewrite `page.tsx` with the new layout. Keep the existing import of `backend-api` functions, but restructure the component tree:

```tsx
"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import {
  FamilyContext,
  VoiceProfile,
  VoiceStatusResponse,
  cloneVoice,
  fetchCurrentFamily,
  fetchVoiceProfiles,
  deleteVoiceProfile,
  queryVoiceStatus,
  upgradeVoice,
} from "../../lib/backend-api";

type NavTab = "library" | "import" | "clone";
type VoiceManagementState = { isLoading?: boolean; error?: string; result?: VoiceStatusResponse };

export default function VoicesPage() {
  const [activeTab, setActiveTab] = useState<NavTab>("library");
  const [familyContext, setFamilyContext] = useState<FamilyContext | null>(null);
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [voiceManagement, setVoiceManagement] = useState<Record<string, VoiceManagementState>>({});

  useEffect(() => { void loadVoiceSpace(); }, []);

  async function loadVoiceSpace() {
    setIsLoading(true);
    setError("");
    try {
      const context = await fetchCurrentFamily();
      setFamilyContext(context);
      const nextProfiles = await fetchVoiceProfiles(context.family.id);
      setProfiles(nextProfiles);
    } catch (err) {
      setFamilyContext(null);
      setError(err instanceof Error ? err.message : "声音空间加载失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDelete(profile: VoiceProfile) {
    if (!familyContext) return;
    setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
    try {
      await deleteVoiceProfile(profile.id, familyContext.family.id);
      setProfiles((c) => c.filter((p) => p.id !== profile.id));
      setMessage("音色已删除。");
    } catch (err) {
      setVoiceManagement((c) => ({
        ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "删除失败" },
      }));
    }
  }

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="shell">
      <DoubaoBanner />
      <div className="voiceLayout">
        <VoiceNav activeTab={activeTab} onSelect={setActiveTab} />
        <div className="voiceContent">
          {isLoading ? <p className="helperText">正在加载...</p> : null}
          {error && !familyContext ? <FamilyMissingState error={error} /> : null}
          {familyContext && activeTab === "library" && (
            <FamilyVoiceLibrary
              profiles={profiles}
              canWrite={Boolean(canWrite)}
              management={voiceManagement}
              message={message}
              onDelete={handleDelete}
              onQuery={(profile) => { /* query logic */ }}
              onUpgrade={(profile) => { /* upgrade logic */ }}
            />
          )}
          {familyContext && activeTab === "import" && (
            <ImportVoice
              familyId={familyContext.family.id}
              canWrite={Boolean(canWrite)}
              onImported={(profile) => {
                setProfiles((c) => [profile, ...c]);
                setMessage("音色导入成功。");
                setActiveTab("library");
              }}
              onError={setError}
            />
          )}
          {familyContext && activeTab === "clone" && (
            <CreateCloneVoice
              familyId={familyContext.family.id}
              canWrite={Boolean(canWrite)}
              onCreated={(profile) => {
                setProfiles((c) => [profile, ...c]);
                setMessage("复刻音色创建成功。");
                setActiveTab("library");
              }}
              onError={setError}
            />
          )}
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Add the layout CSS classes via inline style or a CSS module**

The existing page likely uses `shell`, `importSection`, etc. The new layout needs `.voiceLayout` (flex row) and `.voiceContent` (flex 1). Add a `<style jsx>` block or use global CSS. For now, use inline styles or add to existing global styles.

- [ ] **Step 3: Add stub sub-components**

At the bottom of the same file, add stub components that will be filled in later tasks:

```tsx
function DoubaoBanner() {
  return (
    <div className="doubaoBanner">
      <span>使用豆包语音进行声音复刻与音色管理。</span>
      <a className="button buttonSecondary" href="https://console.volcengine.com/speech/new/voices?ResourceID=volc.seedicl.default&projectName=default" target="_blank" rel="noopener noreferrer">
        打开豆包语音控制台
      </a>
    </div>
  );
}

function VoiceNav({ activeTab, onSelect }: { activeTab: NavTab; onSelect: (tab: NavTab) => void }) {
  const tabs: { key: NavTab; label: string }[] = [
    { key: "library", label: "家人音色库" },
    { key: "import", label: "导入已有音色" },
    { key: "clone", label: "创建复刻音色" },
  ];
  return (
    <nav className="voiceNav">
      <h3>音色管理</h3>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          className={activeTab === tab.key ? "navItemActive" : "navItem"}
          onClick={() => onSelect(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function FamilyMissingState({ error }: { error: string }) {
  return (
    <section className="importSection">
      <h2>尚未创建家庭空间</h2>
      <p className="errorText">{error}</p>
      <Link className="button" href="/family">去创建家庭空间</Link>
    </section>
  );
}

function FamilyVoiceLibrary(props: {
  profiles: VoiceProfile[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  message: string;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  return <section className="importSection"><h2>家人音色库</h2><p>TBD</p></section>;
}

function ImportVoice(props: { familyId: string; canWrite: boolean; onImported: (p: VoiceProfile) => void; onError: (e: string) => void }) {
  return <section className="importSection"><h2>导入已有音色</h2><p>TBD</p></section>;
}

function CreateCloneVoice(props: { familyId: string; canWrite: boolean; onCreated: (p: VoiceProfile) => void; onError: (e: string) => void }) {
  return <section className="importSection"><h2>创建复刻音色</h2><p>TBD</p></section>;
}
```

- [ ] **Step 4: Verify the page renders (no TypeScript errors)**

```bash
cd web && npx tsc --noEmit src/app/voices/page.tsx 2>&1 | head -20
```

Expected: No type errors (or only pre-existing ones unrelated to our changes).

- [ ] **Step 5: Commit**

```bash
git add web/src/app/voices/page.tsx
git commit -m "feat(web): restructure voices page shell with sidebar nav"
```

---

### Task 8: Implement FamilyVoiceLibrary component

**Files:**
- Modify: `web/src/app/voices/page.tsx`

- [ ] **Step 1: Replace the stub `FamilyVoiceLibrary` with full implementation**

```tsx
function FamilyVoiceLibrary(props: {
  profiles: VoiceProfile[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  message: string;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  const { profiles, canWrite, management, message, onDelete, onQuery, onUpgrade } = props;
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const filtered = profiles.filter((p) => {
    if (search && !p.display_name.toLowerCase().includes(search.toLowerCase())) return false;
    if (typeFilter !== "all" && p.voice_type !== typeFilter) return false;
    return true;
  });

  return (
    <section className="importSection wide">
      <h2>家人音色库</h2>
      <div className="toolbar">
        <input
          placeholder="搜索音色名称..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">全部</option>
          <option value="preset">预置音色</option>
          <option value="prepaid">已导入</option>
          <option value="postpaid">已复刻</option>
        </select>
      </div>
      {message ? <p className="successText">{message}</p> : null}
      {filtered.length === 0 ? (
        <p className="emptyState">还没有音色档案</p>
      ) : (
        <div className="voiceGrid">
          {filtered.map((profile) => (
            <VoiceCard
              key={profile.id}
              profile={profile}
              canWrite={canWrite}
              management={management}
              onDelete={onDelete}
              onQuery={onQuery}
              onUpgrade={onUpgrade}
            />
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Implement `VoiceCard` sub-component**

```tsx
function VoiceCard(props: {
  profile: VoiceProfile;
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  const { profile, canWrite, management, onDelete, onQuery, onUpgrade } = props;
  const [speakerIdExpanded, setSpeakerIdExpanded] = useState(false);
  const state = management[profile.id] ?? {};
  const cloudStatus = state.result?.voice_status;

  const typeLabel = profile.voice_type === "preset" ? "预置音色"
    : profile.voice_type === "prepaid" ? "已导入"
    : profile.voice_type === "postpaid" ? "已复刻" : "";
  const typeClass = profile.voice_type === "preset" ? "tagPreset"
    : profile.voice_type === "prepaid" ? "tagPrepaid"
    : "tagPostpaid";

  function confirmDelete() {
    const isPostpaid = profile.voice_type === "postpaid";
    const msg = isPostpaid
      ? `确认删除音色「${profile.display_name}」？\n\n该操作仅会将音色从当前系统中移除。\n\n豆包平台中的原始音色不会被删除，\n您仍然可以在豆包控制台中继续使用该音色。`
      : `确认删除音色「${profile.display_name}」？\n\n删除后将从当前家庭空间中永久移除。\n该操作不可恢复。`;
    if (window.confirm(msg)) {
      onDelete(profile);
    }
  }

  return (
    <article className="voiceCard">
      <div className="voiceCardHeader">
        <strong>{profile.display_name}</strong>
        {typeLabel ? <span className={`voiceTag ${typeClass}`}>{typeLabel}</span> : null}
      </div>
      <div className="voiceCardMeta">
        <span>创建时间: {new Date().toLocaleDateString()}</span>
      </div>
      <div className="voiceCardFooter">
        <span className="speakerIdRow">
          Speaker ID{" "}
          {speakerIdExpanded ? (
            <span>{profile.provider_voice_id} <button className="linkButton" onClick={() => setSpeakerIdExpanded(false)}>[收起]</button></span>
          ) : (
            <button className="linkButton" onClick={() => setSpeakerIdExpanded(true)}>[展开]</button>
          )}
        </span>
        <button
          className="buttonSecondary"
          disabled={!canWrite || state.isLoading}
          onClick={confirmDelete}
        >
          删除音色
        </button>
      </div>
      {cloudStatus ? (
        <div className="voiceCardStatus">
          <span>豆包状态：{formatDoubaoVoiceStatus(cloudStatus.status)}</span>
          {cloudStatus.available_training_times !== undefined ? (
            <span>剩余训练次数：{cloudStatus.available_training_times}</span>
          ) : null}
        </div>
      ) : null}
      {state.error ? <p className="errorText">{state.error}</p> : null}
    </article>
  );
}
```

- [ ] **Step 3: Keep the existing utility functions at module scope**

`formatDoubaoVoiceStatus`, `isValidCustomSpeakerId`, `isValidPrepaidSpeakerId`, `readFileAsBase64`, `audioFormatFromFilename` — these were in the original file; keep them since ImportVoice and CreateCloneVoice need them.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/voices/page.tsx
git commit -m "feat(web): implement FamilyVoiceLibrary with card grid and delete flow"
```

---

### Task 9: Implement ImportVoice component

**Files:**
- Modify: `web/src/app/voices/page.tsx`

- [ ] **Step 1: Replace the stub `ImportVoice` with full implementation**

```tsx
function ImportVoice(props: {
  familyId: string;
  canWrite: boolean;
  onImported: (p: VoiceProfile) => void;
  onError: (e: string) => void;
}) {
  const { familyId, canWrite, onImported, onError } = props;
  const [importType, setImportType] = useState<"preset" | "prepaid">("preset");
  const [displayName, setDisplayName] = useState("");
  const [speakerId, setSpeakerId] = useState("");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!displayName.trim()) return;
    if (importType === "prepaid" && !isValidPrepaidSpeakerId(speakerId.trim())) {
      onError("预付费 speaker_id 通常应为 S_ 或 icl_ 开头。");
      return;
    }
    setIsSubmitting(true);
    try {
      const profile = await cloneVoice({
        family_id: familyId,
        display_name: displayName.trim(),
        sample_ids: [],
        consent_confirmed: consentConfirmed,
        sample_source: importType === "preset" ? "preset" : "upload",
        speaker_id: importType === "prepaid" ? speakerId.trim() : "",
        voice_type: importType,
      });
      onImported(profile);
    } catch (err) {
      onError(err instanceof Error ? err.message : "导入音色失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="importSection">
      <h2>导入已有音色</h2>
      <p className="helperText">
        如果您已经拥有豆包语音中的音色，可直接导入已有 Speaker ID，无需重新进行声音复刻。
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          <span>音色类型</span>
          <select value={importType} onChange={(e) => setImportType(e.target.value as "preset" | "prepaid")}>
            <option value="preset">预置音色</option>
            <option value="prepaid">预付费 Speaker ID</option>
          </select>
        </label>
        <label>
          <span>音色名称</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="例如：妈妈的声音" />
        </label>
        {importType === "prepaid" ? (
          <label>
            <span>Speaker ID</span>
            <input
              value={speakerId}
              onChange={(e) => setSpeakerId(e.target.value)}
              placeholder="例如 S_example"
            />
          </label>
        ) : null}
        <label className="voiceConsent">
          <input checked={consentConfirmed} onChange={(e) => setConsentConfirmed(e.target.checked)} type="checkbox" />
          <span>我确认此声音将用于本家庭空间的语音陪伴。</span>
        </label>
        <button type="submit" disabled={!canWrite || isSubmitting || !consentConfirmed || !displayName.trim()}>
          {isSubmitting ? "添加中..." : "添加音色"}
        </button>
      </form>
    </section>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/app/voices/page.tsx
git commit -m "feat(web): implement ImportVoice form"
```

---

### Task 10: Implement CreateCloneVoice component

**Files:**
- Modify: `web/src/app/voices/page.tsx`

- [ ] **Step 1: Replace the stub `CreateCloneVoice` with full implementation**

```tsx
function CreateCloneVoice(props: {
  familyId: string;
  canWrite: boolean;
  onCreated: (p: VoiceProfile) => void;
  onError: (e: string) => void;
}) {
  const { familyId, canWrite, onCreated, onError } = props;
  const [displayName, setDisplayName] = useState("我的声音");
  const [selectedAudioFile, setSelectedAudioFile] = useState<File | null>(null);
  const [speakerMode, setSpeakerMode] = useState<"custom" | "prepaid">("custom");
  const [customSpeakerId, setCustomSpeakerId] = useState("");
  const [speakerId, setSpeakerId] = useState("");
  const [demoText, setDemoText] = useState("妈，我在呢。");
  const [language, setLanguage] = useState(0);
  const [enableAudioDenoise, setEnableAudioDenoise] = useState(false);
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [demoAudioUrl, setDemoAudioUrl] = useState("");
  const [paramsExpanded, setParamsExpanded] = useState(true);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedAudioFile) return;
    setIsSubmitting(true);
    try {
      if (selectedAudioFile.size > 10 * 1024 * 1024) throw new Error("声音样本不能超过 10MB。");
      const audioDataBase64 = await readFileAsBase64(selectedAudioFile);
      const audioFormat = audioFormatFromFilename(selectedAudioFile.name);
      const nextCustomSpeakerId = customSpeakerId.trim();
      const nextSpeakerId = speakerMode === "custom" ? "custom_speaker_id" : speakerId.trim();
      if (speakerMode === "custom" && !isValidCustomSpeakerId(nextCustomSpeakerId)) {
        throw new Error("后付费自定义音色 ID 必须至少 8 位，以字母开头，只能包含字母、数字、-、_，且不能以 - 或 _ 结尾。");
      }
      if (speakerMode === "prepaid" && !isValidPrepaidSpeakerId(nextSpeakerId)) {
        throw new Error("预付费 speaker_id 通常应为 S_ 或 icl_ 开头。后付费请切换到自定义音色 ID。");
      }
      const profile = await cloneVoice({
        family_id: familyId,
        display_name: displayName.trim() || "我的声音",
        sample_ids: [],
        consent_confirmed: consentConfirmed,
        sample_source: "upload",
        audio_data_base64: audioDataBase64,
        audio_format: audioFormat,
        speaker_id: nextSpeakerId,
        custom_speaker_id: speakerMode === "custom" ? nextCustomSpeakerId : "",
        language,
        demo_text: demoText.trim(),
        enable_audio_denoise: enableAudioDenoise,
        voice_type: speakerMode === "prepaid" ? "prepaid" : "postpaid",
      });
      setDemoAudioUrl(profile.demo_audio_url ?? "");
      onCreated(profile);
    } catch (err) {
      onError(err instanceof Error ? err.message : "创建复刻音色失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="importSection">
      <h2>创建复刻音色</h2>
      <p className="warningText">后付费声音复刻可能产生额外费用，请提前查看官方计费规则。</p>
      <form onSubmit={handleSubmit}>
        <label>
          <span>音色名称</span>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <label>
          <span>音频上传</span>
          <input
            accept=".wav,.mp3,.ogg,.m4a,.aac,.pcm,audio/*"
            onChange={(e) => setSelectedAudioFile(e.target.files?.[0] ?? null)}
            type="file"
          />
        </label>
        <p className="helperText">建议 14-30 秒、低噪声、单人单轨 wav/mp3 音频，文件不超过 10MB。</p>
        <div className="collapsibleSection">
          <button type="button" className="linkButton" onClick={() => setParamsExpanded(!paramsExpanded)}>
            {paramsExpanded ? "▼" : "▶"} 复刻参数
          </button>
          {paramsExpanded ? (
            <>
              <label>
                <span>音色创建方式</span>
                <select value={speakerMode} onChange={(e) => setSpeakerMode(e.target.value as "custom" | "prepaid")}>
                  <option value="custom">后付费自定义音色 ID</option>
                  <option value="prepaid">预付费 speaker_id</option>
                </select>
              </label>
              {speakerMode === "custom" ? (
                <label>
                  <span>后付费自定义音色 ID</span>
                  <input value={customSpeakerId} onChange={(e) => setCustomSpeakerId(e.target.value)} placeholder="例如 family_voice_001" />
                </label>
              ) : (
                <label>
                  <span>预付费 speaker_id</span>
                  <input value={speakerId} onChange={(e) => setSpeakerId(e.target.value)} placeholder="例如 S_example" />
                </label>
              )}
              <label>
                <span>试听文本</span>
                <input value={demoText} onChange={(e) => setDemoText(e.target.value)} placeholder="4-300 字，建议贴近陪伴场景" />
              </label>
              <label>
                <span>语种</span>
                <select value={language} onChange={(e) => setLanguage(Number(e.target.value))}>
                  <option value={0}>中文</option>
                  <option value={1}>英文</option>
                  <option value={2}>日语</option>
                  <option value={3}>西班牙语</option>
                  <option value={4}>印尼语</option>
                  <option value={5}>葡萄牙语</option>
                  <option value={8}>韩语</option>
                </select>
              </label>
              <label className="voiceConsent">
                <input checked={enableAudioDenoise} onChange={(e) => setEnableAudioDenoise(e.target.checked)} type="checkbox" />
                <span>样本噪声较大时启用降噪；音频质量好时建议关闭以保留相似度。</span>
              </label>
            </>
          ) : null}
        </div>
        <label className="voiceConsent">
          <input checked={consentConfirmed} onChange={(e) => setConsentConfirmed(e.target.checked)} type="checkbox" />
          <span>我确认这是我本人的声音，用于本家庭空间的语音陪伴。</span>
        </label>
        <button
          type="submit"
          disabled={!canWrite || isSubmitting || !selectedAudioFile || !consentConfirmed}
        >
          {isSubmitting ? "训练中..." : "创建复刻音色"}
        </button>
        {demoAudioUrl ? (
          <div style={{ marginTop: 12 }}>
            <p className="helperText">试听复刻效果：</p>
            <audio controls src={demoAudioUrl} style={{ width: "100%" }}>当前浏览器不支持音频播放。</audio>
          </div>
        ) : null}
      </form>
    </section>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

Expected: No new type errors from our file.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/voices/page.tsx
git commit -m "feat(web): implement CreateCloneVoice form with collapsible params"
```

---

### Task 11: Add CSS styles for new components

**Files:**
- Modify: `web/src/app/globals.css` (or equivalent global stylesheet)

- [ ] **Step 1: Find the existing global stylesheet**

Check which CSS file contains the existing `.shell`, `.importSection`, `.voiceGrid` classes.

- [ ] **Step 2: Add new styles**

```css
/* Voice page layout */
.voiceLayout {
  display: flex;
  gap: 24px;
  min-height: calc(100vh - 120px);
}

.voiceNav {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.voiceNav h3 {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.navItem, .navItemActive {
  text-align: left;
  padding: 8px 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  background: none;
}

.navItem:hover { background: var(--bg-hover); }
.navItemActive { background: var(--primary-light); color: var(--primary); font-weight: 600; }

.voiceContent { flex: 1; min-width: 0; }

/* Banner */
.doubaoBanner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 13px;
}

/* Toolbar */
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar input { flex: 1; }

/* Voice cards */
.voiceCard {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voiceCardHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.voiceCardHeader strong { font-size: 16px; }

.voiceCardMeta { font-size: 12px; color: var(--text-secondary); }

.voiceCardFooter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.voiceCardStatus { font-size: 12px; color: var(--text-secondary); }

.speakerIdRow { display: flex; align-items: center; gap: 6px; }

/* Voice type tags */
.voiceTag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.tagPreset { background: #e8ecf4; color: #4a5f8a; }
.tagPrepaid { background: #e6f4ea; color: #2d6a4f; }
.tagPostpaid { background: #fdf0e0; color: #9a5d1a; }

/* Collapsible */
.collapsibleSection { margin: 8px 0; }

/* Link button */
.linkButton {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  text-decoration: underline;
  font-size: inherit;
  padding: 0;
}

/* Warning */
.warningText {
  background: #fff8e6;
  border: 1px solid #f0d77b;
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  color: #8a6d10;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/app/globals.css
git commit -m "style(web): add voice page layout and card styles"
```

---

### Task 12: Wire onQuery and onUpgrade into FamilyVoiceLibrary (integration)

**Files:**
- Modify: `web/src/app/voices/page.tsx`

- [ ] **Step 1: Add query/upgrade handlers in the page shell**

In `VoicesPage`, add the query and upgrade handler functions:

```tsx
async function handleQuery(profile: VoiceProfile) {
  if (!familyContext) return;
  setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
  try {
    const result = await queryVoiceStatus({
      family_id: familyContext.family.id,
      voice_profile_id: profile.id,
    });
    setVoiceManagement((c) => ({ ...c, [profile.id]: { isLoading: false, result } }));
  } catch (err) {
    setVoiceManagement((c) => ({
      ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "查询失败" },
    }));
  }
}

async function handleUpgrade(profile: VoiceProfile) {
  if (!familyContext) return;
  setVoiceManagement((c) => ({ ...c, [profile.id]: { ...c[profile.id], isLoading: true } }));
  try {
    const result = await upgradeVoice({
      family_id: familyContext.family.id,
      voice_profile_id: profile.id,
    });
    setVoiceManagement((c) => ({ ...c, [profile.id]: { isLoading: false, result } }));
    setMessage("音色升级请求已完成。");
  } catch (err) {
    setVoiceManagement((c) => ({
      ...c, [profile.id]: { ...c[profile.id], isLoading: false, error: err instanceof Error ? err.message : "升级失败" },
    }));
  }
}
```

Then update the `<FamilyVoiceLibrary ... />` JSX to pass `onQuery={handleQuery}` and `onUpgrade={handleUpgrade}` instead of the empty arrow functions.

- [ ] **Step 2: Update VoiceCard to show query/upgrade buttons**

Add after the `cloudStatus` display section in `VoiceCard`:

```tsx
<div className="actions" style={{ marginTop: 8 }}>
  <button disabled={state.isLoading} onClick={() => onQuery(profile)} type="button">
    {state.isLoading ? "查询中..." : "查询状态"}
  </button>
  <button disabled={!canWrite || state.isLoading} onClick={() => onUpgrade(profile)} type="button">
    升级统一管理
  </button>
</div>
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add web/src/app/voices/page.tsx
git commit -m "feat(web): wire query/upgrade actions in voice library"
```

---

### Task 13: Run full test suite and manual verification

**Files:**
- (none — verification only)

- [ ] **Step 1: Run backend voice tests**

```bash
python -m pytest tests/test_voice_phase3.py tests/test_voice_phase4_tts.py -v
```

Expected: All tests pass.

- [ ] **Step 2: Run all backend tests**

```bash
python -m pytest tests/ -v
```

Expected: All 13+ tests pass.

- [ ] **Step 3: Start dev server and verify visually**

```bash
# Terminal 1 (backend)
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2 (frontend)
cd web && npm run dev
```

Navigate to `http://localhost:3000/voices` and verify:
- Left sidebar navigation switches between three views
- Default view is "家人音色库"
- Card grid shows existing voice profiles with type tags
- Speaker ID expands/collapses on click
- Delete button shows correct confirmation dialog per voice_type
- Import form creates preset or prepaid voices
- Clone form creates postpaid/prepaid voices with collapsible params
- Doubao banner links to the Volcengine console

- [ ] **Step 4: Commit (if any cleanup needed)**

```bash
git add -A && git commit -m "chore: final cleanup and verification"
```

---

### Task 14: Remove unused code and final cleanup

**Files:**
- Modify: `web/src/app/voices/page.tsx`
- Modify: `web/src/lib/backend-api.ts`

- [ ] **Step 1: Remove unused imports and functions**

From `page.tsx`, remove:
- `createVoiceUploadIntent`, `fetchVoiceSamples` (sample management internalized)
- `VoiceSample` type (no longer displayed)
- `samples` state, `selectedSampleId`, `filename`, `sampleSource` states (sample creation removed)
- `onCreateSample`, `onCloneVoice`, `onCreatePresetVoice` functions (moved into sub-components)
- `VoiceList` component (samples no longer displayed)
- `onHideVoiceProfile` function (replaced by `handleDelete`)

From `backend-api.ts`, optionally mark `hideVoiceProfile` as deprecated if it was already removed.

- [ ] **Step 2: Verify nothing breaks**

```bash
cd web && npx tsc --noEmit 2>&1 | head -20
python -m pytest tests/test_voice_phase3.py -v
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore(voice): remove unused sample management UI and deprecated imports"
```
