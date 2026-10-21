/* Run with: node tests/test_emoji_exporter.cjs (no npm dependencies). */
async function testEmojiExporter(source) {
  let checks = 0;
  function assert(condition, message) {
    checks++;
    if (!condition) throw new Error(message);
  }
  function environment() {
    const downloads = [], errors = [], timers = new Map();
    class FakeURL {
      constructor(input, base) {
        const value = String(input);
        const absolute = value.includes("://") ? value : new FakeURL(base).origin + value;
        const match = absolute.match(/^(https?:\/\/[^/]+)([^?#]*)(\?[^#]*)?/);
        if (!match) throw new Error("Invalid test URL");
        this.origin = match[1]; this.pathname = match[2]; this.search = match[3] || "";
      }
      static createObjectURL(blob) { downloads.push(blob); return "blob:test"; }
      static revokeObjectURL() {}
    }
    class FakeXHR {
      constructor() { this.events = new Map(); }
      open(...args) { this.arguments = args; return "opened"; }
      addEventListener(name, listener) { this.events.set(name, listener); }
      removeEventListener(name, listener) {
        if (this.events.get(name) === listener) this.events.delete(name);
      }
      respond(payload, responseType = "json", status = 200) {
        this.status = status; this.responseType = responseType;
        this.response = payload; this.responseText = JSON.stringify(payload);
        const listener = this.events.get("load");
        this.events.delete("load");
        listener?.();
      }
    }
    const originalFetch = function () { return this.nextResponse; };
    const originalOpen = FakeXHR.prototype.open;
    let timerId = 0;
    const window = {
      location: { hostname: "discord.com", origin: "https://discord.com",
        pathname: "/developers/applications/123/emojis", href: "https://discord.com/developers/applications/123/emojis" },
      fetch: originalFetch, XMLHttpRequest: FakeXHR, URL: FakeURL,
      Blob: class { constructor(parts) { this.text = parts.join(""); } },
      document: { body: { appendChild() {} }, createElement() { return { click() {}, remove() {} }; } },
      setTimeout(callback, delay) { const id = ++timerId; timers.set(id, { callback, delay }); return id; },
      clearTimeout(id) { timers.delete(id); },
      console: { log() {}, warn() {}, error(...args) { errors.push(args); } },
    };
    return { window, downloads, errors, timers, originalFetch, originalOpen };
  }
  const install = env => new Function("window", source)(env.window);
  const emoji = (id = "9007199254740993123", name = "soul_core", animated = false) => ({ id, name, animated, user: { secret: "omitted" } });
  const payload = { items: [emoji(), emoji("123456789012345678", "animated_core", true)] };
  const route = "/api/v9/applications/123/emojis";

  {
    const env = environment(); install(env);
    assert(env.window.farmerEmojiExport.status === "waiting", "Report waiting before any response");
    let rejected = false;
    try { env.window.farmerEmojiExport.download(); } catch { rejected = true; }
    assert(rejected && env.downloads.length === 0, "Explain retry before capture without downloading");
    const result = env.window.farmerEmojiExport.fromResponse(payload);
    assert(result.emoji_count === 2, "Export both emojis");
    assert(result.emojis.some(e => e.id === "9007199254740993123"), "Preserve exact snowflake strings");
    assert(result.references_by_name.animated_core === "<a:animated_core:123456789012345678>", "Animated mention");
    assert(result.references_by_name.soul_core === "<:soul_core:9007199254740993123>", "Static mention");
    assert(!JSON.stringify(result).includes("secret"), "Omit uploader and unrelated response data");
    assert(env.downloads.length === 1 && JSON.parse(env.downloads[0].text).application_id === "123", "Download parsed JSON");
    assert(!("soul-core" in result.references_by_name), "Do not invent API keys");
    assert(env.window.fetch === env.originalFetch && env.window.XMLHttpRequest.prototype.open === env.originalOpen, "Restore original browser functions");
    assert(env.window.farmerEmojiExport.status === "captured", "Report captured after cleanup");
    env.window.farmerEmojiExport.download();
    assert(env.downloads.length === 2 && env.downloads[0].text === env.downloads[1].text, "Retry the same JSON download after cleanup");
  }
  {
    const env = environment(); install(env);
    const createElement = env.window.document.createElement;
    let removed = false;
    env.window.document.createElement = () => ({
      click() { throw new Error("Download unavailable"); }, remove() { removed = true; },
    });
    const result = env.window.farmerEmojiExport.fromResponse(payload);
    assert(result.emoji_count === 2 && env.window.farmerEmojiExport.result === result,
      "Keep captured JSON available when download throws");
    assert(removed && env.errors.length === 1 && env.window.fetch === env.originalFetch &&
      env.window.XMLHttpRequest.prototype.open === env.originalOpen, "Clean up and report failed download");
    env.window.document.createElement = createElement;
    env.window.farmerEmojiExport.download();
    assert(JSON.parse(env.downloads[1].text).emoji_count === 2, "Retry after a failed automatic download");
  }
  {
    const env = environment(); install(env);
    const result = env.window.farmerEmojiExport.fromResponse({ items: [emoji("123", "same"), emoji("456", "same"), emoji("456", "same")] });
    assert(result.emoji_count === 2, "Deduplicate IDs without losing duplicate names");
    assert(result.duplicate_names[0] === "same" && !("same" in result.references_by_name), "Flag ambiguous names without overwriting");
  }
  for (const invalid of [{}, { items: [emoji(9007199254740992)] }, { items: [emoji("12", "bad-name")] },
    { items: [emoji("12", "valid", "false")] }, { items: [emoji("12", "first"), emoji("12", "second")] }]) {
    const env = environment(); install(env);
    let rejected = false;
    try { env.window.farmerEmojiExport.fromResponse(invalid); } catch { rejected = true; }
    assert(rejected && env.downloads.length === 0, "Reject malformed/conflicting data without a download");
    env.window.farmerEmojiExport.stop();
  }
  {
    const env = environment(); install(env);
    let cloned = false;
    env.window.nextResponse = Promise.resolve({ ok: true, clone() {
      cloned = true; return { json: async () => payload };
    } });
    const promise = env.window.fetch({ url: route, method: "GET" });
    assert(promise === env.window.nextResponse, "Preserve the original fetch promise");
    for (let i = 0; i < 6; i++) await Promise.resolve();
    assert(cloned && env.downloads.length === 1, "Capture fetch using a cloned response");
  }
  for (const [url, method, status] of [[route, "POST", 200], [route + "/999", "GET", 200],
    [route + "?limit=10", "GET", 200], ["/api/v9/applications/456/emojis", "GET", 200],
    ["https://example.com" + route, "GET", 200], [route, "GET", 403]]) {
    const env = environment(); install(env);
    const xhr = new env.window.XMLHttpRequest();
    assert(xhr.open(method, url, true) === "opened", "Preserve XHR open result");
    xhr.respond(payload, "json", status);
    assert(env.downloads.length === 0, "Ignore writes, individual records, pagination, other apps/origins, and failed requests");
    env.window.farmerEmojiExport.stop();
  }
  for (const type of ["json", ""]) {
    const env = environment(); install(env);
    const xhr = new env.window.XMLHttpRequest();
    xhr.open("GET", route, true); xhr.respond(payload, type);
    assert(env.downloads.length === 1, "Capture JSON and text XHR responses");
  }
  {
    const env = environment(); install(env);
    const oldController = env.window.farmerEmojiExport;
    const pending = new env.window.XMLHttpRequest(); pending.open("GET", route);
    install(env);
    assert(oldController !== env.window.farmerEmojiExport && pending.events.size === 0, "Reinstallation cleans up pending listeners");
    [...env.timers.values()].find(timer => timer.delay === 180000).callback();
    assert(env.window.fetch === env.originalFetch && env.window.XMLHttpRequest.prototype.open === env.originalOpen, "Timeout restores hooks");
    assert(env.window.farmerEmojiExport.status === "stopped", "Distinguish timeout from waiting and capture");
  }
  {
    const env = environment(); env.window.location.hostname = "example.com";
    let rejected = false;
    try { install(env); } catch { rejected = true; }
    assert(rejected && env.window.fetch === env.originalFetch, "Reject the wrong website without installing hooks");
  }
  return checks;
}

if (typeof module !== "undefined") module.exports = { testEmojiExporter };
if (typeof require === "function" && require.main === module) {
  const fs = require("node:fs");
  const path = require("node:path");
  const source = fs.readFileSync(path.join(__dirname, "../tools/export_application_emojis.js"), "utf8");
  testEmojiExporter(source).then(checks => console.log(`Passed ${checks} emoji exporter assertions.`))
    .catch(error => { console.error(error); process.exitCode = 1; });
}
