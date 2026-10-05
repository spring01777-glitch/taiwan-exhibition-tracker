"""Fetch licensed exhibition metadata. Python standard library only."""
import argparse
import hashlib
import html
import json
import re
import ssl
import socket
import subprocess
import sys
import time
from venues import classify_all
from source_links import resolve_source_link
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
API = 'https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category=6'
TW = timezone(timedelta(hours=8))
CITIES = ['臺北市','新北市','基隆市','桃園市','新竹市','新竹縣','苗栗縣','臺中市','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','臺南市','高雄市','屏東縣','宜蘭縣','花蓮縣','臺東縣','澎湖縣','金門縣','連江縣']

class SourceUpdateError(ValueError):
    def __init__(self, code, stage, counts=None):
        super().__init__(code)
        self.code, self.stage, self.counts = code, stage, counts or {}

def safe_error_code(exc):
    if isinstance(exc, SourceUpdateError): return exc.code
    if isinstance(exc, HTTPError): return f'HTTP_{exc.code}'
    if isinstance(exc, URLError): return safe_error_code(exc.reason) if isinstance(exc.reason, Exception) else 'NETWORK_ERROR'
    if isinstance(exc, ssl.SSLCertVerificationError): return 'TLS_CERTIFICATE_VERIFICATION'
    if isinstance(exc, ssl.SSLError): return 'TLS_ERROR'
    if isinstance(exc, socket.gaierror): return 'DNS_FAILURE'
    if isinstance(exc, TimeoutError): return 'TIMEOUT'
    if isinstance(exc, ConnectionRefusedError): return 'CONNECTION_REFUSED'
    if isinstance(exc, json.JSONDecodeError): return 'INVALID_JSON'
    if isinstance(exc, subprocess.TimeoutExpired): return 'TIMEOUT'
    if isinstance(exc, subprocess.CalledProcessError):
        return {60:'TLS_CERTIFICATE_VERIFICATION',28:'TIMEOUT',6:'DNS_FAILURE',7:'CONNECTION_REFUSED',22:'HTTP_ERROR'}.get(exc.returncode,'CURL_FAILURE')
    if isinstance(exc, PermissionError): return 'POLICY_OR_ROBOTS_REJECTED'
    if isinstance(exc, ValueError): return 'VALIDATION_ERROR'
    return 'SOURCE_ERROR'

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', '', str(value or '')))).strip()

def date(value):
    v = str(value or '')[:10].replace('/', '-')
    return datetime.strptime(v, '%Y-%m-%d').date().isoformat()

def safe_url(value):
    value = html.unescape(str(value or '')).strip()
    p = urlparse(value)
    return value if p.scheme in ('https','http') and p.hostname and not p.username and not p.password else ''

