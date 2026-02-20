/**
 * sidebar.js — Document upload + document list
 */

const Sidebar = (() => {
  let onDocumentSelected = null;
  let onDocumentDeleted  = null;

  function init({ onSelect, onDelete }) {
    onDocumentSelected = onSelect;
    onDocumentDeleted  = onDelete;

    const dropZone  = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    // dropZone is a <label for="fileInput"> — clicking it opens the picker natively.
    // No JS click handler needed.
    fileInput.addEventListener('change', () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });

    // Drag & drop
    dropZone.addEventListener('dragover', e => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });
  }

  async function handleFile(file) {
    showProgress(0, 'Uploading…');

    let uploadResult;
    try {
      uploadResult = await API.uploadDocument(file);
    } catch (err) {
      showProgress(-1, `Upload failed: ${err.message}`);
      return;
    }

    const { doc_id, filename, already_processed } = uploadResult;

    if (already_processed) {
      showProgress(1, 'Already processed!');
      setTimeout(() => hideProgress(), 1200);
      await refreshDocList();
      onDocumentSelected && onDocumentSelected(doc_id);
      return;
    }

    showProgress(0.05, 'Processing…');

    const es = API.processDocument(doc_id, (type, data) => {
      if (type === 'ping') {
        // connection confirmed, nothing to do
      } else if (type === 'progress') {
        showProgress(data.pct || 0, data.msg || 'Processing…');
      } else if (type === 'done') {
        showProgress(1, 'Done!');
        setTimeout(() => hideProgress(), 1000);
        refreshDocList().then(() => {
          onDocumentSelected && onDocumentSelected(data.doc_id);
        });
        es.close();
      } else if (type === 'error') {
        showProgress(-1, `Error: ${data.message}`);
        es.close();
      }
    }, err => {
      showProgress(-1, 'Connection error during processing');
    });
  }

  function showProgress(pct, msg) {
    const wrap = document.getElementById('uploadProgress');
    const bar  = document.getElementById('progressBar');
    const msgEl = document.getElementById('progressMsg');

    wrap.classList.remove('hidden');
    msgEl.textContent = msg;

    if (pct < 0) {
      bar.style.background = 'var(--danger)';
      bar.style.width = '100%';
    } else {
      bar.style.background = 'var(--accent)';
      bar.style.width = `${Math.round(pct * 100)}%`;
    }
  }

  function hideProgress() {
    document.getElementById('uploadProgress').classList.add('hidden');
    document.getElementById('progressBar').style.width = '0%';
  }

  async function refreshDocList() {
    let docs;
    try {
      docs = await API.listDocuments();
    } catch {
      docs = [];
    }

    const list   = document.getElementById('docList');
    const count  = document.getElementById('docCount');
    count.textContent = docs.length;

    if (docs.length === 0) {
      list.innerHTML = '<li class="doc-list-empty">No documents loaded</li>';
      return;
    }

    list.innerHTML = '';
    docs.forEach(doc => {
      const li = document.createElement('li');
      li.className = 'doc-item';
      li.dataset.docId = doc.doc_id;
      li.innerHTML = `
        <div class="doc-item-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="doc-item-info">
          <div class="doc-item-name" title="${escHtml(doc.filename)}">${escHtml(doc.filename)}</div>
          <div class="doc-item-meta">${doc.page_count} page${doc.page_count !== 1 ? 's' : ''} · ${doc.total_layout_regions} regions</div>
        </div>
      `;
      li.addEventListener('click', () => {
        setActiveDoc(doc.doc_id);
        onDocumentSelected && onDocumentSelected(doc.doc_id);
      });
      list.appendChild(li);
    });
  }

  function setActiveDoc(docId) {
    document.querySelectorAll('.doc-item').forEach(el => {
      el.classList.toggle('active', el.dataset.docId === docId);
    });
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { init, refreshDocList, setActiveDoc };
})();
