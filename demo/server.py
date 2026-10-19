"""Loopback-only demo server; no dependencies and no connection to PostgreSQL."""
import argparse, json, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .engine import Engine

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--data',default='data/receipt-demo')
    args=parser.parse_args()
    engine=Engine(args.data)
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def send(self,code,value,kind='application/json'):
            raw=value.encode() if isinstance(value,str) else json.dumps(value).encode()
            self.send_response(code); self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/':
                html=Path(__file__).with_name('index.html').read_text(encoding='utf-8').replace('__TOKEN__',token)
                return self.send(200,html,'text/html; charset=utf-8')
            if self.path=='/state': return self.send(200,engine.snapshot())
            return self.send(404,{'error':'Unknown route'})
        def do_POST(self):
            if self.headers.get('X-Demo-Token')!=token: return self.send(403,{'error':'Invalid demo token'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size>4096: raise ValueError('Request too large')
                body=json.loads(self.rfile.read(size))
                if self.path=='/write': result={'receipt':engine.write(body['id'],body.get('amount'),body.get('delete',False))}
                elif self.path=='/anchor': result=engine.anchor()
                elif self.path=='/attack': result=engine.attack(body['id'],body['kind'])
                elif self.path=='/verify': result=engine.verify(body['id'])
                else: return self.send(404,{'error':'Unknown route'})
                self.send(200,result)
            except (ValueError,KeyError,TypeError) as exc: self.send(400,{'error':str(exc)})
            except Exception as exc: self.send(500,{'error':type(exc).__name__+': '+str(exc)})
    print('Receipt reconciliation lab: http://127.0.0.1:'+str(args.port),flush=True)
    print('Disposable SQLite mode. Two files simulate trust domains; no production isolation.',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__': main()
