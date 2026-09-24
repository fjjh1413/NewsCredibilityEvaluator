import ast,pathlib,json,csv,collections
r=pathlib.Path("."); out={}
for label,folder in [("backend","backend/tests"),("evaluation","evaluation/tests"),("alert","deploy/alertmanager")]:
 fs=list((r/folder).glob("test_*.py")); counts={str(p):sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test_") for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig")))) for p in fs};out[label]={"files":len(fs),"definitions":sum(counts.values()),"per_file":counts}
for f in ["evaluation/datasets/news_eval.csv","evaluation/datasets/knowledge_base_eval.csv","evaluation/datasets/news_eval_demo.csv"]:
 rows=list(csv.DictReader(open(f,encoding="utf-8-sig",newline="")));out[f]={"rows":len(rows),"fields":list(rows[0]) if rows else [],"gold_distribution":dict(collections.Counter(x.get("gold_label") for x in rows)),"nonempty_fields":{k:sum(bool(x.get(k,"").strip()) for x in rows) for k in rows[0]} if rows else {},"firstrow":rows[0] if rows else {}}
print(json.dumps(out,ensure_ascii=False))