import re
from datetime import date, datetime
from decimal import Decimal

from scanner.hebeltrader.domain import Extraction, RecommendationData
from scanner.hebeltrader.pdf import read_pdf

HEADER = re.compile(r'(\d{2}\.\d{2}\.\d{4})\s*[·•]?\s*#\s*(\d+)\s*/\s*(\d{4})')
PRODUCT = re.compile(r'^(Optionsschein|Turbo|Knock.?Out|Faktor.?Zertifikat|Hebelzertifikat)\b', re.I)
NUMBER = re.compile(r'^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$')


def parse_number(value):
    token = re.sub(r'\s*(?:€|EUR|USD|\$|GBP|%|x|×)\s*$', '', value.strip())
    if not NUMBER.fullmatch(token):
        raise ValueError('Ambiguous or invalid German decimal')
    number = Decimal(token.replace('.', '').replace(',', '.'))
    if number > Decimal('1e18'):
        raise ValueError('Number exceeds supported range')
    return number


def parse_date(value):
    for fmt in ('%d.%m.%Y', '%d.%m.%y'):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError('Invalid date')


def isin(value):
    if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}\d', value):
        raise ValueError('Invalid ISIN')
    digits = ''.join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = sum((int(c)*2 // 10 + int(c)*2 % 10) if i % 2 else int(c)
                for i, c in enumerate(reversed(digits)))
    if total % 10:
        raise ValueError('Invalid ISIN checksum')
    return value


def add(rec, field, raw, line, convert=str, rule='label-v1'):
    rec.evidence.setdefault(field, []).append(dict(
        page=line['page'], bbox=line['bbox'], raw=raw, text=line['text'], rule=rule,
    ))
    try:
        value = convert(raw.strip())
    except ValueError:
        rec.flags.append(dict(code='invalid_value', field=field, page=line['page']))
        rec.values[field] = None
        return
    previous = rec.values.get(field)
    if any(f['field'] == field and f['code'] in ('invalid_value', 'conflicting_values') for f in rec.flags):
        return
    if previous is not None and previous != value:
        rec.values[field] = None
        rec.flags.append(dict(code='conflicting_values', field=field, page=line['page']))
    else:
        rec.values[field] = value


def parse_fields(rec, lines, stock=False):
    prefix = 'stock' if stock else 'derivative'
    rules = [
        (r'WKN\s+(.+)', prefix+'_wkn', lambda s: s if re.fullmatch(r'[A-HJ-NP-Z0-9]{6}', s) else _invalid()),
        (r'ISIN\s+(.+)', prefix+'_isin', isin),
        (r'(?:Akt\.?\s*Kurs\*{0,2}|Aktueller Kurs)\s+(.+)', 'stock_price' if stock else 'entry_price', parse_number),
        (r'(?:Kursziel|Ziel)\s*([12])\s+(.+)', None, parse_number),
        (r'Stopp?\s*([12])\s+(.+)', None, parse_number),
        (r'Emittent\s*:?\s+(.+)', 'issuer', str),
        (r'Basispreis\s+(.+)', 'strike', parse_number),
        (r'(?:Omega/Hebel|Omega|Hebel)\s+(.+)', 'omega', parse_number),
        (r'(?:Laufzeit|Fälligkeit)\s+(.+)', 'maturity_date', parse_date),
        (r'CRV\s*:?\s*(.+)', 'crv', parse_number),
    ]
    for i, line in enumerate(lines):
        text = line['text']
        if text in ('Laufzeit', 'Fälligkeit'):
            for neighbor in lines[max(0,i-1):i+2]:
                if re.fullmatch(r'\d{2}\.\d{2}\.\d{2,4}', neighbor['text']):
                    add(rec, 'maturity_date', neighbor['text'], neighbor, parse_date, 'adjacent-date-v1')
        if re.fullmatch(r'[\d /½]+\s*(?:Monate?|Jahre?)', text):
            add(rec, 'term_text', text, line)
        if text.startswith('Basiswert '):
            add(rec, 'stock_name', text.removeprefix('Basiswert '), line)
        if re.search(r'Kursindikation.*Stand:', text):
            add(rec, 'quote_as_of_text', text, line)
        if re.match(r'Fundamentaler Hinweis:', text):
            add(rec, 'fundamental_notes', text.split(':',1)[1].strip(), line)
        if re.match(r'Technischer Hinweis:', text):
            add(rec, 'technical_notes', text.split(':',1)[1].strip(), line)
        for pattern, field, converter in rules:
            match = re.fullmatch(pattern, text, re.I)
            if not match:
                continue
            if field is None:
                kind = 'stop' if text.lower().startswith('stop') else 'target'
                field = prefix + '_' + kind + match[1]
                raw = match[2]
            else:
                raw = match[1]
            add(rec, field, raw, line, converter)
            if field in ('entry_price','stock_price','strike'):
                currency = re.search(r'(EUR|€|USD|\$|GBP)\s*$', raw)
                if currency:
                    add(rec, prefix+'_currency', {'€':'EUR','$':'USD'}.get(currency[1], currency[1]), line)
            if field == 'omega':
                add(rec, 'omega_label', text[:match.start(1)].strip(), line)
            if field == 'entry_price':
                add(rec, 'entry_kind', 'indication', line)


def _invalid():
    raise ValueError('Invalid identifier')


def _name(value):
    return re.sub(r'\s+', ' ', value.casefold()).strip()


def extract_pdf(data: bytes) -> Extraction:
    result = Extraction(pages=read_pdf(data))
    headers = []
    for page in result.pages:
        for match in HEADER.finditer(page['text']):
            result.metadata_evidence.append(dict(page=page['number'], raw=match[0], rule='header-v1'))
            try:
                headers.append((parse_date(match[1]), int(match[2]), int(match[3])))
            except ValueError:
                result.flags.append(dict(code='invalid_publication_date', page=page['number']))
    unique = set(headers)
    if len(unique) == 1 and not result.flags:
        pub, number, year = unique.pop()
        if pub.year == year and number > 0:
            result.publication_date, result.issue_number, result.issue_year = pub, number, year
        else:
            result.flags.append(dict(code='metadata_conflict'))
    elif headers:
        result.flags.append(dict(code='metadata_conflict'))
    else:
        result.flags.append(dict(code='missing_publication_metadata'))
    if not any(p['text'].strip() for p in result.pages):
        result.flags.append(dict(code='ocr_required'))
        return result
    stock_sections = []
    for page in result.pages:
        for lines in page['regions']:
            products = [i for i, line in enumerate(lines) if PRODUCT.match(line['text'])]
            if products:
                for n, start in enumerate(products):
                    end = products[n+1]-1 if n+1<len(products) else len(lines)
                    rec = RecommendationData()
                    add(rec, 'product_type', lines[start]['text'], lines[start])
                    if start > 0 and not HEADER.search(lines[start-1]['text']):
                        add(rec, 'stock_name', lines[start-1]['text'], lines[start-1], rule='product-heading-v1')
                    parse_fields(rec, lines[start+1:end])
                    result.recommendations.append(rec)
            elif any(l['text'].startswith('Basiswert ') for l in lines):
                stock_sections.append(lines)
    for lines in stock_sections:
        basis = next(l['text'].removeprefix('Basiswert ') for l in lines if l['text'].startswith('Basiswert '))
        matches = [r for r in result.recommendations if _name(r.values.get('stock_name','')) == _name(basis)]
        if len(matches) == 1:
            parse_fields(matches[0], lines, stock=True)
        elif not result.recommendations:
            rec = RecommendationData(values={'product_type': 'stock'})
            parse_fields(rec, lines, stock=True)
            result.recommendations.append(rec)
        else:
            result.flags.append(dict(code='ambiguous_stock_section', page=lines[0]['page']))
    if len(result.recommendations) == 1:
        rec = result.recommendations[0]
        for page in result.pages:
            for match in re.finditer(r'\(CRV\)\s*(?:von|:)?\s*([\d.,]+)', page['text']):
                add(rec, 'crv', match[1], dict(page=page['number'],bbox=[0,0,page['width'],page['height']],
                                             text=match[0]), parse_number, 'prose-crv-v1')
            if 'CHARTTECHNISCHES BILD AKTIE' in page['text'] and not rec.values.get('technical_notes'):
                add(rec, 'technical_notes', page['text'], dict(page=page['number'],
                    bbox=[0,0,page['width'],page['height']],text=page['text']), rule='technical-page-v1')
        if not rec.values.get('fundamental_notes') and result.pages:
            page = result.pages[0]
            add(rec, 'fundamental_notes', page['text'], dict(page=page['number'],
                bbox=[0,0,page['width'],page['height']],text=page['text']), rule='opening-commentary-v1')
    if not result.recommendations:
        result.flags.append(dict(code='unrecognized_layout'))
    for rec in result.recommendations:
        for field in ('stock_name','derivative_wkn','stock_wkn','issuer','entry_price','stock_price',
                      'strike','maturity_date','omega','crv','derivative_target1','derivative_target2',
                      'derivative_stop1','derivative_stop2','stock_target1','stock_target2',
                      'stock_stop1','stock_stop2'):
            if rec.values.get(field) is None:
                rec.flags.append(dict(code='missing_field', field=field))
        maturity = rec.values.get('maturity_date')
        if isinstance(maturity, date) and result.publication_date and maturity < result.publication_date:
            rec.flags.append(dict(code='expired_at_publication',field='maturity_date'))
    return result
