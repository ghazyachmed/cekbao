import json
from pathlib import Path
from checker import analyze, load_fixture_file

base = Path(__file__).resolve().parent
rows = load_fixture_file(str(base/'fixtures.json'))
results = [analyze(row) for row in rows]
output = base/'execution_results.json'
output.write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for r in results:
    print(f"{r['id']} status={r['status']} flags={','.join(r['risk_flags']) or 'none'} verified_settlement={r['verified_bank_settlement']}")
assert [x['status'] for x in results] == [
    'REQUIRES_OFFICIAL_CHECK','REQUIRES_OFFICIAL_CHECK',
    'MATCHES_SYNTHETIC_POLICY_ONLY','NOT_VERIFIABLE'
]
print('4/4 synthetic scenario outcomes matched expected statuses.')
