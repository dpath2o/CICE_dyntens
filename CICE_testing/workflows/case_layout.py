"""Plan/apply a backed-up case move; model run archives and physics stay fixed."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from ..core.cases import classification, organised_path, retarget_text
from ..core.paths import model_repo, run_root
from ..core.reporting import sha256

ACTIVE = {'ice_in','cice.settings','cice.run','cice.submit','cice.build',
          'cice.baseline.run','cice.continuous','cice.run.continuous','Makefile'}


def active_file(relative):
    # Provenance and result logs are historical records, not runtime inputs.
    return not any('provenance' in part or part in ('logs','case-migration') for part in relative.parts) and (
        relative.name in ACTIVE or relative.suffix in ('.csh','.sh','.base','.mods') or relative.name.startswith('env.'))


class CaseLayoutWorkflow:
    def __init__(self, repo, runs):
        self.repo=Path(repo).resolve(); self.runs=Path(runs).resolve()

    def plan(self):
        marker=self.repo/'box01_tests/_legacy_registry/migration-in-progress.json'
        if marker.exists():
            raise ValueError('incomplete migration; inspect backup/plan in '+str(marker))
        entries=[]
        for source in sorted(self.repo.iterdir()):
            if not source.is_dir() or not (source/'cice.settings').is_file(): continue
            try: root,stage,canonical=classification(source.name)
            except ValueError:
                if source.name.startswith(('dt_b','dyntens')):
                    raise ValueError('classify this case before moving: '+source.name)
                continue
            target=organised_path(self.repo,source.name)
            if target.exists(): raise ValueError('destination already exists: '+str(target))
            text=(source/'cice.settings').read_text()
            match=re.search(r'(?m)^\s*setenv\s+ICE_CASEDIR\s+(\S+)',text)
            if not match or Path(match[1].strip('\"\''))!=source:
                raise ValueError('ICE_CASEDIR differs from source: '+str(source))
            match=re.search(r'(?m)^\s*setenv\s+ICE_RUNDIR\s+(\S+)',text)
            if not match or '$' in match[1]: raise ValueError('explicit ICE_RUNDIR required: '+str(source))
            run=Path(match[1].strip('\"\''))
            if run!=self.runs/source.name:
                raise ValueError('unexpected run archive; inspect before moving: '+str(run))
            entries.append(dict(case_id=source.name,canonical_name=canonical,stage=stage,
                                source=str(source),target=str(target),run=str(run)))
        return entries

    def apply(self, backup):
        entries=self.plan(); backup=Path(backup).expanduser().resolve()
        if backup.exists(): raise ValueError('backup destination already exists')
        if backup==self.repo or self.repo in backup.parents:
            raise ValueError('put backup outside the repository')
        moves={e['source']:e['target'] for e in entries}
        prepared=[]
        # Preflight all text/symlink operations before copying or moving cases.
        for e in entries:
            source=Path(e['source']); edits=[]; links=[]
            rename=[e['case_id'],e['canonical_name']] if e['case_id']!=e['canonical_name'] else None
            if (source/'case-migration').exists(): raise ValueError('existing migration ledger: '+str(source))
            for path in source.rglob('*'):
                relative=path.relative_to(source)
                if path.is_symlink():
                    if any('provenance' in part or part=='logs' for part in relative.parts): continue
                    old=str(path.readlink()); new=retarget_text(old,moves)
                    if old!=new: links.append((relative,new))
                elif path.is_file() and active_file(relative):
                    old=path.read_bytes().decode(); new=retarget_text(old,moves,rename)
                    if old!=new: edits.append((relative,old,new))
            prepared.append((e,rename,edits,links))
        records=[p for p in sorted(self.repo.glob('caselist*')) if p.is_file()]
        logs=[p for p in sorted(self.repo.glob('b6-mapping-*.log')) if p.is_file()]
        backup.mkdir(parents=True)
        # Full original case trees preserve local edits, logs and symlink targets.
        for e in entries: shutil.copytree(e['source'],backup/e['case_id'],symlinks=True)
        for path in records+logs: shutil.copy2(path,backup/path.name)
        plan=dict(schema_version=1,created_utc=datetime.now(timezone.utc).isoformat(),
                  entries=entries,backup=str(backup),runs_moved=False)
        (backup/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        destination=self.repo/'box01_tests/_legacy_registry'; destination.mkdir(parents=True,exist_ok=True)
        marker=destination/'migration-in-progress.json'
        marker.write_text(json.dumps(plan,indent=2)+'\n')
        # If a filesystem error interrupts application, backup/plan is complete;
        # a rerun refuses mixed destinations instead of overwriting them.
        for e,rename,edits,links in prepared:
            target=Path(e['target']); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(e['source'],target)
            ledger=target/'case-migration'; (ledger/'original').mkdir(parents=True)
            files={}
            for relative,old,new in edits:
                saved=ledger/'original'/relative; saved.parent.mkdir(parents=True,exist_ok=True)
                saved.write_bytes(old.encode())
                path=target/relative; path.write_bytes(new.encode())
                files[str(relative)]=dict(before_sha256=sha256(saved),after_sha256=sha256(path))
            for relative,new in links:
                path=target/relative; path.unlink(); path.symlink_to(new)
            record=dict(schema_version=1,**e,moves=moves,rename=rename,files=files,
                        symlinks={str(r):v for r,v in links})
            (ledger/'record.json').write_text(json.dumps(record,indent=2)+'\n')
            # Auditable case configuration only; no history/compiled output.
            runtime=target/'case-configuration.json'
            runtime.write_text(json.dumps(dict(case_id=e['case_id'],stage=e['stage'],
                run=e['run'],inputs={p.name:sha256(p) for p in target.iterdir()
                    if p.is_file() and not p.is_symlink() and p.name in ACTIVE}),indent=2)+'\n')
        destination=self.repo/'box01_tests/_legacy_registry'; destination.mkdir(parents=True,exist_ok=True)
        if records:
            registry=destination/'case_creation_records.json'
            existing=json.loads(registry.read_text()) if registry.exists() else []
            existing.extend(dict(filename=p.name,sha256=sha256(p),original_text=p.read_text(),
                                 relocated_text=retarget_text(p.read_text(),moves)) for p in records)
            registry.write_text(json.dumps(existing,indent=2)+'\n')
            for path in records: shutil.move(path,destination/path.name)
        for path in logs: shutil.move(path,destination/path.name)
        (destination/'migration-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        marker.unlink()
        return plan


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan','apply'))
    p.add_argument('--repo',type=Path)
    p.add_argument('--runs',type=Path,default=run_root())
    p.add_argument('--backup',type=Path,help='required fresh directory outside repo for apply')
    args=p.parse_args()
    if args.action=='apply' and not args.backup: p.error('apply requires --backup')
    try:
        work=CaseLayoutWorkflow(args.repo or model_repo(),args.runs)
        result=work.plan() if args.action=='plan' else work.apply(args.backup)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError) as exc: p.exit(1,'FAIL: '+str(exc)+'\n')

if __name__=='__main__': main()
