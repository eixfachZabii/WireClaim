from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "case_analysis" / "data" / "fair_value_study.json"
DEFAULT_OUTPUT = ROOT / "case_analysis" / "data" / "fair_value_study.html"


def _counter(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(item["field"][key])
    return dict(counts)


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    invoice = item.get("invoice") or {}
    fair = item["fair_value"]
    return {
        "index": item["index"],
        "name": invoice.get("name") or "Invoice row not parsed",
        "quantity": invoice.get("quantity"),
        "quantityMissing": bool(invoice.get("quantity_missing")),
        "fair": {
            "lower": fair["lower"],
            "upper": fair["upper"]["value"],
            "relation": fair["upper"]["relation"],
            "identifiedSet": fair["identified_set"],
            "evidence": fair["evidence"],
        },
        "field": {
            "charge": item["field"]["charge_direction_counts"],
            "limit": item["field"]["limit_direction_counts"],
            "hiddenOvercharges": item["field"]["hidden_overcharges"],
            "exactChargeCount": item["field"]["exact_charge_count"],
            "meanExactCharge": item["field"]["mean_exact_charge"],
            "meanExactChargeRelation": item["field"]["mean_exact_charge_relation"],
            "caution": item["field"]["caution"],
        },
    }


def _compact_game(game: dict[str, Any]) -> dict[str, Any]:
    items = [_compact_item(item) for item in game["line_items"]]
    return {
        "id": game["game_id"],
        "invoiceItemCount": game["invoice_item_count"],
        "transactionItemCount": game["transaction_item_count"],
        "itemCountMatches": game["item_count_matches"],
        "transactionRows": game["transaction_rows"],
        "matrixTeamsCompared": game["verification"]["matrix_teams_compared"],
        "matrixMatches": game["verification"]["matrix_matches"],
        "errors": game["errors"],
        "items": items,
        "boundedItems": sum(item["fair"]["identifiedSet"] == "bounded" for item in items),
        "lowerBoundedItems": sum(item["fair"]["identifiedSet"] == "lower_bounded" for item in items),
        "charge": _counter(items, "charge"),
        "limit": _counter(items, "limit"),
    }


def build_payload(study: dict[str, Any]) -> dict[str, Any]:
    games = [_compact_game(game) for game in study["games"]]
    items = [item for game in games for item in game["items"]]
    widths = [
        item["fair"]["upper"] - item["fair"]["lower"]
        for item in items
        if item["fair"]["upper"] is not None
    ]
    return {
        "source": study["source"],
        "teamCount": len(study["team_names"]),
        "games": games,
        "summary": {
            "games": len(games),
            "items": len(items),
            "bounded": sum(item["fair"]["identifiedSet"] == "bounded" for item in items),
            "lowerBounded": sum(item["fair"]["identifiedSet"] == "lower_bounded" for item in items),
            "itemCountMatches": sum(game["itemCountMatches"] for game in games),
            "charge": _counter(items, "charge"),
            "limit": _counter(items, "limit"),
            "medianBoundedWidth": sorted(widths)[len(widths) // 2] if widths else None,
        },
    }


def render(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__STUDY_DATA__", data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    study = json.loads(args.input.read_text(encoding="utf-8"))
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(build_payload(study)), encoding="utf-8")
    print(f"wrote {output}")


HTML_TEMPLATE = r'''<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WireClaim · Fair Value Study</title>
<style>
:root{--ink:#e9eef7;--muted:#aeb9cc;--panel:#171d2b;--panel2:#111724;--line:#2a3650;--canvas:#0c1120;--accent:#70a7ff;--teal:#52d2b8;--gold:#ffcf70;--coral:#ff7d8a;--violet:#bb9cff;--slate:#7f8ca3;--shadow:0 16px 45px #03061377}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 12% -10%,#1c315a 0,transparent 32rem),radial-gradient(circle at 90% 8%,#183d41 0,transparent 28rem),var(--canvas);color:var(--ink);font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}button,select,input{font:inherit}button{cursor:pointer}.shell{max-width:1560px;margin:auto;padding:28px 26px 60px}.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;margin-bottom:24px}.eyebrow{color:var(--teal);font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;font-weight:800}.hero h1{font-size:clamp(2rem,4vw,3.7rem);line-height:1;margin:.3rem 0 .65rem;letter-spacing:-.05em}.hero p{max-width:850px;color:var(--muted);margin:0}.source{border:1px solid var(--line);background:#0c1423bd;border-radius:14px;padding:13px 16px;min-width:260px;color:var(--muted);font-size:.8rem}.source strong{color:var(--ink);display:block;margin-bottom:4px}.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:20px 0}.metric{background:linear-gradient(145deg,#1b2436,#121927);border:1px solid var(--line);box-shadow:var(--shadow);border-radius:15px;padding:16px}.metric .value{font-size:1.7rem;font-weight:800;letter-spacing:-.04em}.metric .label{font-size:.79rem;color:var(--muted);margin-top:3px}.panel{background:linear-gradient(145deg,#171f30eF,#111725f2);border:1px solid var(--line);box-shadow:var(--shadow);border-radius:18px;padding:19px;margin-top:15px}.panel h2{font-size:1rem;margin:0 0 3px}.panel .sub{margin:0 0 15px;color:var(--muted);font-size:.86rem}.overview{display:grid;grid-template-columns:1.3fr .7fr;gap:15px}.game-chart{display:grid;grid-template-columns:repeat(31,minmax(12px,1fr));gap:4px;align-items:end;height:142px;padding-top:18px;border-bottom:1px solid var(--line)}.game-bar{min-width:0;border:0;border-radius:5px 5px 0 0;background:linear-gradient(180deg,var(--accent),#5277d5);position:relative;padding:0;transition:.18s transform,.18s filter}.game-bar:hover,.game-bar.active{transform:translateY(-4px);filter:brightness(1.25)}.game-bar:after{content:attr(data-game);position:absolute;bottom:-22px;left:50%;transform:translateX(-50%);font-size:10px;color:var(--muted)}.legend{display:flex;flex-wrap:wrap;gap:10px 15px;color:var(--muted);font-size:.78rem;margin-top:25px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field-group{border:1px solid var(--line);border-radius:12px;padding:12px;background:#0d1421a8}.field-group h3{font-size:.82rem;margin:0 0 9px;color:var(--muted)}.stack{display:flex;height:12px;border-radius:999px;overflow:hidden;background:#263249;margin:6px 0 9px}.segment{min-width:0}.chip-row{display:flex;flex-wrap:wrap;gap:6px}.chip{padding:4px 7px;border-radius:6px;background:#202b3e;color:#d6deec;font-size:.7rem;white-space:nowrap}.below{background:var(--teal)}.fair{background:var(--gold)}.over{background:var(--coral)}.unknown{background:var(--slate)}.above{background:var(--violet)}.controls{display:grid;grid-template-columns:180px 1fr 170px 170px;gap:10px;align-items:center;margin:12px 0 0}.control{height:40px;border-radius:10px;border:1px solid var(--line);background:#0c1421;color:var(--ink);padding:0 11px}.case-status{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 0}.badge{font-size:.72rem;border-radius:999px;padding:5px 9px;border:1px solid var(--line);color:var(--muted)}.badge.ok{border-color:#2a8d7b;color:#7be3cd}.badge.warn{border-color:#b46c78;color:#ffb5bd}.items-head{display:grid;grid-template-columns:54px minmax(220px,2.1fr) minmax(230px,1.2fr) minmax(250px,1.45fr) minmax(215px,1.25fr);gap:13px;padding:18px 10px 8px;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.08em}.item{display:grid;grid-template-columns:54px minmax(220px,2.1fr) minmax(230px,1.2fr) minmax(250px,1.45fr) minmax(215px,1.25fr);gap:13px;align-items:center;padding:13px 10px;border-top:1px solid #263147}.item:hover{background:#1a243750}.index{font-weight:800;color:var(--accent);font-variant-numeric:tabular-nums}.name{font-weight:700;line-height:1.25}.quantity{font-size:.77rem;color:var(--muted);margin-top:3px}.interval-label{font-weight:800;font-variant-numeric:tabular-nums}.interval-kind{font-size:.7rem;color:var(--muted);margin-top:4px}.track{height:13px;border-radius:999px;background:#263146;overflow:hidden;position:relative;margin:9px 0 0}.range{height:100%;position:absolute;border-radius:999px;background:linear-gradient(90deg,var(--accent),var(--teal))}.unbounded{height:100%;position:absolute;border-radius:999px;background:linear-gradient(90deg,var(--accent),#8799bd55);border-right:1px dashed var(--ink)}.field-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mini{border-left:3px solid var(--line);padding-left:8px;font-size:.75rem;min-width:0}.mini strong{display:block;font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px}.counts{display:flex;gap:5px;flex-wrap:wrap}.count{font-variant-numeric:tabular-nums;border-radius:5px;padding:2px 5px;color:#09111d;font-weight:800}.evidence{font-size:.75rem;color:var(--muted)}.empty{padding:35px;color:var(--muted);text-align:center}.method{border-left:3px solid var(--gold);background:#30271688;padding:12px 14px;border-radius:9px;color:#f2e2b5;margin-top:15px;font-size:.86rem}.footer{margin:24px 0 0;color:var(--muted);font-size:.78rem;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}.footer a{color:var(--accent)}@media(max-width:1150px){.grid{grid-template-columns:repeat(3,1fr)}.overview{grid-template-columns:1fr}.items-head{display:none}.item{grid-template-columns:44px 1fr;gap:9px}.item>div:nth-child(n+3){grid-column:2}.controls{grid-template-columns:1fr 1fr}.hero{display:block}.source{margin-top:16px}}@media(max-width:620px){.shell{padding:20px 13px 36px}.grid{grid-template-columns:repeat(2,1fr)}.controls{grid-template-columns:1fr}.field-grid{grid-template-columns:1fr}.item{padding:13px 2px}.hero h1{font-size:2.2rem}}
</style>
</head>
<body>
<main class="shell">
<section class="hero">
<div><div class="eyebrow">WireClaim · Settlement inversion</div><h1>Fair Value Study</h1><p>Interaktive Sicht auf die deterministisch identifizierten Fair-Value-Mengen pro Case und Line Item. Offene Grenzen bleiben offen; Charge und Limit werden nur dort relativ zu <em>t</em> klassifiziert, wo die Settlement-Daten dies beweisen.</p></div>
<div class="source"><strong>Statische Offline-Ansicht</strong><span id="sourceNote"></span><br><a href="fair_value_study.json">Rohdaten öffnen</a></div>
</section>
<section class="grid" id="metrics"></section>
<section class="overview">
<div class="panel"><h2>Identifikation pro Game</h2><p class="sub">Höhe = Anzahl Line Items, blau = vollständig begrenzte Fair-Value-Menge, dunkler Anteil = nur Untergrenze.</p><div class="game-chart" id="gameChart"></div><div class="legend"><span><i class="dot below"></i>bounded</span><span><i class="dot unknown"></i>lower bounded</span><span>Game auswählen, um die Item-Tabelle zu wechseln.</span></div></div>
<div class="panel"><h2>Field-Richtung</h2><p class="sub">Keine gemittelten Limits oder erfundenen Charge-Werte.</p><div class="field-grid" id="fieldSummary"></div></div>
</section>
<section class="panel">
<h2 id="caseTitle">Case</h2><p class="sub" id="caseSub"></p>
<div class="controls"><select class="control" id="gameSelect" aria-label="Game auswählen"></select><input class="control" id="search" placeholder="Line Item durchsuchen …"><select class="control" id="setFilter"><option value="all">alle Mengen</option><option value="bounded">nur bounded</option><option value="lower_bounded">nur Untergrenze</option><option value="zero">Untergrenze 0</option></select><select class="control" id="sort"><option value="index">nach Index</option><option value="lower">nach Untergrenze</option><option value="width">nach Intervallbreite</option></select></div>
<div class="case-status" id="caseStatus"></div>
<div class="items-head"><span>Index</span><span>Line Item</span><span>Fair Value t</span><span>Identifizierte Menge</span><span>Field-Richtung</span></div>
<div id="items"></div>
<div class="method">Die Darstellung zeigt <strong>identifizierte Mengen</strong>, keine statistischen Konfidenzintervalle: wrongful rejections erhöhen die Untergrenze; nachvollziehbare Overcharge-/Cap-Evidenz begrenzt die Oberseite. Für Limits werden keine Mittelpunkte konstruiert.</div>
</section>
<div class="footer"><span>Erzeugt aus <code>case_analysis/data/fair_value_study.json</code>.</span><span id="footerStatus"></span></div>
</main>
<script id="study-data" type="application/json">__STUDY_DATA__</script>
<script>
const study=JSON.parse(document.getElementById('study-data').textContent);
const labels={certainly_below_fair_value:'unter t',fair_or_at_fair_value:'fair / bei t',overcharge:'Overcharge',overcharge_from_interval:'Overcharge',overcharge_from_payment_bound:'Overcharge',unknown:'unbekannt',certainly_above_fair_value:'über t',ambiguous:'mehrdeutig'};
const styles={certainly_below_fair_value:'below',fair_or_at_fair_value:'fair',overcharge:'over',overcharge_from_interval:'over',overcharge_from_payment_bound:'over',unknown:'unknown',certainly_above_fair_value:'above',ambiguous:'unknown'};
const byId=new Map(study.games.map(game=>[String(game.id),game]));
const state={game:String(study.games[0].id),search:'',filter:'all',sort:'index'};
const euro=value=>value==null?'∞':new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:2}).format(value);
const number=value=>new Intl.NumberFormat('de-DE',{maximumFractionDigits:2}).format(value);
const count=(source,key)=>source[key]||0;
const titleForSet=item=>{const fair=item.fair;const upper=fair.upper==null?'∞':euro(fair.upper);const end=fair.upper==null?')':fair.relation==='le'?']':')';return `[${euro(fair.lower)}, ${upper}${end}`};
const flatItems=study.games.flatMap(game=>game.items);
function totalCounts(key){return flatItems.reduce((total,item)=>{Object.entries(item.field[key]).forEach(([name,value])=>total[name]=(total[name]||0)+value);return total},{})}
function renderMetrics(){const summary=study.summary;const metrics=[['Games',summary.games],['Line Items',summary.items],['bounded t-Mengen',summary.bounded],['nur Untergrenze',summary.lowerBounded],['Count-Abgleiche',`${summary.itemCountMatches}/${summary.games}`]];document.getElementById('metrics').innerHTML=metrics.map(([label,value])=>`<article class="metric"><div class="value">${value}</div><div class="label">${label}</div></article>`).join('');document.getElementById('sourceNote').textContent=`${summary.games} Games · ${summary.items} Line Items · ${study.teamCount} Teams`;}
function stack(counts,limit){const entries=Object.entries(counts).filter(([,value])=>value);const total=entries.reduce((sum,[,value])=>sum+value,0)||1;return `<div class="stack">${entries.map(([name,value])=>`<span class="segment ${styles[name]||'unknown'}" style="width:${value/total*100}%" title="${labels[name]||name}: ${value}"></span>`).join('')}</div><div class="chip-row">${entries.map(([name,value])=>`<span class="chip">${labels[name]||name} ${value}</span>`).join('')}</div>`}
function renderFieldSummary(){const charge=totalCounts('charge');const limit=totalCounts('limit');document.getElementById('fieldSummary').innerHTML=`<div class="field-group"><h3>Charge a · alle Items</h3>${stack(charge)}</div><div class="field-group"><h3>Limit b · alle Items</h3>${stack(limit)}</div>`}
function renderChart(){const max=Math.max(...study.games.map(game=>game.items.length));document.getElementById('gameChart').innerHTML=study.games.map(game=>{const height=Math.max(11,game.items.length/max*100);const bounded=game.boundedItems/game.items.length*100;return `<button class="game-bar ${String(game.id)===state.game?'active':''}" style="height:${height}%" data-game="${game.id}" title="Game ${game.id}: ${game.items.length} Items, ${game.boundedItems} bounded" onclick="selectGame('${game.id}')"><span style="display:block;width:100%;height:${bounded}%;background:var(--accent);border-radius:5px 5px 0 0"></span></button>`}).join('')}
function intervalTrack(item){const finite=flatItems.filter(entry=>entry.fair.upper!=null).map(entry=>entry.fair.upper);const max=Math.max(...finite,1);const lower=Math.min(item.fair.lower/max*100,100);if(item.fair.upper==null)return `<div class="track" title="Untergrenze ${euro(item.fair.lower)}, keine beobachtete Obergrenze"><span class="unbounded" style="left:${lower}%;right:0"></span></div>`;const width=Math.max((item.fair.upper-item.fair.lower)/max*100,1);return `<div class="track" title="${titleForSet(item)}"><span class="range" style="left:${lower}%;width:${width}%"></span></div>`}
function mini(title,counts){return `<div class="mini"><strong>${title}</strong><div class="counts">${Object.entries(counts).filter(([,value])=>value).map(([name,value])=>`<span class="count ${styles[name]||'unknown'}">${labels[name]||name}: ${value}</span>`).join('')}</div></div>`}
function renderItems(){const game=byId.get(state.game);let items=game.items.filter(item=>{const query=`${item.index} ${item.name}`.toLocaleLowerCase();if(state.search&&!query.includes(state.search.toLocaleLowerCase()))return false;if(state.filter==='zero'&&item.fair.lower!==0)return false;return state.filter==='all'||item.fair.identifiedSet===state.filter});items=items.sort((left,right)=>state.sort==='lower'?left.fair.lower-right.fair.lower:state.sort==='width'?((left.fair.upper??Infinity)-left.fair.lower)-((right.fair.upper??Infinity)-right.fair.lower):left.index-right.index);document.getElementById('items').innerHTML=items.length?items.map(item=>`<article class="item"><div class="index">${item.index}</div><div><div class="name">${escapeHtml(item.name)}</div><div class="quantity">Menge: ${item.quantity==null?'–':number(item.quantity)}${item.quantityMissing?' · Mengenangabe im PDF unsicher':''}</div></div><div><div class="interval-label">${titleForSet(item)}</div><div class="interval-kind">${item.fair.identifiedSet==='bounded'?'beidseitig begrenzt':'nur untere Schranke'}</div></div><div><div class="evidence">${item.fair.evidence.wrongful_rejections} wrongful rejections · Oberquelle: ${item.fair.evidence.upper_sources.length?item.fair.evidence.upper_sources.join(', '):'keine'}</div>${intervalTrack(item)}</div><div class="field-summary">${mini('Charge a',item.field.charge)}${mini('Limit b',item.field.limit)}</div></article>`).join(''):`<div class="empty">Keine Line Items entsprechen dem Filter.</div>`}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]))}
function renderCase(){const game=byId.get(state.game);document.getElementById('caseTitle').textContent=`Case ${game.id} · ${game.items.length} Line Items`;document.getElementById('caseSub').textContent=`${game.transactionRows.toLocaleString('de-DE')} veröffentlichte Transactions · ${game.boundedItems} bounded · ${game.lowerBoundedItems} nur untere Schranke`;document.getElementById('caseStatus').innerHTML=`<span class="badge ${game.itemCountMatches?'ok':'warn'}">Invoice ${game.invoiceItemCount} · Transactions ${game.transactionItemCount}</span><span class="badge ${game.matrixMatches?'ok':'warn'}">${game.matrixTeamsCompared?`Matrix: ${game.matrixTeamsCompared} Team-Abgleiche`:'Matrix-Zelle nicht im aktuellen Fenster'}</span>${game.errors.map(error=>`<span class="badge warn">${escapeHtml(error)}</span>`).join('')}`;renderItems()}
function selectGame(id){state.game=id;document.getElementById('gameSelect').value=id;renderChart();renderCase()}
window.selectGame=selectGame;
function init(){document.getElementById('gameSelect').innerHTML=study.games.map(game=>`<option value="${game.id}">Game ${game.id} · ${game.items.length} Items</option>`).join('');document.getElementById('gameSelect').addEventListener('change',event=>selectGame(event.target.value));document.getElementById('search').addEventListener('input',event=>{state.search=event.target.value;renderItems()});document.getElementById('setFilter').addEventListener('change',event=>{state.filter=event.target.value;renderItems()});document.getElementById('sort').addEventListener('change',event=>{state.sort=event.target.value;renderItems()});document.getElementById('footerStatus').textContent=`${study.source.fair_value_bounds} · statische Offline-Datei`;renderMetrics();renderFieldSummary();renderChart();renderCase()}
init();
</script>
</body>
</html>'''


if __name__ == "__main__":
    main()
