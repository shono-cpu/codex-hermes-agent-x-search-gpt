# 中野優作bot

X、YouTube、記事、画像プロンプト、スライドなどの制作物をナレッジとしてストックし、要約・文体分析・制作プロンプト化までつなげるためのローカルMVPです。

現時点のこのCodexセッションではHermes Agent / `x_search` の呼び出し口が見えていないため、収集部分はアダプタとして切り出しています。まずはJSON取り込みでワークフローを動かし、Hermes側の安定した呼び出し形式が決まったら `x_knowledge/providers/hermes.py` を実装して差し替える想定です。

## できること

- Xポスト、YouTube動画、記事、制作物メモをSQLiteに保存
- 重複コンテンツは取得元URL/ID/titleから判定し、同じ情報は最新を正として上書き
- 個人アカウントと会社公式アカウントを `entity` / `profile` / `purpose` で分けて管理
- 手動アップロードしたMarkdown/TXT/DOCXも同じナレッジとして保存
- 用途別にMarkdownファイルへ自動で棲み分け
- 直近コンテンツの要約、主要トピック、表現パターンをMarkdown化
- ナレッジを元に、インフォグラフィック、記事、スライドなどの制作プロンプトを生成

## クイックスタート

```bash
python3 -m x_knowledge init
python3 -m x_knowledge ingest-json --account @sample --entity founder --profile personal --purpose style --file examples/sample_posts.json
python3 -m x_knowledge report --entity founder --profile personal --purpose style --out outputs/sample_report.md
python3 -m x_knowledge prompt --entity founder --profile personal --purpose style --goal "Hermes AgentとCodexを組み合わせたX検索ワークフローを紹介する" --asset infographic --out outputs/infographic_prompt.md
```

YouTubeや自分の制作物も混ぜる場合:

```bash
python3 -m x_knowledge ingest-json --source "Sample AI Channel" --entity sample-company --profile company --purpose creative --file examples/mixed_media_items.json
python3 -m x_knowledge ingest-file --source "Manual Upload" --entity founder --profile personal --purpose style --kind note --file examples/manual_upload_note.md
python3 -m x_knowledge report --entity sample-company --profile company --out outputs/mixed_media_report.md
python3 -m x_knowledge prompt --entity sample-company --profile company --purpose creative --goal "AI検索を制作ナレッジに変えるワークフローを紹介する" --asset slide --out outputs/slide_prompt.md
python3 -m x_knowledge export --out-dir knowledge --clean --entity nakano-yusaku
```

`knowledge/{entity}/{profile}/{purpose}/{platform}.md` の形で、取得元と用途ごとに分かれたMarkdownが作られます。

実運用の監視対象は `sources.toml` に入れます。現在は以下を登録済みです。

- X: `@yuusaku_buddica`, `@TheNeutral_of`
- X長文ナレッジ: 上記2アカウントの300文字以上投稿を `purpose = "style_longform"` として保存
- YouTube: `@yuusaku_buddica`, `@BUDDICA-nakanokun`, `@TheNeutral-official`, `@buddica_phoenix_pro`
- 書籍: `成長以外全て死_全テキスト.docx`

## 想定ワークフロー

1. Hermes Agentの `x_search` で指定アカウントの直近ポストを取得
2. YouTube、note、ブログ、制作ログもJSON化してDBに保存
3. `xkw report` でナレッジと文体を抽出
4. `xkw prompt` で制作物用プロンプトへ変換
5. GPT-Image系モデル、記事生成、スライド生成ワークフローに渡す

## 自動クロール設定

`sources.example.toml` のように、個人/会社、媒体、用途を分けて設定します。

```bash
python3 -m x_knowledge crawl --config sources.example.toml
```

このローカルMVPでは `provider = "json"` の取り込みまで動きます。`provider = "hermes_x"` や `provider = "youtube"` は、実際のHermes Agent / YouTube取得口が見えたらプロバイダを実装するための予約枠です。

## TheNeutral-Agents運用（TEN-Agentsと分離）

