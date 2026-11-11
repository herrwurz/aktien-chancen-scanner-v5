"""Offline analysis of archived numerical observations; never invents call fills.
Run from any directory: python <path>/reproduce.py [--check]. Standard library only.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AS_OF = date(2026, 11, 11)
D = Decimal
SYMBOLS = dict(zip(
    ['22/25','31/25','34/25','73/25','74/25','92/25','110/25','158/25','169/25','171/25','175/25','176/25','179/25','198/25','203/25','10/26','46/26','81/26','93/26'],
    ['KGX.DE','HEN3.DE','DHL.DE','UBER','AMZN','GOOG','QCOM','HO.PA','HAL','SZG.DE','HNR1.DE','SU.PA','GILD','MBG.DE','TTE.PA','FRA.DE','AI.PA','UNH','ADS.DE']))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def price(text):
    """German report numbers, including missing space before currency."""
    return D(re.sub(r'[^0-9,.\-]', '', text).replace('.', '').replace(',', '.'))


def allocation(entry, fee=D('0')):
    qty = int(((D('500') - fee) / entry).to_integral_value(rounding=ROUND_FLOOR))
    cost = (qty * entry).quantize(D('0.01'), rounding=ROUND_HALF_UP)
    return {'quantity': qty, 'purchase_fee_eur': str(fee),
            'purchase_value_eur': str(cost),
            'cash_eur': str(D('500') - cost - fee)}


def observed_touches(bars, levels):
    events = {}
    for bar in bars:
        for key in ('target1', 'target2', 'stop1'):
            field = 'low' if key == 'stop1' else 'high'
            hit = D(bar[field]) <= levels[key] if key == 'stop1' else D(bar[field]) >= levels[key]
            if hit and key not in events:
                events[key] = {'date': bar['date'], 'threshold': str(levels[key]),
                               'observed_' + field: bar[field]}
    # No stateful trade logic: later targets do not undo an earlier stop.
    return {key: events.get(key) for key in ('target1', 'target2', 'stop1')}


def verify_register(records):
    text = (ROOT / 'docs/hebeltrader-identification-rules.md').read_text()
    call_text = text.split('### Call-Marken und Szenarien')[1].split('### Aktienmarken')[0]
    stock_text = text.split('### Aktienmarken')[1].split('### Originaldateien')[0]
    def table(section):
        return {c[0]: c for line in section.splitlines() if line.startswith('| ')
                and re.match(r'\d+/\d+$', (c := [x.strip() for x in line.split('|')[1:-1]])[0])}
    calls, stocks = table(call_text), table(stock_text)
    for r in records:
        c, s = calls[r['issue']], stocks[r['issue']]
        assert c[2] == r['call']['wkn']
        assert c[12] == r['call']['maturity']
        for key, col in [('indication',3),('target1',5),('target2',6),('stop1',7),('stop2',8),('strike',10)]:
            assert price(c[col]) == price(r['call'][key]), (r['issue'], key)
        assert s[2] == r['stock']['wkn']
        for key, col in [('indication',3),('target1',4),('target2',5),('stop1',6),('stop2',7)]:
            assert price(s[col]) == price(r['stock'][key]), (r['issue'], key)


def build():
    records = json.loads((ROOT / 'docs/hebeltrader-originalreports-42.json').read_text())['records']
    assert len(records) == 42 and len({r['issue'] for r in records}) == 42
    verify_register(records)
    evidence = json.loads((HERE / 'evidence.json').read_text())
    sources = json.loads((HERE / 'market-sources.json').read_text())
    sources = {s['symbol']: s for s in sources}
    settlements = {s['issue']: s for s in evidence['settlements']}
    results = []
    for r in records:
        maturity = datetime.strptime(r['call']['maturity'], '%d.%m.%y').date()
        publication = datetime.strptime(r['source']['publication_date'], '%d.%m.%Y').date()
        expired = maturity <= AS_OF
        entry = price(r['call']['recommended_entry'] or r['call']['indication'])
        row = {'issue': r['issue'], 'underlying': r['basiswert'], 'wkn': r['call']['wkn'],
               'publication_date': publication.isoformat(), 'report_maturity': maturity.isoformat(),
               'expired_by_cutoff': expired, 'budget_eur': '500', 'entry_eur': str(entry),
               'entry_basis': 'recommended_entry_assumed_fill' if r['call']['recommended_entry'] else 'report_indication_proxy_assumed_fill',
               'allocation_zero_fees': allocation(entry),
               'wittmer_call_simulation': {'status': 'not_evaluable' if expired else 'not_researched_in_this_expired_batch',
                   'verified_executable': False, 'pnl_eur': None, 'return_pct': None, 'events': []},
               'model_price_simulation': {'status': 'not_run_missing_historical_product_terms_and_volatility', 'pnl_eur': None},
               'real_trades': {'status': 'no_execution_receipts_in_input', 'pnl_eur': None, 'executions': []}}
        if expired:
            row['blockers'] = ['no_historical_timestamped_bid_ask_series', 'no_historical_quote_size_or_liquidity',
                 'entry_is_indication_proxy_not_proven_fill', 'historical_issue_rule_scope_unverified',
                 'publication_time_unknown', 'original_pdf_not_reverified', 'product_trading_calendar_unverified']
            symbol = SYMBOLS[r['issue']]
            src = sources[symbol]
            path = HERE / src['file']
            assert digest(path) == src['sha256'], path
            with path.open() as stream:
                bars = list(csv.DictReader(stream))
            dates = [b['date'] for b in bars]
            assert dates == sorted(set(dates)) and len(bars) == src['rows']
            assert all(publication < date.fromisoformat(b['date']) <= maturity for b in bars)
            assert all(D(b['low']) <= min(D(b['open']),D(b['close'])) <= max(D(b['open']),D(b['close'])) <= D(b['high']) for b in bars)
            warnings = ['single_provider_series', 'calendar_completeness_not_verified', 'publication_day_excluded_assumption']
            if any(not b['volume'] or D(b['volume']) == 0 for b in bars): warnings.append('missing_or_zero_volume')
            flat = sum(len({b[f] for f in ('open','high','low','close')}) == 1 for b in bars)
            if flat and any(not b['volume'] for b in bars): warnings.append('incomplete_intraday_ranges')
            blocked = symbol == 'AI.PA' or 'incomplete_intraday_ranges' in warnings
            if symbol == 'AI.PA': warnings.append('capital_action_requires_historical_level_adjustment')
            levels = {key: price(r['stock'][key]) for key in ('target1','target2','stop1')}
            row['stock_observations'] = {'symbol':symbol, 'source_file':src['file'], 'source_url':src['url'],
                'currency':src['currency'], 'rows':len(bars), 'first_date':dates[0], 'last_date':dates[-1],
                'flat_ohlc_rows':flat, 'status':'blocked' if blocked else 'provisional_observed_touches_only',
                'warnings':warnings, 'first_observed_touches':None if blocked else observed_touches(bars, levels),
                'interpretation':'Earliest observed rows only; null means not seen, not proof of no touch. Independent thresholds, no Call fills or strategy outcomes.'}
            # One-day comparisons are quality checks, not full-series validation.
            checks=[]
            for v in evidence['validation']:
                if v['symbol'] != symbol: continue
                b=next((b for b in bars if b['date']==v['date']),None)
                matches={f: b is not None and D(b[f])==D(v[f]) for f in ('open','high','low','close') if f in v}
                checks.append({'date':v['date'],'source_url':v['source_url'],'price_matches':matches})
            row['stock_observations']['independent_checks']=checks
            if r['issue'] in settlements:
                s=settlements[r['issue']]
                assert s['wkn'] == r['call']['wkn']
                assert price(r['call']['strike']) == D(s['strike'])
                scenario={'class':'counterfactual_hold_to_redemption_not_wittmer_strategy',
                    'settlement_evidence':s,'executable_purchase_verified':False,'fee_scenarios':[]}
                for fee in (D('0'),D('5')):
                    a=allocation(entry,fee);q=a['quantity']; redemption=D(s['settlement_eur'])*q
                    pnl=redemption - D(a['purchase_value_eur']) - fee - fee
                    scenario['fee_scenarios'].append({**a,'redemption_eur':str(redemption),'redemption_fee_assumption_eur':str(fee),
                        'pnl_eur':str(pnl),'return_on_500_budget_pct':str(pnl/D('5'))})
                row['hold_to_redemption_scenario']=scenario
        results.append(row)
    expired=[r for r in results if r['expired_by_cutoff']]
    assert len(expired)==19
    inputs=['docs/hebeltrader-identification-rules.md','docs/hebeltrader-originalreports-42.json']
    input_hashes={p:digest(ROOT/p) for p in inputs}
    input_hashes.update({p.name:digest(p) for p in [HERE/'market-sources.json', HERE/'evidence.json', HERE/'research-log.json', HERE/'reproduce.py']})
    return {'schema_version':1,'as_of':AS_OF.isoformat(),'baseline_commit':evidence['baseline_commit'],
        'method':'archived_daily_stock_observations_and_evidence_gated_call_audit_v1',
        'input_sha256':input_hashes,'totals':{'universe':42,'budget_eur':21000,'expired':19,'expired_budget_eur':9500,
        'remaining_not_researched':23,'verified_executable_call_simulations':0,'call_strategy_pnl_eur':None,
        'real_trade_pnl_eur':None,'settlement_counterfactuals':2,
        'stock_series_imported':19,'stock_observation_cases_provisional':sum(r['stock_observations']['status']!='blocked' for r in expired)},
        'records':results}


def render(result):
    lines=['# HEBELTRADER: historische Prüfung der 19 abgelaufenen Calls', '',
        'Stichtag 11.11.2026. Budget 500 EUR je Call. **Keine belegte historische Wittmer-Gesamtrendite.**', '',
        'Diese Tabelle zeigt Aktienbeobachtungen, keine Call-Verkäufe. Zielberührungen nach einem früheren Stopp sind keine gewonnenen Trades. Alle Datenreihen sind vorläufig; Kalender-Vollständigkeit und vollständiger Zweitquellenabgleich fehlen. „—“ bedeutet nur: in den abgerufenen Zeilen nicht beobachtet.', '',
        '| Ausgabe | Aktie / Call | Aktienziel 1 | Aktienziel 2 | Aktienstopp 1 | Kurszeilen |',
        '|---|---|---|---|---|---:|']
    for r in result['records']:
        if not r['expired_by_cutoff']:continue
        s=r['stock_observations']; e=s['first_observed_touches']
        values=[(e[k]['date'] if e[k] else '—') for k in ('target1','target2','stop1')] if e else ['gesperrt']*3
        lines.append(f"| {r['issue']} | {r['underlying']} / {r['wkn']} | {' | '.join(values)} | {s['rows']} |")
    lines += ['', 'DHL ist wegen 14 Zeilen mit identischen OHLC-Werten und fehlenden Volumenangaben vorläufig gesperrt. Air Liquide ist wegen der Kapitalmaßnahme und noch nicht freigegebener Anpassung der Originalmarken gesperrt. Einzelne fehlende/Null-Volumina stehen zusätzlich in results.json.', '',
        '## Separates Szenario: bis zur Rückzahlung gehalten', '',
        'Emittenten-Rückzahlungen sind belegt; Kauf zur Reportindikation und Halten ohne Stopp sind eigene Annahmen. Dies ist keine Simulation von Wittmers Strategie und kein realer Trade. Die Kostenvariante mit 5 EUR je Kauf/Rückzahlung ist nur eine Sensitivität, kein belegter Banktarif. Stückzahl wird innerhalb des 500-EUR-Budgets angepasst; Steuern nicht berücksichtigt.', '',
        '| Ausgabe / Call | Rückzahlung je Stück | Stück ohne Gebühren | Gewinn ohne Gebühren | Gewinn bei 5 EUR je Vorgang |',
        '|---|---:|---:|---:|---:|']
    for r in result['records']:
        if 'hold_to_redemption_scenario' not in r:continue
        s=r['hold_to_redemption_scenario'];a,b=s['fee_scenarios']
        lines.append(f"| {r['issue']} / {r['wkn']} | {s['settlement_evidence']['settlement_eur']} EUR | {a['quantity']} | {a['pnl_eur']} EUR | {b['pnl_eur']} EUR |")
    lines += ['', 'Die zwei Fälle sind eine selektive Teilmenge. Es wird daraus keine Trefferquote und kein 19- oder 42-Call-Gesamtergebnis berechnet.', '',
        '## Reproduktion', '', '`python research/hebeltrader-performance-20261111/reproduce.py --check` prüft Quellenhashes, Registerabgleich, Kursdaten und erzeugte Ergebnisse offline. Ohne --check werden results.json und RESULTS.md reproduziert.', '',
        'Methodik, Quellenbewertung und konkrete Datenanforderungen: [README.md](README.md).']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    result=build()
    outputs={'results.json':json.dumps(result,indent=2,ensure_ascii=False)+'\n','RESULTS.md':render(result)}
    if '--check' in sys.argv:
        for name,content in outputs.items():
            assert (HERE/name).read_text()==content, f'{name} differs; reproduce first'
        print('PASS: 42 register records; 19 archived series; hashes, OHLC, cutoff and output reproducibility')
    else:
        for name,content in outputs.items():(HERE/name).write_text(content)
        print(json.dumps(result['totals'],ensure_ascii=False))
