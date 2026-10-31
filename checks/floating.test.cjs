const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const listeners={},events={},elements={},messages=[];
for(const id of ['#widget','#detail','#meters'])elements[id]={innerHTML:'',style:{setProperty(){}},classList:{toggle(){}},addEventListener(type,fn){events[id+type]=fn}};
let snapshots=[
 {project:{id:'running',title:'正在实现'},status:'running',tasks:[],percent:35,done:1,total:3,time:'12:00'},
 {project:{id:'blocked',title:'<script>alert(1)</script>'},status:'blocked',blocked:1,tasks:[...Array.from({length:3},(_,i)=>({title:'执行 '+i,status:'running'})),{title:'服务检查',status:'blocked',blocker:'凭据 <待提供>',current:'自主恢复中'}],percent:40,done:1,total:2,time:'12:01'},
 {project:{id:'archived',title:'不应显示',archivedAt:'2026-10-30'},status:'running',tasks:[],percent:0,done:0,total:1}
];
let status='online',preferences={taskMode:'automatic',taskIDs:[]};
const live={get status(){return status},projects:()=>snapshots.map(s=>s.project),snapshot:id=>snapshots.find(s=>s.project.id===id),init:options=>assert.equal(options.liveOnly,true)};
const context=vm.createContext({Date,Math,setTimeout,clearTimeout,TraceLive:live,TraceFloatingPreferences:{get value(){return preferences},init(){}},window:{webkit:{messageHandlers:{traceFloating:{postMessage:value=>messages.push(value)}}}},document:{body:{classList:{toggle(){}}},querySelector:key=>elements[key],querySelectorAll:()=>[],addEventListener:(key,fn)=>listeners[key]=fn}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../floating.js'),'utf8'),context);
const meters=()=>elements['#meters'].innerHTML;
const detail=()=>elements['#detail'].innerHTML;
const target=selector=>({target:{closest:key=>key===selector?{dataset:selector==='[data-task]'?{task:'blocked'}:selector==='[data-open]'?{open:'blocked'}:{action:'collapse'}}:null}});
assert(meters().indexOf('data-task="blocked"')<meters().indexOf('data-task="running"'));
assert(!meters().includes('不应显示'));
assert(meters().includes('&lt;script&gt;'));
assert.equal(messages.at(-1).expanded,false);
events['#metersmouseover'](target('[data-task]'));
assert(detail().includes('凭据 &lt;待提供&gt;'));
assert(detail().includes('自主恢复中'));
assert.equal(messages.at(-1).expanded,true);
events['#widgetclick'](target('[data-task]'));
events['#widgetclick'](target('[data-open]'));assert.equal(messages.at(-1).id,'blocked');
status='offline';listeners['trace:status']();assert(detail().includes('已断开，保留最近快照'));assert(meters().includes('offline-dot'));
listeners.keydown({key:'Escape'});assert.equal(detail(),'');assert.equal(messages.at(-1).expanded,false);
status='online';preferences={taskMode:'manual',taskIDs:['running']};listeners['trace:floating-settings']();assert(meters().includes('data-task="running"'));assert(!meters().includes('data-task="blocked"'));
preferences={taskMode:'manual',taskIDs:['archived','missing']};listeners['trace:floating-settings']();assert(meters().includes('选择任务'));
let cancelled=false;listeners.mousedown({button:0,screenX:10,screenY:10});listeners.mousemove({buttons:1,screenX:30,screenY:20});listeners.mouseup();listeners.click({preventDefault(){cancelled=true},stopImmediatePropagation(){}});assert(cancelled);
snapshots=[];status='online';listeners['trace:state']();assert(meters().includes('选择任务'));
events['#widgetcontextmenu']({preventDefault(){}});assert.equal(messages.at(-1).action,'menu');
console.log('PASS: task rings, blocked priority, archived exclusion, escaping, detail expansion, offline snapshot, collapse, empty state and native navigation.');
