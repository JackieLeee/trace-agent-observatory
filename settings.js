(()=>{
 const prefs=TraceFloatingPreferences,escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={blocked:'已阻塞',recovery:'自主恢复',running:'进行中',waiting:'等待执行',done:'已完成',error:'执行异常'};
 let query='';
 function renderTasks(){
  const p=prefs.value,projects=TraceLive.projects().filter(task=>!task.archivedAt),selected=new Set(p.taskIDs);
  document.querySelector('#selection-count').textContent=`已选 ${selected.size} / 4`;
  const visible=projects.filter(task=>(task.title+' '+task.id).toLowerCase().includes(query.toLowerCase()));
  document.querySelector('#task-list').innerHTML=visible.length?visible.map(task=>{const s=TraceLive.snapshot(task.id);return `<label class="task-option"><input type="checkbox" data-task="${escape(task.id)}" ${selected.has(task.id)?'checked':''} ${selected.size>=4&&!selected.has(task.id)?'disabled':''}><span><b>${escape(task.title)}</b><small>${escape(task.id)} · ${labels[s.status]||'等待执行'}</small></span><strong class="task-progress">${s.percent}%</strong></label>`}).join(''):`<p class="empty-picker">${TraceLive.status!=='online'?'正在连接本机任务，连接恢复后会自动更新。':query?'没有匹配的任务。':'暂无可选任务。Agent 创建任务后会出现在这里。'}</p>`;
  const missing=p.taskIDs.filter(id=>!projects.some(task=>task.id===id));
  if(missing.length)document.querySelector('#task-list').innerHTML+=missing.filter(id=>id.toLowerCase().includes(query.toLowerCase())).map(id=>`<label class="task-option"><input type="checkbox" data-task="${escape(id)}" checked><span><b>当前不可用的任务</b><small>${escape(id)} · 可取消选择</small></span></label>`).join('');
  const unavailable=missing.length;
  document.querySelector('#picker-note').textContent=unavailable?`${unavailable} 个已选任务当前不可用，不会在挂件中显示。`:'选择会立即同步到悬浮窗。';
 }
 function sync(){const p=prefs.value;document.querySelector('#enabled').checked=p.enabled;document.querySelector('#auto-hide').checked=p.autoHide;document.querySelectorAll('[name=edge]').forEach(input=>input.checked=input.value===p.edge);document.querySelectorAll('[name=task-mode]').forEach(input=>input.checked=input.value===p.taskMode);document.querySelector('#task-picker').hidden=p.taskMode!=='manual';renderTasks()}
 document.addEventListener('change',event=>{const input=event.target,p=prefs.value;if(input.id==='enabled')prefs.update({enabled:input.checked});else if(input.id==='auto-hide')prefs.update({autoHide:input.checked});else if(input.name==='edge')prefs.update({edge:input.value});else if(input.name==='task-mode')prefs.update({taskMode:input.value});else if(input.dataset.task){const ids=new Set(p.taskIDs);if(input.checked&&ids.size<4)ids.add(input.dataset.task);else ids.delete(input.dataset.task);prefs.update({taskIDs:[...ids]})}});
 document.querySelector('#task-search').addEventListener('input',event=>{query=event.target.value;renderTasks()});
 document.addEventListener('trace:floating-settings',sync);document.addEventListener('trace:state',renderTasks);document.addEventListener('trace:status',renderTasks);
 prefs.init();TraceLive.init({liveOnly:true});sync();
})();
