/* Mac preferences are authoritative; local storage is a browser-preview fallback. */
const TraceFloatingPreferences=(()=>{
 const key='trace.floating.v1',defaults={enabled:true,autoHide:true,edge:'right',taskMode:'automatic',taskIDs:[]};
 function normalize(raw){const p=raw&&typeof raw==='object'?raw:{};return {enabled:typeof p.enabled==='boolean'?p.enabled:defaults.enabled,autoHide:typeof p.autoHide==='boolean'?p.autoHide:defaults.autoHide,edge:p.edge==='left'?'left':'right',taskMode:p.taskMode==='manual'?'manual':'automatic',taskIDs:[...new Set((Array.isArray(p.taskIDs)?p.taskIDs:[]).filter(id=>typeof id==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$/.test(id)))].slice(0,4)}}
 let saved;try{saved=JSON.parse(localStorage.getItem(key))}catch{}
 let value=normalize(window.TraceNativeFloatingPreferences||saved);
 const bridge=()=>window.webkit?.messageHandlers?.traceFloatingPreferences;
 function apply(raw){value=normalize(raw);try{localStorage.setItem(key,JSON.stringify(value))}catch{}document.dispatchEvent(new Event('trace:floating-settings'))}
 function update(patch){const next=normalize({...value,...patch});apply(next);bridge()?.postMessage({action:'set',preferences:next})}
 addEventListener('trace:floating-preferences',event=>apply(event.detail));
 addEventListener('storage',event=>{if(!bridge()&&(event.key===key||event.key===null)){try{apply(JSON.parse(localStorage.getItem(key)))}catch{apply(defaults)}}});
 function init(){bridge()?.postMessage({action:'get'})}
 return {get value(){return {...value,taskIDs:[...value.taskIDs]}},update,init,normalize};
})();
