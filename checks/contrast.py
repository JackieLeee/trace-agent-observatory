from pathlib import Path
import re,json
root=Path(__file__).resolve().parent.parent
blocks=re.findall(r'(:root[^{}]*)\{([^{}]+)\}',(root/'theme.css').read_text())
pairs=[('text','surface'),('muted','surface'),('faint','canvas'),('accent','accent-soft'),('on-accent','accent'),('success','success-soft'),('warning','warning-soft'),('danger','danger-soft'),('pending','pending-soft'),('muted','subtle')]
results=[]
for mode in ['light','dark']:
 values={}
 for selector,body in blocks:
  if 'dark' in selector and mode!='dark':continue
  values.update(dict(re.findall(r'--([\w-]+)\s*:\s*([^;]+);',body)))
 def rgb(key):
  value=values[key].strip()
  if value.startswith('var('):return rgb(value[6:-1])
  h=value.lstrip('#');h=''.join(c*2 for c in h) if len(h)==3 else h
  return [int(h[i:i+2],16)/255 for i in (0,2,4)]
 def lum(c):return sum(w*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for w,v in zip([.2126,.7152,.0722],c))
 ratios={f'{a}/{b}':(max(lum(rgb(a)),lum(rgb(b)))+.05)/(min(lum(rgb(a)),lum(rgb(b)))+.05) for a,b in pairs}
 assert min(ratios.values())>=4.5,(mode,ratios)
 results.append({'mode':mode,'semanticTextPairs':{k:round(v,3) for k,v in ratios.items()},'minimum':min(ratios.values())})
 print(mode, 'PASS; minimum tested text contrast:',round(min(ratios.values()),2))
(root/'checks/contrast.json').write_text(json.dumps(results,indent=2))
