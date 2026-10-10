"""Daily low-rate reads of public, robots-permitted feeds and venue pages.

Only low-risk sources are automated: KKTIX organizer JSON feeds (卡米地、薩泰爾),
Taipei Arena government open-data JSON, Taipei Music Center public event pages
and OPENTIX schema.org event data listed in its sitemap. Ticket platforms whose
terms or bot protection forbid automation (tixCraft, ibon, ERA, KHAM, the
kktix.com marketplace) stay on reviewed imports.

Each source fails independently and keeps its complete last successful
snapshot. Manually reviewed facts (price, sale time, notes) are never
overwritten by sparser crawled facts. Provider prose is used only for
classification and never stored.
"""
import argparse
import copy
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bs4 import BeautifulSoup
from live_sources import classify, load_registry, normalized, read, retain_missing, snapshot_path, validate_event, write

ROOT = Path(__file__).resolve().parents[1]
TW = timezone(timedelta(hours=8))
UA = 'TaiwanExhibitionTracker/0.5 (+https://github.com/spring01777-glitch/taiwan-exhibition-tracker)'
DELAY = 1.2
CITIES = ['臺北市','新北市','基隆市','桃園市','新竹市','新竹縣','苗栗縣','臺中市','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','臺南市','高雄市','屏東縣','宜蘭縣','花蓮縣','臺東縣','澎湖縣','金門縣','連江縣']
SHORT_CITIES = {'北市':'臺北市','新北':'新北市','桃市':'桃園市','中市':'臺中市','南市':'臺南市','高市':'高雄市'}
PLATFORMS = {'tixcraft.com':'拓元 tixCraft','ticket.com.tw':'年代 ERA','kham.com.tw':'寬宏 KHAM','ticket.ibon.com.tw':'ibon',
             'www.opentix.life':'OPENTIX','ticketplus.com.tw':'遠大 Ticket Plus','ticket.mna.com.tw':'寬宏 KHAM'}
CRAWL_FIELDS = ('title','region','venue','address','sessions','sourceUrl')
EVENT_FIELDS = {'source','sourceUid','title','performers','region','venue','address','sessions','price','saleAt','saleNote',
                'ticketStatus','ticketUrl','ticketVerifiedAt','tickets','status','statusNote','summary','revisions',
                'verificationMethod','sessionFacts','programKey','sourceUrl'}
SAFE_REASONS = {'robots disallows URL','unexpected host','unexpected redirect host','response too large','empty feed or changed structure',
                'more than 50% source loss; preserve last success','too many invalid records'}


class SourceError(ValueError):
    pass


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(str(value or '')).replace('\xa0', ' ')).strip()


def stamp():
    return datetime.now(TW).isoformat(timespec='seconds')


def region_of(*values):
    text = ' '.join(clean(v) for v in values if v).replace('台', '臺')
    hit = next((c for c in CITIES if c in text), None)
    if hit:
        return hit
    return next((city for short, city in SHORT_CITIES.items() if re.search(r'(?:^|[\s/、])' + short, text)), None)


def platform_of(url):
    host = (urlsplit(url).hostname or '').lower()
    if host.endswith('.kktix.cc') or host in ('kktix.com', 'www.kktix.com'):
        return 'KKTIX'
    return PLATFORMS.get(host)