def normalize(rows, diagnostics=None):
    counts = diagnostics if diagnostics is not None else {}
    counts.update(inputCount=len(rows) if isinstance(rows,list) else None, validCount=0, rejectedCount=0, eventCount=0)
    if not isinstance(rows, list) or not rows:
        raise SourceUpdateError('EMPTY_INPUT' if isinstance(rows,list) else 'INPUT_NOT_LIST','normalize',counts)
    events, rejected, rejection_reasons = {}, 0, {}
    link_file=ROOT/'data/source-links.json'
    checked=json.loads(link_file.read_text(encoding='utf-8')) if link_file.exists() else {}
    for row in rows:
        try:
            title = clean(row['title'])
            if not title or str(row.get('category')) != '6':
                raise ValueError('not exhibition')
            shows = row.get('showInfo') or row.get('showinfo') or []
            if not shows:
                raise ValueError('missing venue')
            for show in shows:
                start = date(show.get('time') or row.get('startDate'))
                end = date(show.get('endTime') or row.get('endDate'))
                if end < start:
                    raise ValueError('reversed dates')
                address, venue = clean(show.get('location')), clean(show.get('locationName'))
                region = next((c for c in CITIES if c in address.replace('台','臺')), '地區未提供')
                uid = clean(row.get('UID'))
                # UID and venue remain stable when the provider edits a date/title.
                key = '|'.join((uid, venue, address)) if uid else '|'.join((title, start, end, venue, address))
                eid = hashlib.sha256(key.encode()).hexdigest()[:20]
                park = 'songshan' if re.search('松山文創|松菸|松煙', venue + address) else 'huashan' if '華山' in venue + address else 'pier2' if '駁二' in venue + address else ''
                price = clean(show.get('price'))[:180] or ('免費' if show.get('onSales') == 'N' else '未提供，請洽官方')
                # Do not copy the provider's full prose or infer popularity.
                summary = f'{region}的展覽，展出於{venue or address}。實際開放日與入場規定請查閱來源。'
                promote=safe_url(row.get('sourceWebPromote'))
                resolved = resolve_source_link(uid,title,checked,promote)
                link = resolved['url']
                event = dict(id=eid,title=title,start=start,end=end,region=region,venue=venue,address=address,park=park,price=price,category='展覽',summary=summary,url=link,source='moc',sourceUid=uid,sourceVersion=clean(row.get('version')))
                event.update(resolved)
                if promote:event['promoteUrl']=promote
                if eid in events:
                    event['start'] = min(start, events[eid]['start'])
                    event['end'] = max(end, events[eid]['end'])
                events[eid] = event
        except (KeyError, ValueError, TypeError) as exc:
            rejected += 1
            fixed={'not exhibition':'CATEGORY_OR_TITLE_INVALID','missing venue':'MISSING_VENUE','reversed dates':'REVERSED_DATES'}
            reason=fixed.get(str(exc),'MISSING_REQUIRED_FIELD' if isinstance(exc,KeyError) else 'INVALID_ROW_SHAPE' if isinstance(exc,TypeError) else 'INVALID_DATE_OR_VALUE')
            rejection_reasons[reason]=rejection_reasons.get(reason,0)+1
    counts.update(validCount=len(rows)-rejected,rejectedCount=rejected,eventCount=len(events),rejectedReasons=rejection_reasons)
    if not events or rejected > len(rows) * .2:
        raise SourceUpdateError('NO_VALID_EVENTS' if not events else 'REJECTION_RATE_OVER_20_PERCENT','normalize',counts)
    return list(events.values()), rejected

def merge(previous, incoming, now):
    old = {e['id']: e for e in previous}
    by_source = {(e.get('sourceUid'),e.get('venue'),e.get('address')):e for e in previous if e.get('sourceUid')}
    result = []
    seen = set()
    for e in incoming:
        seen.add(e['id'])
        before = old.get(e['id']) or by_source.get((e.get('sourceUid'),e.get('venue'),e.get('address')), {})
        if before:
            seen.add(before['id'])
        revisions = list(before.get('revisions', []))
        if before and any(before.get(k)!=e.get(k) for k in ('title','start','end','price')):
            revisions.append({k:before.get(k) for k in ('title','start','end','price','lastSeen')})
        result.append({**e, 'firstSeen':before.get('firstSeen', now), 'lastSeen':now, 'missingFromSource':False, 'revisions':revisions})
    for e in previous:
        if e['id'] not in seen:
            result.append({**e, 'missingFromSource':True})
    return result

def fetch():
    for attempt in range(3):
        try:
            with urlopen(Request(API, headers={'User-Agent':'TaiwanExhibitionTracker/0.1 (open-data reader)','Accept':'application/json'}), timeout=30) as r:
                if urlparse(r.url).hostname != 'cloud.culture.tw':
                    raise SourceUpdateError('REDIRECT_HOST_REJECTED','fetch')
                data = r.read(10_000_001)
                if len(data) > 10_000_000:
                    raise SourceUpdateError('RESPONSE_SIZE_LIMIT','fetch')
                return json.loads(data)
        except Exception as exc:
            # Only connection diagnostics for this fixed public endpoint, never payloads.
            reason = getattr(exc, 'reason', None)
            diagnostic = safe_error_code(exc)
            print(f'Official source attempt {attempt + 1}: {diagnostic}', file=sys.stderr)
            if isinstance(reason, ssl.SSLCertVerificationError):
                # System curl verifies the certificate/hostname against its trust store.
                # Python 3.13 strict RFC checks reject this provider's older chain.
                # Never use --insecure, unverified contexts or modify trust settings.
                try:
                    r = subprocess.run(['curl','--disable','--fail','--silent','--show-error',
                        '--proto','=https','--max-time','30','--max-filesize','10000000',
                        '--header','Accept: application/json',API], capture_output=True,
                        check=True, timeout=35)
                    if len(r.stdout)>10_000_000:
                        raise SourceUpdateError('RESPONSE_SIZE_LIMIT','decode')
                    print('Official source fetched with system curl and default TLS verification.', file=sys.stderr)
                    return json.loads(r.stdout)
                except (OSError, subprocess.SubprocessError, ValueError) as fallback_error:
                    print(f'Verified curl fallback failed: {safe_error_code(fallback_error)}', file=sys.stderr)
                    if attempt == 2:
                        raise fallback_error
            if attempt == 2:
                raise
            time.sleep(attempt + 1)

