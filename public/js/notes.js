/* Phase 2 notes UI: file extraction, saved-note CRUD, analysis results, and Mermaid studio. */
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const cleanTextbookText = value => String(value || '').replace(/\bSindh\s+Textbook\s+Board(?:\s+Jamshoro)?\b/gi, ' ').replace(/\bSTUDENTS\s+LEARNING\s+OUT\s+COMES\s*\(\s*SLO'?S\s*\)/gi, ' ').replace(/\b\d{1,3}\s+(?=Chemical\s+Equilibrium\b)/gi, '').split(/\r?\n/).map(line => line.replace(/^\s*\d{1,3}\s+(?=[A-Z][A-Za-z ]{2,60}$)/, '').replace(/^\s*\d{1,3}\s*$/, '').replace(/[ \t]{2,}/g,' ').trim()).filter(line => line && /[A-Za-z]{3}/.test(line)).join('\n').trim();
  function sanitizeMermaidCode(code) {
    if (!code || typeof code !== 'string') return '';
    let text = code.trim();
    text = text.replace(/^```(?:mermaid)?\s*/i, '').replace(/\s*```$/i, '').replace(/```(?:mermaid)?/gi, '').trim();
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (text.includes('\\n')) text = text.replace(/\\n/g, '\n');
    if (/^mindmap\b/i.test(text)) {
      const lines=text.split('\n').filter(line=>line.trim());
      const rootSource=lines.find(line=>/^\s*root\b/i.test(line))||'  root((Study topic))';
      const rootLine=rootSource.trim();
      const rootLabel=rootLine.replace(/^root\s*/i,'').replace(/[^A-Za-z0-9 _-]/g,' ').replace(/\s+/g,' ').trim()||'Study topic';
      const rootIndent=rootSource.length-rootSource.trimStart().length;
      const children=lines.filter(line=>!/^\s*(?:mindmap|root\b|%%)/i.test(line)).map(line=>{const sourceIndent=line.length-line.trimStart().length;let indent=Math.max(4,Math.min(12,sourceIndent-rootIndent+2));if(indent%2)indent++;const label=line.replace(/[^A-Za-z0-9 _-]/g,' ').replace(/\s+/g,' ').trim();return label?{indent,label}:null}).filter(Boolean);
      return `mindmap\n  root(( ${rootLabel.slice(0,90)} ))${children.slice(0,30).map(child=>`\n${' '.repeat(child.indent)}${child.label.slice(0,90)}`).join('')}`;
    }
    text = text.replace(/^((?:flowchart|graph)\s+[A-Za-z]{2}|mindmap)\s+([^\n]+)/i, '$1\n  $2');
    text = text.replace(/(^\s*|(?:-->|---|-.->|==>)\s*)([A-Za-z0-9_]+)\s+([\[\{\(\>])/gm, '$1$2$3');

    let prev;
    do {
      prev = text;
      text = text.replace(/([\]\)\}]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))/g, '$1\n  $2');
    } while (prev !== text);

    do {
      prev = text;
      text = text.replace(/((?:-->|---|-.->|==>)(?:\|[^|\n]*\|)?\s*[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))/g, '$1\n  $2');
    } while (prev !== text);

    const lines = text.split('\n');
    const cleaned = [];
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      const parts = [];
      let cur = '', inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQ = !inQ; cur += ch; }
        else if (ch === ';' && !inQ) { parts.push(cur.trim()); cur = ''; }
        else { cur += ch; }
      }
      if (cur.trim()) parts.push(cur.trim());

      for (let part of parts) {
        if (!part) continue;
        part = part.replace(/(^\s*|(?:-->|---|-.->|==>)\s*)([A-Za-z0-9_]+)\s+([\[\{\(\>])/m, '$1$2$3');
        // Preserve quoted flowchart labels, including physics formulas and punctuation.
        part = part.replace(/(\|)(.*?)(\|)/g, (m, p1, p2, p3) => p1 + p2.replace(/"/g, "'") + p3);

        if (/^(?:flowchart|graph|mindmap|subgraph|end)\b/i.test(part)) {
          cleaned.push(part);
        } else {
          cleaned.push(`  ${part}`);
        }
      }
    }
    return cleaned.join('\n');
  }
  window.sanitizeMermaidCode = sanitizeMermaidCode;
  const loadScript = (src, test) => new Promise((resolve, reject) => {
    if (test()) return resolve();
    const found = document.querySelector(`script[src="${src}"]`);
    const script = found || document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    if (!found) document.head.append(script);
  });
  let notes = [], selected = null, activeDiagram = 'flowchart', zoom = 1, pendingPageImages = [];
  let mermaidReady = false;
  const noteView = $('#view-notes'), diagramView = $('#view-diagrams');

  function installUI() {
    if (!noteView || !diagramView) return;
    const work = $('.work-card', noteView);
    work.innerHTML = `<div class="notes-layout">
      <section class="notes-editor"><div class="notes-form-head"><div><p class="eyebrow">CAPTURE & UNDERSTAND</p><h2>Build a study note</h2></div><span class="phase-badge">AI STUDY TOOLS</span></div>
      <form id="note-form"><label class="field-label" for="note-title">Note title</label><input id="note-title" name="title" maxlength="180" placeholder="e.g. Photosynthesis" required>
      <label class="field-label" for="note-subject">Subject <span class="muted">(optional)</span></label><input id="note-subject" name="subject" maxlength="100" placeholder="e.g. Biology">
      <label class="field-label">Add your material</label><label class="drop-zone" id="note-drop-zone"><span class="drop-icon">↑</span><span><strong>Choose a PDF, TXT, or Markdown file</strong><small>Text is extracted in your browser · up to 1 GB</small></span><input id="note-file" type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" hidden></label>
      <div class="upload-status" id="file-label" aria-live="polite">Ready for your notes</div>
      <label class="field-label" for="note-content">Your notes</label><textarea id="note-content" name="raw_content" rows="9" maxlength="100000" placeholder="Paste your notes here, or upload a file above…" required></textarea>
      <div class="notes-form-foot"><span class="muted tiny" id="content-count">0 / 100,000 characters</span><button class="button primary" id="generate-note" type="submit">✦ Generate study guide <span>→</span></button></div>
      <p class="form-message" id="notes-message" role="status"></p></form></section>
      <aside class="saved-notes"><div class="saved-head"><div><p class="eyebrow">YOUR LIBRARY</p><h3>Saved notes</h3></div><span class="note-count" id="note-count">0</span></div><div class="saved-list" id="saved-list"><div class="saved-empty">Your saved notes will appear here.</div></div></aside></div>
      <div class="generated-output" id="generated-output"><div class="output-empty"><span>✦</span><strong>Your study guide will appear here</strong><small>Add some notes above to generate a summary, key points, definitions, and diagrams.</small></div></div>`;
    $('.empty-feature', diagramView).outerHTML = `<div class="diagram-studio"><div class="studio-header"><div><p class="eyebrow">VISUALIZE YOUR IDEAS</p><h2>Diagram studio</h2><p class="muted">Explore how your notes connect and export a copy for your study materials.</p></div><label class="diagram-select-label">Saved note<select id="diagram-note-select"><option value="">Choose a saved note</option></select></label></div>
      <div class="diagram-tabs" role="tablist"><button class="diagram-tab active" data-diagram="flowchart" role="tab">Step-by-step flowchart</button><button class="diagram-tab" data-diagram="mindmap" role="tab">Mind map / knowledge graph</button></div>
      <div class="diagram-toolbar"><div class="zoom-tools"><button data-zoom="out" aria-label="Zoom out">−</button><button data-zoom="reset" aria-label="Reset zoom">100%</button><button data-zoom="in" aria-label="Zoom in">＋</button></div><div class="export-tools"><button class="button secondary" id="export-svg">Export SVG</button><button class="button secondary" id="export-png">Download PNG</button><button class="button secondary" id="print-diagram">Print / PDF</button><button class="button primary" id="regenerate-diagrams">↻ Regenerate</button></div></div>
      <div class="diagram-canvas" id="diagram-canvas"><div class="diagram-placeholder">Choose a saved note to see its diagrams.</div></div>
      <details class="mermaid-editor"><summary>Edit Mermaid code</summary><textarea id="mermaid-code" rows="8" spellcheck="false" aria-label="Mermaid diagram source"></textarea><div class="editor-actions"><span class="muted tiny" id="diagram-message">Edit the code and preview it live.</span><button class="button secondary" id="render-code">Preview code</button></div></details></div>`;
    $('.placeholder-banner', noteView)?.remove();
    bindUI();
  }

  function bindUI() {
    $('#note-form').addEventListener('submit', generateNote);
    $('#note-content').addEventListener('input', () => $('#content-count').textContent = `${$('#note-content').value.length.toLocaleString()} / 100,000 characters`);
    $('#note-file').addEventListener('change', event => { if (event.target.files[0]) extractFile(event.target.files[0]); });
    const zone = $('#note-drop-zone');
    zone.addEventListener('dragover', event => { event.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', event => { event.preventDefault(); zone.classList.remove('drag-over'); const file=event.dataTransfer.files[0]; if(file) extractFile(file); });
    $('#saved-list').addEventListener('click', event => { const del=event.target.closest('[data-delete]'); if(del){event.stopPropagation();deleteNote(Number(del.dataset.delete));return} const row=event.target.closest('[data-note-id]');if(row)openNote(Number(row.dataset.noteId)); });
    $('#diagram-note-select').addEventListener('change', event => { if(event.target.value) openNote(Number(event.target.value)); });
    document.querySelector('.nav-item[data-view="diagrams"]')?.addEventListener('click',()=>{if(selected){$('#mermaid-code').value=sanitizeMermaidCode(activeDiagram==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);setTimeout(renderDiagram,0)}});
    document.querySelectorAll('.diagram-tab').forEach(tab=>tab.addEventListener('click',()=>{activeDiagram=tab.dataset.diagram;document.querySelectorAll('.diagram-tab').forEach(t=>t.classList.toggle('active',t===tab));if(selected)$('#mermaid-code').value=sanitizeMermaidCode(activeDiagram==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);renderDiagram()}));
    document.querySelectorAll('[data-zoom]').forEach(button=>button.addEventListener('click',()=>{zoom=button.dataset.zoom==='reset'?1:Math.min(2.5,Math.max(.5,zoom+(button.dataset.zoom==='in'?.15:-.15)));$('#diagram-canvas').style.setProperty('--diagram-zoom',zoom);$('#diagram-canvas [data-mermaid-svg]')?.style.setProperty('transform',`scale(${zoom})`);$('#diagram-canvas [data-mermaid-svg]')?.style.setProperty('transform-origin','center center');document.querySelector('[data-zoom="reset"]').textContent=`${Math.round(zoom*100)}%`}));
    $('#render-code').addEventListener('click',renderDiagram);
    $('#regenerate-diagrams').addEventListener('click',regenerate);
    $('#export-svg').addEventListener('click',exportSVG);$('#export-png').addEventListener('click',exportPNG);$('#print-diagram').addEventListener('click',printDiagram);
    $('#generated-output').addEventListener('click',event=>{if(event.target.closest('[data-copy-summary]'))navigator.clipboard?.writeText(selected?.summary||'').then(()=>flash(event.target.closest('[data-copy-summary]'),'Copied'));if(event.target.closest('[data-show-diagram]')){switchToDiagram(event.target.closest('[data-show-diagram]').dataset.showDiagram)}});
  }

  async function extractFile(file) {
    const status=$('#file-label');
    if(file.size>1024*1024*1024){status.textContent='File is larger than 1 GB.';status.className='upload-status error';return}
    const ext=file.name.split('.').pop().toLowerCase();if(!['pdf','txt','md'].includes(ext)){status.textContent='Choose a PDF, TXT, or Markdown file.';status.className='upload-status error';return}
    status.textContent=`Reading ${file.name}…`;status.className='upload-status loading';
    let truncated=false;
    try {
      let text='';
      if(ext==='pdf') {
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js',()=>Boolean(window.pdfjsLib));
        pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        const objectUrl=URL.createObjectURL(file);let pdf;
        try {
        pdf=await pdfjsLib.getDocument({url:objectUrl}).promise;const pages=[];let extractedChars=0;pendingPageImages=[];
        for(let n=1;n<=pdf.numPages;n++){
          status.textContent=`Extracting PDF text: page ${n} of ${pdf.numPages}…`;
          const page=await pdf.getPage(n);
          try {const content=await page.getTextContent();const pageText=cleanTextbookText(content.items.map(item=>item.str).join(' '));const remaining=100000-extractedChars;pages.push(pageText.slice(0,remaining));extractedChars+=Math.min(pageText.length,remaining);
            const meaningful=pageText.replace(/[^A-Za-z0-9]/g,'').length;
            if(n<=15&&meaningful<100){const viewport=page.getViewport({scale:1.35});const canvas=document.createElement('canvas');canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);const ctx=canvas.getContext('2d');await page.render({canvasContext:ctx,viewport}).promise;pendingPageImages.push(canvas.toDataURL('image/jpeg',0.65));canvas.width=0;canvas.height=0;}
            if(pageText.length>remaining||extractedChars>=100000){truncated=n<pdf.numPages||pageText.length>remaining;break}}
          finally {page.cleanup();}
        }
        text=pages.join('\n\n');
        if(pdf.cleanup)pdf.cleanup();
        } finally {if(pdf?.destroy)await pdf.destroy();URL.revokeObjectURL(objectUrl)}
      } else text=await file.text();
      text=cleanTextbookText(text);
      if(!text.trim()&&!pendingPageImages.length)throw new Error('No readable text or scanned page images were found. You can paste notes into the text box.');
      if(!text.trim())text=`Scanned textbook pages from ${file.name}. Text will be extracted from the page images when the study guide is generated.`;
      $('#note-content').value=text.slice(0,100000);$('#content-count').textContent=`${$('#note-content').value.length.toLocaleString()} / 100,000 characters`;
      if(!$('#note-title').value)$('#note-title').value=file.name.replace(/\.(pdf|txt|md)$/i,'').replace(/[_-]+/g,' ');
      status.textContent=`✓ Extracted ${truncated?'the first 100,000 characters from':'text from'} ${file.name}${pendingPageImages.length?` · ${pendingPageImages.length} scanned pages ready for OCR`:''}`;status.className='upload-status success';
    } catch(error){status.textContent=error.message||'Unable to read this file.';status.className='upload-status error'}
  }

  async function generateNote(event) {
    event.preventDefault();const button=$('#generate-note'),message=$('#notes-message');message.textContent='';message.className='form-message';
    const payload={title:$('#note-title').value.trim(),subject:$('#note-subject').value.trim(),raw_content:cleanTextbookText($('#note-content').value.trim()),page_images:pendingPageImages};
    button.disabled=true;button.innerHTML='<span class="spinner"></span> Creating your study guide…';
    try{const result=await API.request('/api/notes/generate',{method:'POST',body:JSON.stringify(payload)});pendingPageImages=[];await loadNotes();openNote(result.note.id);message.textContent='Your study guide is ready.';message.classList.add('success')}
    catch(error){message.textContent=error.message}finally{button.disabled=false;button.innerHTML='✦ Generate study guide <span>→</span>'}
  }

  async function loadNotes() {
    try{const data=await API.request('/api/notes');notes=data.notes||[];renderSavedList();renderSelect();window.NoteTutor?.syncNotes?.(notes,selected?.id||window.appState?.currentNote?.id);window.QuizArena?.syncNotes?.(notes,selected?.id||window.appState?.currentNote?.id);return notes}
    catch(error){if(error.message!=='Please sign in to manage your notes.')$('#saved-list').innerHTML=`<div class="saved-empty">${escapeHTML(error.message)}</div>`;return []}
  }
  function renderSavedList(){
    $('#note-count').textContent=notes.length;$('#saved-list').innerHTML=notes.length?notes.map(note=>`<button class="saved-note ${selected?.id===note.id?'selected':''}" data-note-id="${note.id}"><span class="saved-note-icon">▤</span><span class="saved-note-copy"><strong>${escapeHTML(note.title)}</strong><small>${escapeHTML(note.subject||'Study note')} · ${new Date(note.created_at).toLocaleDateString()}</small></span><span class="delete-note" data-delete="${note.id}" role="button" aria-label="Delete ${escapeHTML(note.title)}">×</span></button>`).join(''):'<div class="saved-empty">No notes saved yet. Create your first study guide.</div>';
  }
  function renderSelect(){const select=$('#diagram-note-select');select.innerHTML='<option value="">Choose a saved note</option>'+notes.map(note=>`<option value="${note.id}">${escapeHTML(note.title)}</option>`).join('');if(selected)select.value=String(selected.id)}
  async function openNote(id){if(!Number.isInteger(Number(id))||Number(id)<1)return;try{const data=await API.request(`/api/notes/${id}`);selected=data.note;window.appState=window.appState||{};window.appState.currentNote=selected;renderSavedList();renderSelect();window.NoteTutor?.syncNotes?.(notes,selected.id);window.QuizArena?.syncNotes?.(notes,selected.id);renderOutput();$('#diagram-canvas').innerHTML='<div class="diagram-placeholder">Open the diagram studio to render this note.</div>';$('#mermaid-code').value=sanitizeMermaidCode(activeDiagram==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);if(diagramView.classList.contains('active'))renderDiagram()}catch(error){showMessage(error.message)}}
  function renderOutput(){
    if(!selected)return;const points=Array.isArray(selected.key_points)?selected.key_points:[],defs=Array.isArray(selected.definitions)?selected.definitions:[];
    $('#generated-output').innerHTML=`<div class="output-title"><div><p class="eyebrow">YOUR STUDY GUIDE</p><h2>${escapeHTML(selected.title)}</h2><span class="muted tiny">${escapeHTML(selected.subject||'Personal study notes')}</span></div><div class="output-actions"><button class="button secondary" data-show-diagram="flowchart">View flowchart</button><button class="button secondary" data-show-diagram="mindmap">View mind map</button></div></div>
      <article class="output-card summary-card"><div class="output-card-head"><div><span class="output-icon violet">✦</span><h3>Executive summary</h3></div><button class="text-button" data-copy-summary>Copy summary</button></div><p class="summary-text">${escapeHTML(selected.summary).replace(/\n\n/g,'</p><p class="summary-text">')}</p></article>
      <article class="output-card"><div class="output-card-head"><div><span class="output-icon mint">✓</span><h3>Key points</h3></div></div><ul class="key-points">${points.map(point=>`<li><span>✓</span>${escapeHTML(point)}</li>`).join('')}</ul></article>
      <article class="output-card"><div class="output-card-head"><div><span class="output-icon amber">Aa</span><h3>Key definitions & concepts</h3></div></div>${defs.length?`<div class="definition-grid">${defs.map(def=>`<div class="definition-card"><strong>${escapeHTML(def.term)}</strong><p>${escapeHTML(def.definition)}</p></div>`).join('')}</div>`:'<p class="muted tiny">No clear term definitions were detected in these notes.</p>'}</article>`;
  }
  async function deleteNote(id){if(!confirm('Delete this saved note? This cannot be undone.'))return;try{await API.request(`/api/notes/${id}`,{method:'DELETE'});notes=notes.filter(note=>note.id!==id);if(selected?.id===id){selected=null;$('#generated-output').innerHTML='<div class="output-empty"><span>✦</span><strong>Select a note to view your study guide</strong></div>';$('#diagram-canvas').innerHTML='<div class="diagram-placeholder">Choose a saved note to see its diagrams.</div>'}renderSavedList();renderSelect()}catch(error){showMessage(error.message)}}

  function switchToDiagram(which){activeDiagram=which;document.querySelectorAll('.diagram-tab').forEach(tab=>tab.classList.toggle('active',tab.dataset.diagram===which));if(selected)$('#mermaid-code').value=sanitizeMermaidCode(which==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);switchView('diagrams');if(selected){$('#diagram-note-select').value=String(selected.id);renderDiagram()}}
  function switchView(name){document.querySelector(`.nav-item[data-view="${name}"]`)?.click()}
  async function renderDiagram(){
    if(!selected){$('#diagram-canvas').innerHTML='<div class="diagram-placeholder">Choose a saved note to see its diagrams.</div>';return}
    try{
      await loadScript('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',()=>Boolean(window.mermaid));
      if(!mermaidReady){mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'dark',themeVariables:{darkMode:true,background:'#111a2b',primaryColor:'#292651',primaryTextColor:'#f4f5fb',primaryBorderColor:'#8579dd',lineColor:'#8792b5',secondaryColor:'#173c39',tertiaryColor:'#202a41'}});mermaidReady=true}
      const field=$('#mermaid-code');if(!field.value)field.value=sanitizeMermaidCode(activeDiagram==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);
      const rawSource=field.value.trim();if(!rawSource)throw new Error('There is no diagram source to display.');
      const source=sanitizeMermaidCode(rawSource);
      if(field.value!==source)field.value=source;
      $('#diagram-canvas').innerHTML='<div class="diagram-loading"><span class="spinner"></span> Drawing your diagram…</div>';
      const result=await mermaid.render(`diagram-${Date.now()}`,source);$('#diagram-canvas').innerHTML=`<div data-mermaid-svg class="mermaid-svg" style="transform:scale(${zoom});transform-origin:center center">${result.svg}</div>`;
      $('#diagram-message').textContent='Diagram preview updated.';
    }catch(error){
      const points=Array.isArray(selected.key_points)?selected.key_points.slice(0,8):[];
      const labels=[selected.title,...points].filter(Boolean).map(value=>String(value).replace(/[^A-Za-z0-9 ]/g,' ').replace(/\s+/g,' ').trim().slice(0,70)).filter(Boolean);
      const fallback=['flowchart TD',...labels.map((label,i)=>`  f${i}["${label}"]`),...labels.slice(1).map((_,i)=>`  f${i} --> f${i+1}`)].join('\n');
      try{const result=await mermaid.render(`diagram-fallback-${Date.now()}`,fallback);$('#diagram-canvas').innerHTML=`<div data-mermaid-svg class="mermaid-svg" style="transform:scale(${zoom});transform-origin:center center">${result.svg}</div>`;$('#diagram-message').textContent='Showing a simplified diagram from this note.'}
      catch{$('#diagram-canvas').innerHTML=`<div class="diagram-error"><strong>${escapeHTML(selected.title)}</strong><ul>${points.map(point=>`<li>${escapeHTML(point)}</li>`).join('')}</ul></div>`;$('#diagram-message').textContent='Showing the note concepts as a text outline.'}
    }
  }
  async function regenerate(){if(!selected)return showMessage('Choose a saved note first.');const button=$('#regenerate-diagrams');button.disabled=true;button.textContent='Regenerating…';try{const data=await API.request(`/api/notes/${selected.id}/regenerate-diagrams`,{method:'POST'});selected={...selected,...data.note};$('#mermaid-code').value=sanitizeMermaidCode(activeDiagram==='flowchart'?selected.flowchart_mermaid:selected.mindmap_mermaid);await renderDiagram()}catch(error){showMessage(error.message)}finally{button.disabled=false;button.textContent='↻ Regenerate'}}
  function currentSvg(){return $('#diagram-canvas svg')}
  function download(blob,name){const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}
  function exportSVG(){const svg=currentSvg();if(!svg)return showMessage('Render a diagram first.');const copy=svg.cloneNode(true);copy.setAttribute('xmlns','http://www.w3.org/2000/svg');download(new Blob([new XMLSerializer().serializeToString(copy)],{type:'image/svg+xml'}),`${selected?.title||'diagram'}-${activeDiagram}.svg`)}
  function exportPNG(){const svg=currentSvg();if(!svg)return showMessage('Render a diagram first.');const copy=svg.cloneNode(true);copy.setAttribute('xmlns','http://www.w3.org/2000/svg');const src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(copy));const image=new Image();image.onload=()=>{const canvas=document.createElement('canvas');canvas.width=image.width*2;canvas.height=image.height*2;const ctx=canvas.getContext('2d');ctx.fillStyle='#111a2b';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);canvas.toBlob(blob=>blob&&download(blob,`${selected?.title||'diagram'}-${activeDiagram}.png`))};image.onerror=()=>showMessage('Could not export this diagram as PNG.');image.src=src}
  function printDiagram(){const svg=currentSvg();if(!svg)return showMessage('Render a diagram first.');const win=window.open('','_blank');if(!win)return showMessage('Allow pop-ups to print this diagram.');win.document.write(`<html><head><title>${escapeHTML(selected?.title||'Study diagram')}</title><style>body{font:16px sans-serif;padding:24px;color:#142033}svg{max-width:100%;height:auto}</style></head><body><h1>${escapeHTML(selected?.title||'Study diagram')}</h1>${svg.outerHTML}</body></html>`);win.document.close();win.focus();win.print()}
  function showMessage(text){const msg=$('#notes-message');if(msg){msg.textContent=text;msg.classList.remove('success')}else alert(text)}
  function flash(button,text){const before=button.textContent;button.textContent=text;setTimeout(()=>button.textContent=before,1200)}
  window.Notes={init:async()=>{installUI();try{await loadScript('https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',()=>Boolean(window.mermaid));mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'dark'});mermaidReady=true}catch{}await loadNotes()},loadNotes,openNote,selectedId:()=>selected?.id};
})();
