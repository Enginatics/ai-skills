#!/usr/bin/env python
"""Parse an Oracle Reports .rex text export (Reports Builder: File > Convert, "Report Definition file" -> "Text file")
into its DEFINE records, decoding <<"...">> text and (BINARY)/(TLONG) blocks.

Fallback when rwconverter segfaults on the .rdf (no <PROG>_rdf.xml): ask the customer for the .rex and run
    python rex_parse.py <folder-with-rex> <PROG> [<PROG> ...]
which prints the record-type counts, every SRW2_QUERY SQL, every non-trivial TOOL_PLSQL unit and the
parameter columns (SRW2_COLUMN FUNCTION=3), and writes <PROG>_<QUERY>.sql + <PROG>_plsql.txt next to the .rex.
Query variants that differ only in sort/group expressions collapse into one Blitz SQL; the LDT stays the parameter source.
"""
import re,io,sys,os,collections
def parse(path):
    with io.open(path,encoding='latin-1') as f: lines=f.read().split('\n')
    recs=[];i=0;n=len(lines)
    while i<n:
        m=re.match(r'^DEFINE\s+(\S+)',lines[i])
        if not m: i+=1; continue
        typ=m.group(1); i+=1
        assert lines[i].strip()=='BEGIN',(path,i,lines[i]); i+=1
        rec={'_type':typ}
        while i<n and lines[i].strip()!='END':
            l=lines[i]
            fm=re.match(r'^\s*(\w+)\s*=\s*(.*)$',l)
            if fm:
                k,v=fm.group(1),fm.group(2).strip()
                if v.startswith('(') and v.endswith(')') or v=='':
                    # value follows as <<" ... ">> block
                    i+=1
                    buf=[]
                    if lines[i].startswith('<<"'):
                        first=lines[i][3:]
                        if first.endswith('">>'):
                            buf.append(first[:-3]); i+=1
                        else:
                            buf.append(first); i+=1
                            while i<n and not lines[i].endswith('">>'):
                                buf.append(lines[i]); i+=1
                            buf.append(lines[i][:-3]); i+=1
                    raw='\n'.join(buf)
                    if v=='(BINARY)':
                        hx=re.sub(r'\s+','',raw)
                        try: txt=bytes.fromhex(hx).decode('latin-1').rstrip('\x00')
                        except Exception: txt=raw
                        rec[k]=txt
                    else:
                        rec[k]=raw
                    continue
                if v.startswith('<<"'):
                    if v.endswith('">>'): rec[k]=v[3:-3]; i+=1; continue
                    buf=[v[3:]]; i+=1
                    while i<n and not lines[i].endswith('">>'):
                        buf.append(lines[i]); i+=1
                    buf.append(lines[i][:-3]); i+=1
                    rec[k]='\n'.join(buf); continue
                rec[k]=v.strip()
            i+=1
        recs.append(rec); i+=1
    return recs
if __name__=='__main__':
    M=sys.argv[1]
    for prog in sys.argv[2:]:
        recs=parse(os.path.join(M,prog+'.rex'))
        print('#'*20,prog,len(recs),'records')
        c=collections.Counter(r['_type'] for r in recs)
        print({k:v for k,v in c.items() if not k.startswith('VG_')})
        plsql=[]
        for r in recs:
            t=r['_type']
            if t=='SRW2_QUERY':
                sql=next((v for k,v in r.items() if isinstance(v,str) and len(v)>40 and 'select' in v.lower()),None)
                fn=os.path.join(M,'%s_%s.sql'%(prog,r.get('NAME')))
                if sql:
                    with io.open(fn,'w',encoding='utf-8',newline='\n') as f: f.write(sql)
                print('--- QUERY',r.get('NAME'),'->',fn,'(%d chars)'%len(sql or ''))
            if t=='TOOL_PLSQL':
                src=r.get('PLSLFID_ST') or ''
                plsql.append('=== PLSQL %s type %s\n%s'%(r.get('NAME'),r.get('TYPE'),src))
                body=re.sub(r'/\*.*?\*/','',src,flags=re.S); body=re.sub(r'--[^\n]*','',body)
                lines=[l for l in body.splitlines() if l.strip()]
                trivial=len(lines)<=6 and re.search(r'return\s*\(?\s*(true|false)\s*\)?\s*;',body,re.I) and not re.search(r'select|:=',body,re.I)
                print('--- PLSQL',r.get('NAME'),'type',r.get('TYPE'),'src',len(src),'(trivial)' if trivial else '')
            if t in ('SRW2_PARAMETER','SRW2_USER_PARAM','SRW2_PARAM'):
                print('--- PARAM',{k:v for k,v in r.items() if k in ('NAME','DATA_TYPE','INIT_VALUE','WIDTH','PARAM_TYPE')})
            if t=='SRW2_COLUMN' and str(r.get('FUNCTION'))=='3':
                print('--- PARAM',r.get('NAME'),'| datatype',r.get('DATA_TYPE'),'| width',r.get('WIDTH'))
        with io.open(os.path.join(M,prog+'_plsql.txt'),'w',encoding='utf-8',newline='\n') as f: f.write('\n'.join(plsql))
