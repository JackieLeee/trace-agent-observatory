"""Loopback HTTP API, static UI and revision notifications."""
import hmac
import json
import mimetypes
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from trace_store import Store, Problem

ROOT=Path(__file__).resolve().parent
ASSETS={'index.html','app.js','data.js','live.js','app.css','theme.js','theme.css','floating.html','floating.js','floating.css','floating-prefs.js','settings.html','settings.js','settings.css'}

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,home,port=8770):
        self.store=Store(home)
        self.instance=uuid.uuid4().hex
        try:
            super().__init__(('127.0.0.1',port),Handler)
        except Exception:
            self.store.close();raise
        self.stopping=threading.Event()
    def server_close(self):
        self.stopping.set()
        with self.store.changed:
            self.store.changed.notify_all()
        super().server_close()

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup()
        self.connection.settimeout(15)
    def log_message(self,format,*args):
        pass
    def headers_common(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
    def send_json(self,value,status=200):
        body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.headers_common()
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def guard(self,write=False,app_only=False):
        port=self.server.server_port
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:
            raise Problem('Invalid Host header',403)
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+host for host in allowed}:
            raise Problem('Cross-origin access is not allowed',403)
        token=self.server.store.app_token if app_only else self.server.store.token
        if write and not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
            raise Problem('Mac app authorization required' if app_only else 'Local CLI token required',401)
    def body(self):
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            raise Problem('Content-Type must be application/json',415)
        try:
            length=int(self.headers.get('Content-Length','-1'))
        except ValueError:
            raise Problem('Invalid Content-Length')
        if length<0 or length>2*1024*1024:
            raise Problem('JSON body must be no larger than 2 MiB',413)
        try:
            raw=self.rfile.read(length)
            if len(raw)!=length:
                raise Problem('Incomplete request body')
            result=json.loads(raw.decode('utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
            if not isinstance(result,dict):
                raise Problem('Expected JSON object')
            return result
        except (UnicodeDecodeError,ValueError):
            raise Problem('Invalid JSON body')
    def handle_request(self,write=False):
        try:
            parts=[unquote(p) for p in urlsplit(self.path).path.strip('/').split('/') if p]
            app_only=len(parts)>=2 and parts[:2]==['api','app']
            self.guard(write,app_only)
            if write:
                body=self.body();store=self.server.store
                if self.command=='POST' and len(parts)==5 and parts[:3]==['api','app','tasks']:
                    result=store.lifecycle(parts[3],parts[4],body)
                elif self.command=='POST' and parts==['api','tasks']:
                    result=store.create_task(body)
                elif self.command=='PUT' and len(parts)==4 and parts[:2]==['api','tasks'] and parts[3]=='plan':
                    result=store.put_plan(parts[2],body)
                elif self.command=='PATCH' and len(parts)==5 and parts[:2]==['api','tasks'] and parts[3]=='nodes':
                    result=store.report(parts[2],parts[4],body)
                elif self.command=='PUT' and len(parts)==4 and parts[:2]==['api','tasks'] and parts[3]=='diagrams':
                    result=store.put_diagram(parts[2],body)
                elif self.command=='POST' and len(parts)==6 and parts[:2]==['api','tasks'] and parts[3]=='diagrams' and parts[5]=='runs':
                    result=store.start_run(parts[2],parts[4],body)
                elif self.command=='POST' and len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='steps':
                    result=store.step(parts[2],body)
                elif self.command=='POST' and len(parts)==4 and parts[:2]==['api','runs'] and parts[3]=='finish':
                    result=store.finish_run(parts[2],body)
                else:
                    raise Problem('API endpoint not found',404)
                self.send_json(result);return
            if parts==['api','health']:
                self.send_json({'service':'agent-trace','api_version':1,'instance':self.server.instance,'revision':self.server.store.revision});return
            if parts==['api','state']:
                self.send_json(self.server.store.state());return
            if parts==['api','events']:
                self.events();return
            name=parts[0] if len(parts)==1 else 'index.html' if not parts else ''
            if name not in ASSETS:
                raise Problem('Not found',404)
            body=(ROOT/name).read_bytes()
            self.send_response(200);self.headers_common()
            self.send_header('Content-Type',mimetypes.guess_type(name)[0] or 'application/octet-stream')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except Problem as exc:
            self.close_connection=True
            self.send_json({'error':str(exc)},exc.status)
        except (BrokenPipeError,ConnectionResetError):
            self.close_connection=True
        except Exception:
            self.close_connection=True
            self.send_json({'error':'Internal service error'},500)
            import traceback
            traceback.print_exc()
    def events(self):
        self.send_response(200);self.headers_common()
        self.send_header('Content-Type','text/event-stream; charset=utf-8')
        self.send_header('Connection','keep-alive');self.end_headers()
        version=-1
        self.connection.settimeout(20)
        try:
            while not self.server.stopping.is_set():
                with self.server.store.changed:
                    if version==self.server.store.revision:
                        self.server.store.changed.wait(timeout=10)
                    if self.server.stopping.is_set():
                        break
                    current=self.server.store.revision
                if self.server.stopping.is_set():
                    break
                if current!=version:
                    self.wfile.write(f'id: {current}\ndata: {{"revision":{current}}}\n\n'.encode());version=current
                else:
                    self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except (OSError,TimeoutError):
            pass
        self.close_connection=True
    def do_GET(self):self.handle_request()
    def do_POST(self):self.handle_request(True)
    def do_PUT(self):self.handle_request(True)
    def do_PATCH(self):self.handle_request(True)
