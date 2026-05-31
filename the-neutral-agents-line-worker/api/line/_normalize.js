function normalizeTextMessage({ event, destination }) {
  const msg = event.message || {};
  const source = event.source || {};

  const messageId = msg.id || null;
  const timestampMs = Number(event.timestamp || Date.now());
  const createdAt = new Date(timestampMs).toISOString();
  const groupId = source.groupId || source.roomId || null;

  const text = String(msg.text || "").trim();
  const title = text.length > 60 ? `${text.slice(0, 57)}...` : text;

  const stableId = messageId ? `line:${messageId}` : `line:${groupId || "unknown"}:${timestampMs}`;
  const url = messageId ? `line://message/${messageId}` : `line://message/${timestampMs}`;

  return {
    id: stableId,
    platform: "line",
    kind: "message",
    entity: "nakano-yusaku",
    profile: "personal",
    purpose: "research",
    source: groupId ? `line-group:${groupId}` : "line",
    url,
    created_at: createdAt,
    title,
    text,
    metadata: {
      destination: destination || null,
      event_type: event.type || null,
      source_type: source.type || null,
      group_id: groupId,
      user_id: source.userId || null,
      message_id: messageId
    }
  };
}

module.exports = { normalizeTextMessage };

