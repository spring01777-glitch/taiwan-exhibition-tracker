"""Package exactly the public static website for private cloud QA, no publishing."""
import hashlib,json,re,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=['index.html','sources.html','app.js','style.css','concerts.html','comedy.html','concerts.js','concerts.css','f1.html','f1.js','f1.css','data/exhibitions.json','data/concerts.json','data/comedy.json','data/f1.json','data/f1-platforms.json','docs/CONCERTS.md','docs/F1.md','docs/VISUAL_REVIEW.md']
out=ROOT/'output/cloud-preview';out.mkdir(parents=True,exist_ok=True)
archive=out/'taiwan-event-guide-preview.zip';manifest={}
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
    for name in FILES:
        raw=(ROOT/name).read_bytes();text=raw.decode('utf8')
        assert not re.search(r'(?i)(C:[\\/]+Users|github_pat_|gh[pousr]_[a-z0-9]{20,}|sk-proj-|-----BEGIN .*PRIVATE KEY)',text),name
        bundle.writestr(name,raw);manifest[name]=hashlib.sha256(raw).hexdigest()
    guide='Private cloud QA package. Serve extracted files over localhost HTTP. Do not deploy or publish. Review docs/VISUAL_REVIEW.md. No credentials, repository internals or source scraping required. All F1-derived data attribution remains CC BY-NC-SA 4.0, non-commercial.\n'
    bundle.writestr('QA_README.txt',guide)
(out/'manifest.json').write_text(json.dumps({'archive':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':manifest},indent=2)+'\n',encoding='utf8')
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(FILES)+1,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
