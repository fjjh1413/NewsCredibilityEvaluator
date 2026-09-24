import ast,pathlib,json,collections
r=pathlib.Path(".");apis=[];tables=[];migrations=[]
for p in (r/"backend/app/api/v1").glob("*.py"):
 t=ast.parse(p.read_text(encoding="utf-8-sig"));prefix=""
 for n in ast.walk(t):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="APIRouter":
   prefix=next((ast.literal_eval(k.value) for k in n.keywords if k.arg=="prefix"),"")
 for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   for d in n.decorator_list:
    if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ("get","post","put","patch","delete","options","head"):
     apis.append({"method":d.func.attr.upper(),"path":"/api"+prefix+ast.literal_eval(d.args[0]),"file":str(p).replace(chr(92),"/"),"line":d.lineno})
for p in (r/"backend/app/models").glob("*.py"):
 t=ast.parse(p.read_text(encoding="utf-8-sig"))
 for n in ast.walk(t):
  if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=="__tablename__" for x in n.targets): tables.append({"name":ast.literal_eval(n.value),"file":str(p).replace(chr(92),"/"),"line":n.lineno})
for p in (r/"backend/alembic/versions").glob("*.py"):
 t=ast.parse(p.read_text(encoding="utf-8-sig")); vals={}
 for n in t.body:
  if isinstance(n,ast.Assign):
   for x in n.targets:
    if isinstance(x,ast.Name) and x.id in ["revision","down_revision"]:vals[x.id]=ast.literal_eval(n.value)
 migrations.append({"file":p.name,**vals})
print(json.dumps({"api_operations":len(apis),"unique_paths":len(set(a["path"] for a in apis)),"by_module":dict(collections.Counter(a["file"] for a in apis)),"apis":apis,"tables":tables,"migrations":migrations}))