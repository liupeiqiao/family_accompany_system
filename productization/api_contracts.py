from __future__ import annotations


API_ENDPOINTS = {
    "family_current": "GET /api/family/current",
    "family_create": "POST /api/family",
    "elder_current": "GET/PUT /api/elders/current",
    "family_profiles": "GET/POST /api/family-profiles",
    "family_profile_item": "PUT/DELETE /api/family-profiles/{id}",
    "memories": "GET/POST /api/memories",
    "memory_item": "PUT/DELETE /api/memories/{id}",
    "personas": "GET/POST /api/personas",
    "persona_item": "PUT /api/personas/{id}",
    "parse": "POST /api/parse",
    "import": "POST /api/import",
    "chat": "POST /api/chat",
    "voice_clone": "POST /api/voices/clone",
    "tts": "POST /api/tts",
}
