"""Print the value-set definitions from converter *_vs_*.ldt files (table, id/value columns, where clause)."""
import glob,re,sys
def attr(t,k):
    i=t.find(k+" =")
    if i<0: return None
    j=t.index('"',i)+1; out=[]
    while True:
        c=t[j]
        if c=="\\": out.append(t[j+1]); j+=2; continue
        if c=='"': break
        out.append(c); j+=1
    return "".join(out).replace("\n","\n")
for f in sorted(glob.glob("*vs_*.ldt")):
    t=open(f,encoding="utf-8",errors="replace").read()
    print("==",re.search(r'BEGIN VALUE_SET "([^"]+)"',t).group(1),"validation",attr(t,"VALIDATION_TYPE"))
    for k in ("TABLE_NAME","ID_COLUMN_NAME","VALUE_COLUMN_NAME","MEANING_COLUMN_NAME","ADDITIONAL_WHERE_CLAUSE"):
        v=attr(t,k)
        if v: print("   ",k,"=",re.sub(r"\s+"," ",v)[:900])
