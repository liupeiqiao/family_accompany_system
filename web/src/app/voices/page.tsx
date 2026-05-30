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

  const canWrite = familyContext?.membership.role === "owner" || familyContext?.membership.role === "editor";

  return (
    <main className="shell">
      <DoubaoBanner />
      <div className="voiceLayout">
        <VoiceNav activeTab={activeTab} onSelect={setActiveTab} />
        <div className="voiceContent">
          {isLoading ? <p className="helperText">正在加载声音空间...</p> : null}
          {error && !familyContext ? (
            <section className="importSection">
              <h2>尚未创建家庭空间</h2>
              <p className="errorText">{error}</p>
              <Link className="button" href="/family">去创建家庭空间</Link>
            </section>
          ) : null}
          {familyContext && activeTab === "library" && (
            <FamilyVoiceLibrary
              profiles={profiles}
              canWrite={Boolean(canWrite)}
              management={voiceManagement}
              message={message}
              onDelete={handleDelete}
              onQuery={handleQuery}
              onUpgrade={handleUpgrade}
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

// ====== Sub-components (stubs to be filled in later tasks) ======

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

function FamilyVoiceLibrary(props: {
  profiles: VoiceProfile[];
  canWrite: boolean;
  management: Record<string, VoiceManagementState>;
  message: string;
  onDelete: (profile: VoiceProfile) => void;
  onQuery: (profile: VoiceProfile) => void;
  onUpgrade: (profile: VoiceProfile) => void;
}) {
  return <section className="importSection wide"><h2>家人音色库</h2><p className="emptyState">还没有声音档案</p></section>;
}

function ImportVoice(props: { familyId: string; canWrite: boolean; onImported: (p: VoiceProfile) => void; onError: (e: string) => void }) {
  return <section className="importSection"><h2>导入已有音色</h2><p>TBD</p></section>;
}

function CreateCloneVoice(props: { familyId: string; canWrite: boolean; onCreated: (p: VoiceProfile) => void; onError: (e: string) => void }) {
  return <section className="importSection"><h2>创建复刻音色</h2><p>TBD</p></section>;
}

// ====== Utility functions (kept from original file) ======

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取声音文件失败"));
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.readAsDataURL(file);
  });
}

function audioFormatFromFilename(filename: string): string {
  const extension = filename.split(".").pop()?.toLowerCase() ?? "";
  return extension || "wav";
}

function isValidCustomSpeakerId(value: string): boolean {
  return /^[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]$/.test(value);
}

function isValidPrepaidSpeakerId(value: string): boolean {
  return /^(S_|icl_)/i.test(value);
}

function formatDoubaoVoiceStatus(status: number | undefined): string {
  if (status === 0) return "NotFound";
  if (status === 1) return "Training";
  if (status === 2) return "Success";
  if (status === 3) return "Failed";
  if (status === 4) return "Active";
  return "Unknown";
}
