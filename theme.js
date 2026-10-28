(() => {
 const key='trace.appearance.v1';
 const media=matchMedia('(prefers-color-scheme: dark)');
 const normalize=p=>({mode:['system','light','dark'].includes(p?.mode)?p.mode:'system',brand:'trace'});
 const read=()=>{try{return normalize(JSON.parse(localStorage.getItem(key)))}catch{return normalize(null)}};
 let preferences=read();
 function apply(){
  document.documentElement.dataset.mode=preferences.mode==='system'?(media.matches?'dark':'light'):preferences.mode;
  document.documentElement.dataset.brand=preferences.brand;
  document.querySelectorAll('[data-pref]').forEach(input=>input.checked=preferences[input.dataset.pref]===input.value);
 }
 apply();
 media.addEventListener('change',()=>{if(preferences.mode==='system')apply()});
 document.addEventListener('DOMContentLoaded',()=>{
  apply();
  document.addEventListener('change',event=>{
   if(event.target.dataset.pref!=='mode')return;
   preferences=normalize({...preferences,mode:event.target.value});apply();
   try{localStorage.setItem(key,JSON.stringify(preferences))}catch{document.querySelector('#theme-note').textContent='此浏览器无法保存偏好，本次页面仍可切换外观。'}
  });
 });
 addEventListener('storage',event=>{if(event.key===key||event.key===null){preferences=read();apply()}});
})();
