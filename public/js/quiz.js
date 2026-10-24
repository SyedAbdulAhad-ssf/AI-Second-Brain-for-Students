/* Phase 3 assessment arena: quiz, flashcards, reports, and recovery plans. */
(() => {
  const $=(s,r=document)=>r.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let notes=[], quiz=null, cards=[], cardIndex=0, known=0, selectedNoteId=null;
  async function ensureMermaid(){if(window.mermaid)return;await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';script.onload=resolve;script.onerror=reject;document.head.append(script)});window.mermaid?.initialize({startOnLoad:false,securityLevel:'strict',theme:'dark'})}
  function install(){
    const quizView=$('#view-quiz'), gapsView=$('#view-gaps'); if(!quizView||!gapsView)return;
    quizView.innerHTML=`<div class="page-heading"><p class="eyebrow">PRACTICE & RECALL</p><h1>Quiz & Flashcards Arena</h1><p class="muted">Test your understanding and turn review into lasting recall.</p></div><section class="assessment-panel"><div class="assessment-controls"><label>Saved subject / note<select id="assessment-note"><option value="">Loading saved notes…</option></select></label><label>Difficulty<select id="assessment-difficulty"><option value="easy">Easy</option><option value="medium" selected>Medium</option><option value="exam_level">Exam Level</option></select></label><button class="button primary" id="make-assessment">✦ Generate / Refresh Quiz & Flashcards</button></div><p class="form-message" id="assessment-message" role="status"></p></section><div id="assessment-body" class="assessment-body"><div class="output-empty"><span>🧠</span><strong>Loading your saved assessment…</strong><small>Choose a note to begin.</small></div></div>`;
    gapsView.innerHTML=`<div class="page-heading"><p class="eyebrow">PERSONALIZED LEARNING</p><h1>Knowledge Gap Detector</h1><p class="muted">Use a missed answer as a clear signal for what to practice next.</p></div><div id="gaps-body"><div class="output-empty"><span>🎯</span><strong>Your recovery plan will grow here</strong><small>Take a quiz to surface topics that need more practice.</small></div></div>`;
    $('#make-assessment').addEventListener('click',makeAssessment);$('#assessment-note').addEventListener('change',event=>{selectedNoteId=Number(event.target.value)||null;loadExisting(selectedNoteId)});
    $('#assessment-body').addEventListener('click',handleAssessmentClick);$('#gaps-body').addEventListener('click',handleGapClick);
    document.querySelector('.nav-item[data-view="gaps"]')?.addEventListener('click',loadGaps);document.querySelector('.nav-item[data-view="quiz"]')?.addEventListener('click',()=>loadNotes(selectedNoteId));
  }
  async function loadNotes(preferredId){try{const data=await API.request('/api/notes');notes=data.notes||[];const select=$('#assessment-note');if(!select)return;const chosen=Number(preferredId||window.appState?.currentNote?.id||window.Notes?.selectedId?.()||select.value)||Number(notes[0]?.id)||null;select.innerHTML='<option value="">Choose a saved note</option>'+notes.map(n=>`<option value="${n.id}">${esc(n.title)}${n.subject?' · '+esc(n.subject):''}</option>`).join('');selectedNoteId=chosen;select.value=chosen?String(chosen):'';if(chosen)await loadExisting(chosen);else renderEmpty('Create a smart note to start your quiz.')}catch(error){show(error.message)}}
  function syncNotes(nextNotes, preferredId){notes=nextNotes||notes;const select=$('#assessment-note');if(!select)return;const chosen=Number(preferredId||selectedNoteId||window.appState?.currentNote?.id)||Number(notes[0]?.id)||null;select.innerHTML='<option value="">Choose a saved note</option>'+notes.map(n=>`<option value="${n.id}">${esc(n.title)}${n.subject?' · '+esc(n.subject):''}</option>`).join('');selectedNoteId=chosen;select.value=chosen?String(chosen):'';if(chosen)loadExisting(chosen)}
  async function loadExisting(id){if(!id){quiz=null;renderEmpty();return}selectedNoteId=Number(id);try{const data=await API.request(`/api/quizzes/note/${id}`);quiz=data.quiz;if(quiz){cards=quiz.flashcards||[];cardIndex=0;known=0;renderQuiz()}else await makeAssessment()}catch(error){show(error.message)}}
  async function makeAssessment(){const noteId=Number($('#assessment-note').value||selectedNoteId);if(!noteId)return show('Choose a saved note first.');selectedNoteId=noteId;const button=$('#make-assessment');button.disabled=true;button.innerHTML='<span class="spinner"></span> Building assessment…';try{const data=await API.request('/api/quizzes/generate',{method:'POST',body:JSON.stringify({note_id:noteId,difficulty:$('#assessment-difficulty').value})});quiz=data.quiz;cards=quiz.flashcards||[];cardIndex=0;known=0;renderQuiz();show('Your quiz and flashcards are ready.',true)}catch(error){show(error.message)}finally{button.disabled=false;button.innerHTML='✦ Generate / Refresh Quiz & Flashcards'}}
  function renderEmpty(text){$('#assessment-body').innerHTML=`<div class="output-empty"><span>🧠</span><strong>${esc(text||'Choose a saved note to begin')}</strong><small>Generate an assessment to begin active recall.</small></div>`}
  function renderQuiz(){if(!quiz)return renderEmpty();const questions=quiz.questions||[];$('#assessment-body').innerHTML=`<div class="assessment-tabs"><button class="assessment-tab active" data-assessment-tab="quiz">Quiz mode <span>${questions.length}</span></button><button class="assessment-tab" data-assessment-tab="cards">Flashcards <span>${cards.length}</span></button></div><div id="quiz-mode"><form id="quiz-form" class="quiz-form">${questions.map((q,i)=>`<article class="question-card"><span class="question-number">${i+1}</span><div><p class="question-type">${q.type==='mcq'?'MULTIPLE CHOICE':'SHORT ANSWER'} · ${esc(q.concept_tag||'Concept')}</p><h3>${esc(q.question)}</h3>${q.type==='mcq'?`<div class="option-list">${(q.options||[]).map(o=>`<label class="option"><input type="radio" name="${esc(q.id)}" value="${esc(o)}"><span>${esc(o)}</span></label>`).join('')}</div>`:`<textarea name="${esc(q.id)}" rows="3" placeholder="Write your answer in your own words…"></textarea>`}</div></article>`).join('')}<button class="button primary quiz-submit" type="submit">Submit answers <span>→</span></button></form></div><div id="cards-mode" hidden></div>`;renderCards();$('#quiz-form').addEventListener('submit',submitQuiz)}
  function renderCards(){const host=$('#cards-mode');if(!cards.length){host.innerHTML='<div class="output-empty"><strong>No flashcards were generated.</strong></div>';return}const card=cards[cardIndex];host.innerHTML=`<div class="flashcard-area"><div class="flashcard-progress">Card ${cardIndex+1} of ${cards.length} · ${known} marked known</div><button class="flashcard" id="flashcard" aria-label="Flip flashcard"><span class="flashcard-face flash-front"><small>${esc(card.concept_tag||'Study concept')}</small><strong>${esc(card.front)}</strong><em>Click to reveal</em></span><span class="flashcard-face flash-back"><small>ANSWER</small><strong>${esc(card.back)}</strong><em>Click to flip back</em></span></button><div class="flashcard-actions"><button class="button secondary" data-card="prev">← Previous</button><button class="button secondary" data-card="flip">↻ Flip</button><button class="button secondary" data-card="known">✓ I knew this</button><button class="button secondary" data-card="next">Next →</button></div></div>`}
  function handleAssessmentClick(event){const tab=event.target.closest('[data-assessment-tab]');if(tab){document.querySelectorAll('.assessment-tab').forEach(b=>b.classList.toggle('active',b===tab));const cardsMode=$('#cards-mode'),quizMode=$('#quiz-mode');const cardsActive=tab.dataset.assessmentTab==='cards';cardsMode.hidden=!cardsActive;quizMode.hidden=cardsActive;return}if(event.target.closest('#flashcard')){$('#flashcard').classList.toggle('flipped');return}const action=event.target.closest('[data-card]')?.dataset.card;if(!action||!cards.length)return;if(action==='next')cardIndex=(cardIndex+1)%cards.length;if(action==='prev')cardIndex=(cardIndex-1+cards.length)%cards.length;if(action==='known')known++;if(action==='flip'){$('#flashcard').classList.toggle('flipped');return}renderCards()}
  async function submitQuiz(event){event.preventDefault();if(!quiz)return;const answers={};for(const q of quiz.questions||[]){const field=event.currentTarget.elements[q.id];answers[q.id]=field?.value||''}const button=$('.quiz-submit');button.disabled=true;button.innerHTML='<span class="spinner"></span> Checking answers…';try{const report=await API.request(`/api/quizzes/${quiz.id}/submit`,{method:'POST',body:JSON.stringify({answers})});renderReport(report)}catch(error){show(error.message)}finally{button.disabled=false;button.innerHTML='Submit answers <span>→</span>'}}
  function renderReport(report){$('#assessment-body').innerHTML=`<section class="score-report"><div class="score-ring"><strong>${report.percentage}%</strong><span>${report.score}/${report.total_questions}</span></div><div><p class="eyebrow">ASSESSMENT COMPLETE</p><h2>${report.percentage>=80?'Great recall.':'A useful check-in.'}</h2><p class="muted">Review the explanations below, then use the recovery plans for any missed concepts.</p><button class="button primary" data-view-gaps>View detected knowledge gaps</button></div></section><div class="result-list">${report.results.map((r,i)=>`<article class="result-card ${r.correct?'correct':'incorrect'}"><strong>${r.correct?'Correct':'Incorrect'} · Question ${i+1} · ${esc(r.concept_tag||'Concept')}</strong><p>${esc(r.explanation||'Review this concept in your study notes.')}</p>${r.correct?'':`<small>Your answer: ${esc(r.answer||'No answer')} · Expected: ${esc(r.correct_answer||'Review the note')}</small>`}</article>`).join('')}</div>`;$('#assessment-body [data-view-gaps]').addEventListener('click',()=>{document.querySelector('.nav-item[data-view="gaps"]')?.click()})}
  async function loadGaps(){
    const host=$('#gaps-body');
    try {
      const data=await API.request('/api/quizzes/knowledge-gaps');
      const gaps=data.gaps||[], needs=gaps.filter(g=>g.status==='needs_practice').length;
      let content='';
      if(gaps.length){
        content=`<div class="gap-list">${gaps.map(g=>`<article class="gap-card ${esc(g.status)}"><header><div><span class="gap-status">${g.status==='mastered'?'RESOLVED':'NEEDS PRACTICE'}</span><h2>${esc(g.weak_topic)}</h2><small>${esc(g.note_title||'Study note')}</small></div><button class="button secondary" data-gap-status="${g.id}" data-status="${g.status}">${g.status==='mastered'?'Reopen':'Mark Resolved'}</button></header><div class="recovery-steps"><section><span>1</span><div><h3>Simple explanation</h3><p>${esc(g.simple_explanation)}</p></div></section><section><span>2</span><div><h3>Recovery map</h3><div class="gap-diagram" data-gap-diagram="${g.id}">${esc(g.mini_flowchart)}</div></div></section><section><span>3</span><div><h3>Next action</h3><p>${esc(g.recommended_action)}</p><button class="text-button" data-practice="${g.note_id}">Practice this note →</button></div></section></div></article>`).join('')}</div>`;
      } else {
        content='<div class="output-empty"><span>✓</span><strong>No gaps detected yet</strong><small>Complete an assessment to get personalized recovery steps.</small></div>';
      }
      host.innerHTML=`<div class="mastery-grid"><div class="mastery-stat"><span>Needs practice</span><strong>${needs}</strong></div><div class="mastery-stat mastered"><span>Resolved</span><strong>${gaps.length-needs}</strong></div><div class="mastery-stat"><span>Total signals</span><strong>${gaps.length}</strong></div></div>${content}`;
      renderGapDiagrams(gaps);
    } catch(error) { host.innerHTML=`<div class="output-empty"><strong>${esc(error.message)}</strong></div>`; }
  }
  function sanitizeMermaidCode(code) {
    if (window.sanitizeMermaidCode) return window.sanitizeMermaidCode(code);
    if (!code || typeof code !== 'string') return '';
    let text = code.trim();
    text = text.replace(/^```(?:mermaid)?\s*/i, '').replace(/\s*```$/i, '').replace(/```(?:mermaid)?/gi, '').trim();
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (text.includes('\\n')) text = text.replace(/\\n/g, '\n');
    text = text.replace(/^((?:flowchart|graph)\s+[A-Za-z]{2}|mindmap)\s+([^\n]+)/i, '$1\n  $2');
    text = text.replace(/(\b[A-Za-z0-9_]+)\s+([\[\{\(\>])/g, '$1$2');
    let prev;
    do { prev = text; text = text.replace(/([\]\)\}]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))/g, '$1\n  $2'); } while (prev !== text);
    do { prev = text; text = text.replace(/((?:-->|---|-.->|==>)(?:\|[^|\n]*\|)?\s*[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))/g, '$1\n  $2'); } while (prev !== text);
    const lines = text.split('\n'), cleaned = [];
    const shapePattern = /([A-Za-z0-9_]+(?:\[\(|\(\[|\[\[|\{\{|\(\(|\[\/|\[\\|[\[\{\(\>]))(.*?)((\]\)|\)\]|\]\]|\}\}|\)\)|\/\]|\\\]|[\]\}\)]))/g;
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (!line) continue;
      const parts = []; let cur = '', inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"') { inQ = !inQ; cur += ch; }
        else if (ch === ';' && !inQ) { parts.push(cur.trim()); cur = ''; }
        else { cur += ch; }
      }
      if (cur.trim()) parts.push(cur.trim());
      for (let part of parts) {
        if (!part) continue;
        part = part.replace(/(\b[A-Za-z0-9_]+)\s+([\[\{\(\>])/g, '$1$2');
        part = part.replace(shapePattern, (m, prefix, content, suffix) => {
          if (content.startsWith('"') && content.endsWith('"') && content.length >= 2) {
            const inner = content.slice(1, -1).replace(/"/g, "'");
            return `${prefix}"${inner}"${suffix}`;
          }
          const inner = content.replace(/"/g, "'");
          return `${prefix}"${inner}"${suffix}`;
        });
        part = part.replace(/(\|)(.*?)(\|)/g, (m, p1, p2, p3) => p1 + p2.replace(/"/g, "'") + p3);
        if (/^(?:flowchart|graph|mindmap|subgraph|end)\b/i.test(part)) cleaned.push(part);
        else cleaned.push(`  ${part}`);
      }
    }
    return cleaned.join('\n');
  }
  async function renderGapDiagrams(gaps){if(!window.mermaid)return;for(const gap of gaps){const host=$(`[data-gap-diagram="${gap.id}"]`);if(!host)continue;try{const cleanFlow=sanitizeMermaidCode(gap.mini_flowchart||'');const out=await mermaid.render(`gap-${gap.id}-${Date.now()}`,cleanFlow);host.innerHTML=out.svg}catch{host.textContent='Recovery diagram is unavailable; follow the three steps above.'}}}
  async function handleGapClick(event){const status=event.target.closest('[data-gap-status]');if(status){try{await API.request(`/api/quizzes/knowledge-gaps/${status.dataset.gapStatus}/status`,{method:'POST',body:JSON.stringify({status:status.dataset.status==='mastered'?'needs_practice':'mastered'})});loadGaps()}catch(error){show(error.message)}return}const practice=event.target.closest('[data-practice]');if(practice){document.querySelector('.nav-item[data-view="quiz"]')?.click();$('#assessment-note').value=String(practice.dataset.practice);loadExisting(Number(practice.dataset.practice))}}
  function show(text,success=false){const node=$('#assessment-message');if(node){node.textContent=text;node.className=`form-message${success?' success':''}`}}
  window.QuizArena={init:async()=>{try{await ensureMermaid()}catch{}install();await loadNotes()},loadNotes,syncNotes,loadGaps};
})();
