#!/usr/bin/env python3
"""Agent-facing CLI. All successful output is JSON; errors go to stderr."""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
DEFAULT_HOME=Path.home()/'.local/share/agent-trace'

class ClientError(Exception):
    pass

def emit(value,stream=sys.stdout):
    print(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),file=stream)

def read_json(path):
    try:
        raw=sys.stdin.read() if path=='-' else Path(path).expanduser().read_text()
        return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
    except (OSError,ValueError) as exc:
        raise ClientError('Cannot read JSON input: '+str(exc))

def control(home):
    try:
        value=json.loads((home/'service.json').read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}

def endpoint(args):
    value=args.url or control(args.data_dir).get('url') or 'http://127.0.0.1:8770'
    parsed=urlsplit(value)
    if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost'} or parsed.username or parsed.password or parsed.path not in {'','/'} or parsed.query or parsed.fragment:
        raise ClientError('--url must be a loopback HTTP origin')
    return value.rstrip('/')

def request(args,method,path,body=None):
    headers={}
    if method!='GET':
        try:
            token=(args.data_dir/'auth.token').read_text().strip()
        except OSError:
            raise ClientError('Local token not found. Run agent-trace start first, or select the matching --data-dir.')
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    raw=None if body is None else json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
    req=Request(endpoint(args)+path,data=raw,headers=headers,method=method)
    try:
        with urlopen(req,timeout=8) as response:
            return json.load(response)
    except HTTPError as exc:
        try:message=json.loads(exc.read()).get('error',str(exc))
        except ValueError:message=str(exc)
        finally:exc.close()
        raise ClientError(f'HTTP {exc.code}: {message}')
    except (URLError,TimeoutError,OSError,ValueError) as exc:
        raise ClientError('Local service unavailable: '+str(exc))

def health(url):
    try:
        with urlopen(url+'/api/health',timeout=.4) as response:
            value=json.load(response)
        return value if value.get('service')=='agent-trace' else None
    except (URLError,TimeoutError,OSError,ValueError):
        return None

