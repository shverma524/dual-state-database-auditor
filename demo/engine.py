"""Receipt reconciliation lab. Separate files simulate two trust domains.
No production isolation is claimed. Database-only attacks are in scope."""
import hashlib, json, sqlite3, threading, time
from pathlib import Path
from decimal import Decimal, InvalidOperation
from app.merkle import build_tree, verify_proof

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

class Engine:
    def __init__(self,directory):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(self.directory/'business.sqlite',check_same_thread=False)
        self.w=sqlite3.connect(self.directory/'witness.sqlite',check_same_thread=False)
        self.db.executescript('CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,event TEXT NOT NULL);')
        self.w.executescript('CREATE TABLE IF NOT EXISTS receipts(seq INTEGER PRIMARY KEY AUTOINCREMENT,event TEXT NOT NULL,created REAL NOT NULL); CREATE TABLE IF NOT EXISTS epochs(id INTEGER PRIMARY KEY,document TEXT NOT NULL);')
    def close(self):
        self.db.close(); self.w.close()
    def current(self,rid):
        r=self.db.execute('SELECT value FROM records WHERE id=?',(rid,)).fetchone()
        return json.loads(r[0]) if r else None
    def receipts(self):
        return [dict(seq=s,event=json.loads(e),created=t) for s,e,t in self.w.execute('SELECT seq,event,created FROM receipts ORDER BY seq')]
    def epochs(self):
        return [json.loads(r[0]) for r in self.w.execute('SELECT document FROM epochs ORDER BY id')]
    def write(self,rid,amount=None,delete=False):
        rid=int(rid)
        if rid<1: raise ValueError('Record ID must be positive')
        if not delete:
            try:
                n=Decimal(str(amount))
                if not n.is_finite() or n!=n.quantize(Decimal('.01')): raise ValueError('Use a finite amount with at most two decimals')
                amount=format(n.quantize(Decimal('.01')),'f')
            except InvalidOperation as exc: raise ValueError('Invalid amount') from exc
        with self.lock:
            history=[r for r in self.receipts() if r['event']['id']==rid]
            old=self.current(rid)
            if history and self.verify(rid)['status'] not in ('VERIFIED','DELETED_VERIFIED','PENDING_ANCHOR'):
                raise ValueError('Reconcile inconsistent evidence before another write')
            expected=history[-1]['event']['after'] if history else None
            if old!=expected: raise ValueError('Live row disagrees with witness')
            if delete and old is None: raise ValueError('Cannot delete a missing row')
            after=None if delete else dict(id=rid,amount=amount,revision=len(history)+1)
            event=dict(id=rid,revision=len(history)+1,before=old,after=after,previous=digest(history[-1]['event']) if history else None)
            # Witness-first commit: a later crash remains visible as missing evidence.
            with self.w:
                seq=self.w.execute('INSERT INTO receipts(event,created) VALUES (?,?)',(canonical(event),time.time())).lastrowid
            with self.db:
                if delete: self.db.execute('DELETE FROM records WHERE id=?',(rid,))
                else: self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?)',(rid,canonical(after)))
                self.db.execute('INSERT INTO audit VALUES (?,?)',(seq,canonical(event)))
            return seq
    def verify(self,rid):
        with self.lock:
            rid=int(rid); current=self.current(rid)
            history=[r for r in self.receipts() if r['event']['id']==rid]
            def result(status,detail,**extra): return dict(status=status,detail=detail,**extra)
            if not history: return result('UNWITNESSED_ROW' if current else 'UNKNOWN','No witness receipt exists for this record')
            previous=None
            for index,r in enumerate(history):
                e=r['event']
                if e['previous']!=(digest(previous) if previous else None) or e['before']!=(previous['after'] if previous else None) or e['revision']!=index+1:
                    return result('WITNESS_CHAIN_INVALID','Witness sequence is internally inconsistent')
                audit=self.db.execute('SELECT event FROM audit WHERE seq=?',(r['seq'],)).fetchone()
                if not audit: return result('EVIDENCE_MISSING','Witness receipt has no corresponding database audit entry')
                if audit[0]!=canonical(e): return result('AUDIT_TAMPERED','Audit event differs from its witness receipt')
                previous=e
            latest=history[-1]
            if current!=latest['event']['after']: return result('TAMPER_DETECTED','Live row differs from the latest witnessed state')
            for epoch in self.epochs():
                for item in epoch['items']:
                    if item['seq']==latest['seq']:
                        leaf=digest(dict(seq=latest['seq'],event=latest['event']))
                        if not verify_proof(leaf,item['proof'],epoch['root']): return result('PROOF_INVALID','Merkle path does not reconstruct the checkpoint')
                        return result('DELETED_VERIFIED' if current is None else 'VERIFIED','Live row, receipt, audit event and checkpoint agree',epoch=epoch['id'],root=epoch['root'],proof=item['proof'],leaf=leaf)
            return result('PENDING_ANCHOR','Witnessed state agrees but has no checkpoint yet',pending_seconds=round(time.time()-latest['created'],3))
    def anchor(self):
        with self.lock:
            receipts=self.receipts(); epochs=self.epochs()
            covered={i['seq'] for e in epochs for i in e['items']}
            pending=[r for r in receipts if r['seq'] not in covered]
            known={r['event']['id'] for r in receipts}
            live={r[0] for r in self.db.execute('SELECT id FROM records')}
            for rid in known|live:
                v=self.verify(rid)
                if v['status'] not in ('PENDING_ANCHOR','VERIFIED','DELETED_VERIFIED'):
                    return dict(status='ANCHOR_BLOCKED',record_id=rid,reason=v)
            expected={r['seq'] for r in receipts}
            if {r[0] for r in self.db.execute('SELECT seq FROM audit')}!=expected:
                return dict(status='ANCHOR_BLOCKED',reason=dict(status='AUDIT_SET_MISMATCH'))
            if not pending: return dict(status='NO_PENDING_EVENTS')
            leaves=[digest(dict(seq=r['seq'],event=r['event'])) for r in pending]
            root,proofs=build_tree(leaves)
            doc=dict(id=len(epochs)+1,root=root,created=time.time(),items=[dict(seq=r['seq'],proof=proofs[i]) for i,r in enumerate(pending)])
            with self.w: self.w.execute('INSERT INTO epochs VALUES (?,?)',(doc['id'],canonical(doc)))
            return dict(status='ANCHORED',**doc)
    def attack(self,rid,kind):
        with self.lock,self.db:
            rid=int(rid); row=self.current(rid)
            if not row: raise ValueError('Select an existing demo row')
            if kind=='delete': self.db.execute('DELETE FROM records WHERE id=?',(rid,))
            elif kind=='erase-audit': self.db.execute('DELETE FROM audit')
            elif kind in ('edit','rewrite-both'):
                row['amount']='999999.00'
                self.db.execute('UPDATE records SET value=? WHERE id=?',(canonical(row),rid))
                if kind=='rewrite-both':
                    for seq,raw in list(self.db.execute('SELECT seq,event FROM audit')):
                        e=json.loads(raw)
                        if e['id']==rid and e['after']:
                            e['after']['amount']='999999.00'
                            self.db.execute('UPDATE audit SET event=? WHERE seq=?',(canonical(e),seq))
            else: raise ValueError('Unknown fault')
            return self.verify(rid)
    def snapshot(self):
        with self.lock:
            ids=sorted({r['event']['id'] for r in self.receipts()}|{r[0] for r in self.db.execute('SELECT id FROM records')})
            return dict(records=[dict(id=i,row=self.current(i),verdict=self.verify(i)) for i in ids],receipts=self.receipts(),epochs=self.epochs())
