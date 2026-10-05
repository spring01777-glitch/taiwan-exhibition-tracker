"""Use only title-verified official links; no guessed or unverified detail links."""
import re
from urllib.parse import parse_qs,urlparse
DATASET='https://data.gov.tw/dataset/6012'
def resolve_source_link(uid,title,checked,promote=''):
    entry=checked.get(uid,{})
    url=entry.get('url','')
    p=urlparse(url);q=parse_qs(p.query)
    valid_uid=bool(re.fullmatch('[0-9a-f]{24}',uid))
    culture_url=(p.scheme=='https' and p.netloc=='cloud.culture.tw' and p.path=='/frontsite/inquiry/eventInquiryAction.do' and q=={'method':['showEventDetail'],'uid':[uid]})
    promote_url=(url==promote and p.scheme in ('https','http') and bool(p.hostname) and not p.username and not p.password)
    valid_url=culture_url or promote_url
    verified=valid_uid and valid_url and entry.get('state')=='verified' and entry.get('title')==title
    if verified:return {'url':url,'sourceLinkState':'verified','sourceLinkCheckedAt':entry.get('checkedAt',''),'sourceLinkType':'culture' if culture_url else 'promote'}
    return {'url':DATASET,'sourceLinkState':'unavailable' if valid_uid else 'invalid-id','sourceLinkCheckedAt':entry.get('checkedAt',''),'sourceLinkType':'dataset'}
