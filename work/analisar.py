"""Análise exploratória PRF e Apriori em Python, sem bibliotecas externas.
Execute junto dos ZIPs oficiais datatran2023.zip, datatran2024.zip e datatran2025.zip.
Se faltarem, o programa tenta baixá-los dos links oficiais. Gera resultados/.
"""
import csv, io, json, math, hashlib, zipfile, urllib.request
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

IDS = {2023:'1-WO3SfNrwwZ5_l7fRTiwBKRw7mi1-HUq',2024:'14lB0vqMFkaZj8HZ44b0njYgxs9nAN8KO',2025:'1-G3MdmHBt6CprDwcW99xxC4BZ2DU5ryR'}
FIELDS = ['dia_semana','fase_dia','condicao_metereologica','tipo_pista','uso_solo']
SUPORTE_MINIMO = 0.01
CONFIANCA_MINIMA = 0.25
MAX_ITENS = 3  # até duas condições no antecedente e gravidade no consequente
TARGET = 'gravidade=grave'

def minerar_regras(records):
    """Aplica o Apriori original às ocorrências fornecidas."""
    transactions = [frozenset(f'{f}={r[f]}' for f in FIELDS+['gravidade']) for r in records]
    n = len(transactions)
    threshold = math.ceil(SUPORTE_MINIMO*n)
    item_rows = defaultdict(set)
    for i,t in enumerate(transactions):
        for item in t: item_rows[item].add(i)

    # Apriori: conjuntos frequentes de tamanho 1, junção de candidatos e poda.
    # Se algum subconjunto de k-1 itens não é frequente, o candidato é descartado.
    frequent = {frozenset([v]):len(ids) for v,ids in item_rows.items() if len(ids)>=threshold}
    level = set(frequent)
    levels = {'1':len(level)}
    for k in range(2, MAX_ITENS+1):
        candidates = set()
        ordered = sorted(tuple(sorted(s)) for s in level)
        for i,a in enumerate(ordered):
            for b in ordered[i+1:]:
                if a[:-1] != b[:-1]: continue
                c = frozenset(a+b)
                if len(c) != k: continue
                if len({x.split('=',1)[0] for x in c}) != k: continue
                if all(frozenset(sub) in level for sub in combinations(c,k-1)):
                    candidates.add(c)
        next_level = set()
        for c in candidates:
            count = len(set.intersection(*(item_rows[x] for x in c)))
            if count >= threshold:
                frequent[c] = count
                next_level.add(c)
        level = next_level
        levels[str(k)] = len(level)

    base_rate = len(item_rows[TARGET])/n
    rules = []
    for itemset, count in frequent.items():
        if TARGET not in itemset or len(itemset)<2: continue
        antecedent = itemset - {TARGET}
        covered = frequent[antecedent]
        confidence = count/covered
        lift = confidence/base_rate
        if confidence >= CONFIANCA_MINIMA and lift > 1:
            rules.append({'antecedente':' E '.join(sorted(antecedent)), 'consequente':TARGET,
                          'n_antecedente':covered,'n_graves':count,'suporte':count/n,
                          'confianca':confidence,'lift':lift})
    rules.sort(key=lambda r:(-r['lift'],-r['suporte'],r['antecedente']))
    return rules, levels, len(item_rows[TARGET]), base_rate

def main():
    out = Path('resultados'); out.mkdir(exist_ok=True)
    records, audit, seen = [], [], set()
    for year, file_id in IDS.items():
        path = Path(f'datatran{year}.zip')
        if not path.exists():
            urllib.request.urlretrieve('https://drive.google.com/uc?export=download&id='+file_id, path)
        data = path.read_bytes()
        z = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in z.namelist() if n.endswith('.csv'))
        reader = csv.DictReader(io.StringIO(z.read(name).decode('latin1')), delimiter=';')
        counts = Counter()
        for r in reader:
            counts['brasil'] += 1
            if r['uf'].strip() != 'PR': continue
            counts['parana_bruto'] += 1
            key = (year, r['id'])
            if key in seen:
                counts['duplicados'] += 1
                continue
            seen.add(key)
            try:
                dead, injured = int(r['mortos']), int(r['feridos_graves'])
                if min(dead, injured) < 0: raise ValueError('contagem negativa')
            except (ValueError, TypeError):
                counts['alvo_invalido'] += 1
                continue
            row = {'ano':year,'id':r['id']}
            for f in FIELDS:
                row[f] = r[f].strip() or 'Não informado'
                if row[f] == 'Não informado': counts['campos_ausentes'] += 1
            row['gravidade'] = 'grave' if dead+injured > 0 else 'nao_grave'
            records.append(row)
            counts['analisados'] += 1
            counts['graves'] += row['gravidade'] == 'grave'
        audit.append({'ano':year, **counts, 'sha256':hashlib.sha256(data).hexdigest(), 'url':'https://drive.google.com/file/d/'+file_id+'/view'})

    rules, levels, graves_total, base_rate = minerar_regras(records)
    n = len(records)

    def write_csv(name, rows):
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter=';'); w.writeheader();w.writerows(rows)
    write_csv('base_preparada.csv', records)
    if rules: write_csv('regras_apriori.csv',rules)
    groups = {}
    for field in ['fase_dia','tipo_pista']:
        categories = sorted(set(r[field] for r in records))
        groups[field] = []
        for v in categories:
            group = [r for r in records if r[field]==v]
            graves = sum(r['gravidade']=='grave' for r in group)
            groups[field].append({'categoria':v,'n':len(group),'graves':graves,'proporcao':graves/len(group)})
    summary = {'n':n,'graves':graves_total,'taxa_graves':base_rate,'auditoria':audit,
               'parametros':{'suporte_minimo':SUPORTE_MINIMO,'confianca_minima':CONFIANCA_MINIMA,'lift_maior_que':1,'max_itens':MAX_ITENS},
               'itens_frequentes_por_tamanho':levels,'n_regras':len(rules),'regras':rules,'grupos':groups}
    (out/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
