from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass

from .models import StoredContent


STOPWORDS = {
    "これ",
    "それ",
    "ため",
    "よう",
    "こと",
    "かなり",
    "できる",
    "して",
    "から",
    "まで",
    "する",
    "なる",
    "ある",
    "いる",
    "the",
    "and",
    "for",
    "with",
}


@dataclass(frozen=True)
class PostDigest:
    post: StoredContent
    summary: str
    keywords: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class KnowledgeReport:
    scope: str
    item_count: int
    digests: list[PostDigest]
    top_keywords: list[tuple[str, int]]
    style_notes: list[str]
    reusable_phrases: list[str]
    platforms: list[str]
    kinds: list[str]

    @property
    def account(self) -> str:
        return self.scope

    @property
    def post_count(self) -> int:
        return self.item_count


def build_report(scope: str, contents: list[StoredContent]) -> KnowledgeReport:
    digests = [digest_post(content) for content in contents]
    keyword_counter: Counter[str] = Counter()
    for digest in digests:
        keyword_counter.update(digest.keywords)

    return KnowledgeReport(
        scope=scope,
        item_count=len(contents),
        digests=digests,
        top_keywords=keyword_counter.most_common(12),
        style_notes=style_notes(contents),
        reusable_phrases=reusable_phrases(contents),
        platforms=sorted({content.platform for content in contents}),
        kinds=sorted({content.kind for content in contents}),
    )


def digest_post(post: StoredContent) -> PostDigest:
    metadata = json.loads(post.metadata_json or "{}")
    return PostDigest(
        post=post,
        summary=summarize_text(post.text),
        keywords=extract_keywords(post.text),
        metadata=metadata,
    )


def summarize_text(text: str, max_chars: int = 96) -> str:
    normalized = " ".join(text.split())
    parts = re.split(r"(?<=[。.!?！？])\s*", normalized)
    summary = parts[0] if parts and parts[0] else normalized
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 1].rstrip() + "…"


def extract_keywords(text: str) -> list[str]:
    hashtags = [token.lower() for token in re.findall(r"#[\w\u3040-\u30ff\u3400-\u9fffー]+", text)]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}|[\u3040-\u30ff\u3400-\u9fffー]{2,}", text)
    cleaned = []
    for word in words:
        value = word.lower()
        if value in STOPWORDS:
            continue
        if len(value) <= 1:
            continue
        cleaned.append(value)
    return list(dict.fromkeys(hashtags + cleaned))[:10]


def style_notes(contents: list[StoredContent]) -> list[str]:
    if not contents:
        return ["まだ分析対象のコンテンツがありません。"]

    texts = [content.text for content in contents]
    avg_len = round(sum(len(text) for text in texts) / len(texts))
    line_break_posts = sum(1 for text in texts if "\n" in text)
    exclamations = sum(text.count("!") + text.count("！") for text in texts)
    questions = sum(text.count("?") + text.count("？") for text in texts)
    arrow_posts = sum(1 for text in texts if "→" in text or "↓" in text)
    price_posts = sum(1 for text in texts if "円" in text or "月" in text)
    youtube_items = sum(1 for content in contents if content.platform == "youtube")
    artifact_items = sum(1 for content in contents if content.kind in {"image", "slide", "article", "prompt", "artifact"})

    notes = [f"平均文字数は約{avg_len}字。短い所感よりも、具体的な手順や価値を一気に伝える投稿が中心。"]
    if arrow_posts:
        notes.append("矢印で工程をつなぎ、読者に「流れが一発で見える」構造を作っている。")
    if price_posts:
        notes.append("価格や月額などの具体数字を入れて、体験価値を生活感のある比較に落としている。")
    if youtube_items:
        notes.append("YouTube素材はタイトル・概要・台本を一緒に見ることで、導入のフックと章立てを抽出できる。")
    if artifact_items:
        notes.append("完成物や制作メモも混ぜることで、反応のよい題材だけでなく実際のアウトプット表現も再利用できる。")
    if exclamations > questions:
        notes.append("疑問形よりも断定・驚き・発見のトーンが強く、熱量のある発見メモとして読ませる。")
    if line_break_posts:
        notes.append("改行でテンポを作り、箇条書きに近いリズムで読ませている。")
    return notes


def reusable_phrases(contents: list[StoredContent]) -> list[str]:
    phrases: list[str] = []
    patterns = [
        r"[^。！？\n]*(?:ヤバ|エグ|強い|貴重|遊べる)[^。！？\n]*[。！？]?",
        r"[^。！？\n]*(?:月[\d,]+円|月額|サブスク)[^。！？\n]*[。！？]?",
        r"[^。！？\n]*(?:一発|自動|ワークフロー|組み込める)[^。！？\n]*[。！？]?",
    ]
    for post in contents:
        for pattern in patterns:
            for match in re.findall(pattern, post.text):
                phrase = " ".join(match.split())
                if 8 <= len(phrase) <= 90 and phrase not in phrases:
                    phrases.append(phrase)
    return phrases[:8]
