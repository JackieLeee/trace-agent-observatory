const TraceData = (() => {
 const agents={
  atlas:{name:'Atlas',role:'协调 Agent',letter:'A'},forge:{name:'Forge',role:'服务端 Agent',letter:'F'},pixel:{name:'Pixel',role:'前端 Agent',letter:'P'},scout:{name:'Scout',role:'验证 Agent',letter:'S'}
 };
 const groups=[
  {id:'scope',number:'01',title:'明确需求与技术方案',description:'目标与边界已对齐',children:[
   {id:'requirements',number:'1.1',title:'梳理导入规则与验收标准',weight:8,progress:100,agent:'atlas',dependencies:[],duration:'3分12秒',objective:'明确文件类型、容量限制、错误反馈和验收条件。',current:'验收标准已确认，已交接实现 Agent。',done:['支持 CSV / XLSX，单文件上限 20 MB','明确重复数据、空行和格式错误的处理规则','形成 12 条可验证的验收条件'],todo:[],artifact:'需求与验收清单'},
   {id:'contract',number:'1.2',title:'定义接口与任务状态模型',weight:7,progress:100,agent:'atlas',dependencies:['requirements'],duration:'2分48秒',objective:'让上传、校验、写入及结果查询共享一致的数据契约。',current:'接口契约和状态迁移已完成。',done:['定义上传与批次查询接口','明确待处理、处理中、完成与失败状态','约定错误码和可重试条件'],todo:[],artifact:'接口与状态模型'}
  ]},
  {id:'backend',number:'02',title:'构建导入服务',description:'正在实现断点续传',children:[
   {id:'parser',number:'2.1',title:'实现文件解析与字段映射',weight:18,progress:100,agent:'forge',dependencies:['contract'],duration:'6分24秒',objective:'把不同格式的表格转换成统一的标准记录。',current:'两种格式已接通，字段映射验证通过。',done:['CSV / XLSX 解析完成','支持表头匹配和日期类型转换','通过 24 组解析样例'],todo:[],artifact:'解析模块 · 验证摘要'},
   {id:'validator',number:'2.2',title:'完成数据校验与去重',weight:12,progress:100,agent:'forge',dependencies:['parser'],duration:'4分36秒',objective:'在写入前识别格式错误和重复记录，输出清楚的原因。',current:'校验与去重已完成，边界样例通过。',done:['必填、类型与取值范围检查完成','批次内与跨批次去重完成','错误行保留定位信息'],todo:[],artifact:'数据校验 · 结果摘要'},
   {id:'persist',number:'2.3',title:'实现幂等写入与断点续传',weight:10,progress:80,agent:'forge',dependencies:['validator'],duration:'5分08秒',objective:'中断后继续导入，重复提交不会生成重复数据。',current:'正在验证网络中断后，从最近检查点继续写入。',done:['批次幂等键已接通','写入检查点已保存','重复提交用例已通过'],todo:['完成中断恢复验证'],artifact:'导入服务 · 实现摘要'}
  ]},
  {id:'frontend',number:'03',title:'交付前端体验',description:'与服务端并行推进',children:[
   {id:'upload',number:'3.1',title:'构建文件上传与字段预览',weight:12,progress:80,agent:'pixel',dependencies:['contract'],duration:'7分16秒',objective:'让用户先确认文件内容和字段匹配，再开始导入。',current:'正在完善大文件预览与空字段提示。',done:['拖拽和选择文件已完成','前 20 行预览已接通','字段映射控件已完成'],todo:['完善大文件与空字段反馈'],artifact:'上传与预览 · 界面摘要'},
   {id:'feedback',number:'3.2',title:'展示批次进度与错误反馈',weight:8,progress:50,agent:'pixel',dependencies:['contract'],duration:'3分42秒',objective:'让每个批次的处理进度与结果可理解、可追踪。',current:'正在实现错误行说明与失败批次的恢复入口。',done:['批次状态与进度展示完成','成功结果摘要完成'],todo:['完成错误行说明','补齐恢复入口和空态'],artifact:'批次反馈 · 设计摘要'}
  ]},
  {id:'verification',number:'04',title:'验证与交付',description:'等待实现分支汇合',children:[
   {id:'integration',number:'4.1',title:'验证端到端流程与异常恢复',weight:15,progress:0,agent:'scout',dependencies:['persist','upload','feedback'],duration:'尚未开始',objective:'覆盖从上传到结果的完整路径，以及中断、重试和错误输入。',current:'等待服务端与前端就绪后自动开始。',done:[],todo:['验证完整导入路径','检查中断恢复与重复提交','检查错误输入与大文件场景'],artifact:null},
   {id:'delivery',number:'4.2',title:'整理交付产物与验收结论',weight:10,progress:0,agent:'scout',dependencies:['integration'],duration:'尚未开始',objective:'汇总可查看的实现产物、验证结果与使用说明。',current:'等待端到端验证完成。',done:[],todo:['汇总验证结果','补充使用说明','形成最终交付摘要'],artifact:null}
  ]}
 ];
 const scenes={
  running:{label:'并行执行',time:'14:26:08',elapsed:'18分42秒',version:'v1.0',summary:'服务端与前端并行推进，验证 Agent 等待依赖就绪。'},
  recovery:{label:'自主恢复',time:'14:27:16',elapsed:'19分50秒',version:'v1.0',summary:'Forge 正在自动处理写入冲突，前端工作继续推进。'},
  replan:{label:'计划调整',time:'14:29:04',elapsed:'21分38秒',version:'v1.1',summary:'新增编码兼容子任务，Agent 已更新计划与依赖。'},
  complete:{label:'全部完成',time:'14:38:42',elapsed:'31分16秒',version:'v1.1',summary:'实现与验证均已结束，交付产物已整理完成。'}
 };
 function flatten(list){return list.flatMap(group=>group.children)}
 function summarize(tasks){
  const weight=tasks.reduce((sum,t)=>sum+t.weight,0);
  const progress=weight?tasks.reduce((sum,t)=>sum+t.weight*t.progress,0)/weight:0;
  return {weight,progress,percent:Math.round(progress),done:tasks.filter(t=>t.progress===100).length,running:tasks.filter(t=>t.status?['running','recovery'].includes(t.status):t.progress>0&&t.progress<100).length,waiting:tasks.filter(t=>t.status?t.status==='waiting':t.progress===0).length,total:tasks.length};
 }
 function snapshot(scene='running'){
  const list=structuredClone(groups);
  if(scene==='recovery'){
   const t=flatten(list).find(t=>t.id==='persist');t.progress=65;t.recovering=true;
   t.current='已识别并发写入冲突，正在切换为按批次串行恢复。';
   t.issue='两个恢复请求同时写入同一检查点。';t.recovery='保留已写入记录，收敛为单个恢复任务，并重新验证幂等键。';
  }
  if(scene==='replan'||scene==='complete'){
   list[1].children.splice(2,0,{id:'encoding',number:'2.3',title:'修复历史文件编码兼容性',weight:8,progress:25,agent:'forge',dependencies:['parser'],duration:'1分12秒',objective:'兼容历史系统导出的非 UTF-8 文件，保持字段内容正确。',current:'已定位 GB18030 样例，正在补充自动识别与转换。',done:['复现历史编码输入'],todo:['完成编码识别','补充混合字符验证'],artifact:null});
   const t=flatten(list).find(t=>t.id==='persist');t.number='2.4';t.dependencies.push('encoding');t.waitingForDependency=true;t.current='已保留写入实现，等待编码兼容分支完成后继续验证。';
   list[1].description='新增编码兼容分支';
  }
  if(scene==='complete')flatten(list).forEach(t=>{t.progress=100;t.current='目标已完成，验证结果通过。';t.done.push(...t.todo);t.todo=[];t.artifact=t.artifact||`${t.title} · 完成摘要`;if(t.duration==='尚未开始')t.duration=t.id==='delivery'?'2分18秒':'8分06秒'});
  flatten(list).forEach(t=>t.status=t.recovering?'recovery':t.progress===100?'done':t.waitingForDependency?'waiting':t.progress>0?'running':'waiting');
  return {groups:list,tasks:flatten(list),...summarize(flatten(list)),...scenes[scene]};
 }
 const architecture={
  title:'系统架构',subtitle:'模块、职责与连接',icon:'network',description:'查询路径与入库路径共享数据层，检索与生成分开处理。',unit:'模块',
  nodes:[
   {id:'client',title:'客户端',sub:'Web / App',x:22,y:140,icon:'window',description:'接收用户查询，持续呈现流式答案与引用来源。',inputs:['用户问题'],outputs:['查询请求','文件上传请求']},
   {id:'api',title:'API 网关',sub:'请求与会话入口',x:222,y:140,icon:'gateway',description:'统一处理请求校验、会话标识和响应分发。',inputs:['查询请求','会话标识'],outputs:['标准化查询','流式响应']},
   {id:'retriever',title:'语义检索器',sub:'召回与上下文整理',x:422,y:140,icon:'search',description:'从向量索引召回相关片段，整理成生成服务可用的上下文。',inputs:['标准化查询','召回数量 top_k'],outputs:['相关片段 chunks[]','引用信息与相关度']},
   {id:'model',title:'生成服务',sub:'答案与引用',x:622,y:140,icon:'spark',description:'结合问题与检索上下文生成答案，按片段持续返回。',inputs:['用户问题','检索上下文'],outputs:['答案片段','引用来源']},
   {id:'object',title:'文件存储',sub:'原始文档',x:22,y:362,icon:'storage',description:'保存原始文件及版本信息，供解析和来源追溯使用。',inputs:['原始文件','文档版本'],outputs:['文件地址','文件元信息']},
   {id:'ingest',title:'入库服务',sub:'解析与向量化',x:222,y:362,icon:'layers',description:'解析文档、切分片段并生成向量，将内容写入可检索的数据层。',inputs:['文档文件','解析配置'],outputs:['文档片段','向量与元数据']},
   {id:'vector',title:'向量索引',sub:'片段与相似度',x:422,y:362,icon:'database',description:'存储文档片段向量，按查询向量返回相似内容。',inputs:['片段向量','查询向量'],outputs:['匹配片段','相关度分数']}
  ],
  edges:[
   {id:'client-api',from:'client',to:'api',d:'M176 182H222',label:'查询',lx:198,ly:169},
   {id:'api-retriever',from:'api',to:'retriever',d:'M376 182H422',label:'检索',lx:398,ly:169},
   {id:'retriever-model',from:'retriever',to:'model',d:'M576 182H622',label:'上下文',lx:598,ly:169},
   {id:'retriever-vector',from:'retriever',to:'vector',d:'M499 224V362',label:'向量召回',lx:540,ly:295},
   {id:'api-ingest',from:'api',to:'ingest',d:'M299 224V362',label:'上传',lx:324,ly:295},
   {id:'ingest-object',from:'ingest',to:'object',d:'M222 404H176',label:'保存',lx:198,ly:390},
   {id:'ingest-vector',from:'ingest',to:'vector',d:'M376 404H422',label:'索引',lx:398,ly:390},
   {id:'model-api',from:'model',to:'api',d:'M699 140V84H299V140',label:'流式答案',lx:495,ly:70}
  ],
  steps:[
   {title:'接收用户查询',nodes:['client','api'],edge:'client-api',ms:12},
   {title:'构建语义检索请求',nodes:['api','retriever'],edge:'api-retriever',ms:24},
   {title:'召回相关文档片段',nodes:['retriever','vector'],edge:'retriever-vector',ms:178},
   {title:'组织生成上下文',nodes:['retriever','model'],edge:'retriever-model',ms:38},
   {title:'流式返回答案与引用',nodes:['model','api','client'],edge:'model-api',ms:860}
  ],defaultNode:'retriever',failureAt:3
 };
 const flow={
  title:'文档入库流程',subtitle:'数据处理与流向',icon:'flow',description:'文档经过解析、切分与向量化后发布到可查询的索引。',unit:'步骤',
  nodes:[
   {id:'receive',title:'接收文档',sub:'文件 + 元信息',x:40,y:110,icon:'upload',description:'验证文档类型与大小，为本次入库创建唯一批次。',inputs:['原始文件','文档标题与来源'],outputs:['文档 ID','入库批次 ID']},
   {id:'parse',title:'提取正文',sub:'保留段落与来源',x:315,y:110,icon:'file',description:'从文档中提取正文，保留页码、段落和标题关系。',inputs:['文档文件'],outputs:['结构化正文','页码与标题信息']},
   {id:'split',title:'切分片段',sub:'按语义与长度',x:590,y:110,icon:'layers',description:'把正文划分为长度适中的检索片段，保留必要重叠和来源关系。',inputs:['结构化正文','切分配置'],outputs:['片段数组','片段来源映射']},
   {id:'embed',title:'生成向量',sub:'片段 → 向量',x:590,y:350,icon:'spark',description:'为每个片段生成语义向量，失败片段按批次恢复。',inputs:['片段数组'],outputs:['片段向量','向量模型版本']},
   {id:'index',title:'写入索引',sub:'向量 + 元数据',x:315,y:350,icon:'database',description:'将片段、向量和来源元信息写入索引，并检查批次完整性。',inputs:['片段向量','来源元数据'],outputs:['索引版本','写入结果']},
   {id:'publish',title:'开放检索',sub:'文档状态就绪',x:40,y:350,icon:'check',description:'索引检查通过后，将文档标记为就绪，供后续查询召回。',inputs:['索引版本','完整性检查结果'],outputs:['可查询文档','就绪状态']}
  ],
  edges:[
   {id:'receive-parse',from:'receive',to:'parse',d:'M194 152H315',label:'文档',lx:254,ly:138},
   {id:'parse-split',from:'parse',to:'split',d:'M469 152H590',label:'正文',lx:530,ly:138},
   {id:'split-embed',from:'split',to:'embed',d:'M667 194V350',label:'片段数组',lx:709,ly:276},
   {id:'embed-index',from:'embed',to:'index',d:'M590 392H469',label:'向量',lx:530,ly:378},
   {id:'index-publish',from:'index',to:'publish',d:'M315 392H194',label:'索引版本',lx:254,ly:378}
  ],
  steps:[{title:'创建文档入库批次',nodes:['receive'],ms:24},{title:'提取正文与页码',nodes:['parse'],edge:'receive-parse',ms:138},{title:'切分为 36 个片段',nodes:['split'],edge:'parse-split',ms:42},{title:'生成片段语义向量',nodes:['embed'],edge:'split-embed',ms:648},{title:'写入并检查索引',nodes:['index'],edge:'embed-index',ms:192},{title:'文档已可检索',nodes:['publish'],edge:'index-publish',ms:18}],defaultNode:'embed',failureAt:4
 };
 const sequence={
  title:'查询调用时序',subtitle:'服务交互与先后顺序',icon:'sequence',description:'从用户提问到流式回答，依次查看服务间的请求和返回。',unit:'交互',
  participants:[{id:'p-client',title:'客户端',x:80},{id:'p-api',title:'API 网关',x:295},{id:'p-index',title:'检索服务',x:510},{id:'p-model',title:'生成服务',x:725}],
  nodes:[
   {id:'s1',title:'提交用户问题',sub:'POST /query',from:80,to:295,y:146,icon:'arrow',description:'客户端发送问题及当前会话标识。',inputs:['用户问题','会话 ID'],outputs:['查询请求']},
   {id:'s2',title:'召回相关内容',sub:'semanticSearch(query)',from:295,to:510,y:211,icon:'search',description:'网关调用检索服务，寻找与问题相关的文档片段。',inputs:['用户问题','检索条件'],outputs:['检索调用']},
   {id:'s3',title:'返回片段与引用',sub:'chunks[] + sources[]',from:510,to:295,y:276,icon:'layers',description:'检索服务返回排序后的片段、相关度和来源信息。',inputs:['命中的文档片段'],outputs:['检索上下文','引用来源']},
   {id:'s4',title:'请求生成答案',sub:'generate(question, context)',from:295,to:725,y:341,icon:'spark',description:'网关组合问题与上下文，向生成服务发起流式请求。',inputs:['用户问题','检索上下文'],outputs:['生成请求']},
   {id:'s5',title:'持续返回答案片段',sub:'token stream',from:725,to:295,y:406,icon:'arrow',description:'生成服务持续返回答案片段和引用信息。',inputs:['生成结果'],outputs:['答案流','引用信息']},
   {id:'s6',title:'向用户呈现答案',sub:'Server-Sent Events',from:295,to:80,y:471,icon:'check',description:'网关将答案流转发给客户端，客户端逐段呈现。',inputs:['答案流'],outputs:['可阅读的答案与引用']}
  ],edges:[],steps:[{title:'用户提交查询',nodes:['s1'],ms:12},{title:'发起语义检索',nodes:['s2'],ms:24},{title:'检索上下文返回',nodes:['s3'],ms:178},{title:'发起生成请求',nodes:['s4'],ms:38},{title:'接收答案片段',nodes:['s5'],ms:848},{title:'呈现最终答案',nodes:['s6'],ms:12}],defaultNode:'s4',failureAt:2
 };
 const diagrams={architecture,flow,sequence};
 const projects=[
  {id:'RUN-026',title:'构建文档批量导入能力',description:'支持文件解析、数据校验、断点续传与结果反馈。',owner:'Atlas',category:'功能交付',updated:'14:26:08',diagramTitle:'批量导入系统',diagramDescription:'理解上传、解析、校验和写入之间的关系。',defaultDiagram:'architecture'},
  {id:'RUN-027',title:'搭建文档检索链路',description:'连接语义检索与答案生成，让每次回答都有出处。',owner:'Atlas',category:'系统建设',updated:'14:24:32',diagramTitle:'文档检索系统',diagramDescription:'从结构到运行，看清数据如何流动、服务如何协作。',defaultDiagram:'architecture'},
  {id:'RUN-028',title:'完善文档入库管线',description:'完成正文解析、语义切分与索引发布的整体验证。',owner:'Scout',category:'数据管线',updated:'13:52:10',diagramTitle:'文档入库管线',diagramDescription:'理解文档从原始文件变为可检索内容的全过程。',defaultDiagram:'flow'}
 ];
 function sampleTask(id,number,title,weight,progress,agentId,dependencies,current){return {id,number,title,weight,progress,agent:agentId,dependencies,current,duration:progress===0?'尚未开始':progress===100?'已完成':'4分12秒',objective:title+'，并提供可验证的执行结果。',done:progress===100?['实现内容已完成','对应验证通过']:progress>0?['主要处理路径已接通']:[],todo:progress===100?[]:['补齐边界验证与交付摘要'],artifact:progress===100?title+' · 完成摘要':null,status:progress===100?'done':progress>0?'running':'waiting'}}
 const projectGroups={
  'RUN-027':[
   {id:'query-scope',number:'01',title:'对齐查询与数据契约',description:'方案与输入输出已明确',children:[sampleTask('query-contract','1.1','明确查询与引用契约',8,100,'atlas',[],'查询与引用模型已确认。')]},
   {id:'query-build',number:'02',title:'实现检索与生成链路',description:'召回与生成并行完善',children:[sampleTask('query-store','2.1','接通文档索引与元数据',20,100,'forge',['query-contract'],'索引与来源映射验证通过。'),sampleTask('query-client','2.2','完成流式查询界面',20,100,'pixel',['query-contract'],'流式回答与引用展示已完成。'),sampleTask('query-retrieve','2.3','完善语义召回与重排',20,85,'forge',['query-store'],'正在验证长问题和低相关度输入。'),sampleTask('query-generate','2.4','接入生成服务与来源引用',20,60,'forge',['query-store'],'正在完善答案与来源的逐段对应。')]},
   {id:'query-verify',number:'03',title:'验证回答质量与交付',description:'等待链路实现收敛',children:[sampleTask('query-test','3.1','验证端到端回答与引用',12,0,'scout',['query-retrieve','query-generate'],'等待检索和生成服务就绪后自动开始。')]}
  ],
  'RUN-028':[
   {id:'ingest-extract',number:'01',title:'解析与内容切分',description:'已完成',children:[sampleTask('ingest-parse','1.1','提取文档正文与来源',20,100,'forge',[],'正文与来源关系验证通过。'),sampleTask('ingest-split','1.2','完成语义片段切分',20,100,'forge',['ingest-parse'],'36组切分样例验证通过。')]},
   {id:'ingest-store',number:'02',title:'向量化与索引',description:'已完成',children:[sampleTask('ingest-vector','2.1','生成片段语义向量',25,100,'forge',['ingest-split'],'向量生成与恢复验证通过。'),sampleTask('ingest-index','2.2','写入并发布检索索引',20,100,'forge',['ingest-vector'],'索引完整性检查通过。')]},
   {id:'ingest-verify',number:'03',title:'验收与交付',description:'已完成',children:[sampleTask('ingest-test','3.1','验证文档入库与召回',15,100,'scout',['ingest-index'],'入库、检索与来源追溯验证通过。')]}
  ]
 };
 function projectSnapshot(id,scene='running'){
  const project=projects.find(p=>p.id===id)||projects[0];
  if(project.id==='RUN-026')return {...snapshot(scene),project};
  const list=structuredClone(projectGroups[project.id]),tasks=flatten(list),complete=tasks.every(t=>t.progress===100);
  return {groups:list,tasks,...summarize(tasks),project,time:project.updated,elapsed:complete?'26分18秒':'22分06秒',version:'v1.0',label:complete?'全部完成':'并行执行',summary:complete?'所有子任务已完成，验证与交付已收敛。':'实现 Agent 正在并行完善检索链路，验证将在依赖就绪后开始。'};
 }
 const importArchitecture=structuredClone(architecture);
 importArchitecture.description='上传文件经过解析、校验与幂等写入，进度和结果由导入 API 汇总。';
 const importNames={client:['上传界面','预览与结果反馈','window'],api:['导入 API','批次与进度入口','gateway'],retriever:['解析服务','文件与字段映射','file'],model:['校验与去重','标准化记录','check'],object:['文件存储','原始导入文件','storage'],ingest:['幂等写入','检查点与恢复','layers'],vector:['业务数据存储','记录与批次结果','database']};
 importArchitecture.nodes.forEach(n=>{const [title,sub,ic]=importNames[n.id];Object.assign(n,{title,sub,icon:ic,description:{client:'选择文件、确认字段预览，并查看本次导入的进度与结果。',api:'创建导入批次，统一返回批次状态与处理结果。',retriever:'解析原始表格，转换字段类型并输出标准化记录。',model:'检查记录是否有效，并识别批次内和跨批次的重复数据。',object:'保存原始上传文件，供重试、恢复与来源追溯使用。',ingest:'按批次保存校验后的记录，维护幂等键与恢复检查点。',vector:'保存业务记录、写入检查点和导入批次结果。'}[n.id],inputs:n.id==='client'?['导入文件']:n.id==='ingest'?['有效记录','批次幂等键']:n.id==='model'?['标准化记录']:['文件或批次请求'],outputs:n.id==='retriever'?['标准化记录','字段映射']:n.id==='model'?['有效记录','错误行说明']:n.id==='ingest'?['写入结果','恢复检查点']:['处理结果与状态']})});
 importArchitecture.edges=[
  {id:'client-api',from:'client',to:'api',d:'M176 182H222',label:'上传',lx:198,ly:169},
  {id:'api-retriever',from:'api',to:'retriever',d:'M376 182H422',label:'解析',lx:398,ly:169},
  {id:'retriever-model',from:'retriever',to:'model',d:'M576 182H622',label:'记录',lx:598,ly:169},
  {id:'model-ingest',from:'model',to:'ingest',d:'M699 224V285H299V362',label:'有效记录',lx:540,ly:272},
  {id:'api-object',from:'api',to:'object',d:'M277 224V272H99V362',label:'原文件',lx:172,ly:259},
  {id:'ingest-vector',from:'ingest',to:'vector',d:'M376 404H422',label:'写入',lx:398,ly:390},
  {id:'ingest-api',from:'ingest',to:'api',d:'M252 362V224',label:'进度',lx:223,ly:316}
 ];
 importArchitecture.steps=[{title:'接收文件与创建批次',nodes:['client','api'],edge:'client-api',ms:24},{title:'解析文件与映射字段',nodes:['api','retriever'],edge:'api-retriever',ms:138},{title:'校验记录并去重',nodes:['retriever','model'],edge:'retriever-model',ms:86},{title:'幂等写入有效记录',nodes:['model','ingest'],edge:'model-ingest',ms:192},{title:'保存结果与恢复检查点',nodes:['ingest','vector'],edge:'ingest-vector',ms:42}];importArchitecture.defaultNode='ingest';importArchitecture.failureAt=4;
 const importFlow=structuredClone(flow);
 importFlow.title='数据导入流程';importFlow.description='从原始文件到批次结果，依次完成解析、校验、写入和结果汇总。';
 const importFlowNames=[['接收文件','文件 + 导入配置'],['解析与字段映射','表格 → 标准记录'],['校验与去重','识别错误与重复'],['幂等写入','按检查点恢复'],['汇总导入结果','成功 / 跳过 / 失败'],['批次完成','交付结果摘要']];
 importFlow.nodes.forEach((n,i)=>{n.title=importFlowNames[i][0];n.sub=importFlowNames[i][1];n.description=['创建批次并保存原始文件，确认格式、容量和字段配置。','提取表格内容，完成表头映射和字段类型转换。','验证记录是否有效，输出重复记录和错误行的处理说明。','写入通过校验的记录，持续保存恢复检查点。','汇总成功、跳过和失败的记录数量，并保留原因。','本批次处理结束，向用户呈现可理解的导入摘要。'][i];n.inputs=[['原始文件','导入配置'],['文件内容','字段映射'],['标准化记录'],['有效记录','幂等键'],['各记录处理结果'],['批次结果摘要']][i];n.outputs=[['批次 ID','文件地址'],['标准化记录'],['有效记录','错误行说明'],['写入结果','检查点'],['数量汇总','失败原因'],['完成状态','可查看的结果']][i]});
 importFlow.steps.forEach((s,i)=>s.title=importFlowNames[i][0]);importFlow.edges.forEach((e,i)=>e.label=['文件','标准记录','有效记录','写入结果','结果摘要'][i]);
 const importSequence=structuredClone(sequence);importSequence.participants.forEach((p,i)=>p.title=['上传界面','导入 API','导入 Worker','业务数据库'][i]);
 importSequence.title='导入调用时序';importSequence.description='查看上传界面、导入 API、Worker 与数据库之间的交互顺序。';importSequence.failureAt=3;
 const importMessages=[['提交导入文件','POST /imports',80,295],['派发导入批次','dispatch(batch_id)',295,510],['写入校验后的记录','write(records, key)',510,725],['返回写入检查点','checkpoint + count',725,510],['回报批次进度','progress + summary',510,295],['展示导入结果','batch summary',295,80]];
 importSequence.nodes.forEach((n,i)=>{const [title,sub,from,to]=importMessages[i];Object.assign(n,{title,sub,from,to,description:['界面提交文件与字段配置，API 创建导入批次。','API 将批次交给 Worker，后续按批次处理。','Worker 将已校验记录按幂等键写入业务数据库。','数据库返回已提交数量与恢复检查点。','Worker 将进度和结果摘要汇报给 API。','API 向界面返回批次结果，用户查看成功与失败摘要。'][i],inputs:[i===0?'文件与字段配置':'上一步处理结果'],outputs:[i===5?'可查看的导入摘要':'当前交互处理结果']});importSequence.steps[i].title=title});
 const diagramSets={'RUN-026':{architecture:importArchitecture,flow:importFlow,sequence:importSequence},'RUN-027':diagrams,'RUN-028':{architecture,flow}};
 const runs={live:{title:'运行中 · RUN-1028',status:'running',time:'14:26:08'},success:{title:'已完成 · RUN-1027',status:'done',time:'14:21:36'},failed:{title:'已中断 · RUN-1026',status:'error',time:'14:18:04'}};
 function available(kind,run,project='RUN-027'){const d=diagramSets[project][kind];return run==='success'?d.steps.length:run==='failed'?d.failureAt:d.steps.length-1}
 function runtime(kind,run,cursor,project='RUN-027'){
  const d=diagramSets[project][kind],max=available(kind,run,project),at=Math.max(0,Math.min(cursor,max)),nodes={},edges={};
  d.nodes.forEach(n=>nodes[n.id]='pending');d.edges.forEach(e=>edges[e.id]='pending');
  for(let i=0;i<at;i++){
   const step=d.steps[i],current=i===at-1;
   const state=current&&at===max&&run==='failed'?'error':current&&!(run==='success'&&at===max)?'running':'done';
   step.nodes.forEach(id=>nodes[id]=state);if(step.edge)edges[step.edge]=state;
  }
  return {nodes,edges,cursor:at,max,step:at?d.steps[at-1]:null,elapsed:d.steps.slice(0,at).reduce((sum,s)=>sum+s.ms,0)};
 }
 return {agents,groups,scenes,snapshot,summarize,flatten,diagrams,projects,projectSnapshot,diagramSets,runs,available,runtime};
})();
if(typeof module!=='undefined'&&module.exports)module.exports=TraceData;
