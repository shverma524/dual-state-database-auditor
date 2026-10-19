import json, sqlite3, tempfile, unittest
from demo.engine import Engine, canonical
class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.e=Engine(self.temp.name)
    def tearDown(self):
        self.e.close(); self.temp.cleanup()
    def status(self): return self.e.verify(1)['status']
    def test_pending_then_verified(self):
        self.e.write(1,'250'); self.assertEqual(self.status(),'PENDING_ANCHOR')
        self.e.anchor(); self.assertEqual(self.status(),'VERIFIED')
    def test_legitimate_update_is_pending(self):
        self.e.write(1,'250'); self.e.anchor(); self.e.write(1,'300')
        self.assertEqual(self.status(),'PENDING_ANCHOR'); self.e.anchor(); self.assertEqual(self.status(),'VERIFIED')
    def test_unlogged_edit(self):
        self.e.write(1,'250'); self.e.anchor(); self.e.attack(1,'edit'); self.assertEqual(self.status(),'TAMPER_DETECTED')
    def test_row_and_audit_rewrite(self):
        self.e.write(1,'250'); self.e.anchor(); self.e.attack(1,'rewrite-both'); self.assertEqual(self.status(),'AUDIT_TAMPERED')
        self.assertEqual(self.e.anchor()['status'],'ANCHOR_BLOCKED')
    def test_unlogged_delete(self):
        self.e.write(1,'250'); self.e.attack(1,'delete'); self.assertEqual(self.status(),'TAMPER_DETECTED')
    def test_legitimate_delete(self):
        self.e.write(1,'250'); self.e.anchor(); self.e.write(1,delete=True)
        self.assertEqual(self.status(),'PENDING_ANCHOR'); self.e.anchor(); self.assertEqual(self.status(),'DELETED_VERIFIED')
    def test_missing_audit(self):
        self.e.write(1,'250'); self.e.attack(1,'erase-audit'); self.assertEqual(self.status(),'EVIDENCE_MISSING')
    def test_no_laundering(self):
        self.e.write(1,'250'); self.e.attack(1,'edit')
        self.assertEqual(self.e.anchor()['status'],'ANCHOR_BLOCKED')
        with self.assertRaises(ValueError): self.e.write(1,'500')
    def test_proof_damage(self):
        self.e.write(1,'250'); self.e.write(2,'100'); self.e.anchor()
        epoch=self.e.epochs()[0]; epoch['items'][0]['proof'][0]['sibling']='0'*64
        with self.e.w: self.e.w.execute('UPDATE epochs SET document=?',(canonical(epoch),))
        self.assertEqual(self.status(),'PROOF_INVALID')
    def test_database_rollback(self):
        self.e.write(1,'250'); self.e.anchor(); old=self.e.current(1)
        self.e.write(1,'300'); self.e.anchor()
        with self.e.db: self.e.db.execute('UPDATE records SET value=? WHERE id=1',(canonical(old),))
        self.assertEqual(self.status(),'TAMPER_DETECTED')
    def test_restart(self):
        self.e.write(1,'250'); self.e.anchor(); self.e.close(); self.e=Engine(self.temp.name)
        self.assertEqual(self.status(),'VERIFIED')
    def test_orphan_receipt(self):
        self.e.write(1,'250')
        with self.e.db: self.e.db.execute('DELETE FROM audit'); self.e.db.execute('DELETE FROM records')
        self.assertEqual(self.status(),'EVIDENCE_MISSING')
    def test_precision_and_nan(self):
        for value in ('NaN','Infinity','1.001'):
            with self.assertRaises(ValueError): self.e.write(1,value)
        self.assertEqual(len(self.e.receipts()),0)
    def test_unknown_and_empty(self):
        self.assertEqual(self.status(),'UNKNOWN'); self.assertEqual(self.e.anchor()['status'],'NO_PENDING_EVENTS')
    def test_odd_merkle_batch(self):
        for i in range(1,6): self.e.write(i,'100')
        self.e.anchor()
        for i in range(1,6): self.assertEqual(self.e.verify(i)['status'],'VERIFIED')
    def test_unwitnessed_insert_blocks_anchor(self):
        self.e.write(1,'250')
        with self.e.db: self.e.db.execute('INSERT INTO records VALUES (?,?)',(2,canonical(dict(id=2,amount='50.00',revision=1))))
        self.assertEqual(self.e.verify(2)['status'],'UNWITNESSED_ROW')
        self.assertEqual(self.e.anchor()['status'],'ANCHOR_BLOCKED')