def serve(args):
    from trace_server import Server
    args.data_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=(args.data_dir/'service.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise ClientError('A service already owns this data directory')
    try:
        server=Server(args.data_dir,args.port)
    except OSError as exc:
        raise ClientError(f'Cannot bind 127.0.0.1:{args.port}: {exc}')
    info={'pid':os.getpid(),'url':f'http://127.0.0.1:{server.server_port}','instance':server.instance,'data_dir':str(args.data_dir),'database':str(args.data_dir/'trace.sqlite3')}
    temp=args.data_dir/'service.json.tmp';temp.write_text(json.dumps(info));temp.chmod(0o600);temp.replace(args.data_dir/'service.json')
    def terminate(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,terminate)
    emit({'status':'running',**info});sys.stdout.flush()
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close();server.store.close()
        if control(args.data_dir).get('instance')==server.instance:
            (args.data_dir/'service.json').unlink(missing_ok=True)
        lock.close()

def start(args):
    current=control(args.data_dir)
    existing=health(current.get('url','http://127.0.0.1:'+str(args.port)))
    if existing and existing.get('instance')==current.get('instance'):
        return {'status':'already_running',**current}
    args.data_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    log=(args.data_dir/'service.log').open('ab')
    process=subprocess.Popen([sys.executable,str(ROOT/'agent_trace.py'),'--data-dir',str(args.data_dir),'serve','--port',str(args.port)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    log.close()
    for _ in range(50):
        if process.poll() is not None:
            raise ClientError('Service failed to start; see '+str(args.data_dir/'service.log'))
        current=control(args.data_dir)
        if current.get('pid')==process.pid:
            info=health(current['url'])
            if info and info.get('instance')==current['instance']:
                return {'status':'running',**current}
        time.sleep(.1)
    process.terminate()
    process.wait(timeout=3)
    raise ClientError('Service startup timed out; inspect '+str(args.data_dir/'service.log'))

def status(args):
    info=health(endpoint(args))
    return {'status':'running' if info else 'stopped','url':endpoint(args),'data_dir':str(args.data_dir),**(info or {})}

def stop(args):
    current=control(args.data_dir)
    if not current:
        return {'status':'stopped'}
    info=health(current.get('url',''))
    if not info or info.get('instance')!=current.get('instance'):
        raise ClientError('Service identity could not be verified; no process was stopped')
    os.kill(current['pid'],signal.SIGTERM)
    for _ in range(50):
        if not health(current['url']):
            return {'status':'stopped','url':current['url']}
        time.sleep(.1)
    raise ClientError('Service did not stop in time')

def payload(args,names):
    value=read_json(args.file) if getattr(args,'file',None) else {}
    if not isinstance(value,dict):raise ClientError('Expected a JSON object')
    value=dict(value)
    for name in names:
        item=getattr(args,name,None)
        if item is not None:value[name]=item
    return value

def main():
    parser=argparse.ArgumentParser(prog='agent-trace',description='本机 Agent 任务、进度与图示汇报')
    parser.add_argument('--data-dir',type=Path,default=DEFAULT_HOME)
    parser.add_argument('--url',help='Loopback service origin; otherwise use local service metadata')
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ['start','serve']:
        p=commands.add_parser(name);p.add_argument('--port',type=int,default=8770)
    commands.add_parser('status');commands.add_parser('stop')
    p=commands.add_parser('task');task=p.add_subparsers(dest='action',required=True)
    p=task.add_parser('create');p.add_argument('--file');
    for name in ['id','title','description','owner','category']:p.add_argument('--'+name)
    task.add_parser('list')
    p=task.add_parser('show');p.add_argument('--task',required=True)
    p=task.add_parser('report');p.add_argument('--task',required=True);p.add_argument('--node',required=True);p.add_argument('--file')
    for name in ['status','current','objective','agent','agent_role','artifact','duration','blocker']:p.add_argument('--'+name.replace('_','-'))
    p.add_argument('--progress',type=float);p.add_argument('--expected-revision',type=int)
    p.add_argument('--done',action='append');p.add_argument('--todo',action='append')
    p=commands.add_parser('plan');sub=p.add_subparsers(dest='action',required=True);p=sub.add_parser('put');p.add_argument('--task',required=True);p.add_argument('--file',required=True);p.add_argument('--reason');p.add_argument('--expected-version',type=int)
    p=commands.add_parser('diagram');sub=p.add_subparsers(dest='action',required=True);p=sub.add_parser('put');p.add_argument('--task',required=True);p.add_argument('--file',required=True)
    p=commands.add_parser('run');sub=p.add_subparsers(dest='action',required=True)
    p=sub.add_parser('start');p.add_argument('--task',required=True);p.add_argument('--diagram',required=True);p.add_argument('--id');p.add_argument('--version',type=int)
    p=sub.add_parser('step');p.add_argument('--run',required=True);p.add_argument('--file');p.add_argument('--event-id');p.add_argument('--node',action='append');p.add_argument('--edge',action='append');p.add_argument('--title');p.add_argument('--status',choices=['running','done','error']);p.add_argument('--duration-ms',type=float)
    p=sub.add_parser('finish');p.add_argument('--run',required=True);p.add_argument('--status',choices=['done','error'],default='done')
    args=parser.parse_args();args.data_dir=args.data_dir.expanduser().resolve()
    q=lambda value:quote(value,safe='')
    try:
        if args.command=='serve':serve(args);return
        if args.command=='start':result=start(args)
        elif args.command=='status':result=status(args)
        elif args.command=='stop':result=stop(args)
        elif args.command=='task' and args.action=='create':result=request(args,'POST','/api/tasks',payload(args,['id','title','description','owner','category']))
        elif args.command=='task' and args.action=='list':
            result=[{k:p[k] for k in ['id','title','summary','plan_version','revision','updated_at','archived_at']} for p in request(args,'GET','/api/state')['projects']]
        elif args.command=='task' and args.action=='show':
            result=next((p for p in request(args,'GET','/api/state')['projects'] if p['id']==args.task),None)
            if result is None:raise ClientError('Task not found: '+args.task)
        elif args.command=='task' and args.action=='report':result=request(args,'PATCH',f'/api/tasks/{q(args.task)}/nodes/{q(args.node)}',payload(args,['status','current','objective','agent','agent_role','artifact','duration','blocker','progress','done','todo','expected_revision']))
        elif args.command=='plan':
            value=read_json(args.file);value={'tasks':value} if isinstance(value,list) else value
            if not isinstance(value,dict):raise ClientError('Plan must be a JSON object or task array')
            if args.reason is not None:value['reason']=args.reason
            if args.expected_version is not None:value['expected_version']=args.expected_version
            result=request(args,'PUT',f'/api/tasks/{q(args.task)}/plan',value)
        elif args.command=='diagram':result=request(args,'PUT',f'/api/tasks/{q(args.task)}/diagrams',read_json(args.file))
        elif args.command=='run' and args.action=='start':result=request(args,'POST',f'/api/tasks/{q(args.task)}/diagrams/{q(args.diagram)}/runs',{k:getattr(args,k) for k in ['id','version'] if getattr(args,k) is not None})
        elif args.command=='run' and args.action=='step':
            value=payload(args,['event_id','title','status','duration_ms'])
            if args.node is not None:value['node_ids']=args.node
            if args.edge is not None:value['edge_ids']=args.edge
            result=request(args,'POST',f'/api/runs/{q(args.run)}/steps',value)
        else:result=request(args,'POST',f'/api/runs/{q(args.run)}/finish',{'status':args.status})
        emit(result)
    except (ClientError,OSError,ValueError) as exc:
        emit({'error':str(exc)},sys.stderr);raise SystemExit(1)

if __name__=='__main__':main()
