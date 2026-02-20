/**
 * chunks.js — Chunk explorer with search and page filter
 */

const Chunks = (() => {
  let _docId  = null;
  let _chunks = [];
  let _searchTimer = null;

  function init() {
    document.getElementById('chunkSearch').addEventListener('input', () => {
      clearTimeout(_searchTimer);
      _searchTimer = setTimeout(renderTable, 200);
    });

    document.getElementById('chunkPageFilter').addEventListener('change', renderTable);
  }

  async function loadDocument(docId, pageCount) {
    _docId = docId;

    // Populate page filter
    const sel = document.getElementById('chunkPageFilter');
    sel.innerHTML = '<option value="">All pages</option>';
    for (let p = 1; p <= pageCount; p++) {
      const opt = document.createElement('option');
      opt.value = p;
      opt.textContent = `Page ${p}`;
      sel.appendChild(opt);
    }

    await fetchChunks();
  }

  async function fetchChunks() {
    if (!_docId) return;

    const search = document.getElementById('chunkSearch').value.trim();
    const page   = document.getElementById('chunkPageFilter').value || undefined;

    try {
      const result = await API.getChunks(_docId, { page: page ? +page : undefined, search: search || undefined });
      _chunks = result.chunks || [];
      renderTable();
    } catch (err) {
      _chunks = [];
      document.getElementById('chunkTableBody').innerHTML =
        `<tr><td colspan="3" class="table-empty">Error: ${escHtml(err.message)}</td></tr>`;
      document.getElementById('chunkCount').textContent = '0 chunks';
    }
  }

  function renderTable() {
    const search  = document.getElementById('chunkSearch').value.trim().toLowerCase();
    const pageVal = document.getElementById('chunkPageFilter').value;

    let rows = _chunks;
    if (search) rows = rows.filter(c => c.text.toLowerCase().includes(search));
    if (pageVal) rows = rows.filter(c => String(c.page_number) === pageVal);

    document.getElementById('chunkCount').textContent = `${rows.length} chunk${rows.length !== 1 ? 's' : ''}`;

    const tbody = document.getElementById('chunkTableBody');
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="3" class="table-empty">No chunks match the filter</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(chunk => `
      <tr>
        <td>${chunk.page_number ?? '—'}</td>
        <td>${chunk.chunk_index ?? '—'}</td>
        <td>
          <div class="chunk-text-cell" title="Click to expand">${escHtml(chunk.text)}</div>
        </td>
      </tr>
    `).join('');

    // Expand/collapse on click
    tbody.querySelectorAll('.chunk-text-cell').forEach(el => {
      el.addEventListener('click', () => el.classList.toggle('expanded'));
    });
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { init, loadDocument };
})();
