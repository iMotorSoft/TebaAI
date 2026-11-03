import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parent

def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
def save(name,obj): (R/name).write_text(json.dumps(obj,indent=2)+'\n')
state={k:git(*v) for k,v in {'branch':['branch','--show-current'],'local_head':['rev-parse','HEAD'],'tracking_head':['rev-parse','origin/feature/console-backend-core'],'remote_head':['ls-remote','origin','refs/heads/feature/console-backend-core']}.items()}
state['captured_at']=datetime.now(timezone.utc).isoformat()
save('baseline-git-state.json',state)
paths=git('ls-files','--others','--exclude-standard').splitlines()
save('worktree-before.json',{'status':git('status','--short'),'diff_name_status':git('diff','--name-status'),'cached_name_status':git('diff','--cached','--name-status'),'untracked':paths,'note':'Only capture_initial.py in V2 created before this capture; no candidate files changed.'})
h={}
for d in ['parallel-generation-foundation-v2-publication-v1','parallel-generation-rollback-remediation-v1']:
 for p in sorted((R.parent/d).rglob('*')):
  if p.is_file(): h[str(p.relative_to(Path.cwd()))]=hashlib.sha256(p.read_bytes()).hexdigest()
save('historical-hashes-before.json',h)
