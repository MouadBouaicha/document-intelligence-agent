/**
 * viewer.js — Page viewer with layout region overlays
 */

const Viewer = (() => {
  let _docId     = null;
  let _pageCount = 1;
  let _curPage   = 1;
  let _showOverlays = true;

  // Colour map keyed by region_type (CSS variable names)
  const TYPE_COLORS = {
    text:    '#4e78c4',
    title:   '#e07b39',
    figure:  '#5faa5a',
    table:   '#c4544a',
    chart:   '#9970ab',
    header:  '#8c6d31',
    footer:  '#d38080',
    list:    '#60b7be',
    caption: '#c9aa71',
  };
  function colorFor(type) {
    const key = (type || '').toLowerCase();
    return TYPE_COLORS[key] || '#a0a0a0';
  }

  function init() {
    document.getElementById('prevPage').addEventListener('click', () => navigate(-1));
    document.getElementById('nextPage').addEventListener('click', () => navigate(+1));
    document.getElementById('showOverlays').addEventListener('change', e => {
      _showOverlays = e.target.checked;
      document.getElementById('overlayLayer').style.display = _showOverlays ? '' : 'none';
    });
  }

  function navigate(delta) {
    const next = _curPage + delta;
    if (next < 1 || next > _pageCount) return;
    loadPage(next);
  }

  async function loadDocument(docId, pageCount) {
    _docId     = docId;
    _pageCount = pageCount;
    _curPage   = 1;
    updateNav();
    await loadPage(1);
  }

  async function loadPage(pageNum) {
    _curPage = pageNum;
    updateNav();

    const img   = document.getElementById('pageImage');
    const layer = document.getElementById('overlayLayer');

    // Load image
    img.src = API.pageImageUrl(_docId, pageNum);

    // Wait for image to load so we know dimensions (non-fatal if it fails)
    await new Promise((res) => {
      if (img.complete && img.naturalWidth) { res(); return; }
      img.onload  = res;
      img.onerror = res;  // resolve anyway so the rest of the UI still renders
    });

    // Fetch layout
    let layout = { regions: [], width: img.naturalWidth, height: img.naturalHeight };
    try { layout = await API.getPageLayout(_docId, pageNum); } catch { /* ok */ }

    renderOverlays(layer, layout, img.naturalWidth, img.naturalHeight);
    renderLegend(layout.regions);
  }

  function renderOverlays(layer, layout, imgW, imgH) {
    layer.innerHTML = '';

    // Use the *displayed* image size (after CSS scaling) so the SVG maps correctly.
    const img = document.getElementById('pageImage');
    const dispW = img.offsetWidth  || imgW;
    const dispH = img.offsetHeight || imgH;
    layer.style.width  = dispW + 'px';
    layer.style.height = dispH + 'px';
    layer.setAttribute('viewBox', `0 0 ${imgW} ${imgH}`);

    layout.regions.forEach(region => {
      if ((region.confidence || 0) < 0.3) return;
      const [x1, y1, x2, y2] = region.bbox;
      const color = colorFor(region.region_type);

      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', x1);
      rect.setAttribute('y', y1);
      rect.setAttribute('width', x2 - x1);
      rect.setAttribute('height', y2 - y1);
      rect.setAttribute('stroke', color);
      rect.setAttribute('fill', color);
      rect.setAttribute('fill-opacity', '0.08');
      rect.setAttribute('class', 'overlay-rect');

      const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      title.textContent = `#${region.region_id} ${region.region_type} (${Math.round(region.confidence * 100)}%)`;
      rect.appendChild(title);

      layer.appendChild(rect);
    });

    layer.style.display = _showOverlays ? '' : 'none';
  }

  function renderLegend(regions) {
    const legend = document.getElementById('viewerLegend');
    const types  = [...new Set(regions.map(r => r.region_type))].sort();

    if (types.length === 0) { legend.innerHTML = ''; return; }

    let html = '<div class="legend-title">Region types</div>';
    types.forEach(t => {
      const color = colorFor(t);
      html += `
        <div class="legend-item">
          <div class="legend-swatch" style="background:${color}"></div>
          <span>${t}</span>
        </div>`;
    });
    legend.innerHTML = html;
  }

  function updateNav() {
    document.getElementById('currentPage').textContent = _curPage;
    document.getElementById('totalPages').textContent  = _pageCount;
    document.getElementById('prevPage').disabled = _curPage <= 1;
    document.getElementById('nextPage').disabled = _curPage >= _pageCount;
  }

  return { init, loadDocument };
})();