TEN-Agentsとは完全に別のデータベースで運用する前提で、runnerPCの定期ジョブからこのリポを回します。

- 専用SQLite: `data/the-neutral-agents.sqlite`（デフォルト）
- ジョブ: `./scripts/run-nakano-monitor.sh`

DBパスを変える場合:

```bash
THE_NEUTRAL_AGENTS_DB_PATH=data/the-neutral-agents.sqlite ./scripts/run-nakano-monitor.sh
```

## LINEグループのナレッジ格納 + 定期通知（TEN-Agents構造風）

LINEは「Webhook受信ワーカー（クラウド常駐）」と「runnerPCの定期sync」を分けます。

### 1) Webhook受信ワーカー（Vercel想定）

- `the-neutral-agents-line-worker/` を別アプリとしてデプロイ
- `POST /api/line/webhook` でLINE webhookを受けて保存（デフォルトはSupabase）
- `GET /api/line/export?since=...&limit=...&token=...` でrunnerPCがpullしてローカルDBへ取り込み

必要なenv（ワーカー側）:

- `LINE_CHANNEL_SECRET`
- `LINE_EXPORT_TOKEN`（`export` を外部公開しないためのトークン）
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Supabaseのテーブルは `the-neutral-agents-line-worker/supabase.sql` を適用します。

### 2) runnerPC（pull取り込み + 通知）

runnerPC側は `scripts/run-nakano-monitor.sh` が以下を自動で実行します。

- `x_knowledge line-sync`（`LINE_WORKER_ENDPOINT` があれば）
- `crawl` → `export`
- `notify-line`（`LINE_NOTIFY_TO` と `LINE_CHANNEL_ACCESS_TOKEN` があれば）

runnerPCのenv例:

- `LINE_WORKER_ENDPOINT=https://<your-worker>.vercel.app`
- `LINE_EXPORT_TOKEN=...`
- `LINE_NOTIFY_TO=<groupId>`
- `LINE_CHANNEL_ACCESS_TOKEN=...`

## Bot UI

監視対象の編集・保存、クロール実行、用途別エクスポート、手動ファイル取り込みはローカルUIから操作できます。

```bash
python3 -m x_knowledge ui --config sources.toml --port 8765
```

起動後に `http://127.0.0.1:8765` を開きます。

## モデル設定

コストより精度を優先するため、`bot_settings.toml` のデフォルトは以下にしています。

- テキスト/チャット改善: `gpt-5.5`
- フォールバック: `gpt-5.2-pro`
- Reasoning: `xhigh`
- 画像生成: `gpt-image-1.5`, quality `high`

`OPENAI_API_KEY` が設定されている場合はOpenAI Responses APIを使います。`gpt-5.5` がAPI側で使えない場合は `gpt-5.2-pro` に自動フォールバックし、未設定の場合はローカルの簡易ブラッシュアップにフォールバックします。

## 入力JSON形式

```json
[
  {
    "id": "post-id",
    "platform": "x",
    "kind": "post",
    "entity": "founder",
    "profile": "personal",
    "purpose": "style",
    "source": "@user",
    "url": "https://x.com/user/status/post-id",
    "created_at": "2026-05-18T10:00:00+09:00",
    "text": "ポスト本文",
    "metrics": {
      "likes": 120,
      "reposts": 12
    }
  }
]
```

YouTubeなら `platform: "youtube"`、`kind: "video"`、`title`、`description`、`transcript`、`published_at` を使えます。自分の制作物なら `platform: "local"`、`kind: "image_prompt"` や `kind: "slide"` として保存できます。

`id` がない場合は媒体・ソース・本文・日時・URLから安定IDを作ります。重複判定は `canonical_key`、URL、媒体ID、titleの順で作られ、同じキーなら新しい `created_at` の内容で上書きします。

## Hermes連携の差し替えポイント

`x_knowledge/providers/hermes.py` の `HermesXSearchProvider.fetch_posts()` に、CodexからHermes Agentを呼び出す処理を入れます。返り値は `ContentInput` の配列に揃えるだけで、DB保存以降の処理はそのまま使えます。
