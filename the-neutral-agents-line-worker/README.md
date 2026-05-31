# TheNeutral-Agents LINE worker

LINE Messaging API webhook receiver + storage adapter.

This worker is meant to be deployed as a small serverless app (e.g. Vercel) and paired with the
local runner job in the main repo that periodically syncs stored LINE messages into the local
SQLite knowledge DB.

## What it does

- Receives LINE webhook events at `POST /api/line/webhook`
- Verifies request signature using `LINE_CHANNEL_SECRET`
- Normalizes LINE messages into the `x_knowledge ingest-json` shape
- Stores normalized items (default: Supabase table) for runnerPC to pull

## Environment variables

- `LINE_CHANNEL_SECRET` (required): Messaging API channel secret
- `SUPABASE_URL` (required for Supabase storage)
- `SUPABASE_SERVICE_ROLE_KEY` (required for Supabase storage)
- `LINE_EVENTS_TABLE` (optional, default `line_events`)

## Supabase schema

Apply `supabase.sql` to your Supabase project (SQL editor).

## Endpoints

- `POST /api/line/webhook`
- `GET /api/line/export?since=<ISO8601>&limit=500` (requires `SUPABASE_*`)

