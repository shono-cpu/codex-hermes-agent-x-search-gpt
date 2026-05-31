from __future__ import annotations

import re

from .analysis import build_report, extract_keywords
from .llm import generate_with_openai, load_llm_settings
from .models import ContentInput
from .store import KnowledgeStore


def save_artifact(
    store: KnowledgeStore,
    title: str,
    text: str,
    entity: str = "nakano-yusaku",
    profile: str = "personal",
    purpose: str = "creative",
    kind: str = "draft",
    source: str = "中野優作bot UI",
) -> tuple[int, int, int]:
    content = ContentInput(
        source=source,
        platform="local",
        kind=kind,
        entity=entity,
        profile=profile,
        purpose=purpose,
        title=title or "untitled",
        text=text.strip(),
        metadata={"origin": "bot_ui"},
    )
    return store.upsert_contents([content])


def refine_for_nakano(
    store: KnowledgeStore,
    draft: str,
    instruction: str = "",
    entity: str = "nakano-yusaku",
    profile: str = "personal",
    purpose: str = "style",
    asset: str = "post",
) -> dict[str, object]:
    style_sources = store.recent_contents(
        entity=entity,
        profile=profile,
        purpose=purpose,
        limit=12,
    )
    longform_sources = store.recent_contents(
        entity=entity,
        profile=profile,
        purpose="style_longform",
        platform="x",
        limit=20,
    )
    style_sources = longform_sources + style_sources
    report = build_report(f"{entity} / {profile} / {purpose}", style_sources)
    keywords = [keyword for keyword, _ in report.top_keywords[:8]]
    llm_text, llm_error = high_quality_refine(draft, instruction, asset, report.style_notes, report.reusable_phrases, keywords)
    if llm_text:
        return {
            "message": llm_text,
            "revised_text": extract_revision(llm_text),
            "checks": [],
            "style_notes": report.style_notes[:5],
            "reference_count": report.item_count,
            "model_used": load_llm_settings().model,
            "quality_mode": load_llm_settings().quality_mode,
        }

    revised = rewrite_draft(draft, instruction, keywords, asset)
    checks = critique_draft(draft)

    return {
        "message": build_chat_message(revised, checks, report.reusable_phrases[:4]),
        "revised_text": revised,
        "checks": checks,
        "style_notes": report.style_notes[:5],
        "reference_count": report.item_count,
        "model_used": "local_fallback",
        "llm_error": llm_error,
    }


def high_quality_refine(
    draft: str,
    instruction: str,
    asset: str,
    style_notes: list[str],
    phrases: list[str],
    keywords: list[str],
) -> tuple[str | None, str | None]:
    system = (
        "あなたは中野優作botの編集長です。本人の文体を丸写しせず、"
        "ナレッジから抽出した熱量、具体性、成長への意志、工程の見える化を使って、"
        "制作物を最高品質にブラッシュアップしてください。出力は日本語。"
    )
    prompt = "\n".join(
        [
            f"制作物タイプ: {asset}",
            f"ユーザー指示: {instruction or '中野優作bot仕様にブラッシュアップ'}",
            "",
            "参照する高レベル文体傾向:",
            "\n".join(f"- {note}" for note in style_notes[:8]),
            "",
            "短い参考フレーズ:",
            "\n".join(f"- {clip(phrase, 48)}" for phrase in phrases[:6]),
            "",
            "主要キーワード:",
            ", ".join(keywords[:10]),
            "",
            "下書き:",
            draft,
            "",
            "必ず以下の構成で出力:",
            "1. 改善方針: 3点",
            "2. ブラッシュアップ案: そのまま使える完成稿",
            "3. 追加すると強くなる素材: 数字、実例、CTAなど",
        ]
    )
    return generate_with_openai(prompt, system)


def extract_revision(text: str) -> str:
    marker = "ブラッシュアップ案"
    if marker not in text:
        return text.strip()
    tail = text.split(marker, 1)[1]
    tail = tail.lstrip("：:\n ")
    next_section = re.split(r"\n\s*(?:3\.|###|##)\s*", tail, maxsplit=1)
    return next_section[0].strip() or text.strip()


