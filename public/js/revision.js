(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  let plan = null;
  function install() {
    const view = $('#view-revision');
    if (!view) return;
    const date = new Date(); date.setDate(date.getDate() + 7);
    const seven = `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
    view.innerHTML = `<div class="page-heading"><p class="eyebrow">MAKE TIME FOR WHAT MATTERS</p><h1>Smart Revision Planner</h1><p class="muted">Build a day-by-day timetable around your exam, saved notes, and weak concepts.</p></div><form class="planner-config" id="planner-form"><label>Exam title / subject<input id="exam-title" maxlength="120" value="Matric Examination" required></label><label>Exam date<input id="exam-date" type="date" value="${seven}" required></label><label>Hours per day<input id="daily-hours" type="number" min="1" max="8" value="2" required></label><label>Priority focus<select id="priority-focus"><option value="saved_and_weak">Saved notes + weak concepts</option><option value="weak_concepts">Weak concepts first</option><option value="saved_notes">Saved notes</option></select></label><button class="button primary" id="generate-plan" type="submit">Generate Smart Revision Plan</button></form><p class="form-message" id="planner-message" role="status"></p><div id="plan-body"><div class="output-empty"><span>📅</span><strong>Loading your study timetable…</strong><small>Your saved plan will appear here.</small></div></div>`;
    $('#planner-form').addEventListener('submit', generate);
    $('#plan-body').addEventListener('change', toggle);
    $('#plan-body').addEventListener('click', jump);
  }
  async function load() {
    try {
      const data = await API.request('/api/rag/revision');
      if (data.plan) {
        plan = data.plan;
        $('#exam-title').value = plan.exam_title || 'Matric Examination';
        $('#exam-date').value = String(plan.exam_date).slice(0,10);
        $('#daily-hours').value = plan.daily_hours || 2;
        $('#priority-focus').value = plan.priority_focus || 'saved_and_weak';
        render(plan, data.active_knowledge_gaps);
      } else renderEmpty(data.notes_count);
    } catch (error) { msg(error.message); renderEmpty(0); }
  }
  function renderEmpty(noteCount=0) {
    $('#plan-body').innerHTML = `<div class="output-empty"><span>📅</span><strong>${noteCount ? 'Create your first 7-day timetable' : 'Add a saved note to build your timetable'}</strong><small>${noteCount ? 'Your plan will prioritize saved subjects and weak concepts.' : 'Revision sessions are built from your notes and quiz results.'}</small></div>`;
  }
  async function generate(event) {
    event.preventDefault();
    const button = $('#generate-plan'); button.disabled = true; button.textContent = 'Building your timetable…';
    try {
      const data = await API.request('/api/rag/revision/generate', {method:'POST', body:JSON.stringify({exam_title:$('#exam-title').value.trim(), exam_date:$('#exam-date').value, daily_hours:Number($('#daily-hours').value), priority_focus:$('#priority-focus').value})});
      plan = data.plan; render(plan); msg('Your revision plan is ready.');
    } catch (error) { msg(error.message); }
    finally { button.disabled = false; button.textContent = 'Generate Smart Revision Plan'; }
  }
  function render(value, gaps=0) {
    plan = value;
    const days = value.schedule || [];
    $('#plan-body').innerHTML = `<section class="plan-summary"><div><span>Exam</span><strong>${esc(value.exam_title || 'Matric Examination')}</strong></div><div><span>Study schedule</span><strong>${days.length} days · ${value.daily_hours} h / day</strong></div><div><span>Weak topics</span><strong>${gaps ?? 0}</strong></div><div><span>Completed</span><strong>${value.completion_percentage || 0}%</strong></div><div class="progress"><i style="width:${value.completion_percentage || 0}%"></i></div></section>${value.summary_advice?`<p class="plan-advice">${esc(value.summary_advice)}</p>`:''}<div class="plan-days">${days.map(day=>{const done=day.tasks.length>0&&day.tasks.every(task=>task.done);return `<article class="plan-day"><header><div><span class="priority ${day.priority.startsWith('High')?'high':''}">${esc(day.priority)}</span><h2>Day ${day.day_number}: ${esc(day.focus_title)}</h2><small>${esc(day.date)} · ${esc(day.note_title)} · ${esc(day.allocated_hours)}</small></div><label class="day-complete"><input type="checkbox" data-complete-day="${day.day_number}" ${done?'checked':''}><span>Mark Completed</span></label></header><div class="plan-tasks">${day.tasks.map(task=>`<label><input type="checkbox" data-day="${day.day_number}" data-task="${esc(task.id)}" ${task.done?'checked':''}><span>${esc(task.text)}</span></label>`).join('')}</div><p class="plan-tip"><strong>Exam tip:</strong> ${esc(day.exam_tip || 'Define the concept, show the formula, and explain your result.')}</p><button class="button secondary" data-jump="${day.note_id||''}">Open this note</button></article>`}).join('')}</div>`;
  }
  async function toggle(event) {
    const control = event.target;
    if (control.matches('[data-complete-day]')) {
      const day = plan?.schedule.find(item => item.day_number === Number(control.dataset.completeDay));
      if (!day) return;
      control.disabled = true;
      try {
        for (const task of day.tasks) {
          if (Boolean(task.done) === control.checked) continue;
          const data = await API.request(`/api/rag/revision/${plan.id}/toggle-task`, {method:'POST', body:JSON.stringify({day_number:day.day_number, task_id:task.id, done:control.checked})});
          plan = data.plan;
        }
        render(plan);
      } catch (error) { msg(error.message); render(plan); }
      return;
    }
    if (!control.matches('[data-task]') || !plan) return;
    try {
      const data = await API.request(`/api/rag/revision/${plan.id}/toggle-task`, {method:'POST', body:JSON.stringify({day_number:Number(control.dataset.day), task_id:control.dataset.task, done:control.checked})});
      render(data.plan);
    } catch (error) { msg(error.message); control.checked = !control.checked; }
  }
  function jump(event) {
    const button = event.target.closest('[data-jump]');
    if (!button?.dataset.jump) return;
    document.querySelector('.nav-item[data-view="notes"]')?.click();
    window.Notes?.openNote?.(Number(button.dataset.jump));
  }
  function msg(text) { const node=$('#planner-message'); if (node) node.textContent=text; }
  window.RevisionPlanner = {init:async () => {install(); await load();}, load};
})();
