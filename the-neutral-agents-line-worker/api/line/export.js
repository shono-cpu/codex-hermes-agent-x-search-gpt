const { supabaseExport } = require("./_supabase");

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    res.statusCode = 405;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: "Method not allowed" }));
    return;
  }

  const requiredToken = process.env.LINE_EXPORT_TOKEN;
  if (requiredToken) {
    const provided =
      (req.headers["x-export-token"] ? String(req.headers["x-export-token"]) : null) ||
      (req.query && req.query.token ? String(req.query.token) : null);
    if (!provided || provided !== requiredToken) {
      res.statusCode = 401;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ error: "Unauthorized" }));
      return;
    }
  }

  const since = req.query && req.query.since ? String(req.query.since) : null;
  const limit = req.query && req.query.limit ? String(req.query.limit) : "500";

  try {
    const rows = await supabaseExport({ since, limit });
    const items = rows.map((r) => r.normalized_item);
    const lastReceivedAt = rows.length ? rows[rows.length - 1].received_at : null;
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ items, last_received_at: lastReceivedAt, count: items.length }));
  } catch (e) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ error: String(e && e.message ? e.message : e) }));
  }
};
