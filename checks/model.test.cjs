const assert=require('node:assert/strict');
const d=require('../data.js');
assert.equal(d.snapshot('running').progress,66.6);
assert.equal(d.snapshot('recovery').percent,65);
assert.equal(d.snapshot('replan').percent,64);
assert.equal(d.snapshot('replan').weight,108);
assert.equal(d.snapshot('replan').tasks.find(t=>t.id==='persist').status,'waiting');
assert.equal(d.snapshot('complete').percent,100);
assert.equal(d.snapshot('complete').total,10);
assert.equal(d.snapshot('complete').weight,108);
assert.equal(d.projectSnapshot('RUN-027').percent,77);
assert.equal(d.projectSnapshot('RUN-028').percent,100);
for(const p of d.projects){
 for(const scene of Object.keys(d.scenes)){
  const s=d.projectSnapshot(p.id,scene),ids=new Set(s.tasks.map(t=>t.id));
  assert.equal(ids.size,s.total);
  assert.equal(s.done+s.running+s.waiting,s.total);
  for(const t of s.tasks){
   assert(t.progress>=0&&t.progress<=100&&t.weight>0);
   for(const id of t.dependencies)assert(ids.has(id));
   if(['running','recovery'].includes(t.status))for(const id of t.dependencies)assert.equal(s.tasks.find(x=>x.id===id).progress,100,`${p.id}/${scene}/${t.id} started before dependency ${id}`);
   function visit(id,seen=new Set()){assert(!seen.has(id),'Dependency cycle');const next=new Set(seen);next.add(id);for(const dep of s.tasks.find(x=>x.id===id).dependencies)visit(dep,next)}visit(t.id);
  }
 }
 assert(d.diagramSets[p.id][p.defaultDiagram]);
 for(const [kind,g] of Object.entries(d.diagramSets[p.id])){
  const nodeIds=new Set(g.nodes.map(n=>n.id)),edgeIds=new Set(g.edges.map(e=>e.id));
  assert.equal(nodeIds.size,g.nodes.length);assert.equal(edgeIds.size,g.edges.length);
  for(const edge of g.edges){assert(nodeIds.has(edge.from));assert(nodeIds.has(edge.to))}
  for(const step of g.steps){step.nodes.forEach(id=>assert(nodeIds.has(id)));if(step.edge)assert(edgeIds.has(step.edge));}
  for(const run of Object.keys(d.runs)){
   const max=d.available(kind,run,p.id);
   for(let cursor=0;cursor<=max;cursor++){
    const rt=d.runtime(kind,run,cursor,p.id);assert.equal(rt.cursor,cursor);assert.equal(rt.max,max);
    if(cursor===max&&run==='failed')assert(Object.values(rt.nodes).includes('error'));
    if(cursor===max&&run==='success')assert(!Object.values(rt.nodes).includes('running'));
   }
  }
 }
}
console.log('PASS: weighted progress, dynamic plan, dependency readiness and DAGs, root totals, per-task diagrams, all replay paths and failure/completion boundaries.');
