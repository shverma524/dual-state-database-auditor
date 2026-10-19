"""Reproducible local experiments. No external services or real customer data."""
import json, platform, statistics, tempfile, time, unittest
from pathlib import Path
from .engine import Engine

def measure():
    rows=[]
    for count in (10,100,300):
        with tempfile.TemporaryDirectory() as directory:
            e=Engine(directory); timings=[]
            for i in range(1,count+1):
                start=time.perf_counter(); e.write(i,'250.00'); timings.append((time.perf_counter()-start)*1000)
            start=time.perf_counter(); anchored=e.anchor(); anchor_ms=(time.perf_counter()-start)*1000
            verify=[]
            for i in range(1,min(count,30)+1):
                start=time.perf_counter(); verdict=e.verify(i); verify.append((time.perf_counter()-start)*1000)
                assert verdict['status']=='VERIFIED'
            rows.append(dict(records=count,write_median_ms=round(statistics.median(timings),3),anchor_ms=round(anchor_ms,3),verify_median_ms=round(statistics.median(verify),3),proof_siblings=len(e.verify(1)['proof'])))
            e.close()
    cases=[]
    for name,attack in [('Unlogged edit','edit'),('Row and audit rewrite','rewrite-both'),('Unlogged delete','delete'),('Audit erasure','erase-audit')]:
        with tempfile.TemporaryDirectory() as directory:
            e=Engine(directory); e.write(1,'250'); e.anchor(); v=e.attack(1,attack)
            cases.append(dict(scenario=name,status=v['status'])); e.close()
    return dict(timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),python=platform.python_version(),platform=platform.platform(),mode='SQLite receipt laboratory; local witness simulation',benchmark=rows,scenarios=cases,limitations='Single run per size; warm OS caches; no PostgreSQL or network blockchain measurements. Verification scans history; only Merkle path evaluation is logarithmic in batch size.')
if __name__=='__main__':
    result=measure(); output=Path('evidence/experiments.json');output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
