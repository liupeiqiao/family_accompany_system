# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

亲情陪伴系统 (Family Companionship System) — an AI-powered empathetic companion for elderly users. Based on the patent `一种亲情记忆驱动的适老共情对话方法_发明专利方案.docx`, the system generates emotionally appropriate dialogue by combining family memory retrieval, user profiling, real-time emotional state detection, and elderly-adapted response generation.

## Current State

Core prototype implemented. Streamlit chat UI with SQLite persistence, LLM-powered smart parsing, scoring engine, and elderly adaptation rules. 13 unit tests.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run app (requires DEEPSEEK_API_KEY env var)
export DEEPSEEK_API_KEY="your-key"
python -m streamlit run app.py --server.port 8501

# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_smart_parse_preview.py -v
```

## Architecture

```
app.py                  # Streamlit 主入口: UI + pipeline 编排
engine/
  memory.py             # MemoryUnit dataclass + 内存存储 (add/remove/get)
  persona.py            # PersonaProfile dataclass + 内存存储 (set/get)
  scorer.py             # 五因子评分: Score = αR + βE + γC + δS − εM + 情感冲突矩阵
  strategy.py           # 意图×情绪 → 策略 7×9 映射矩阵
  adaptation.py         # 6 条老年适配规则 + 安全检查 (假承诺/医学边界)
  db.py                 # SQLite 持久化: persona + memories 两张表
llm/
  client.py             # DeepSeek API 客户端 (OpenAI 兼容 SDK)
  prompts.py            # 3 组 Prompt 模板 (意图识别/回复生成/策略描述)
  parser.py             # 自然语言 → 结构化画像+记忆 (LLM 智能解析)
tests/
  test_smart_parse_preview.py          # 解析预览数据逻辑
  test_preview_has_editable_widgets.py # 预览控件可编辑性
  test_import_syncs_form_fields.py     # 导入表单同步
```

## Core Architecture (from Patent)

The system follows an 8-step pipeline:

1. **Multimodal Input Collection (S1)** — text, audio, video input with emotion/intonation features
2. **Intent & Emotion Recognition (S2)** — classify dialogue intent (reminiscing, complaining, missing someone, expressing loneliness, worrying, verifying facts, asking for help) and emotional state (calm, happy, sad, anxious, lonely, excited, wronged, doubtful)
3. **Family Memory Retrieval (S3)** — query the 家庭记忆库 (Family Memory Base) which stores: shared experiences, family member relationships, appellation habits, dietary preferences, health notes, important anniversaries, sensitive topics, and historical dialogue segments
4. **Character Profile Loading (S4)** — load the target caregiver's 人物画像 (Persona Profile) including: relationship type, customary appellation, personality traits, comfort style, speech patterns, and interaction habits. Profiles have static attributes (fixed traits) and dynamic attributes (preference updates, response effectiveness history)
5. **Memory Scoring & Selection (S5)** — score candidate memory clips using: `Score = αR + βE + γC + δS - εM` where R=Relevance (semantic + emotion tag + family member + temporal), E=Empathy (emotion state alignment + historical effectiveness), C=Closeness (relationship strength + shared frequency), S=Safety (risk detection + medical boundary + sensitivity), M=Sensitive topic penalty
6. **Strategy Decision (S6)** — select an empathy strategy: greeting, sharing, comforting, encouraging, distraction, inquiry, or confirmation
7. **Response Generation (S7)** — generate candidate response constrained by: the target memory clip, persona profile, emotional state, dialogue context, and elderly-adaptation rules
8. **Verification & Output (S8)** — validate against: elderly language suitability, safety, role consistency, and context continuity. Regenerate on failure before outputting final response

### Key Design Constraints

- **Elderly adaptation rules**: short sentences, low-complexity vocabulary, avoidance of taboo topics, slow pacing, affirmative phrasing, use of the target caregiver's customary appellation
- **Safety guardrails**: medical boundary check, negative emotion risk check, false promise check, sensitive topic trigger check
- **Sensitive topic handling**: when a memory clip touches a sensitive topic, re-rank or switch to gentle/distraction/confirmation strategies
- **Dynamic learning**: memory intimacy weights and persona preferences update based on interaction history and response effectiveness feedback

### 回答语言要求

尽量用中文和我沟通