class Fetcher:
    """HTTPS GET for one fixed host, robots.txt enforced, rate limited."""

    def __init__(self, base, opener=None, delay=DELAY):
        self.base = base.rstrip('/')
        self.host = urlsplit(base).netloc
        self.opener = opener or self._urlopen
        self.delay = delay
        self.last = 0.0
        self.robot = None
        self.requests = 0

    @staticmethod
    def _urlopen(url):
        with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': '*/*'}), timeout=25) as response:
            if urlsplit(response.url).netloc != urlsplit(url).netloc:
                raise SourceError('unexpected redirect host')
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise SourceError('response too large')
        return raw

    def _get(self, url):
        p = urlsplit(url)
        if p.scheme != 'https' or p.netloc != self.host or p.username or p.password:
            raise SourceError('unexpected host')
        wait = self.delay - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.requests += 1
        return self.opener(url)

    def get(self, url):
        if self.robot is None:
            try:
                rules = self._get(self.base + '/robots.txt').decode('utf-8', 'replace')
            except HTTPError as error:
                if error.code not in (404, 410):
                    raise
                rules = ''
            # Some sites answer robots.txt with an HTML error page; that is not
            # a rule set, so treat it like a missing file rather than parse it.
            if '<html' in rules[:500].lower():
                rules = ''
            self.robot = RobotFileParser()
            self.robot.parse(rules.splitlines())
        if not self.robot.can_fetch(UA, url):
            raise SourceError('robots disallows URL')
        return self._get(url)

    def text(self, url):
        return self.get(url).decode('utf-8-sig')

    def json(self, url):
        return json.loads(self.text(url))


class Counter:
    def __init__(self):
        self.stats = dict(discovered=0, included=0, excluded=0, pending=0, failed=0, reasons={})

    def add(self, decision, reason):
        self.stats[decision] += 1
        self.stats['reasons'][reason] = self.stats['reasons'].get(reason, 0) + 1


def upcoming(sessions, today):
    return [s for s in sessions if s['date'] >= today]


def base_event(kind, uid, title, region, venue, address, sessions, url, today, price=None, sale_note=None, tickets=None):
    label = '演唱會' if kind == 'concerts' else '單口喜劇'
    return dict(sourceUid=uid, title=title, performers=None, region=region, venue=venue, address=address or None,
                sessions=sessions, price=price, saleAt=None, saleNote=sale_note or '一般開賣時間未提供，請見官方。',
                ticketStatus='非即時票況', ticketUrl=None, ticketVerifiedAt=None, tickets=tickets or [],
                status='scheduled', summary=f'{region}的{label}，演出地點為{venue}。', sourceUrl=url,
                verificationMethod='daily-crawl', revisions=[])


def kktix_ticket(url, sessions, today):
    return [dict(platform='KKTIX', url=url, checkedAt=today, sessions=[dict(date=s['date'], time=s.get('time')) for s in sessions])]


# --- KKTIX organizer feeds -------------------------------------------------

KKTIX_TIME = re.compile(r'時間：\s*(\d{4})/(\d{2})/(\d{2})\s+(\d{2}:\d{2})\(\+0800\)\s*(?:~\s*(?:(\d{4})/(\d{2})/(\d{2})\s+)?(\d{2}:\d{2}))?')


def parse_kktix(kind, feed, today, counter):
    entries = feed.get('entry') if isinstance(feed, dict) else None
    if not isinstance(entries, list) or not entries:
        raise SourceError('empty feed or changed structure')
    events = []
    for entry in entries:
        counter.stats['discovered'] += 1
        try:
            url = str(entry['url'])
            p = urlsplit(url)
            if p.scheme != 'https' or not p.hostname.endswith('.kktix.cc') or not p.path.startswith('/events/'):
                raise ValueError('unexpected event URL')
            title = clean(entry['title'])
            content = clean(entry.get('content')).replace(' 地點：', '\n地點：')
            m = KKTIX_TIME.search(content)
            if not title or not m:
                raise ValueError('missing title or time')
            day = f'{m[1]}-{m[2]}-{m[3]}'
            if m[5] and f'{m[5]}-{m[6]}-{m[7]}' != day:
                # Parent listings spanning several days repeat the child pages.
                counter.add('excluded', 'MULTI_DAY_PARENT_LISTING')
                continue
            if day < today:
                counter.add('excluded', 'PAST_EVENT')
                continue
            place = content.split('地點：', 1)[1].strip() if '地點：' in content else ''
            venue, _, address = (x.strip() for x in place.partition(' / '))
            region = region_of(address, venue, title)
            decision, reason = classify(kind, {'title': title, 'description': clean(entry.get('summary'))})
            if decision != 'included':
                counter.add(decision, reason)
                continue
            if not venue or not region or '依' in venue[:3]:
                counter.add('pending', 'PLACE_NOT_STRUCTURED')
                continue
            sessions = [dict(date=day, time=m[4])]
            events.append(base_event(kind, url, title, region, venue, address, sessions, url, today,
                                     tickets=kktix_ticket(url, sessions, today)))
            counter.add('included', reason)
        except (KeyError, TypeError, ValueError, AttributeError):
            counter.add('failed', 'INVALID_FEED_RECORD')
    return events


def crawl_kktix(kind, entry, fetch, today, counter):
    base = entry['crawler']['base']
    feed = fetch(base).json(base + '/events.json')
    return parse_kktix(kind, feed, today, counter), 1


# --- Taipei Arena open data ------------------------------------------------

ARENA_DATE = re.compile(r'(\d{4})/(\d{1,2})(?:/|月)(\d{1,2})日?')


def arena_sessions(content):
    section = content.split('活動日期', 1)[1] if '活動日期' in content else ''
    section = re.split(r'主辦單位|聯絡電話|票\s*價', section)[0]
    hits = list(ARENA_DATE.finditer(section))
    sessions = []
    for i, m in enumerate(hits):
        chunk = section[m.end():hits[i + 1].start() if i + 1 < len(hits) else len(section)]
        # Door-opening and end times sit in brackets or carry 開場; the first
        # remaining clock, or one explicitly marked 開演, is the start time.
        chunk = re.sub(r'[（(][^)）]*[)）]', ' ', chunk)
        start = re.search(r'(\d{1,2}:\d{2})\s*開演', chunk) or re.search(r'(\d{1,2}:\d{2})(?!\d|\s*開場)', chunk)
        clock = start[1].zfill(5) if start else None
        day = f'{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}'
        datetime.strptime(day, '%Y-%m-%d')
        if clock:
            datetime.strptime(clock, '%H:%M')
        sessions.append(dict(date=day, time=clock))
    return sessions


def arena_field(content, label, stop):
    m = re.search(label + r'\s*[:：]\s*(.*?)(?=' + stop + r'|$)', content)
    return clean(m[1])[:160] if m else None


def parse_arena(kind, rows, today, counter):
    if not isinstance(rows, list) or not rows:
        raise SourceError('empty feed or changed structure')
    events = []
    for row in rows:
        counter.stats['discovered'] += 1
        try:
            url = str(row['Source'])
            if urlsplit(url).netloc != 'www.arena.taipei':
                raise ValueError('unexpected source URL')
            raw_title = clean(row['title'])
            m = re.search(r'《(.*)》\s*$', raw_title)
            title = clean(m[1]) if m else raw_title
            content = clean(re.sub(r'<[^>]+>', ' ', str(row.get('內容') or '')))
            sessions = arena_sessions(content)
            if not title or not sessions:
                raise ValueError('missing title or dates')
            if not upcoming(sessions, today):
                counter.add('excluded', 'PAST_EVENT')
                continue
            decision, reason = classify(kind, {'title': title, 'description': content[:600]})
            if decision != 'included':
                counter.add(decision, reason)
                continue
            price = arena_field(content, r'票\s*價', r'售票系統|聯絡電話|主辦單位|※')
            system = arena_field(content, '售票系統', r'聯絡電話|主辦單位|票\s*價|※|抽選')
            note = f'售票系統：{system}；開賣時間請見官方。' if system else None
            events.append(base_event(kind, url, title, '臺北市', '臺北小巨蛋', '臺北市松山區南京東路四段2號', sessions, url,
                                     today, price=price, sale_note=note))
            counter.add('included', reason)
        except (KeyError, TypeError, ValueError, AttributeError):
            counter.add('failed', 'INVALID_FEED_RECORD')
    return events


def crawl_arena(kind, entry, fetch, today, counter):
    c = entry['crawler']
    rows = fetch(c['base']).json(c['base'] + c['feed'])
    return parse_arena(kind, rows, today, counter), 1


# --- Taipei Music Center ---------------------------------------------------

TMC_POINT = re.compile(r'(\d{4})\.(\d{2})\.(\d{2})\s*(\d{2}:\d{2})?')


def tmc_sessions(text):
    points = [(f'{m[1]}-{m[2]}-{m[3]}', m[4]) for m in TMC_POINT.finditer(text)]
    if not points or len(points) > 2:
        raise ValueError('unexpected date format')
    first, last = points[0], points[-1]
    if first[0] == last[0]:
        # Same-day "start - end" is one performance, not two sessions.
        return [dict(date=first[0], time=first[1])]
    gap = (datetime.strptime(last[0], '%Y-%m-%d') - datetime.strptime(first[0], '%Y-%m-%d')).days
    if gap > 1:
        # A long range does not say which days have performances.
        return None
    return [dict(date=d, time=t) for d, t in dict.fromkeys(points)]


def parse_tmc_list(body, base):
    soup = BeautifulSoup(body, 'html.parser')
    cards = {}
    for a in soup.select('a.c-card-clip-wrap[href*="/tw/blog/show/"]'):
        url = urljoin(base, a['href'])
        p = urlsplit(url)
        if p.netloc != urlsplit(base).netloc or p.query:
            continue
        cards[url] = dict(tag=clean(a.select_one('.c-tag').get_text() if a.select_one('.c-tag') else ''),
                          title=clean(a.select_one('.c-card-clip__title').get_text() if a.select_one('.c-card-clip__title') else ''))
    if not cards:
        raise SourceError('empty feed or changed structure')
    return cards


def parse_tmc_detail(kind, body, url, today):
    soup = BeautifulSoup(body, 'html.parser')
    title = clean(soup.select_one('h2.event-title').get_text() if soup.select_one('h2.event-title') else '')
    aside = soup.select_one('aside.event-detail') or soup.select_one('.event-detail')
    if not title or not aside:
        raise ValueError('missing title or details')
    sessions = tmc_sessions(clean(aside.select_one('.date').get_text() if aside.select_one('.date') else ''))
    info = {}
    for block in aside.select('.each-info'):
        label = clean(block.select_one('.title').get_text() if block.select_one('.title') else '')
        info[label] = block
    venue = clean(info['活動地點'].select_one('.content').get_text(' ')) if '活動地點' in info else ''
    price = clean(info['票價'].select_one('.content').get_text(' '))[:160] if '票價' in info else None
    links = [a.get('href', '') for a in info['購票連結'].select('a[href]')] if '購票連結' in info else []
    tickets = []
    for link in links:
        label = platform_of(link)
        if label and urlsplit(link).scheme == 'https' and urlsplit(link).path not in ('', '/') and sessions:
            tickets.append(dict(platform=label, url=link, checkedAt=today, sessions=[dict(s) for s in sessions]))
    return title, sessions, venue or '臺北流行音樂中心', price, tickets[:3]


def crawl_tmc(kind, entry, fetch, today, counter):
    c = entry['crawler']
    reader = fetch(c['base'])
    cards = parse_tmc_list(reader.text(c['base'] + c['list']), c['base'])
    events = []
    pages = 1
    for url, card in cards.items():
        counter.stats['discovered'] += 1
        # The card tag is the venue's own format label; exhibitions, talks and
        # courses never need a detail request.
        if card['tag'] not in ('演唱會', '中心自辦', '中心合辦'):
            counter.add('excluded', 'OTHER_REVIEWED_FORMAT')
            continue
        decision, reason = classify(kind, {'title': card['title'], 'reviewedKind': 'concerts' if card['tag'] == '演唱會' else None})
        if decision != 'included':
            counter.add(decision, reason)
            continue
        try:
            pages += 1
            title, sessions, venue, price, tickets = parse_tmc_detail(kind, reader.text(url), url, today)
            if sessions is None:
                counter.add('pending', 'DATE_RANGE_WITHOUT_SESSIONS')
                continue
            if not upcoming(sessions, today):
                counter.add('excluded', 'PAST_EVENT')
                continue
            address = '臺北市南港區市民大道八段99號' if re.search(r'流行音樂中心|表演廳|文化館|Live House D|Legacy TERA', venue, re.I) else None
            events.append(base_event(kind, url, title, '臺北市', venue, address, sessions, url, today,
                                     price=price, tickets=tickets))
            counter.add('included', reason)
        except (KeyError, TypeError, ValueError, AttributeError):
            counter.add('failed', 'INVALID_DETAIL_PAGE')
    return events, pages


# --- OPENTIX sitemap + schema.org Event ------------------------------------

def opentix_sessions(body):
    """One schema.org Event block per session on the public event page."""
    found = []
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', body, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get('@type') == 'Event':
                found.append(item)
    return found


def parse_opentix(body, url, today):
    blocks = opentix_sessions(body)
    if not blocks:
        raise ValueError('no structured event data')
    first = blocks[0]
    title = clean(first.get('name'))
    location = first.get('location') or {}
    venue = clean(location.get('name'))
    address = location.get('address') or {}
    address_text = clean(' '.join(str(address.get(k) or '') for k in ('addressLocality', 'streetAddress')))
    region = region_of(address_text, venue)
    evidence = {'title': title, 'description': clean(first.get('description'))[:600]}
    decisions = {kind: list(classify(kind, evidence)) for kind in ('concerts', 'comedy')}
    sessions = {}
    for b in blocks:
        if clean(b.get('name')) != title or clean((b.get('location') or {}).get('name')) != venue:
            continue
        if 'Cancelled' in str(b.get('eventStatus')):
            continue
        start = datetime.fromisoformat(str(b['startDate'])[:19])
        sessions[(start.date().isoformat(), start.strftime('%H:%M'))] = None
    sessions = [dict(date=d, time=t) for d, t in sorted(sessions)]
    offers = first.get('offers') or {}
    low, high = offers.get('lowPrice'), offers.get('highPrice')
    price = (f'NT${low:,}' if low == high else f'NT${low:,}–{high:,}') if isinstance(low, int) and isinstance(high, int) else None
    sale = offers.get('availabilityStarts') or offers.get('validFrom')
    return dict(title=title, venue=venue, address=address_text or None, region=region, sessions=sessions,
                price=price, saleAt=(sale + '+08:00') if sale and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', sale) else None,
                decisions=decisions)


def refresh_opentix(entry, fetch, today, state):
    """Only newly listed events are read (newest first); known events are not
    re-read unless refreshDays is set, and past events never are. A daily cap
    keeps the request rate low. One read serves every kind; no prose cached."""
    c = entry['crawler']
    reader = fetch(c['base'])
    tree = ET.fromstring(reader.get(c['base'] + c['sitemap']))
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    listed = {}
    for node in tree.findall('s:url', ns):
        loc = (node.findtext('s:loc', default='', namespaces=ns) or '').strip()
        if re.fullmatch(re.escape(c['base']) + r'/event/\d+', loc):
            listed[loc] = (node.findtext('s:lastmod', default='', namespaces=ns) or '').strip()
    if not listed:
        raise SourceError('empty feed or changed structure')
    cache = state.setdefault('pages', {})
    refresh = c.get('refreshDays')  # None: never re-read a known event
    limit = c.get('maxPagesPerRun', 60)
    due = (datetime.fromisoformat(today) - timedelta(days=refresh)).date().isoformat() if refresh else None

    def priority(url):
        page = cache.get(url)
        if not page:
            return (0, '')  # never read
        facts = page.get('facts')
        if facts and facts['sessions'] and max(x['date'] for x in facts['sessions']) < today:
            return None  # every session is past: never read again
        if due is None or page.get('readAt', '') > due:
            return None  # read recently; lastmod churns daily, so it is not used
        return (1, page.get('readAt', ''))

    ranked = {u: priority(u) for u in listed}
    fresh = sorted((u for u, r in ranked.items() if r and r[0] == 0), key=lambda u: listed[u], reverse=True)
    recheck = sorted((u for u, r in ranked.items() if r and r[0] == 1), key=lambda u: ranked[u][1])
    stale = fresh + recheck
    for url in stale[:limit]:
        try:
            cache[url] = dict(readAt=today, facts=parse_opentix(reader.text(url), url, today))
        except (KeyError, TypeError, ValueError, AttributeError):
            cache[url] = dict(readAt=today, facts=None)
    for url in list(cache):
        if url not in listed:
            del cache[url]
    state['pendingPages'] = max(0, len(stale) - limit)
    state['listed'] = len(listed)
    return 1 + min(len(stale), limit)


def crawl_opentix(kind, entry, fetch, today, counter, state):
    cache = state.get('pages', {})
    events = []
    for url, page in cache.items():
        facts = page.get('facts')
        if facts is not None and facts['sessions'] and not upcoming(facts['sessions'], today):
            continue  # past events are neither counted nor published
        counter.stats['discovered'] += 1
        if facts is None or not facts['sessions']:
            # Ticket packages and closed listings carry no session data.
            counter.add('excluded', 'NO_STRUCTURED_EVENT')
            continue
        decision, reason = facts['decisions'][kind]
        if decision != 'included':
            counter.add(decision, reason)
            continue
        if not facts['region'] or not facts['venue']:
            counter.add('pending', 'PLACE_NOT_STRUCTURED')
            continue
        tickets = [dict(platform='OPENTIX', url=url, checkedAt=today, sessions=[dict(s) for s in facts['sessions']])]
        event = base_event(kind, url, facts['title'], facts['region'], facts['venue'], facts['address'], facts['sessions'], url,
                           today, price=facts['price'], tickets=tickets)
        if facts['saleAt']:
            event['saleAt'] = facts['saleAt']
            event['saleNote'] = '開賣時間取自 OPENTIX 結構化資料；請以官方頁面為準。'
        events.append(event)
        counter.add('included', reason)
    return events, 0


ADAPTERS = {'kktix-feed': crawl_kktix, 'arena-opendata': crawl_arena, 'tmc-pages': crawl_tmc, 'opentix-sitemap': crawl_opentix}


# --- snapshot persistence ----------------------------------------------------

def same_program(before, raw):
    days = {s['date'] for s in raw['sessions']}
    return normalized(before.get('title')) == normalized(raw['title']) and bool(days & {s['date'] for s in before.get('sessions', [])})


def overlay(previous, raw, sid, today):
    """Update crawler-owned facts while keeping reviewed price/sale/notes."""
    probe = validate_event(raw, sid, today)
    before = previous.get(probe['id'])
    if not before:
        # Earlier reviewed imports may cite the same page with another URL
        # spelling or venue label. Keep that record's identity and wording.
        matches = [e for e in previous.values() if same_program(e, raw)]
        if len(matches) != 1:
            return probe
        before = matches[0]
        raw = {**raw, **{k: before[k] for k in ('sourceUid', 'title', 'region', 'venue') if before.get(k)}}
        raw['address'] = before.get('address') or raw.get('address')
    merged = {k: copy.deepcopy(v) for k, v in before.items() if k in EVENT_FIELDS}
    for field in CRAWL_FIELDS:
        merged[field] = copy.deepcopy(raw[field])
    for field in ('price', 'saleAt', 'performers'):
        if not merged.get(field) and raw.get(field):
            merged[field] = raw[field]
            if field == 'saleAt':
                # A filled-in sale time must not sit beside a "not provided" note.
                merged['saleNote'] = raw.get('saleNote')
    valid = {(s['date'], s.get('time')) for s in raw['sessions']}
    tickets = []
    for t in merged.get('tickets', []) + raw.get('tickets', []):
        scoped = [s for s in t.get('sessions', []) if (s['date'], s.get('time')) in valid]
        if scoped and not any(x['url'] == t['url'] for x in tickets):
            tickets.append({**t, 'sessions': scoped})
    merged['tickets'] = tickets
    if merged.get('status') == 'unconfirmed':
        merged['status'] = 'scheduled'
        merged.pop('statusNote', None)
    merged.setdefault('verificationMethod', 'daily-crawl')
    return validate_event(merged, sid, today)


def persist(root, kind, entry, events, counter, pages, now, error=None, extra=None):
    sid = entry['id']
    path = snapshot_path(root, kind, sid)
    old = read(path, {'events': [], 'status': {}})
    status = {**old.get('status', {}), 'id': sid, 'name': entry['name'], 'url': entry['url'], 'checkedAt': now,
              'mode': 'daily-crawl', **counter.stats, 'coverageComplete': False, 'scope': entry['crawler']['scope'],
              'pagesVisited': pages, 'expectedPages': None}
    status.pop('reasonCode', None)
    if extra:
        status.update(extra)
    today = now[:10]
    if error is None:
        try:
            previous = {e['id']: e for e in old['events']}
            fresh = [overlay(previous, raw, sid, today) for raw in events]
            last = old.get('status', {}).get('lastSuccessfulIncluded')
            if old.get('status', {}).get('mode') == 'daily-crawl' and last and last >= 6 and len(fresh) < last * .5:
                raise SourceError('more than 50% source loss; preserve last success')
            if counter.stats['failed'] > max(2, counter.stats['discovered'] * .2):
                raise SourceError('too many invalid records')
            merged = retain_missing(old['events'], fresh, complete=False)
            status.update(status='ok', lastSuccess=now, reviewedAt=today, lastSuccessfulIncluded=len(fresh),
                          message=f'每日公開資料自動更新完成；納入 {len(fresh)} 筆，待分類 {counter.stats["pending"]} 筆；不代表完整目錄。')
            status['retainedEventCount'] = len(merged)
            write(path, {'schemaVersion': 1, 'sourceId': sid, 'kind': kind, 'events': merged, 'status': status,
                         'records': old.get('records', [])})
            return True
        except (KeyError, TypeError, ValueError) as caught:
            error = caught
    reason = str(error) if str(error) in SAFE_REASONS else (f'HTTP {error.code}' if isinstance(error, HTTPError) else type(error).__name__)
    status.update(status='error', reasonCode='CRAWL_FAILED', reason=reason,
                  message='每日自動更新失敗；保留最後成功資料。')
    status['retainedEventCount'] = len(old['events'])
    write(path, {'schemaVersion': 1, 'sourceId': sid, 'kind': kind, 'events': old['events'], 'status': status,
                 'records': old.get('records', [])})
    return False


def run(root=ROOT, only=None, fetch=Fetcher, now=None):
    now = now or stamp()
    today = now[:10]
    ok = True
    state_path = root / 'data/live-sources/crawl-state.json'
    state = read(state_path, {})
    for entry in load_registry(root):
        crawler = entry.get('crawler')
        if not crawler or (only and entry['id'] not in only):
            continue
        adapter = ADAPTERS[crawler['adapter']]
        shared_error = None
        read_pages = 0
        if adapter is crawl_opentix:
            source_state = state.setdefault(entry['id'], {})
            try:
                read_pages = refresh_opentix(entry, fetch, today, source_state)
            except Exception as caught:
                shared_error = caught
        for kind in crawler['kinds']:
            counter = Counter()
            pages = 0
            events = []
            error = None
            extra = None
            try:
                if shared_error:
                    raise shared_error
                if adapter is crawl_opentix:
                    events, _ = adapter(kind, entry, fetch, today, counter, source_state)
                    pages = read_pages
                    extra = {'pendingPages': source_state.get('pendingPages', 0), 'listedPages': source_state.get('listed')}
                else:
                    events, pages = adapter(kind, entry, fetch, today, counter)
            except Exception as caught:  # Every failure keeps the last snapshot.
                error = caught
            success = persist(root, kind, entry, events, counter, pages, now, error, extra)
            ok = ok and success
            print(json.dumps({'source': entry['id'], 'kind': kind, 'ok': success, **counter.stats}, ensure_ascii=False), flush=True)
    write(state_path, state)
    return ok


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', action='append')
    args = parser.parse_args()
    raise SystemExit(0 if run(only=args.source) else 1)
