/* Paste into the Console on your application's Discord Developer Portal page.
 * Then switch to General Information and back to Emojis without reloading.
 * Reads the next full emoji-list response and downloads parsed JSON locally.
 * No credentials are read and no requests or Discord changes are initiated.
 */
(() => {
  "use strict";
  const app = window.location.pathname.match(/^\/developers\/applications\/(\d+)(?:\/|$)/);
  if (window.location.hostname !== "discord.com" || !app) {
    throw new Error("Run this on https://discord.com/developers/applications/YOUR_APP_ID/emojis");
  }
  window.farmerEmojiExport?.stop();
  const applicationId = app[1];
  const originalFetch = window.fetch;
  const originalOpen = window.XMLHttpRequest.prototype.open;
  const listeners = new Map();
  let active = true;
  let timer;

  function isListRequest(input, method) {
    if (String(method || "GET").toUpperCase() !== "GET") return false;
    const url = new window.URL(input, window.location.href);
    return url.origin === window.location.origin &&
      new RegExp(`^/api(?:/v\\d+)?/applications/${applicationId}/emojis/?$`).test(url.pathname) &&
      !url.search; // Do not label a paginated response as a complete inventory.
  }

  function stop() {
    if (!active) return;
    active = false;
    window.clearTimeout(timer);
    if (window.fetch === captureFetch) window.fetch = originalFetch;
    if (window.XMLHttpRequest.prototype.open === captureOpen) {
      window.XMLHttpRequest.prototype.open = originalOpen;
    }
    for (const [xhr, listener] of listeners) xhr.removeEventListener("load", listener);
    listeners.clear();
  }

  function download() {
    const result = window.farmerEmojiExport.result;
    if (!result) throw new Error("No emoji list captured yet. Reopen the Emojis tab without reloading.");
    const blob = new window.Blob([JSON.stringify(result, null, 2) + "\n"], { type: "application/json" });
    const href = window.URL.createObjectURL(blob);
    const link = window.document.createElement("a");
    link.href = href;
    link.download = `application-emojis-${applicationId}.json`;
    try {
      window.document.body.appendChild(link);
      link.click();
    } finally {
      link.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(href), 10000);
    }
  }

  function exportResponse(payload) {
    if (!active) return;
    const items = Array.isArray(payload) ? payload : payload?.items;
    if (!Array.isArray(items)) throw new Error("Expected an emoji list or an object with an items array.");
    const byId = new Map();
    for (const item of items) {
      if (!item || typeof item.id !== "string" || !/^\d+$/.test(item.id) ||
          typeof item.name !== "string" || !/^[A-Za-z0-9_]+$/.test(item.name) ||
          (item.animated !== undefined && typeof item.animated !== "boolean")) {
        throw new Error("An emoji has an invalid name, ID, or animation flag; no export was made.");
      }
      const emoji = {
        id: item.id, name: item.name, animated: item.animated === true,
        mention: `<${item.animated ? "a" : ""}:${item.name}:${item.id}>`,
      };
      if (byId.has(item.id) && JSON.stringify(byId.get(item.id)) !== JSON.stringify(emoji)) {
        throw new Error(`Conflicting records for emoji ID ${item.id}; no export was made.`);
      }
      byId.set(item.id, emoji);
    }
    const emojis = [...byId.values()].sort((a, b) =>
      a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
    const names = new Map();
    for (const emoji of emojis) names.set(emoji.name, (names.get(emoji.name) || 0) + 1);
    const result = {
      application_id: applicationId,
      exported_at: new Date().toISOString(),
      emoji_count: emojis.length,
      emojis,
      // These are Discord names, not guessed PoE2Scout API mapping keys.
      references_by_name: Object.fromEntries(emojis
        .filter(emoji => names.get(emoji.name) === 1)
        .map(emoji => [emoji.name, emoji.mention])),
      duplicate_names: [...names].filter(([, count]) => count > 1).map(([name]) => name),
    };
    window.farmerEmojiExport.result = result;
    stop();
    try { download(); }
    catch (error) { window.console.error("Emoji download:", error.message); }
    window.console.log(`Captured ${emojis.length} emojis; requested download of application-emojis-${applicationId}.json. ` +
      "If no file appeared, run farmerEmojiExport.download() to retry, or copy(JSON.stringify(farmerEmojiExport.result, null, 2)) to copy the JSON.", result);
    return result;
  }

  function captureFetch(input, options) {
    const responsePromise = Reflect.apply(originalFetch, this, arguments);
    try {
      if (isListRequest(typeof input === "string" ? input : input?.url || String(input),
          options?.method || input?.method)) {
        responsePromise.then(response => {
          if (active && response.ok) return response.clone().json().then(exportResponse);
        }).catch(error => window.console.error("Emoji export:", error.message));
      }
    } catch (error) { window.console.error("Emoji export:", error.message); }
    return responsePromise;
  }

  function captureOpen(method, url) {
    const result = Reflect.apply(originalOpen, this, arguments);
    try {
      if (listeners.has(this)) this.removeEventListener("load", listeners.get(this));
      listeners.delete(this);
      if (isListRequest(url, method)) {
        const xhr = this;
        const listener = () => {
          listeners.delete(xhr);
          if (!active || xhr.status < 200 || xhr.status >= 300) return;
          try {
            exportResponse(xhr.responseType === "json" ? xhr.response : JSON.parse(xhr.responseText));
          } catch (error) { window.console.error("Emoji export:", error.message); }
        };
        listeners.set(xhr, listener);
        xhr.addEventListener("load", listener, { once: true });
      }
    } catch (error) { window.console.error("Emoji export:", error.message); }
    return result;
  }

  window.farmerEmojiExport = {
    stop, download, fromResponse: exportResponse, result: null,
    get status() { return this.result ? "captured" : active ? "waiting" : "stopped"; },
  };
  window.fetch = captureFetch;
  window.XMLHttpRequest.prototype.open = captureOpen;
  timer = window.setTimeout(() => {
    stop();
    window.console.warn("Emoji exporter timed out. Paste it again, then reopen the Emojis tab without reloading.");
  }, 180000);
  window.console.log("Exporter ready. Switch to General Information, then back to Emojis. Do not reload the page.");
})();
