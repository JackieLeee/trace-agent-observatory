"""SQLite state for a single-user, loopback Agent workspace."""
import copy
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STATES = {'waiting', 'running', 'recovery', 'blocked', 'done', 'error'}
ICONS = {'window','gateway','search','spark','storage','layers','database','upload','file','check','arrow','tasks','network','flow','sequence','terminal','target'}

class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'), sort_keys=True)

def obj(value):
    if not isinstance(value, dict):
        raise Problem('Expected a JSON object')
    return value

def fields(value, allowed):
    obj(value)
    extra = set(value) - set(allowed)
    if extra:
        raise Problem('Unknown fields: ' + ', '.join(sorted(extra)))

def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}', value):
        raise Problem('IDs must be 1–80 letters, digits, dots, colons, underscores or hyphens')
    return value

def text(value, limit=4000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise Problem(f'Expected {"nonempty " if required else ""}text, at most {limit} characters')
    return value

def number(value, low=0, high=1e12):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not low <= value <= high:
        raise Problem(f'Expected a finite number between {low} and {high}')
    return value

def integer(value, low=0):
    if isinstance(value,bool) or not isinstance(value,int) or value<low:
        raise Problem('Expected an integer at least '+str(low))
    return value

def strings(value, ids=False):
    if not isinstance(value, list) or len(value) > 500:
        raise Problem('Expected an array of at most 500 items')
    return [(ident(x) if ids else text(x)) for x in value]

def summary(project):
    nodes = copy.deepcopy(project['nodes'])
    by_id = {n['id']:n for n in nodes}
    children = {n['id']:[] for n in nodes}
    for n in nodes:
        if n['parent_id']:
            children[n['parent_id']].append(n['id'])
    cache = {}
    def aggregate(node_id):
        if node_id in cache:
            return cache[node_id]
        n = by_id[node_id]
        if children[node_id]:
            leaves = [leaf for child in children[node_id] for leaf in aggregate(child)]
            weight = sum(x['weight'] for x in leaves)
            n['progress'] = sum(x['weight']*x['progress'] for x in leaves)/weight
            statuses = {x['status'] for x in leaves}
            n['status'] = 'done' if statuses == {'done'} else 'blocked' if 'blocked' in statuses else 'recovery' if statuses & {'error','recovery'} else 'running' if statuses & {'running','done'} else 'waiting'
            n['weight'] = weight
        else:
            leaves = [n]
        n['children'] = children[node_id]
        cache[node_id] = leaves
        return leaves
    leaves = [leaf for n in nodes if not n['parent_id'] for leaf in aggregate(n['id'])]
    weight = sum(n['weight'] for n in leaves)
    progress = sum(n['weight']*n['progress'] for n in leaves)/weight if weight else 0
    statuses = {n['status'] for n in leaves}
    status = 'done' if leaves and statuses == {'done'} else 'blocked' if 'blocked' in statuses else 'recovery' if statuses & {'error','recovery'} else 'running' if statuses & {'running','done'} else 'waiting'
    return {**project, 'archived_at':project.get('archived_at'), 'nodes':nodes, 'summary':{
        'progress':progress,'status':status,'weight':weight,'total':len(leaves),
        'done':sum(n['status']=='done' for n in leaves),
        'running':sum(n['status'] in {'running','recovery','error'} for n in leaves),
        'waiting':sum(n['status']=='waiting' for n in leaves),
        'blocked':sum(n['status']=='blocked' for n in leaves)}}

def validate_graph(nodes):
    by_id = {n['id']:n for n in nodes}
    if len(by_id) != len(nodes):
        raise Problem('Duplicate task node ID')
    children = {n['id']:[] for n in nodes}
    for n in nodes:
        for dep in n['dependencies']:
            if dep not in by_id:
                raise Problem('Unknown dependency: '+dep)
        parent = n['parent_id']
        if parent:
            if parent not in by_id:
                raise Problem('Unknown parent: '+parent)
            children[parent].append(n['id'])
    visiting, visited = set(), set()
    def walk(node_id):
        if len(visiting)>64:
            raise Problem('Task hierarchy/dependency depth must not exceed 64')
        if node_id in visiting:
            raise Problem('Task hierarchy/dependency cycle at '+node_id)
        if node_id in visited:
            return
        visiting.add(node_id)
        for dep in by_id[node_id]['dependencies'] + children[node_id]:
            walk(dep)
        visiting.remove(node_id);visited.add(node_id)
    for n in nodes:
        walk(n['id'])
    resolved = {n['id']:n for n in summary({'nodes':nodes})['nodes']}
    for n in nodes:
        if not children[n['id']] and n['status'] in {'running','recovery','done'}:
            for dep in n['dependencies']:
                if resolved[dep]['status'] != 'done':
                    raise Problem(f"{n['id']} requires completed dependency {dep}",409)

NODE_FIELDS = {'id','parent_id','title','objective','current','done','todo','artifact','duration','agent','agent_role','weight','progress','status','dependencies','blocker'}
EXECUTION_FIELDS = {'objective','current','done','todo','artifact','duration','agent','agent_role','progress','status','blocker'}

def normalize_node(raw, previous=None):
    fields(raw,NODE_FIELDS)
    n = {'parent_id':None,'objective':'','current':'等待 Agent 汇报','done':[],'todo':[],
         'artifact':None,'duration':'','blocker':'','agent':'agent','agent_role':'执行 Agent','weight':1,
         'progress':0,'status':'waiting','dependencies':[],**(previous or {}),**raw}
    n['id'] = ident(n.get('id'))
    if n['parent_id'] is not None:
        n['parent_id'] = ident(n['parent_id'])
    n['title'] = text(n.get('title'),240,True)
    for key in ['objective','current','duration','agent_role','blocker']:
        n[key] = text(n[key])
    n['agent'] = ident(n['agent'])
    n['artifact'] = None if n['artifact'] is None else text(n['artifact'])
    n['weight'] = number(n['weight'],0.0001)
    n['progress'] = number(n['progress'],0,100)
    for key in ['done','todo','dependencies']:
        n[key] = strings(n[key],key=='dependencies')
    if len(set(n['dependencies'])) != len(n['dependencies']):
        raise Problem('Duplicate dependency')
    if not isinstance(n['status'],str) or n['status'] not in STATES:
        raise Problem('Unknown task status')
    if n['status'] == 'blocked' and not n['blocker'].strip():
        raise Problem('Blocked tasks require a blocker description')
    if n['status'] != 'blocked':
        if raw.get('blocker'):
            raise Problem('Blocker description requires status blocked')
        n['blocker']=''
    if n['status'] == 'done':
        n['progress'] = 100
    elif n['progress'] == 100:
        if 'status' in raw:
            raise Problem('100% progress requires status done')
        n['status'] = 'done'
    return n

def normalize_diagram(raw):
    fields(raw, {'id','kind','title','description','nodes','edges','participants','messages'})
    result = {'id':ident(raw.get('id')), 'title':text(raw.get('title'),240,True),
              'kind':raw.get('kind'), 'description':text(raw.get('description',''))}
    if not isinstance(result['kind'],str) or result['kind'] not in {'architecture','flow','sequence'}:
        raise Problem('Diagram kind must be architecture, flow or sequence')
    if result['kind'] == 'sequence':
        participants = raw.get('participants')
        if not isinstance(participants,list) or not 2 <= len(participants) <= 12:
            raise Problem('Sequence diagrams require 2–12 participants')
        result['participants'] = []
        for p in participants:
            fields(p,{'id','title'})
            result['participants'].append({'id':ident(p.get('id')),'title':text(p.get('title'),120,True)})
        ids = {p['id'] for p in result['participants']}
        if len(ids) != len(participants):
            raise Problem('Duplicate participant ID')
        messages = raw.get('messages')
        if not isinstance(messages,list) or not 1 <= len(messages) <= 200:
            raise Problem('Sequence diagrams require 1–200 messages')
        result['messages'] = []
        for m in messages:
            fields(m,{'id','from','to','title','description','inputs','outputs'})
            if ident(m.get('from')) not in ids or ident(m.get('to')) not in ids or m.get('from') == m.get('to'):
                raise Problem('Message endpoints must be distinct known participants')
            result['messages'].append({'id':ident(m.get('id')),'from':m['from'],'to':m['to'],
                'title':text(m.get('title'),240,True),'description':text(m.get('description','')),
                'inputs':strings(m.get('inputs',[])),'outputs':strings(m.get('outputs',[]))})
        if len({m['id'] for m in result['messages']}) != len(messages):
            raise Problem('Duplicate message ID')
    else:
        nodes,edges = raw.get('nodes'),raw.get('edges',[])
        if not isinstance(nodes,list) or not 1 <= len(nodes) <= 200 or not isinstance(edges,list) or len(edges)>500:
            raise Problem('Diagrams require 1–200 nodes and at most 500 edges')
        result['nodes'],result['edges'] = [],[]
        for n in nodes:
            fields(n,{'id','title','sub','description','inputs','outputs','icon','x','y'})
            item={'id':ident(n.get('id')),'title':text(n.get('title'),240,True),'sub':text(n.get('sub',''),240),
                'description':text(n.get('description','')),'inputs':strings(n.get('inputs',[])),
                'outputs':strings(n.get('outputs',[])),'icon':n.get('icon','layers')}
            if not isinstance(item['icon'],str) or item['icon'] not in ICONS:
                raise Problem('Unknown diagram icon')
            if ('x' in n) != ('y' in n):
                raise Problem('Provide both x and y, or neither')
            if 'x' in n:
                item.update(x=number(n['x'],0,10000),y=number(n['y'],0,10000))
            result['nodes'].append(item)
        ids = {n['id'] for n in result['nodes']}
        if len(ids)!=len(nodes):
            raise Problem('Duplicate diagram node ID')
        for i,e in enumerate(edges):
            fields(e,{'id','from','to','label'})
            if ident(e.get('from')) not in ids or ident(e.get('to')) not in ids:
                raise Problem('Unknown edge endpoint')
            result['edges'].append({'id':ident(e.get('id',f'edge-{i+1}')),'from':e['from'],'to':e['to'],'label':text(e.get('label',''),240)})
        if len({e['id'] for e in result['edges']})!=len(edges):
            raise Problem('Duplicate edge ID')
    return result

class Store:
    def __init__(self, home):
        self.home=Path(home).expanduser().resolve()
        self.home.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.token_path=self.home/'auth.token'
        try:
            with self.token_path.open('x') as file:
                file.write(secrets.token_urlsafe(32))
            self.token_path.chmod(0o600)
        except FileExistsError:
            pass
        self.token=self.token_path.read_text().strip()
        if len(self.token)<32:
            raise RuntimeError('Invalid auth.token; restore a valid local token')
        self.app_token_path=self.home/'app.token'
        try:
            descriptor=os.open(self.app_token_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(descriptor,'w') as file:
                file.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
        self.app_token=self.app_token_path.read_text().strip()
        if len(self.app_token)<32 or self.app_token==self.token:
            raise RuntimeError('Invalid app.token; restore a valid local application token')
        self.lock=threading.RLock()
        self.changed=threading.Condition(self.lock)
        self.connection=sqlite3.connect(self.home/'trace.sqlite3',check_same_thread=False)
        self.connection.row_factory=sqlite3.Row
        self.connection.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
        INSERT OR IGNORE INTO meta VALUES('revision',0);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS plans(task_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(task_id,version),FOREIGN KEY(task_id) REFERENCES projects(id));
        CREATE TABLE IF NOT EXISTS diagrams(task_id TEXT NOT NULL,id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(task_id,id,version),FOREIGN KEY(task_id) REFERENCES projects(id));
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,diagram_id TEXT NOT NULL,diagram_version INTEGER NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,finished_at TEXT,FOREIGN KEY(task_id,diagram_id,diagram_version) REFERENCES diagrams(task_id,id,version));
        CREATE TABLE IF NOT EXISTS steps(run_id TEXT NOT NULL,seq INTEGER NOT NULL,event_id TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(run_id,seq),UNIQUE(run_id,event_id),FOREIGN KEY(run_id) REFERENCES runs(id));
        ''')
        self.connection.commit()
        (self.home/'trace.sqlite3').chmod(0o600)

    def close(self):
        with self.lock:
            self.connection.close()

    @property
    def revision(self):
        with self.lock:
            return self.connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]

    def _project(self, task_id):
        row=self.connection.execute('SELECT payload FROM projects WHERE id=?',(ident(task_id),)).fetchone()
        if not row:
            raise Problem('Task not found: '+task_id,404)
        return json.loads(row[0])

    def _writable_project(self, task_id):
        project=self._project(task_id)
        if project.get('archived_at'):
            raise Problem('Task is archived and read-only; restore it in the Mac app before making changes',409)
        return project

    def lifecycle(self, task_id, action, raw):
        fields(raw,{'expected_revision','expected_created_at'})
        revision=integer(raw.get('expected_revision'),1)
        created=text(raw.get('expected_created_at'),100,True)
        if action not in {'archive','restore','delete'}:
            raise Problem('Unknown lifecycle action',404)
        def operation():
            p=self._project(task_id)
            if p['revision']!=revision or p['created_at']!=created:
                raise Problem('Task changed since it was displayed; refresh and try again',409)
            if action=='delete':
                self.connection.execute('DELETE FROM steps WHERE run_id IN (SELECT id FROM runs WHERE task_id=?)',(task_id,))
                self.connection.execute('DELETE FROM runs WHERE task_id=?',(task_id,))
                self.connection.execute('DELETE FROM diagrams WHERE task_id=?',(task_id,))
                self.connection.execute('DELETE FROM plans WHERE task_id=?',(task_id,))
                self.connection.execute('DELETE FROM projects WHERE id=?',(task_id,))
                return {'id':task_id,'deleted':True},True
            archived=bool(p.get('archived_at'))
            if archived==(action=='archive'):
                return summary(p),False
            p['archived_at']=now() if action=='archive' else None
            return self._save(p),True
        return self.write(operation)

    def _save(self,p):
        p['updated_at']=now();p['revision']+=1
        self.connection.execute('UPDATE projects SET payload=? WHERE id=?',(encode(p),p['id']))
        return summary(p)

    def write(self, function):
        with self.changed:
            with self.connection:
                result,changed=function()
                if changed:
                    self.connection.execute("UPDATE meta SET value=value+1 WHERE key='revision'")
            if changed:
                self.changed.notify_all()
            return result

    def create_task(self, raw):
        fields(raw,{'id','title','description','owner','category'})
        task={'id':ident(raw.get('id')),'title':text(raw.get('title'),240,True),
            'description':text(raw.get('description','')),'owner':ident(raw.get('owner','agent')),
            'category':text(raw.get('category','Agent 任务'),80)}
        def operation():
            found=self.connection.execute('SELECT payload FROM projects WHERE id=?',(task['id'],)).fetchone()
            if found:
                previous=json.loads(found[0])
                if previous.get('archived_at'):
                    raise Problem('Task is archived and read-only; restore it in the Mac app before making changes',409)
                if all(previous[k]==v for k,v in task.items()):
                    return summary(previous),False
                raise Problem('Task ID already exists with different metadata',409)
            p={**task,'nodes':[],'plan_version':0,'revision':1,'created_at':now(),'updated_at':now(),'last_plan_change':None}
            self.connection.execute('INSERT INTO projects VALUES(?,?)',(p['id'],encode(p)))
            return summary(p),True
        return self.write(operation)

    def put_plan(self,task_id,raw):
        fields(raw,{'tasks','reason','expected_version'})
        if not isinstance(raw.get('tasks'),list) or len(raw['tasks'])>500:
            raise Problem('Plan tasks must be an array of at most 500 nodes')
        reason=text(raw.get('reason','更新任务计划'))
        if 'expected_version' in raw:integer(raw['expected_version'])
        def operation():
            p=self._writable_project(task_id)
            if 'expected_version' in raw and raw['expected_version']!=p['plan_version']:
                raise Problem('Plan version conflict; read the current task before replacing its plan',409)
            previous={n['id']:n for n in p['nodes']}
            nodes=[normalize_node(n,previous.get(ident(n.get('id')))) for n in raw['tasks'] if isinstance(n,dict)]
            if len(nodes)!=len(raw['tasks']):
                raise Problem('Each task node must be an object')
            validate_graph(nodes)
            if nodes==p['nodes']:
                return summary(p),False
            before=summary(p)['summary'];p['nodes']=nodes;p['plan_version']+=1
            after=summary(p)['summary']
            p['last_plan_change']={'reason':reason,'before_progress':before['progress'],'after_progress':after['progress'],
                'before_total':before['total'],'after_total':after['total'],'version':p['plan_version'],'at':now()}
            self.connection.execute('INSERT INTO plans VALUES(?,?,?)',(task_id,p['plan_version'],encode({'nodes':nodes,'change':p['last_plan_change']})))
            return self._save(p),True
        return self.write(operation)

    def report(self,task_id,node_id,raw):
        fields(raw,EXECUTION_FIELDS|{'expected_revision'})
        if 'expected_revision' in raw:integer(raw['expected_revision'],1)
        def operation():
            p=self._writable_project(task_id)
            if 'expected_revision' in raw and raw['expected_revision']!=p['revision']:
                raise Problem('Task revision conflict',409)
            node=next((n for n in p['nodes'] if n['id']==ident(node_id)),None)
            if not node:
                raise Problem('Task node not found',404)
            if any(n['parent_id']==node_id for n in p['nodes']):
                raise Problem('Report progress on leaf tasks; parent progress is calculated',409)
            updated=normalize_node({**{k:v for k,v in raw.items() if k!='expected_revision'},'id':node_id},node)
            if updated==node:
                return summary(p),False
            p['nodes']=[updated if n['id']==node_id else n for n in p['nodes']]
            validate_graph(p['nodes'])
            return self._save(p),True
        return self.write(operation)

    def put_diagram(self,task_id,raw):
        definition=normalize_diagram(raw)
        def operation():
            project=self._writable_project(task_id)
            row=self.connection.execute('SELECT version,payload FROM diagrams WHERE task_id=? AND id=? ORDER BY version DESC LIMIT 1',(task_id,definition['id'])).fetchone()
            if row and json.loads(row['payload'])==definition:
                return {**definition,'version':row['version']},False
            version=row['version']+1 if row else 1
            self.connection.execute('INSERT INTO diagrams VALUES(?,?,?,?,?)',(task_id,definition['id'],version,encode(definition),now()))
            self._save(project)
            return {**definition,'version':version},True
        return self.write(operation)

    def start_run(self,task_id,diagram_id,raw):
        fields(raw,{'id','version'})
        run_id=ident(raw.get('id','run-'+uuid.uuid4().hex[:16]))
        def operation():
            project=self._writable_project(task_id)
            if 'version' in raw:
                integer(raw['version'],1)
                row=self.connection.execute('SELECT version FROM diagrams WHERE task_id=? AND id=? AND version=?',(task_id,ident(diagram_id),raw['version'])).fetchone()
            else:
                row=self.connection.execute('SELECT version FROM diagrams WHERE task_id=? AND id=? ORDER BY version DESC LIMIT 1',(task_id,ident(diagram_id))).fetchone()
            if not row:
                raise Problem('Diagram version not found',404)
            existing=self.connection.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
            if existing:
                if existing['task_id']==task_id and existing['diagram_id']==diagram_id and existing['diagram_version']==row['version']:
                    return dict(existing),False
                raise Problem('Run ID already belongs to a different diagram/version',409)
            stamp=now()
            self.connection.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,NULL)',(run_id,task_id,diagram_id,row['version'],'running',stamp,stamp))
            self._save(project)
            return dict(self.connection.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()),True
        return self.write(operation)

    def _run(self,run_id):
        row=self.connection.execute('SELECT * FROM runs WHERE id=?',(ident(run_id),)).fetchone()
        if not row:
            raise Problem('Run not found',404)
        return dict(row)

    def step(self,run_id,raw):
        fields(raw,{'event_id','title','node_ids','edge_ids','status','duration_ms'})
        event={'event_id':ident(raw.get('event_id','event-'+uuid.uuid4().hex)),
            'title':text(raw.get('title','运行状态更新'),240,True),'node_ids':strings(raw.get('node_ids',[]),True),
            'edge_ids':strings(raw.get('edge_ids',[]),True),'status':raw.get('status','done'),
            'duration_ms':number(raw.get('duration_ms',0))}
        if not isinstance(event['status'],str) or event['status'] not in {'running','done','error'} or not (event['node_ids'] or event['edge_ids']):
            raise Problem('Steps need node_ids or edge_ids and status running/done/error')
        def operation():
            run=self._run(run_id)
            project=self._writable_project(run['task_id'])
            duplicate=self.connection.execute('SELECT * FROM steps WHERE run_id=? AND event_id=?',(run_id,event['event_id'])).fetchone()
            if duplicate:
                if json.loads(duplicate['payload'])==event:
                    return {**event,'seq':duplicate['seq'],'created_at':duplicate['created_at']},False
                raise Problem('event_id was already used for a different payload',409)
            if run['finished_at']:
                raise Problem('Run is finished; create a new run for another attempt',409)
            definition=json.loads(self.connection.execute('SELECT payload FROM diagrams WHERE task_id=? AND id=? AND version=?',(run['task_id'],run['diagram_id'],run['diagram_version'])).fetchone()[0])
            ids={n['id'] for n in definition.get('nodes',definition.get('messages',[]))}
            edges={e['id'] for e in definition.get('edges',[])}
            if set(event['node_ids'])-ids or set(event['edge_ids'])-edges:
                raise Problem('Step references objects outside its pinned diagram version')
            seq=self.connection.execute('SELECT COALESCE(MAX(seq),0)+1 FROM steps WHERE run_id=?',(run_id,)).fetchone()[0]
            stamp=now()
            self.connection.execute('INSERT INTO steps VALUES(?,?,?,?,?)',(run_id,seq,event['event_id'],encode(event),stamp))
            self.connection.execute('UPDATE runs SET status=?,updated_at=? WHERE id=?',('error' if event['status']=='error' else 'running',stamp,run_id))
            self._save(project)
            return {**event,'seq':seq,'created_at':stamp},True
        return self.write(operation)

    def finish_run(self,run_id,raw):
        fields(raw,{'status'})
        status=raw.get('status','done')
        if not isinstance(status,str) or status not in {'done','error'}:
            raise Problem('Finished run status must be done or error')
        def operation():
            run=self._run(run_id)
            project=self._writable_project(run['task_id'])
            if run['finished_at']:
                if run['status']==status:
                    return run,False
                raise Problem('Finished runs are immutable',409)
            latest={}
            for row in self.connection.execute('SELECT payload FROM steps WHERE run_id=? ORDER BY seq',(run_id,)):
                step=json.loads(row[0])
                for kind,refs in [('node',step['node_ids']),('edge',step['edge_ids'])]:
                    for ref in refs:
                        latest[kind+':'+ref]=step['status']
            if status=='done' and any(s!='done' for s in latest.values()):
                raise Problem('Complete or resolve reported running/error objects before finishing successfully',409)
            stamp=now()
            self.connection.execute('UPDATE runs SET status=?,updated_at=?,finished_at=? WHERE id=?',(status,stamp,stamp,run_id))
            self._save(project)
            return self._run(run_id),True
        return self.write(operation)

    def state(self):
        with self.lock:
            projects=[summary(json.loads(row[0])) for row in self.connection.execute('SELECT payload FROM projects ORDER BY rowid DESC')]
            for p in projects:
                p['diagrams']=[]
                for row in self.connection.execute('SELECT d.* FROM diagrams d WHERE task_id=? AND version=(SELECT MAX(version) FROM diagrams WHERE task_id=d.task_id AND id=d.id) ORDER BY rowid',(p['id'],)):
                    p['diagrams'].append({**json.loads(row['payload']),'version':row['version'],'created_at':row['created_at']})
                p['runs']=[]
                for row in self.connection.execute('SELECT * FROM runs WHERE task_id=? ORDER BY rowid DESC',(p['id'],)):
                    run=dict(row)
                    run['definition']=json.loads(self.connection.execute('SELECT payload FROM diagrams WHERE task_id=? AND id=? AND version=?',(p['id'],run['diagram_id'],run['diagram_version'])).fetchone()[0])
                    run['steps']=[{**json.loads(step['payload']),'seq':step['seq'],'created_at':step['created_at']} for step in self.connection.execute('SELECT * FROM steps WHERE run_id=? ORDER BY seq',(run['id'],))]
                    p['runs'].append(run)
            return {'revision':self.revision,'projects':projects,'server_time':now()}
