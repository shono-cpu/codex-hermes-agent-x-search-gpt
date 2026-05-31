from __future__ import annotations

from datetime import datetime

from .analysis import KnowledgeReport


def render_markdown_report(report: KnowledgeReport) -> str:
    lines = [
        f"# Knowledge Report: {report.scope}",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Items analyzed: {report.item_count}",
        f"- Platforms: {', '.join(report.platforms) if report.platforms else 'none'}",
        f"- Kinds: {', '.join(report.kinds) if report.kinds else 'none'}",
        "",
        "## 主要トピック",
    ]
    if report.top_keywords:
        lines.extend([f"- {keyword}: {count}" for keyword, count in report.top_keywords])
    else:
        lines.append("- まだ抽出できるトピックがありません。")

    lines.extend(["", "## 文体・表現の傾向"])
    lines.extend([f"- {note}" for note in report.style_notes])

    lines.extend(["", "## 使い回せる言い回し"])
    if report.reusable_phrases:
        lines.extend([f"- {phrase}" for phrase in report.reusable_phrases])
    else:
        lines.append("- まだ十分な表現パターンがありません。")

    lines.extend(["", "## コンテンツ別要約"])
    for digest in report.digests:
        url = f" ({digest.post.url})" if digest.post.url else ""
        keyword_text = ", ".join(digest.keywords) if digest.keywords else "なし"
        title = f": {digest.post.title}" if digest.post.title else ""
        route = f"{digest.post.entity or 'unknown'} / {digest.post.profile} / {digest.post.purpose}"
        lines.extend(
            [
                f"### [{digest.post.platform}/{digest.post.kind}] {digest.post.created_at}{title}{url}",
                "",
                f"- 区分: {route}",
                f"- 要約: {digest.summary}",
                f"- キーワード: {keyword_text}",
                f"- 本文プレビュー: {preview_text(digest.post.text)}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_creative_prompt(report: KnowledgeReport, goal: str, asset: str) -> str:
    keywords = ", ".join(keyword for keyword, _ in report.top_keywords[:10]) or "なし"
    style_notes = "\n".join(f"- {note}" for note in report.style_notes)
    phrases = "\n".join(f"- {phrase}" for phrase in report.reusable_phrases) or "- なし"
    post_summaries = "\n".join(f"- {digest.summary}" for digest in report.digests[:8])
    image_prompt = render_image_prompt(report, goal, asset, keywords)

    return f"""# Creative Prompt

## 制作ゴール
{goal}

## 制作物タイプ
{asset}

## 参照ソース
{report.scope}

## 抽出された主要トピック
{keywords}

## 参照すべき文体
{style_notes}

## 参考にする言い回し
{phrases}

## 内容の素材
{post_summaries}

## そのまま使う生成プロンプト
{image_prompt}
"""


def render_image_prompt(report: KnowledgeReport, goal: str, asset: str, keywords: str) -> str:
    if asset.lower() not in {"infographic", "インフォグラフィック"}:
        return "\n".join(
            [
                f"{asset}を作成する。",
                f"テーマ: {goal}",
            f"参照ソース: {report.scope}",
                f"主要トピック: {keywords}",
                "トーン: 熱量のある発見メモ。手順、価格感、使い道を具体的に示す。",
                "構成: 発見、仕組み、価値、次に試すことの順で整理する。",
            ]
        )

    return "\n".join(
        [
            "Create a clean Japanese infographic for social media.",
            f"Topic: {goal}",
            f"Source style: content by {report.scope}",
            f"Core keywords: {keywords}",
            "Structure the infographic into four clearly separated blocks:",
            "1. 発見: CodexからHermes Agent / X検索を呼び出せる驚き",
            "2. 流れ: 直近ポスト取得 → 要約 → ナレッジ化 → 制作プロンプト化 → 画像生成",
            "3. 価値: 月額サブスク内で高性能AI検索と制作をつなげられる",
            "4. 使い道: 指定アカウントのポストを自動取得し、文体・表現・知見を制作に活かす",
            "Visual direction: modern creator-tool dashboard aesthetic, crisp typography, compact information hierarchy, subtle contrast, no clutter.",
            "Use Japanese labels. Keep text short and legible. Emphasize arrows, stacked workflow steps, and small callout boxes for price/value/use-case.",
            "Tone: excited but practical, like a sharp discovery memo rather than an advertisement.",
        ]
    )


def preview_text(text: str, max_chars: int = 1200) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"
