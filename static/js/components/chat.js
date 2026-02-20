/**
 * chat.js — Chat UI with tool call visibility and markdown rendering
 */

const Chat = (() => {
  let _docId     = null;
  let _sessionId = '';
  let _streaming = false;

  // Pending assistant message DOM node while streaming
  let _pendingMsg = null;
  let _pendingBody = null;

  function init() {
    document.getElementById('chatSend').addEventListener('click', sendMessage);
    document.getElementById('chatInput').addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    document.getElementById('clearChatBtn').addEventListener('click', clearChat);
  }

  function loadDocument(docId) {
    _docId     = docId;
    _sessionId = '';   // new session for each document switch
    clearMessages();
  }

  function clearMessages() {
    const container = document.getElementById('chatMessages');
    container.innerHTML = `
      <div class="chat-welcome">
        <p>Ask any question about the document. I can search text, analyze charts, tables, and images.</p>
      </div>`;
  }

  async function clearChat() {
    if (_sessionId) {
      try { await API.clearHistory(_sessionId); } catch { /* ok */ }
      _sessionId = '';
    }
    clearMessages();
  }

  async function sendMessage() {
    if (_streaming || !_docId) return;
    const input = document.getElementById('chatInput');
    const text  = input.value.trim();
    if (!text) return;

    input.value = '';
    input.disabled = true;
    document.getElementById('chatSend').disabled = true;
    _streaming = true;

    appendUserMessage(text);
    const assistantEl = appendAssistantMessage();

    try {
      await API.chat(_docId, text, _sessionId, (type, data) => {
        switch (type) {
          case 'session':
            _sessionId = data.session_id;
            break;
          case 'tool_call':
            appendToolCard(assistantEl, 'call', data.name, JSON.stringify(data.args, null, 2));
            break;
          case 'tool_result':
            appendToolCard(assistantEl, 'result', data.name, data.result);
            break;
          case 'answer':
            setAssistantText(assistantEl, data.content);
            break;
          case 'error':
            setAssistantText(assistantEl, `⚠ Error: ${data.message}`, true);
            break;
        }
      });
    } catch (err) {
      setAssistantText(assistantEl, `⚠ ${err.message}`, true);
    } finally {
      _streaming = false;
      input.disabled = false;
      document.getElementById('chatSend').disabled = false;
      input.focus();
      removeTyping(assistantEl);
    }
  }

  function appendUserMessage(text) {
    const container = document.getElementById('chatMessages');
    // Remove welcome msg if present
    container.querySelector('.chat-welcome')?.remove();

    const el = document.createElement('div');
    el.className = 'msg user';
    el.innerHTML = `
      <div class="msg-avatar">U</div>
      <div class="msg-body">
        <div class="msg-bubble">${escHtml(text)}</div>
      </div>`;
    container.appendChild(el);
    scrollToBottom();
  }

  function appendAssistantMessage() {
    const container = document.getElementById('chatMessages');
    const el = document.createElement('div');
    el.className = 'msg assistant';
    el.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-body">
        <div class="typing-dots">
          <span></span><span></span><span></span>
        </div>
      </div>`;
    container.appendChild(el);
    scrollToBottom();
    return el;
  }

  function appendToolCard(msgEl, kind, name, content) {
    const body = msgEl.querySelector('.msg-body');
    const card = document.createElement('div');
    card.className = 'tool-card';

    const badgeClass = kind === 'call' ? 'badge-call' : 'badge-result';
    const label      = kind === 'call' ? 'Tool call' : 'Tool result';

    card.innerHTML = `
      <div class="tool-card-header">
        <span class="tool-badge ${badgeClass}">${label}</span>
        <span class="tool-name">${escHtml(name)}</span>
        <svg class="tool-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
      <div class="tool-card-body">${escHtml(content)}</div>`;

    card.querySelector('.tool-card-header').addEventListener('click', () => {
      card.classList.toggle('open');
    });

    body.appendChild(card);
    scrollToBottom();
  }

  function setAssistantText(msgEl, markdown, isError = false) {
    const body = msgEl.querySelector('.msg-body');
    // Remove typing dots
    body.querySelector('.typing-dots')?.remove();
    // Remove existing bubble (in case of retry)
    body.querySelector('.msg-bubble')?.remove();

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    if (isError) bubble.style.color = 'var(--danger)';
    bubble.innerHTML = renderMarkdown(markdown);
    body.appendChild(bubble);
    scrollToBottom();
  }

  function removeTyping(msgEl) {
    msgEl.querySelector('.typing-dots')?.remove();
  }

  /** Very lightweight Markdown renderer (bold, inline code, code blocks, paragraphs) */
  function renderMarkdown(text) {
    let html = escHtml(text);

    // Code blocks
    html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
      `<pre><code>${code.trim()}</code></pre>`
    );

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Line breaks → paragraphs
    html = html
      .split(/\n\n+/)
      .map(p => p.trim())
      .filter(Boolean)
      .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
      .join('');

    return html;
  }

  function scrollToBottom() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
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
