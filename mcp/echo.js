// Test MCP server for the dec-344 attach proof. Never returns a key value: only
// booleans and a short sha256 prefix of what the API echoed back.
const crypto = require('crypto');
const readline = require('readline');
const sha = s => (s ? crypto.createHash('sha256').update(String(s)).digest('hex').slice(0, 12) : null);
const send = o => process.stdout.write(JSON.stringify(o) + '\n');
const tools = [
  { name: 'selfcheck', description: 'Report whether the API_KEY in this process is a placeholder.', inputSchema: { type: 'object', properties: {} } },
  { name: 'probe', description: 'GET https://<host>/get with the key in a header and a query parameter; report what the API saw.', inputSchema: { type: 'object', properties: { host: { type: 'string' } }, required: ['host'] } },
];
const text = t => ({ content: [{ type: 'text', text: JSON.stringify(t) }] });
async function call(name, args) {
  const key = process.env.API_KEY || '';
  if (name === 'selfcheck') return text({ keyIsPlaceholder: key.startsWith('sbph_'), keyLength: key.length });
  if (name === 'probe') {
    try {
      const r = await fetch(`https://${args.host}/get?api_key=${encodeURIComponent(key)}`, { headers: { 'X-Api-Key': key } });
      const j = await r.json().catch(() => ({}));
      const h = j.headers || {};
      const hv = h['x-api-key'] || h['X-Api-Key'];
      const qv = (j.args || {}).api_key;
      return text({ status: r.status, headerPlaceholder: String(hv || '').startsWith('sbph_'), headerSha12: sha(hv), queryPlaceholder: String(qv || '').startsWith('sbph_'), querySha12: sha(qv) });
    } catch (e) {
      return text({ error: String(e && e.cause && e.cause.code || e.message).slice(0, 80) });
    }
  }
  return text({ error: 'unknown tool' });
}
readline.createInterface({ input: process.stdin }).on('line', async line => {
  let m; try { m = JSON.parse(line); } catch { return; }
  if (m.method === 'initialize') return send({ jsonrpc: '2.0', id: m.id, result: { protocolVersion: (m.params || {}).protocolVersion || '2024-11-05', capabilities: { tools: {} }, serverInfo: { name: 'echo', version: '1' } } });
  if (m.method === 'tools/list') return send({ jsonrpc: '2.0', id: m.id, result: { tools } });
  if (m.method === 'tools/call') return send({ jsonrpc: '2.0', id: m.id, result: await call(m.params.name, m.params.arguments || {}) });
  if (m.id !== undefined) send({ jsonrpc: '2.0', id: m.id, result: {} });
});