def rewrite_draft(draft: str, instruction: str, keywords: list[str], asset: str) -> str:
    core = normalize_draft(draft)
    if not core:
        core = normalize_draft(instruction)
    if not core:
        core = "伝えたい制作テーマをここに入れる。"

    first_sentence = split_sentences(core)[0]
    hook = make_hook(first_sentence, keywords)
    flow = make_flow(core)
    value = make_value(core, asset)
    close = "成長以外、全て死。試す人から、次の景色が変わる。"

    if asset in {"x", "post", "tweet"}:
        return "\n".join([hook, "", flow, "", value, "", close])
    if asset in {"youtube", "script"}:
        return "\n".join(
            [
                f"冒頭: {hook}",
                "",
                "本編:",
                f"1. {flow}",
                f"2. {value}",
                "3. ただ便利で終わらせず、毎日の制作フローに入れる。",
                "",
                f"締め: {close}",
            ]
        )
    return "\n".join([hook, "", flow, "", value, "", close])


def normalize_draft(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def split_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[。.!?！？])\s*", text) if part.strip()]
    return sentences or [text.strip()]


def make_hook(sentence: str, keywords: list[str]) -> str:
    if any(word in sentence for word in ["ヤバ", "すご", "強い", "熱狂"]):
        return sentence
    keyword = next((word for word in keywords if len(word) <= 18 and not word.startswith("#") and word in sentence), "")
    prefix = f"{keyword}、" if keyword else ""
    return f"ヤバっ、{prefix}{sentence.rstrip('。')}。"


def make_flow(text: str) -> str:
    if "→" in text:
        return text
    if any(word in text for word in ["AI", "検索", "Codex", "YouTube", "X検索", "制作"]):
        return "流れはシンプル。情報収集 → 要約 → ナレッジ化 → 制作 → 投稿まで、一つの線にする。"
    keywords = extract_keywords(text)[:4]
    if len(keywords) >= 3:
        return "流れはシンプル。 " + " → ".join(keywords[:4]) + "。"
    return "ただのアイデアで終わらせず、取得して、整理して、制作に使うところまで一気に持っていく。"


def make_value(text: str, asset: str) -> str:
    concrete = []
    if re.search(r"\d|円|月|日|年", text):
        concrete.append("数字があるから、価値がぼやけない")
    if any(word in text for word in ["自動", "ワークフロー", "AI", "検索", "制作"]):
        concrete.append("仕組みにできるから、再現性が出る")
    if not concrete:
        concrete.append("自分の言葉と行動に落ちるから、次の一手が見える")
    label = {
        "post": "X投稿",
        "x": "X投稿",
        "tweet": "X投稿",
        "script": "YouTube台本",
        "youtube": "YouTube台本",
        "article": "記事",
        "slide": "スライド",
        "image_prompt": "画像プロンプト",
    }.get(asset, asset)
    return f"{label}として伝える価値は、" + "。".join(concrete) + "。"


def critique_draft(draft: str) -> list[str]:
    checks: list[str] = []
    if len(draft) < 80:
        checks.append("情報量が少なめ。手順、数字、使い道のどれかを足すと強くなる。")
    if not re.search(r"\d|円|月|日|年", draft):
        checks.append("具体数字がない。月額、期間、件数、成果などを一つ入れたい。")
    if "→" not in draft and "流れ" not in draft:
        checks.append("工程が見えにくい。矢印や順番で読者に一発で見せるとよい。")
    if not any(word in draft for word in ["なぜ", "価値", "使", "変わ", "成長"]):
        checks.append("なぜ重要かの一言が弱い。価値か変化を足すと締まる。")
    return checks or ["素材は十分。冒頭の発見感と締めの意志を少し強めれば使える。"]


def build_chat_message(revised: str, checks: list[str], phrases: list[str]) -> str:
    phrase_text = "\n".join(f"- {clip(phrase, 52)}" for phrase in phrases) if phrases else "- 参照フレーズはまだ少なめ"
    check_text = "\n".join(f"- {check}" for check in checks)
    return "\n".join(
        [
            "中野優作仕様に寄せて、発見の強さ、工程の見え方、最後の意志を足しました。",
            "",
            "改善ポイント:",
            check_text,
            "",
            "参照した言い回し:",
            phrase_text,
            "",
            "ブラッシュアップ案:",
            revised,
        ]
    )


def clip(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"
