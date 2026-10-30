(() => {
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={blocked:'已阻塞',recovery:'自主恢复',error:'执行异常',done:'已完成',running:'进行中',waiting:'等待执行'};
 const bridge=()=>window.webkit?.messageHandlers?.traceFloating;
 let selected='',pinned=false,leaveTimer=null,snapshots=[],layout='';
 function send(value){bridge()?.postMessage(value)}
 function openTask(id){
  if(bridge())send(id?{action:'open-task',id}:{action:'open-main'});
  else location.href=id?'./#task/'+encodeURIComponent(id):'./#tasks';
 }
 function resize(){
  const height=Math.max(130,snapshots.length*100+56),expanded=Boolean(selected);
  const next=expanded+':'+height;if(next===layout)return;layout=next;
  document.querySelector('#widget').classList.toggle('expanded',expanded);
  send({action:'layout',expanded,height:Math.max(height,expanded?500:0)});
 }
 function select(id,pin=false){
  clearTimeout(leaveTimer);
  if(pin){pinned=selected===id?!pinned:true}else if(pinned)return;
  selected=id;renderDetail();resize();
 }
 function close(){selected='';pinned=false;renderDetail();resize()}
 function renderDetail(){
  const s=snapshots.find(s=>s.project.id===selected),detail=document.querySelector('#detail');
  document.querySelectorAll('[data-task]').forEach(b=>b.setAttribute('aria-expanded',String(b.dataset.task===selected)));
  if(!s){detail.innerHTML='';return}
  const leaves=s.tasks.filter(t=>!t.children?.length),blockers=leaves.filter(t=>t.status==='blocked');
  const priority={blocked:0,error:1,recovery:2,running:3};
  const current=leaves.filter(t=>Object.hasOwn(priority,t.status)).sort((a,b)=>priority[a.status]-priority[b.status]).slice(0,3);
  const rows=current.length?current:leaves.filter(t=>t.status==='waiting').slice(0,3);
  const index=snapshots.indexOf(s),notch=Math.max(50,Math.min(352,78+index*100));
  detail.style.setProperty('--notch-y',notch+'px');
  detail.innerHTML=`<section class="detail-card" style="--notch-y:${notch}px"><div class="detail-top"><span class="wordmark">TRACE <i>任务进度</i></span><button data-action="collapse" aria-label="收起任务详情">×</button></div><h1>${escape(s.project.title)}</h1><p class="updated">更新于 ${escape(s.time)}${TraceLive.status!=='online'?' · 已断开，保留最近快照':''}</p><div class="detail-progress"><span>总体完成度</span><strong>${s.percent}<small>%</small></strong></div><div class="track ${s.status}"><i style="width:${s.percent}%"></i></div><div class="progress-meta"><span>${s.done} / ${s.total} 子任务已完成</span><span class="status ${s.status}">${labels[s.status]||'等待执行'}</span></div><div class="metrics"><div><b>${s.running||0}</b><span>执行中</span></div><div><b>${s.waiting||0}</b><span>待推进</span></div><div class="${blockers.length?'warning':''}"><b>${blockers.length}</b><span>已阻塞</span></div></div><div class="activity"><h2>${blockers.length?'当前阻塞':'当前进展'}</h2>${rows.length?rows.map(t=>`<div class="activity-row ${t.status}"><i></i><div><b>${escape(t.title)}</b><p>${escape(t.status==='blocked'?t.blocker||'原因未提供':t.current||'等待 Agent 汇报')}</p>${t.status==='blocked'&&t.current?`<small>处理：${escape(t.current)}</small>`:''}</div></div>`).join(''):`<p class="empty">${s.status==='done'?'任务已完成，可查看完整交付结果。':'等待 Agent 提交执行计划。'}</p>`}</div><button class="open-task" data-open="${escape(s.project.id)}">打开完整任务</button></section>`;
 }
 function render(){
  const available=TraceLive.projects().filter(p=>!p.archivedAt).map(p=>TraceLive.snapshot(p.id));
  const active=available.filter(s=>s.status!=='done');active.sort((a,b)=>(b.blocked||0)-(a.blocked||0));
  snapshots=(active.length?active:available).slice(0,4);
  if(selected&&!snapshots.some(s=>s.project.id===selected)){selected='';pinned=false}
  document.querySelector('#meters').innerHTML=snapshots.length?snapshots.map((s,i)=>`<button class="meter ${s.status}" data-task="${escape(s.project.id)}" aria-label="${escape(s.project.title)}，${s.percent}%，${labels[s.status]||'等待执行'}" aria-expanded="${s.project.id===selected}" title="${escape(s.project.title)}"><span class="ring"><svg viewBox="0 0 64 64" aria-hidden="true"><circle class="ring-track" cx="32" cy="32" r="25"/><circle class="ring-value" cx="32" cy="32" r="25" pathLength="100" stroke-dasharray="${s.percent} 100"/></svg><span class="ring-center">${s.status==='blocked'?'!':s.status==='done'?'✓':String(i+1).padStart(2,'0')}</span>${TraceLive.status!=='online'?'<i class="offline-dot"></i>':''}</span><strong>${s.percent}<small>%</small></strong><span class="meter-name">${escape(s.project.title)}</span></button>`).join(''):`<button class="empty-meter" data-action="open-main" aria-label="打开工作台"><span class="trace-symbol">T.</span><small>${TraceLive.status==='online'?'暂无任务':TraceLive.status==='loading'?'连接中':'已断开'}</small></button>`;
  renderDetail();resize();
 }
 document.querySelector('#meters').addEventListener('mouseover',event=>{const task=event.target.closest('[data-task]');if(task&&task.dataset.task!==selected)select(task.dataset.task)});
 document.querySelector('#widget').addEventListener('mouseenter',()=>clearTimeout(leaveTimer));
 document.querySelector('#widget').addEventListener('mouseleave',()=>{if(!pinned)leaveTimer=setTimeout(close,280)});
 document.querySelector('#widget').addEventListener('click',event=>{
  const task=event.target.closest('[data-task]'),open=event.target.closest('[data-open]'),action=event.target.closest('[data-action]');
  if(task)select(task.dataset.task,true);
  else if(open)openTask(open.dataset.open);
  else if(action?.dataset.action==='collapse')close();
  else if(action?.dataset.action==='open-main')openTask();
 });
 document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
 document.querySelector('#widget').addEventListener('contextmenu',event=>{if(bridge()){event.preventDefault();send({action:'menu'})}});
 document.addEventListener('trace:state',render);document.addEventListener('trace:status',render);
 TraceLive.init({liveOnly:true});render();
})();
