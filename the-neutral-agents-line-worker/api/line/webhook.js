const { verifyLineSignature } = require("./_verify");
const { normalizeTextMessage } = require("./_normalize");
const { supabaseInsert } = require("./_supabase");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }

  const channelSecret = process.env.LINE_CHANNEL_SECRET;
  if (!channelSecret) {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: "Missing LINE_CHANNEL_SECRET" }));
    return;
  }

  const signature = req.headers["x-line-signature"];
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const rawBody = Buffer.concat(chunks);

  if (!verifyLineSignature({ channelSecret, rawBody, signature })) {
    res.statusCode = 401;
    res.end(JSON.stringify({ error: "Invalid signature" }));
    return;
  }

  let payload;
  try {
    payload = JSON.parse(rawBody.toString("utf8"));
  } catch {
    res.statusCode = 400;
    res.end(JSON.stringify({ error: "Invalid JSON" }));
    return;
  }

  const destination = payload.destination || null;
  const events = Array.isArray(payload.events) ? payload.events : [];
  const toStore = [];
  for (const event of events) {
    if (!event || typeof event !== "object") continue;
    if (event.type !== "message") continue;
    if (!event.message || event.message.type !== "text") continue;
    const normalized = normalizeTextMessage({ event, destination });
    toStore.push({
      event_timestamp_ms: Number(event.timestamp || Date.now()),
      destination,
      event_type: event.type || null,
      source_type: (event.source && event.source.type) || null,
      source_id: (event.source && (event.source.groupId || event.source.roomId)) || null,
      user_id: (event.source && event.source.userId) || null,
      message_id: (event.message && event.message.id) || null,
      raw_event: event,
      normalized_item: normalized
    });
  }

  try {
    if (toStore.length) await supabaseInsert(toStore);
  } catch (e) {
    res.statusCode = 500;
    res.end(JSON.stringify({ error: String(e && e.message ? e.message : e) }));
    return;
  }

  res.statusCode = 200;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify({ ok: true, stored: toStore.length }));
};