def atomic(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def run(output, rows=None):
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'exhibitions.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'events':[], 'sources':{}}
    now = datetime.now(TW).isoformat(timespec='seconds')
    status = dict(old.get('sources', {}))
    diagnostics={'inputCount':None,'validCount':None,'rejectedCount':None,'eventCount':None}
    stage='fetch'
    try:
        incoming = fetch() if rows is None else rows
        stage='normalize'
        events, rejected = normalize(incoming, diagnostics)
        previous = [e for e in old['events'] if e['source'] == 'moc']
        active = sum(e['end'] >= now[:10] and not e.get('missingFromSource') for e in previous)
        diagnostics['previousActiveCount']=active
        stage='loss-guard'
        if active > 20 and len(events) < active * .5:
            raise SourceUpdateError('SOURCE_LOSS_OVER_50_PERCENT','loss-guard',diagnostics)
        stage='merge'
        merged = merge(previous, events, now)
        status['moc'] = {'state':'ok','lastAttempt':now,'lastSuccess':now,'count':len(events),'rejected':rejected,'attemptCounts':diagnostics,'message':'官方開放資料更新成功'}
        state = 'ok'
    except Exception as exc:
        merged = [e for e in old['events'] if e['source'] == 'moc']
        code=safe_error_code(exc)
        if isinstance(exc,SourceUpdateError):stage=exc.stage;diagnostics.update(exc.counts)
        elif isinstance(exc,json.JSONDecodeError) and stage=='fetch':stage='decode'
        status['moc'] = {**status.get('moc', {}), 'state':'error','lastAttempt':now,'failureStage':stage,'reasonCode':code,'attemptCounts':diagnostics,'message':'更新失敗；保留最後成功資料，請核對來源'}
        state = 'error'
    seeds = json.loads((ROOT/'data/curated.json').read_text(encoding='utf-8'))
    venue_status_file=ROOT/'data/venue-source-status.json'
    venue_status=json.loads(venue_status_file.read_text(encoding='utf-8')) if venue_status_file.exists() else {}
    # Venue sources are deliberately explicit manual verification, not claimed automated feeds.
    for key in ('songshan','huashan','pier2'):
        group = [e for e in seeds if e['source'] == key]
        if not group:
            continue
        if key in venue_status:
            status[key]=venue_status[key]
            continue
        verified = max(e['lastSeen'] for e in group)
        uncertain = sum(bool(e.get('verificationNote')) for e in group)
        message = f'本次人工核對{len(group)}筆；尚未每日自動核對官網，新活動請查官方'
        if uncertain:
            message += f'；其中{uncertain}筆官網狀態待確認'
        status[key] = {'state':'manual','lastSuccess':verified,'count':len(group),'message':message}
    # Explicit official review can correct titles/dates and retain the MOC identity.
    # Exclude those exact identities before date-based cross-source deduplication.
    for event in merged:
        if event.get('missingFromSource'):
            link_file=ROOT/'data/source-links.json'
            checked=json.loads(link_file.read_text(encoding='utf-8')) if link_file.exists() else {}
            event.update(resolve_source_link(event.get('sourceUid',''),event['title'],checked,event.get('promoteUrl','')))
    curated_ids = {e['id'] for e in seeds}
    curated_uids = {e.get('sourceUid') for e in seeds if e.get('sourceUid')}
    all_events = [e for e in merged if e['id'] not in curated_ids and e.get('sourceUid') not in curated_uids] + seeds
    # Curated venue facts take precedence if an open-data row describes the same event.
    def fingerprint(e):
        return re.sub(r'\W','',e['title']).casefold(), e['region'], e['start'], e['end']
    dedup = {fingerprint(e):e for e in all_events}
    result = {'schemaVersion':1,'generatedAt':now,'sources':status,'events':classify_all(list(dedup.values()))}
    atomic(path, result)
    atomic(output/'status.json', {'generatedAt':now,'sources':status})
    print(json.dumps({'state':state,'events':len(result['events']),'sources':status}, ensure_ascii=True))
    return 0 if state == 'ok' else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'data')
    args = parser.parse_args()
    sys.exit(run(args.output))
