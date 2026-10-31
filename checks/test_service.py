import concurrent.futures
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from trace_server import Server
from trace_store import Store

ROOT=Path(__file__).resolve().parent.parent
class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name)
        self.server=Server(self.home,0);self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.server.store.close();self.temp.cleanup()
    def api(self,method,path,body=None,headers=None,expected=200):
        h={'Content-Type':'application/json','Authorization':'Bearer '+self.server.store.token,**(headers or {})}
        req=Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=h,method=method)
        try:
            with urlopen(req,timeout=3) as r:self.assertEqual(r.status,expected);return json.load(r)
        except HTTPError as e:
            body=e.read();e.close();self.assertEqual(e.code,expected,body.decode());return json.loads(body or b'{}')
    def create(self):return self.api('POST','/api/tasks',{'id':'test','title':'测试任务'})
    def plan(self,nodes):return self.api('PUT','/api/tasks/test/plan',{'tasks':nodes})
    def state(self):return self.api('GET','/api/state')
    def test_create_idempotence_and_disk_persistence(self):
        self.create();revision=self.state()['revision'];self.create();self.assertEqual(self.state()['revision'],revision)
        other=Store(self.home)
        try:self.assertEqual(other.state()['projects'][0]['title'],'测试任务')
        finally:other.close()
        self.api('POST','/api/tasks',{'id':'test','title':'不同标题'},expected=409)
    def test_nested_plan_weighted_progress_and_dependency(self):
        self.create();self.plan([{'id':'group','title':'阶段'},{'id':'nested','parent_id':'group','title':'更细阶段'},{'id':'a','parent_id':'nested','title':'实现','weight':70},{'id':'b','parent_id':'group','title':'验证','weight':30,'dependencies':['nested']}])
        self.api('PATCH','/api/tasks/test/nodes/b',{'status':'running'},expected=409)
        p=self.api('PATCH','/api/tasks/test/nodes/a',{'status':'running','progress':50})
        self.assertEqual(p['summary']['progress'],35)
        partial=self.api('PATCH','/api/tasks/test/nodes/a',{'status':'done'})
        self.assertEqual(partial['summary']['status'],'running')
        p=self.api('PATCH','/api/tasks/test/nodes/b',{'status':'done'})
        self.assertEqual(p['summary']['progress'],100);self.assertEqual(p['summary']['total'],2)
        self.api('PATCH','/api/tasks/test/nodes/group',{'progress':30},expected=409)
    def test_plan_replacement_preserves_progress_and_atomic_rejection(self):
        self.create();self.plan([{'id':'a','title':'A'}]);self.api('PATCH','/api/tasks/test/nodes/a',{'progress':60,'status':'running'})
        self.plan([{'id':'a','title':'A'},{'id':'b','title':'B','weight':2}]);p=self.state()['projects'][0]
        self.assertEqual(p['summary']['progress'],20);self.assertEqual(p['nodes'][0]['progress'],60)
        rev=self.state()['revision']
        self.api('PUT','/api/tasks/test/plan',{'tasks':[{'id':'a','title':'A','dependencies':['a']}]},expected=400)
        self.assertEqual(self.state()['revision'],rev);self.assertEqual(len(self.state()['projects'][0]['nodes']),2)
        self.api('PUT','/api/tasks/test/plan',{'expected_version':1,'tasks':[]},expected=409)
    def test_unknown_refs_bad_values_and_typo_rejected(self):
        self.create()
        self.api('PUT','/api/tasks/test/plan',{'tasks':[{'id':'a','title':'A','parent_id':'missing'}]},expected=400)
        self.api('PUT','/api/tasks/test/plan',{'tasks':[{'id':'a','title':'A','weight':0}]},expected=400)
        self.plan([{'id':'a','title':'A'}])
        self.api('PATCH','/api/tasks/test/nodes/a',{'progess':20},expected=400)
        self.api('PATCH','/api/tasks/test/nodes/a',{'progress':True},expected=400)
        self.api('PATCH','/api/tasks/test/nodes/a',{'progress':101},expected=400)
        self.api('PATCH','/api/tasks/test/nodes/a',{'status':[]},expected=400)
        self.api('PATCH','/api/tasks/test/nodes/a',{'expected_revision':True},expected=400)
        self.api('PUT','/api/tasks/test/plan',{'expected_version':1.5,'tasks':[]},expected=400)
        self.api('PUT','/api/tasks/test/plan',{'tasks':[{'id':[],'title':'Bad'}]},expected=400)
    def test_blockers_are_visible_and_clear_on_resume(self):
        self.create()
        self.plan([{'id':'group','title':'阶段'},{'id':'a','parent_id':'group','title':'实现'},{'id':'b','parent_id':'group','title':'验证'}])
        self.api('PATCH','/api/tasks/test/nodes/a',{'status':'blocked'},expected=400)
        self.api('PATCH','/api/tasks/test/nodes/a',{'status':'blocked','blocker':'等待接口凭据','current':'正在排查替代方案'})
        state=self.state()['projects'][0]
        self.assertEqual(state['summary']['status'],'blocked')
        self.assertEqual(state['summary']['blocked'],1)
        nodes={n['id']:n for n in state['nodes']}
        self.assertEqual(nodes['group']['status'],'blocked')
        self.assertEqual(nodes['a']['blocker'],'等待接口凭据')
        self.plan([{'id':'group','title':'阶段'},{'id':'a','parent_id':'group','title':'实现'},{'id':'b','parent_id':'group','title':'验证'}])
        self.assertEqual(next(n for n in self.state()['projects'][0]['nodes'] if n['id']=='a')['blocker'],'等待接口凭据')
        self.api('PATCH','/api/tasks/test/nodes/a',{'status':'running','current':'已恢复'})
        state=self.state()['projects'][0]
        self.assertEqual(state['summary']['blocked'],0)
        self.assertEqual(state['summary']['status'],'running')
        self.assertEqual(next(n for n in state['nodes'] if n['id']=='a')['blocker'],'')
        self.api('PATCH','/api/tasks/test/nodes/a',{'blocker':'不应残留'},expected=400)

    def test_concurrent_reports_do_not_overwrite_other_nodes(self):
        self.create();self.plan([{'id':f'n{i}','title':f'节点{i}'} for i in range(16)])
        def update(i):return self.api('PATCH',f'/api/tasks/test/nodes/n{i}',{'progress':i+1,'status':'running'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(update,range(16)))
        nodes={n['id']:n for n in self.state()['projects'][0]['nodes']}
        for i in range(16):self.assertEqual(nodes[f'n{i}']['progress'],i+1)
    def test_diagram_run_version_pinning_idempotent_steps_and_recovery(self):
        self.create();diagram=json.loads((ROOT/'examples/diagram.json').read_text())
        self.api('PUT','/api/tasks/test/diagrams',diagram)
        self.api('POST','/api/tasks/test/diagrams/delivery-flow/runs',{'id':'r1'})
        diagram['nodes'].append({'id':'new','title':'新增节点'})
        self.api('PUT','/api/tasks/test/diagrams',diagram)
        self.api('POST','/api/runs/r1/steps',{'node_ids':['new']},expected=400)
        step={'event_id':'e1','node_ids':['implement'],'status':'error','duration_ms':42,'title':'发现异常'}
        self.api('POST','/api/runs/r1/steps',step);rev=self.state()['revision']
        self.api('POST','/api/runs/r1/steps',step);self.assertEqual(self.state()['revision'],rev)
        self.api('POST','/api/runs/r1/steps',{**step,'title':'不同内容'},expected=409)
        self.api('POST','/api/runs/r1/finish',{'status':'done'},expected=409)
        self.api('POST','/api/runs/r1/steps',{'event_id':'e2','node_ids':['implement'],'status':'done'})
        self.api('POST','/api/runs/r1/finish',{'status':'done'})
        self.api('POST','/api/runs/r1/steps',{'node_ids':['implement']},expected=409)
        self.api('POST','/api/runs/r1/steps',step)
        p=self.state()['projects'][0];self.assertEqual(p['diagrams'][0]['version'],2);self.assertEqual(p['runs'][0]['diagram_version'],1);self.assertEqual(len(p['runs'][0]['steps']),2)
    def test_sequence_references_and_invalid_diagram(self):
        self.create();d=json.loads((ROOT/'examples/sequence.json').read_text());self.api('PUT','/api/tasks/test/diagrams',d)
        self.api('POST','/api/tasks/test/diagrams/report-sequence/runs',{'id':'seq'})
        self.api('POST','/api/runs/seq/steps',{'node_ids':['invoke'],'status':'done'})
        self.api('POST','/api/runs/seq/steps',{'node_ids':['agent'],'status':'done'},expected=400)
        d['messages'][0]['to']='missing';self.api('PUT','/api/tasks/test/diagrams',d,expected=400)
    def test_sse_notification_and_reconnect_snapshot(self):
        response=urlopen(self.url+'/api/events',timeout=3)
        def event():
            lines=[]
            while True:
                line=response.readline().decode().strip()
                if not line:break
                lines.append(line)
            return '\n'.join(lines)
        try:
            self.assertIn('"revision":0',event());self.create();self.assertIn('"revision":1',event())
        finally:response.close()
        self.assertEqual(self.state()['projects'][0]['id'],'test')
        with urlopen(self.url+'/api/events',timeout=3) as other:self.assertEqual(other.readline().decode().strip(),'id: 1')
    def test_token_origin_host_and_static_allowlist(self):
        self.api('POST','/api/tasks',{'id':'x','title':'X'},headers={'Authorization':''},expected=401)
        self.api('POST','/api/tasks',{'id':'x','title':'X'},headers={'Origin':'https://example.com'},expected=403)
        self.api('GET','/api/state',headers={'Host':'example.com'},expected=403)
        self.api('GET','/trace_store.py',expected=404)
        self.api('GET','/auth.token',expected=404)
        with urlopen(self.url+'/') as r:self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
        for asset in ['floating.html','floating.js','floating.css','floating-prefs.js','settings.html','settings.js','settings.css']:
            with urlopen(self.url+'/'+asset) as r:self.assertEqual(r.status,200)
    def test_cli_stdin_files_and_nonzero_errors(self):
        base=[sys.executable,str(ROOT/'agent_trace.py'),'--data-dir',str(self.home),'--url',self.url]
        def cli(*args,stdin=None):return subprocess.run(base+list(args),input=stdin,text=True,capture_output=True,timeout=5)
        p=cli('task','create','--id','cli','--title','CLI任务');self.assertEqual(p.returncode,0,p.stderr)
        p=cli('plan','put','--task','cli','--file','-',stdin='{"tasks":[{"id":"a","title":"实现"}]}');self.assertEqual(p.returncode,0,p.stderr)
        p=cli('task','report','--task','cli','--node','a','--status','done');self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['summary']['progress'],100)
        p=cli('task','report','--task','cli','--node','missing','--progress','2');self.assertEqual(p.returncode,1);self.assertIn('error',json.loads(p.stderr))
        p=subprocess.run([sys.executable,str(ROOT/'agent_trace.py'),'--url','https://example.com','task','list'],capture_output=True,text=True);self.assertEqual(p.returncode,1)

    def lifecycle(self, action, project=None, expected=200, token=None):
        project=project or self.state()['projects'][0]
        headers={'Authorization':'Bearer '+(token or self.server.store.app_token)}
        return self.api('POST',f"/api/app/tasks/{project['id']}/{action}",
                        {'expected_revision':project['revision'],'expected_created_at':project['created_at']},headers=headers,expected=expected)

    def test_archive_is_app_only_cli_readable_and_every_write_is_blocked(self):
        self.create();self.plan([{'id':'a','title':'实现'}])
        self.api('PATCH','/api/tasks/test/nodes/a',{'status':'running','progress':30})
        diagram=json.loads((ROOT/'examples/diagram.json').read_text())
        self.api('PUT','/api/tasks/test/diagrams',diagram)
        self.api('POST','/api/tasks/test/diagrams/delivery-flow/runs',{'id':'r1'})
        step={'event_id':'s1','node_ids':['implement'],'status':'done'}
        self.api('POST','/api/runs/r1/steps',step)
        before=self.state()['projects'][0]
        self.lifecycle('archive',before,token=self.server.store.token,expected=401)
        self.api('GET','/app.token',expected=404)
        self.assertEqual(self.server.store.app_token_path.stat().st_mode & 0o777,0o600)
        self.lifecycle('archive',before)
        archived=self.state()['projects'][0]
        self.assertTrue(archived['archived_at'])
        self.assertEqual(archived['summary']['progress'],30)
        self.assertEqual(len(archived['runs'][0]['steps']),1)
        base=[sys.executable,str(ROOT/'agent_trace.py'),'--data-dir',str(self.home),'--url',self.url]
        listing=subprocess.run(base+['task','list'],capture_output=True,text=True,timeout=5)
        self.assertEqual(listing.returncode,0,listing.stderr)
        self.assertTrue(json.loads(listing.stdout)[0]['archived_at'])
        shown=subprocess.run(base+['task','show','--task','test'],capture_output=True,text=True,timeout=5)
        self.assertTrue(json.loads(shown.stdout)['archived_at'])
        failed=subprocess.run(base+['task','report','--task','test','--node','a','--progress','50'],capture_output=True,text=True,timeout=5)
        self.assertEqual(failed.returncode,1);self.assertIn('archived',failed.stderr)
        rev=self.state()['revision']
        self.api('POST','/api/tasks',{'id':'test','title':'测试任务'},expected=409)
        self.api('PUT','/api/tasks/test/plan',{'tasks':[{'id':'a','title':'改动'}]},expected=409)
        self.api('PUT','/api/tasks/test/diagrams',diagram,expected=409)
        self.api('POST','/api/tasks/test/diagrams/delivery-flow/runs',{'id':'r2'},expected=409)
        self.api('POST','/api/runs/r1/steps',step,expected=409)
        self.api('POST','/api/runs/r1/finish',{'status':'done'},expected=409)
        self.assertEqual(self.state()['revision'],rev)
        self.lifecycle('restore',archived)
        restored=self.state()['projects'][0]
        self.assertIsNone(restored['archived_at'])
        self.assertEqual(restored['summary']['progress'],30)
        self.assertEqual(restored['runs'][0]['steps'][0]['event_id'],'s1')
        updated=self.api('PATCH','/api/tasks/test/nodes/a',{'progress':60,'status':'running'})
        self.assertEqual(updated['summary']['progress'],60)

    def test_delete_is_transactional_cascades_and_rejects_stale_confirmation(self):
        self.create();self.plan([{'id':'a','title':'A'}])
        diagram=json.loads((ROOT/'examples/diagram.json').read_text())
        self.api('PUT','/api/tasks/test/diagrams',diagram)
        self.api('POST','/api/tasks/test/diagrams/delivery-flow/runs',{'id':'r1'})
        self.api('POST','/api/runs/r1/steps',{'event_id':'s1','node_ids':['implement']})
        stale=self.state()['projects'][0]
        self.api('POST','/api/runs/r1/steps',{'event_id':'s2','node_ids':['verify']})
        self.lifecycle('delete',stale,expected=409)
        self.assertEqual(len(self.state()['projects']),1)
        self.lifecycle('delete',token=self.server.store.token,expected=401)
        self.api('POST','/api/tasks',{'id':'other','title':'保留任务'})
        doomed=next(p for p in self.state()['projects'] if p['id']=='test')
        result=self.lifecycle('delete',doomed)
        self.assertTrue(result['deleted'])
        self.assertEqual([p['id'] for p in self.state()['projects']],['other'])
        for table in ['plans','diagrams','runs','steps']:
            self.assertEqual(self.server.store.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
        self.api('PATCH','/api/tasks/test/nodes/a',{'progress':10},expected=404)

class LifecycleTest(unittest.TestCase):
    def test_daemon_restart_keeps_committed_state(self):
        with tempfile.TemporaryDirectory() as home:
            base=[sys.executable,str(ROOT/'agent_trace.py'),'--data-dir',home]
            def cli(*args):
                p=subprocess.run(base+list(args),capture_output=True,text=True,timeout=10)
                self.assertEqual(p.returncode,0,p.stderr)
                return json.loads(p.stdout)
            try:
                first=cli('start','--port','0');self.assertEqual(first['status'],'running')
                self.assertEqual(cli('start','--port','0')['status'],'already_running')
                cli('task','create','--id','persisted','--title','Survives restart')
                cli('stop');second=cli('start','--port','0')
                self.assertNotEqual(first['instance'],second['instance'])
                self.assertEqual(cli('task','list')[0]['id'],'persisted')
            finally:
                subprocess.run(base+['stop'],capture_output=True,timeout=10)

if __name__=='__main__':unittest.main()
