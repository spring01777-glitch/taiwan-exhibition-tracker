"""Conservative venue grouping; original room and address facts remain visible."""
import hashlib
import re
import unicodedata

def tidy(value):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value or ''))).strip()

def key_text(value):
    return re.sub(r'[\s_・·()（）]','',tidy(value)).replace('台','臺')

def classify(event):
    venue,address=tidy(event.get('venue')),tidy(event.get('address'))
    region=event.get('region') or '地區未提供'
    park=event.get('park','')
    status='named'
    detail=venue
    if park in ('songshan','huashan','pier2'):
        name={'songshan':'松山文創園區','huashan':'華山1914','pier2':'駁二藝術特區'}[park]
        identity=park if region==('高雄市' if park=='pier2' else '臺北市') else ''
        street=''
    elif not venue or key_text(venue)==key_text(event.get('title')):
        name=('地址地點：'+address) if address else '地點未提供'
        status='address' if address else 'missing'
        identity='';street=address
    elif re.fullmatch(r'.+[鄉鎮市區]\(.+[市縣]\)=?',venue):
        area=venue.split('(')[0]
        name=f'地點待確認（{area}）'
        status='uncertain';identity='';street=address
    else:
        name=venue
        # These are explicit building/room forms in the supplied metadata.
        if re.match(r'府中15\s*\d+F',name): name='府中15'
        elif re.match(r'新浜碼頭藝術空間\s*\d+F',name): name='新浜碼頭藝術空間'
        elif re.match(r'富興工廠1962\s*\d+F',name): name='富興工廠1962'
        elif name.startswith('佛光山佛陀紀念館 '): name='佛光山佛陀紀念館'
        elif name.startswith('國立臺灣科學教育館 '): name='國立臺灣科學教育館'
        elif re.match(r'中正紀念堂\d+展廳',name): name='中正紀念堂'
        elif key_text(name) in ('金車文藝中心承德館',): name='金車文藝中心承德館'
        elif name=='臺南市奇美博物館': name='奇美博物館'
        elif name=='基隆文化中心': name='基隆市文化中心'
        identity=''
        # Remove floor information only for identity, retaining it on the card.
        street=re.sub(r'(?:\d+F|\d+樓|[一二三四五六七八九十]+樓).*$','',address).strip()
        if name=='金車文藝中心承德館' and '承德路三段131號' in street:
            street='承德路三段131號'
    venue_id=identity or 'venue-'+hashlib.sha256((region+'|'+key_text(name)+'|'+key_text(street)).encode()).hexdigest()[:16]
    location={'id':venue_id,'name':name,'region':region,'status':status}
    return {**event,'venue':venue,'address':address,'venueName':name,'venueStatus':status,'locations':[location]}

def classify_all(events):
    return [classify(e) for e in events]
