/**
 * app.js — Main controller: tab switching, state, component coordination
 */

(async function () {
  // ── Theme ──────────────────────────────────────────────────────
  const root = document.documentElement;
  const savedTheme = localStorage.getItem('theme') || 'light';
  root.dataset.theme = savedTheme;

  document.getElementById('themeToggle').addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    localStorage.setItem('theme', next);
  });

  // ── Tab switching ──────────────────────────────────────────────
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const panelId = tab.dataset.tab;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector(`.tab-panel[data-panel="${panelId}"]`).classList.add('active');
    });
  });

  // ── Init components ────────────────────────────────────────────
  Viewer.init();
  Chunks.init();
  Chat.init();

  let _activeDocId = null;

  Sidebar.init({
    onSelect: loadDocument,
    onDelete: () => {
      _activeDocId = null;
      showEmpty();
    },
  });

  // ── Delete button ──────────────────────────────────────────────
  document.getElementById('deleteDocBtn').addEventListener('click', async () => {
    if (!_activeDocId) return;
    if (!confirm('Delete this document and its indexed data?')) return;
    try {
      await API.deleteDocument(_activeDocId);
      _activeDocId = null;
      showEmpty();
      await Sidebar.refreshDocList();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  });

  // ── Load existing documents on startup ────────────────────────
  await Sidebar.refreshDocList();

  // ── Core functions ─────────────────────────────────────────────

  async function loadDocument(docId) {
    _activeDocId = docId;
    Sidebar.setActiveDoc(docId);

    let doc;
    try {
      doc = await API.getDocument(docId);
    } catch (err) {
      alert(`Failed to load document: ${err.message}`);
      return;
    }

    // Update header
    document.getElementById('docTitle').textContent  = doc.filename;
    document.getElementById('docMeta').textContent   =
      `${doc.page_count} page${doc.page_count !== 1 ? 's' : ''} · ` +
      `${doc.total_layout_regions} layout regions · ` +
      `${doc.total_text_regions} text regions`;

    showContent();

    // Load all tabs
    await Promise.all([
      Viewer.loadDocument(docId, doc.page_count),
      Chunks.loadDocument(docId, doc.page_count),
    ]);
    Chat.loadDocument(docId);
  }

  function showEmpty() {
    document.getElementById('emptyState').classList.remove('hidden');
    document.getElementById('content').classList.add('hidden');
  }

  function showContent() {
    document.getElementById('emptyState').classList.add('hidden');
    document.getElementById('content').classList.remove('hidden');
  }
})();
