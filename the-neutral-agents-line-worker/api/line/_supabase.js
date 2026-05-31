function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing env: ${name}`);
  return value;
}

function tableName() {
  return process.env.LINE_EVENTS_TABLE || "line_events";
}

async function supabaseInsert(rows) {
  const url = requireEnv("SUPABASE_URL");
  const key = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  const table = tableName();

  const res = await fetch(`${url}/rest/v1/${table}`, {
    method: "POST",
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=minimal"
    },
    body: JSON.stringify(rows)
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Supabase insert failed: ${res.status} ${res.statusText} ${text}`);
  }
}

async function supabaseExport({ since, limit }) {
  const url = requireEnv("SUPABASE_URL");
  const key = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  const table = tableName();
  const lim = Math.min(Math.max(Number(limit || 500), 1), 2000);

  // Fetch normalized items ordered by received_at ascending.
  // NOTE: PostgREST filter uses ISO8601 string.
  const qs = new URLSearchParams();
  qs.set("select", "normalized_item,received_at,event_timestamp_ms");
  if (since) qs.set("received_at", `gte.${since}`);
  qs.set("order", "received_at.asc");
  qs.set("limit", String(lim));

  const res = await fetch(`${url}/rest/v1/${table}?${qs.toString()}`, {
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`
    }
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Supabase export failed: ${res.status} ${res.statusText} ${text}`);
  }
  return res.json();
}

module.exports = { supabaseInsert, supabaseExport };

