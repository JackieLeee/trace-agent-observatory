const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
let payload={revision:1,projects:[{id:'test',title:'Target',owner:'coordinator',nodes:[
 {id:'root',parent_id:null,children:['nested','b'],title:'Root',agent:'coordinator',agent_role:'Owner',progress:35,status:'running'},
 {id:'nested',parent_id:'root',children:['a'],title:'Nested',agent:'builder',agent_role:'Builder',progress:50,status:'running'},
 {id:'a',parent_id:'nested',children:[],title:'A',agent:'builder',agent_role:'Builder',progress:50,weight:70,status:'running'},
 {id:'b',parent_id:'root',children:[],title:'B',agent:'verifier',agent_role:'Verifier',progress:0,weight:30,status:'waiting'}
],summary:{progress:35,total:2,done:0,running:1,waiting:1,status:'running'},plan_version:1,created_at:new Date().toISOString(),updated_at:new Date().toISOString(),diagrams:[{id:'flow',kind:'flow',version:2,nodes:[{id:'a',title:'A'},{id:'b',title:'B'},{id:'new',title:'New'}],edges:[{id:'ab',from:'a',to:'b',label:'output'}]}],runs:[{id:'run',diagram_id:'flow',diagram_version:1,status:'running',definition:{id:'flow',kind:'flow',nodes:[{id:'a',title:'A'},{id:'b',title:'B'}],edges:[{id:'ab',from:'a',to:'b',label:'output'}]},steps:[{title:'start',node_ids:['a'],edge_ids:[],status:'running',duration_ms:0},{title:'done',node_ids:['a'],edge_ids:['ab'],status:'done',duration_ms:42}]}]}]};
const events=[];
const ctx=vm.createContext({localStorage:{getItem:()=>null,setItem(){}},Event:class{constructor(type){this.type=type}},document:{dispatchEvent:e=>events.push(e.type)},fetch:async()=>({ok:true,json:async()=>payload}),EventSource:class{},setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../live.js'),'utf8')+';this.live=TraceLive',ctx);
(async()=>{
 await ctx.live.refresh();
 const s=ctx.live.snapshot('test');
 assert.equal(s.percent,35);assert.equal(s.groups[0].children[0].children[0].id,'a');assert.equal(s.tasks.length,4);
 assert.match(s.groups[0].description,/2 个子任务/);
 const d=ctx.live.diagram('test','flow','run');assert.equal(d.version,1);assert.equal(d.nodes.length,2);assert(d.edges[0].d);
 assert.equal(ctx.live.diagram('test','flow','').nodes.length,3);
 const at1=ctx.live.runtime('test','flow','run',1);assert.equal(at1.nodes.a,'running');assert.equal(at1.nodes.b,'pending');assert.equal(at1.edges.ab,'pending');
 const at2=ctx.live.runtime('test','flow','run',2);assert.equal(at2.nodes.a,'done');assert.equal(at2.edges.ab,'done');assert.equal(at2.elapsed,42);
 assert.equal(ctx.live.status,'online');assert(events.includes('trace:state'));
 ctx.fetch=async()=>{throw Error('offline')};await ctx.live.refresh();assert.equal(ctx.live.status,'offline');assert.equal(ctx.live.snapshot('test').percent,35);
 payload={...payload,revision:2};ctx.fetch=async()=>({ok:true,json:async()=>payload});await ctx.live.refresh();assert.equal(ctx.live.status,'online');assert.equal(ctx.live.revision,2);
 payload.projects[0].summary.progress=99.9;payload.revision=3;await ctx.live.refresh();assert.equal(ctx.live.snapshot('test').percent,99);
 payload.projects[0].summary.status='done';payload.projects[0].summary.progress=100;payload.revision=4;await ctx.live.refresh();assert.equal(ctx.live.snapshot('test').percent,100);
 console.log('live adapter: nesting, version pinning, runtime replay and reconnect passed');
})().catch(e=>{console.error(e);process.exitCode=1});
