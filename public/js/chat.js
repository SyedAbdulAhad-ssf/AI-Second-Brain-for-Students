(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const starters = [
    'Explain the main concepts of this chapter in simple words',
    'List all important formulas and definitions for exam',
    'How do we predict the direction and extent of reaction using Kc and Qc?',
    'Give me 5 important short questions with answers from these notes'
  ];
  let notes = [], current = null, messages = [];

  function install() {
    const view = $('#view-chat');
    if (!view) return;
    view.innerHTML = `<div class="page-heading"><p class="eyebrow">YOUR PERSONAL STUDY PARTNER</p><h1>Chat With Your Notes</h1><p class="muted">Ask in English or Roman Urdu and get a clear answer from your saved material.</p></div><section class="chat-workspace"><header class="chat-context"><label>Active note<select id="chat-note-select"><option value="">Loading saved notes…</option></select></label><span id="chat-badge" class="document-badge">No note selected</span><span id="chat-status" class="tutor-status">AI Tutor Ready — Grounded in Your Notes</span><button class="button secondary" id="clear-chat" type="button">Clear Chat</button></header><div class="sample-chips" id="sample-chips">${starters.map(question => `<button type="button" data-question="${esc(question)}">${esc(question)}</button>`).join('')}</div><div class="chat-stream" id="chat-stream"><div class="chat-empty">Choose a saved note to begin.</div></div><form class="chat-input" id="chat-form"><input id="chat-question" maxlength="1500" placeholder="Ask about the selected note…" autocomplete="off"><button class="button primary" type="submit">Send <span>→</span></button></form><p class="form-message" id="chat-message" role="status"></p></section>`;
    $('#chat-note-select').addEventListener('change', event => open(Number(event.target.value)));
    $('#chat-form').addEventListener('submit', send);
    $('#clear-chat').addEventListener('click', clear);
    $('#sample-chips').addEventListener('click', prompt);
    $('#chat-stream').addEventListener('click', prompt);
  }
  function syncNotes(nextNotes = notes, selectedId = current?.id || window.appState?.currentNote?.id) {
    notes = nextNotes || [];
    const select = $('#chat-note-select');
    if (!select) return;
    select.innerHTML = '<option value="">Choose a saved note</option>' + notes.map(note => `<option value="${note.id}">${esc(note.title)}</option>`).join('');
    const id = Number(selectedId) || Number(notes[0]?.id) || null;
    if (id) {
      select.value = String(id);
      if (select.value && Number(current?.id) !== id) open(id);
    } else {
      current = null;
      $('#chat-badge').textContent = 'No note selected';
      render([]);
    }
  }
  async function load() {
    try {
      const data = await API.request('/api/notes');
      syncNotes(data.notes || [], window.appState?.currentNote?.id || window.Notes?.selectedId?.());
    } catch (error) { message(error.message); }
  }
  async function open(id) {
    if (!id) return;
    try {
      const data = await API.request(`/api/rag/chat/${id}`);
      current = data.note;
      window.appState = window.appState || {};
      window.appState.currentNote = {...(window.appState.currentNote || {}), ...current};
      $('#chat-note-select').value = String(id);
      $('#chat-badge').textContent = `Active Note: ${current.title}`;
      messages = data.messages || [];
      render(messages);
    } catch (error) { message(error.message); }
  }
  function render(items) {
    messages = items || [];
    const stream = $('#chat-stream');
    if (!stream) return;
    stream.innerHTML = messages.length ? messages.map(item => `<article class="chat-bubble ${item.role === 'user' ? 'user' : 'assistant'}"><strong>${item.role === 'assistant' ? 'AI Study Tutor' : 'You'}</strong><p>${esc(item.message)}</p>${item.source_reference ? `<div class="source-pill">Source: ${esc(item.source_reference)}</div>` : ''}</article>`).join('') : '<div class="chat-empty">Ask a question about this note. Your answer will include its source.</div>';
    stream.scrollTop = stream.scrollHeight;
  }
  function prompt(event) {
    const button = event.target.closest('[data-question]');
    if (!button) return;
    $('#chat-question').value = button.dataset.question;
    send(new Event('submit', {cancelable:true}));
  }
  async function send(event) {
    event?.preventDefault();
    const input = $('#chat-question'), question = input.value.trim();
    if (!current || !question) return message(current ? 'Write a question first.' : 'Choose a saved note first.');
    const button = $('#chat-form button');
    button.disabled = true;
    button.textContent = 'Thinking…';
    $('#chat-status').textContent = 'Reading your note…';
    try {
      const data = await API.request('/api/rag/chat', {method:'POST', body:JSON.stringify({note_id:current.id, question})});
      messages = [...messages, data.user_message, data.assistant_message];
      render(messages);
      if (data.suggested_followups?.length) {
        const followups = document.createElement('div');
        followups.className = 'followups';
        followups.innerHTML = data.suggested_followups.map(item => `<button type="button" data-question="${esc(item)}">${esc(item)}</button>`).join('');
        $('#chat-stream').append(followups);
      }
      input.value = '';
      $('#chat-status').textContent = 'AI Tutor Ready — Grounded in Your Notes';
    } catch (error) { message(error.message); $('#chat-status').textContent = 'Tutor temporarily unavailable'; }
    finally { button.disabled = false; button.innerHTML = 'Send <span>→</span>'; }
  }
  async function clear() {
    if (!current) return;
    try {
      await API.request(`/api/rag/chat/${current.id}`, {method:'DELETE'});
      messages = [];
      render(messages);
      message('Chat cleared.');
    } catch (error) { message(error.message); }
  }
  function message(text) { const node = $('#chat-message'); if (node) node.textContent = text; }
  window.NoteTutor = {init:async () => {install(); await load();}, syncNotes};
})();
