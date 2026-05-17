"""Elderly adaptation rule checks — 6 hard constraints."""

import re


# 禁忌词汇
FORBIDDEN_WORDS = [
    "死", "去世", "癌症", "绝症", "遗产", "遗嘱", "分家", "吵架", "离婚",
    "你懂什么", "别瞎想", "你想多了",
]

# 网络用语/成语 patterns
NET_SLANG_PATTERNS = [
    r"[a-zA-Z]{3,}",  # 英文单词
    r"yyds|emo|awsl|u1s1|dbq|pyq|xs|drl|栓q|芭比q",
]

# 虚假承诺 patterns
FALSE_PROMISE_PATTERNS = [
    r"我(明天|后天|下周|马上|这就|一会儿|很快).*(回来|回去|看你|陪你|接你)",
    r"(以后|再也).*(不会|不了|不走|不离开)",
    r"我保证",
    r"一定.*(回来|陪你|看你)",
]

# 医学建议 patterns
MEDICAL_PATTERNS = [
    r"(吃|服|用|抹|涂|注射).*(药|胶囊|片剂|针剂|冲剂)",
    r"(你|您).*(应该|得|要|必须).*(治|看|检查|做手术|住院)",
    r"(血压|血糖|心脏|肝|肾).*(不好|有问题|要注意)",
]


def check_elderly_adaptation(response: str, appellation: str) -> dict:
    """检查回复是否符合老年适配规则。返回 {pass: bool, issues: list[str]}"""
    issues = []

    # 1. 句子长度
    sentences = re.split(r"[。！？；!?;]", response)
    for s in sentences:
        if len(s.strip()) > 25 and s.strip():
            issues.append("句子过长（超过25字）")
            break

    # 2. 必须包含称呼
    if appellation and appellation not in response:
        issues.append("未使用称呼")

    # 3. 无禁忌词汇
    for word in FORBIDDEN_WORDS:
        if word in response:
            issues.append(f"含禁忌词汇：{word}")
            break

    # 4. 无网络用语
    for pattern in NET_SLANG_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            issues.append("含网络用语或英文")
            break

    return {"pass": len(issues) == 0, "issues": issues}


def safety_check(response: str) -> list[str]:
    """额外的安全检查：假承诺、医学建议。返回问题列表。"""
    issues = []

    # 虚假承诺
    for pattern in FALSE_PROMISE_PATTERNS:
        if re.search(pattern, response):
            issues.append("含虚假承诺——不要代表真人做出具体承诺")
            break

    # 医学建议
    for pattern in MEDICAL_PATTERNS:
        if re.search(pattern, response):
            issues.append("含医学建议——不要给出医疗相关指导")
            break

    return issues


def build_retry_hint(adapt_issues: list[str], safety_issues: list[str]) -> str:
    """构建重试提示文本，注入到下次 LLM 生成。"""
    all_issues = adapt_issues + safety_issues
    if not all_issues:
        return ""
    hints = "\n".join(f"- {issue}" for issue in all_issues)
    return f"上一次回复存在以下问题：\n{hints}\n请修正后重新生成。"
