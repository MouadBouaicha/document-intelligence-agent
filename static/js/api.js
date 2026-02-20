/**
 * api.js — HTTP client wrappers and SSE stream parser
 */

const API = (() => {
  const BASE = '';   // same origin

  async function get(path) {
    const res = await fetch(BASE + path);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function del(path) {
    const res = await fetch(BASE + path, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  async function postForm(path, formData) {
    const res = await fetch(BASE + path, { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  /**
   * SSE via GET — returns an EventSource.
   * onEvent(eventType, data) called for each event.
   */
  function sseGet(path, onEvent, onError) {
    const es = new EventSource(BASE + path);
    let completed = false;  // true once we receive 'done' or 'error'

    const handled = ['ping', 'progress', 'done', 'error'];
    handled.forEach(type => {
      es.addEventListener(type, e => {
        if (type === 'done' || type === 'error') completed = true;
        try { onEvent(type, JSON.parse(e.data)); }
        catch { onEvent(type, e.data); }
      });
    });

    // onerror fires both on real errors AND when the server closes the stream
    // (EventSource tries to reconnect, fails, fires onerror). Ignore it if
    // we already received 'done'.
    es.onerror = (e) => {
      es.close();
      if (!completed && onError) onError(e);
    };

    return es;
  }

  /**
   * SSE via POST (fetch + ReadableStream).
   * Returns a Promise that resolves when the stream closes.
   * onEvent(eventType, data) called for each SSE event.
   */
  async function ssePost(path, body, onEvent) {
    const res = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop();  // incomplete last block

      for (const block of blocks) {
        if (!block.trim()) continue;
        let eventType = 'message';
        let dataStr = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) dataStr = line.slice(5).trim();
        }

        if (dataStr) {
          try { onEvent(eventType, JSON.parse(dataStr)); }
          catch { onEvent(eventType, dataStr); }
        }
      }
    }
  }

  // ── Document endpoints ─────────────────────────────────────────

  function listDocuments() {
    return get('/api/documents');
  }

  function getDocument(docId) {
    return get(`/api/documents/${docId}`);
  }

  async function uploadDocument(file) {
    const fd = new FormData();
    fd.append('file', file);
    return postForm('/api/documents/upload', fd);
  }

  function processDocument(docId, onEvent, onError) {
    return sseGet(`/api/documents/${docId}/process`, onEvent, onError);
  }

  function deleteDocument(docId) {
    return del(`/api/documents/${docId}`);
  }

  function pageImageUrl(docId, page) {
    return `/api/documents/${docId}/pages/${page}/image`;
  }

  function getPageLayout(docId, page) {
    return get(`/api/documents/${docId}/pages/${page}/layout`);
  }

  function getChunks(docId, { page, search } = {}) {
    const params = new URLSearchParams();
    if (page != null) params.set('page', page);
    if (search) params.set('search', search);
    return get(`/api/documents/${docId}/chunks?${params}`);
  }

  // ── Chat endpoints ─────────────────────────────────────────────

  function chat(docId, message, sessionId, onEvent) {
    return ssePost('/api/chat', { doc_id: docId, message, session_id: sessionId || '' }, onEvent);
  }

  function clearHistory(sessionId) {
    return del(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`);
  }

  return {
    listDocuments,
    getDocument,
    uploadDocument,
    processDocument,
    deleteDocument,
    pageImageUrl,
    getPageLayout,
    getChunks,
    chat,
    clearHistory,
  };
})();
