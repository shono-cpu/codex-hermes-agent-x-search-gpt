const crypto = require("node:crypto");

function verifyLineSignature({ channelSecret, rawBody, signature }) {
  const mac = crypto.createHmac("sha256", channelSecret).update(rawBody).digest("base64");
  // Timing-safe compare
  const a = Buffer.from(mac);
  const b = Buffer.from(signature || "");
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

module.exports = { verifyLineSignature };

