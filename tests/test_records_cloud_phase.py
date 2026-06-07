from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_records_page_uses_current_family_cloud_records():
    source = (ROOT / "web" / "src" / "app" / "records" / "page.tsx").read_text(encoding="utf-8")

    assert "fetchCurrentFamily" in source
    assert "fetchCloudElder" in source
    assert "fetchCloudPersonas" in source
    assert "fetchCloudFamilyProfiles" in source
    assert "fetchCloudMemories" in source
    assert "saveCloudElder" in source
    assert "createCloudPersona" in source
    assert "createCloudFamilyProfile" in source
    assert "createCloudMemory" in source
    assert 'family_id: familyContext.family.id' in source
    assert 'family_id: "local"' not in source


def test_records_page_deletes_cloud_records_by_family_id():
    source = (ROOT / "web" / "src" / "app" / "records" / "page.tsx").read_text(encoding="utf-8")
    api_source = (ROOT / "web" / "src" / "lib" / "backend-api.ts").read_text(encoding="utf-8")

    assert "deleteCloudElder" in source
    assert "deleteCloudPersona" in source
    assert "deleteCloudFamilyProfile" in source
    assert "deleteCloudMemory" in source
    assert "export function deleteCloudElder" in api_source
    assert "export function deleteCloudPersona" in api_source
    assert "export function deleteCloudFamilyProfile" in api_source
    assert "export function deleteCloudMemory" in api_source


def test_records_parse_preview_opens_in_modal_instead_of_import_panel():
    source = (ROOT / "web" / "src" / "app" / "records" / "page.tsx").read_text(encoding="utf-8")

    assert "const [isParsePreviewOpen, setParsePreviewOpen]" in source
    assert "setParsePreviewOpen(true)" in source
    assert 'className="recordsDraftModalOverlay"' in source
    assert 'className="recordsDraftModal"' in source

    import_panel = source.split('className="recordsImportPanel"', 1)[1].split('className="recordsDraftModalOverlay"', 1)[0]
    assert 'className="recordsDraftPreview"' not in import_panel
