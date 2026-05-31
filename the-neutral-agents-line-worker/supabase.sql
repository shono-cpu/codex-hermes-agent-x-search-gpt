-- LINE webhook event storage for TheNeutral-Agents.
-- Stores both the raw event and a normalized item that matches x_knowledge ingest-json.

create table if not exists public.line_events (
  id bigserial primary key,
  received_at timestamptz not null default now(),
  event_timestamp_ms bigint not null,
  destination text,
  event_type text,
  source_type text,
  source_id text,
  user_id text,
  message_id text,
  raw_event jsonb not null,
  normalized_item jsonb not null
);

create index if not exists line_events_received_at_idx on public.line_events (received_at desc);
create index if not exists line_events_event_ts_idx on public.line_events (event_timestamp_ms desc);
create unique index if not exists line_events_message_id_uniq on public.line_events (message_id) where message_id is not null;

