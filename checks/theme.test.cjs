const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const code=fs.readFileSync(require('node:path').join(__dirname,'../theme.js'),'utf8');
function setup(saved=null,dark=true,blocked=false){
 let stored=saved;const events={},root={dataset:{}},note={textContent:''};
 const media={matches:dark,addEventListener:(type,fn)=>events.media=fn};
 const document={documentElement:root,querySelectorAll:()=>[],querySelector:()=>note,addEventListener:(type,fn)=>events[type]=fn};
 vm.runInNewContext(code,{document,matchMedia:()=>media,localStorage:{getItem:()=>{if(blocked)throw Error();return stored},setItem:(key,value)=>{if(blocked)throw Error();stored=value}},addEventListener:(type,fn)=>events[type]=fn});
 events.DOMContentLoaded();return {root,media,events,note,stored:()=>stored,choose:mode=>events.change({target:{dataset:{pref:'mode'},value:mode}})};
}
const a=setup();assert.equal(a.root.dataset.mode,'dark');a.media.matches=false;a.events.media();assert.equal(a.root.dataset.mode,'light');a.choose('dark');a.events.media();assert.equal(a.root.dataset.mode,'dark');
assert.equal(setup(a.stored(),false).root.dataset.mode,'dark');a.choose('system');assert.equal(JSON.parse(a.stored()).mode,'system');a.media.matches=true;a.events.media();assert.equal(a.root.dataset.mode,'dark');
assert.equal(setup('{invalid}',false).root.dataset.mode,'light');assert.equal(setup('{"mode":"invalid"}',true).root.dataset.mode,'dark');
const b=setup(null,true,true);b.choose('light');assert.equal(b.root.dataset.mode,'light');assert.match(b.note.textContent,/无法保存/);
console.log('PASS: first paint, live system changes, manual override, persistent preference, invalid values, blocked storage fallback.');
