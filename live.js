/* Read-only browser client; Agent writes go through the authenticated CLI. */
const TraceLive = (() => {
 let mode='live';
 try {if(localStorage.getItem('trace.data-mode.v1')==='demo')mode='demo'}catch{}
 let state={revision:-1,projects:[]},status='loading',stream=null,retryTimer=null,inflight=false,again=false;
 const emit=type=>document.dispatchEvent(new Event(type));
 const stamp=value=>value?new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'—';
 const project=id=>state.projects.find(p=>p.id===id);
 const diagramCache=new Map();
 function agents(){
  const result={agent:{name:'Agent',role:'执行 Agent',letter:'A'}};
  for(const p of state.projects)for(const n of p.nodes)result[n.agent]={name:n.agent,role:n.agent_role,letter:n.agent.slice(0,1).toUpperCase()};
  return result;
 }
 function projects(){return state.projects.map(p=>({id:p.id,title:p.title,description:p.description,owner:p.owner,category:p.category,archivedAt:p.archived_at||null,createdAt:p.created_at,updated:stamp(p.updated_at),diagramTitle:p.title+' · 图谱',diagramDescription:'任务关联的结构、数据逻辑与实际运行。',defaultDiagram:p.diagrams[0]?.id||''}))}
 function snapshot(id){
  const p=project(id);if(!p)return null;
  const byId=new Map(p.nodes.map(n=>[n.id,n]));
  function build(id,number,depth){const n=byId.get(id);return {...n,number,depth,current:n.children.length?'包含 '+n.children.length+' 个子任务，进度由叶子任务汇总。':n.current,done:n.children.length?n.children.map(x=>byId.get(x)).filter(x=>x.status==='done').map(x=>x.title):n.done,todo:n.children.length?n.children.map(x=>byId.get(x)).filter(x=>x.status!=='done').map(x=>x.title):n.todo,children:n.children.map((child,i)=>build(child,number+'.'+(i+1),depth+1))}}
  const roots=p.nodes.filter(n=>!n.parent_id),parents=roots.filter(n=>n.children.length),loose=roots.filter(n=>!n.children.length);
  const groups=parents.map((n,i)=>({...build(n.id,String(i+1),0),number:String(i+1).padStart(2,'0'),description:build(n.id,String(i+1),0).current}));
  if(loose.length)groups.push({id:'_loose',number:String(groups.length+1).padStart(2,'0'),title:'执行计划',description:'Agent 汇报的子任务',children:loose.map((n,i)=>build(n.id,String(groups.length+1)+'.'+(i+1),1))});
  const tasks=[];function walk(n){tasks.push(n);n.children.forEach(walk)}groups.forEach(g=>g.id==='_loose'?g.children.forEach(walk):walk(g));
  const elapsed=Math.max(0,Math.floor((new Date(p.archived_at|| (p.summary.status==='done'?p.updated_at:Date.now()))-new Date(p.created_at))/1000));
  const duration=elapsed>=3600?`${Math.floor(elapsed/3600)}时${Math.floor(elapsed%3600/60)}分`:`${Math.floor(elapsed/60)}分${elapsed%60}秒`;
  const labels={waiting:'等待执行',running:'正在执行',recovery:'自主恢复',blocked:'存在阻塞',done:'全部完成',error:'执行异常'};
  return {...p.summary,percent:p.summary.status==='done'?100:Math.min(99,Math.round(p.summary.progress)),groups,tasks,project:projects().find(x=>x.id===id),time:stamp(p.updated_at),elapsed:duration,version:'v'+p.plan_version,label:labels[p.summary.status],summary:p.description||'由 Agent 汇报当前进度与执行结果。',planChange:p.last_plan_change,revision:p.revision};
 }
 function definitions(id){return Object.fromEntries((project(id)?.diagrams||[]).map(d=>[d.id,d]))}
 function runCatalog(id,diagramId){return Object.fromEntries((project(id)?.runs||[]).filter(r=>r.diagram_id===diagramId).map(r=>[r.id,{...r,title:`${r.status==='done'?'已完成':r.status==='error'?'异常':'运行中'} · ${r.id}`,time:stamp(r.updated_at)}]))}
 function diagram(id,diagramId,runId){
  const p=project(id),run=p?.runs.find(r=>r.id===runId&&r.diagram_id===diagramId);
  const raw=run?{...run.definition,version:run.diagram_version}:p?.diagrams.find(d=>d.id===diagramId);
  if(!raw)return null;
  const cacheKey=[id,diagramId,raw.version,runId||'',run?.steps.length||0].join('/');
  if(diagramCache.has(cacheKey))return diagramCache.get(cacheKey);
  const steps=(run?.steps||[]).map(e=>({title:e.title,nodes:e.node_ids,edges:e.edge_ids,ms:e.duration_ms,status:e.status}));
  let nodes,edges=[],participants=[],width=800,height=540;
  if(raw.kind==='sequence'){
   participants=raw.participants.map((p,i)=>({...p,x:80+i*210}));
   const positions=Object.fromEntries(participants.map(p=>[p.id,p.x]));
   nodes=raw.messages.map((m,i)=>({...m,from:positions[m.from],to:positions[m.to],y:146+i*65,sub:m.from+' → '+m.to,icon:'arrow'}));
   width=Math.max(800,participants.at(-1).x+80);height=Math.max(540,185+nodes.length*65);
  }else{
   const ranks=new Map(),remaining=new Set(raw.nodes.map(n=>n.id));
   for(let round=0;round<raw.nodes.length;round++){
    let changed=false;
    for(const id of [...remaining]){
     const incoming=raw.edges.filter(e=>e.to===id&&e.from!==id).map(e=>e.from);
     if(incoming.every(x=>ranks.has(x))){ranks.set(id,incoming.length?Math.max(...incoming.map(x=>ranks.get(x)))+1:0);remaining.delete(id);changed=true}
    }
    if(!changed)break;
   }
   for(const id of remaining)ranks.set(id,Math.floor(raw.nodes.findIndex(n=>n.id===id)%3));
   const rows=new Map();
   nodes=raw.nodes.map(n=>{const rank=ranks.get(n.id),row=rows.get(rank)||0;rows.set(rank,row+1);return {...n,x:n.x??40+rank*250,y:n.y??110+row*190}});
   const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
   edges=raw.edges.map(e=>{
    const a=byId[e.from],b=byId[e.to];let d,lx,ly;
    if(a.id===b.id){d=`M${a.x+154} ${a.y+25}h25v65h-55v-6`;lx=a.x+193;ly=a.y+65}
    else if(b.x>a.x){const sx=a.x+154,sy=a.y+42,tx=b.x,ty=b.y+42,mx=(sx+tx)/2;d=`M${sx} ${sy}H${mx}V${ty}H${tx}`;lx=mx;ly=(sy+ty)/2-12}
    else if(b.x===a.x&&b.y>a.y){d=`M${a.x+77} ${a.y+84}V${b.y}`;lx=a.x+115;ly=(a.y+84+b.y)/2}
    else{const sx=a.x+77,sy=a.y,tx=b.x+77,ty=b.y,y=Math.max(35,Math.min(sy,ty)-40);d=`M${sx} ${sy}V${y}H${tx}V${ty}`;lx=(sx+tx)/2;ly=y-10}
    return {...e,d,lx,ly};
   });
   width=Math.max(800,...nodes.map(n=>n.x+225));height=Math.max(540,...nodes.map(n=>n.y+150));
  }
  const result={...raw,nodes,edges,participants,steps,width,height,icon:raw.kind==='sequence'?'sequence':raw.kind==='flow'?'flow':'network',subtitle:raw.kind==='sequence'?'服务交互与先后顺序':raw.kind==='flow'?'数据处理与流向':'模块、职责与连接',unit:raw.kind==='sequence'?'交互':'节点',defaultNode:nodes[0].id};
  diagramCache.set(cacheKey,result);return result;
 }
 function runtime(id,diagramId,runId,cursor){
  const d=diagram(id,diagramId,runId),max=d?.steps.length||0,at=Math.max(0,Math.min(cursor||0,max)),nodes={},edges={};
  d?.nodes.forEach(n=>nodes[n.id]='pending');d?.edges.forEach(e=>edges[e.id]='pending');
  for(const step of d?.steps.slice(0,at)||[]){step.nodes.forEach(key=>nodes[key]=step.status);step.edges.forEach(key=>edges[key]=step.status)}
  return {nodes,edges,cursor:at,max,step:at?d.steps[at-1]:null,elapsed:d?.steps.slice(0,at).reduce((sum,s)=>sum+s.ms,0)||0};
 }
 function setStatus(value){if(status!==value){status=value;emit('trace:status')}}
 async function refresh(){
  if(mode!=='live')return;
  if(inflight){again=true;return}
  inflight=true;
  try{
   const response=await fetch('/api/state',{cache:'no-store'});
   if(!response.ok)throw Error('Service unavailable');
   const next=await response.json();
   if(!Number.isInteger(next.revision)||!Array.isArray(next.projects))throw Error('Invalid response');
   setStatus('online');
   if(next.revision!==state.revision){state=next;diagramCache.clear();emit('trace:state')}
  }catch{setStatus('offline')}
  finally{inflight=false;if(again){again=false;refresh()}}
 }
 function connect(){
  if(mode!=='live')return;
  stream?.close();clearTimeout(retryTimer);
  stream=new EventSource('/api/events');
  stream.onopen=()=>refresh();
  stream.onmessage=event=>{try{if(JSON.parse(event.data).revision!==state.revision)refresh()}catch{setStatus('offline')}};
  stream.onerror=()=>{setStatus('offline');if(stream.readyState===EventSource.CLOSED)retryTimer=setTimeout(connect,2000)};
 }
 function setMode(value){
  mode=value==='demo'?'demo':'live';
  try{localStorage.setItem('trace.data-mode.v1',mode)}catch{}
  stream?.close();clearTimeout(retryTimer);emit('trace:state');emit('trace:status');
  if(mode==='live'){refresh();connect()}
 }
 function init({liveOnly=false}={}){if(liveOnly)mode='live';if(mode==='live'){refresh();connect()}}
 return {get mode(){return mode},get status(){return status},get revision(){return state.revision},get raw(){return state},projects,agents,snapshot,definitions,runCatalog,diagram,runtime,refresh,setMode,init};
})();
