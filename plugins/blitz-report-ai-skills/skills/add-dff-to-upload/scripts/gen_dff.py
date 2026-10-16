#!/usr/bin/env python3
"""Generate the descriptive flexfield (DFF) parts of a Blitz Upload.

Writes, for one DFF, every artefact the add-dff-to-upload skill describes:
  main_sql_columns.sql      select-list lines for the upload's main SQL
  success_sql_columns.sql   select-list lines for the Success SQL
  upload_columns.xml        UPLOAD_COLUMNS_ROW elements: context + attribute columns with LOVs and comments
  upload_parameters.xml     UPLOAD_PARAMETERS_ROW elements mapping the procedure parameters
  translation_rule.xml      importable dynamic column translation rule for the upload
  template.xml              TEMPLATES_ROW element: the key columns and the DFF columns, Upload Mode Update
  <package>.pks/.pkb        a complete example package whose procedure carries the DFF handling
Standard library only. Run with --help for the arguments.
"""
import argparse, pathlib, sys, uuid
from xml.sax.saxutils import escape


def x(s):
    return escape(s, {"'": "&apos;"})


def lines(items, sep):
    items = [i.strip() for i in items if i.strip()]
    return [i + (sep if k < len(items) - 1 else "") for k, i in enumerate(items)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app-id", type=int, required=True, help="application_id of the flexfield (Query 1)")
    ap.add_argument("--app-short-name", required=True, help="application_short_name of the flexfield (Query 1)")
    ap.add_argument("--flexfield", required=True, help="descriptive_flexfield_name (Query 1)")
    ap.add_argument("--prefix", required=True, help="column alias prefix, lower case, e.g. subinv")
    ap.add_argument("--count", type=int, required=True, help="number of attribute columns of the table (Query 3)")
    ap.add_argument("--family", default="ATTRIBUTE", help="attribute column family, e.g. ATTRIBUTE or PEI_INFORMATION")
    ap.add_argument("--context-column", default="ATTRIBUTE_CATEGORY", help="context_column_name (Query 1)")
    ap.add_argument("--alias", required=True, help="alias of the flexfield's own table in the main SQL, e.g. msi")
    ap.add_argument("--success-alias", default="x", help="alias of the inline view in the Success SQL")
    ap.add_argument("--param-prefix", default="p_attribute", help="procedure parameter prefix of the attributes")
    ap.add_argument("--context-param", default="p_attribute_category", help="procedure parameter of the context")
    ap.add_argument("--guid", help="GUID of the upload, for translation_rule.xml")
    ap.add_argument("--rule-name", help="name of the dynamic column translation rule")
    ap.add_argument("--first-column", type=int, default=1,
                    help="COLUMN_NUMBER of the upload column the DFF columns go before (usually UPLOAD_ROW)")
    ap.add_argument("--first-sequence", type=int, default=1,
                    help="DISPLAY_SEQUENCE of the last existing upload parameter + 1")
    ap.add_argument("--template-keys", default="",
                    help="comma separated upload column names identifying the record, e.g. ORGANIZATION_CODE,SUBINVENTORY")
    ap.add_argument("--template-name", default="Descriptive Flexfield", help="name of the generated template")
    ap.add_argument("--package", default="xx_my_upload", help="package name of the example procedure")
    ap.add_argument("--procedure", default="upload_record", help="procedure name")
    ap.add_argument("--key-params", default="", help="comma separated key parameters, e.g. p_organization_code,p_subinventory")
    ap.add_argument("--cursor-from", help="comma separated from list of the stored-record cursor (default: the flexfield table)")
    ap.add_argument("--table", help="the flexfield's own table, used when --cursor-from is not given")
    ap.add_argument("--cursor-where", default="", help="predicates of the stored-record cursor, separated by ' and '")
    ap.add_argument("--hidden", default="", help="comma separated columns of non-displayed segments (Query 2 display_flag N)")
    ap.add_argument("--dry-run", action="store_true", help="report the values the API would receive in message_ instead of calling it")
    ap.add_argument("--out", required=True, help="output directory")
    a = ap.parse_args()

    fam = a.family.upper()
    famlc = fam.lower()
    ctx = a.context_column.lower()
    n = a.count
    attrs = range(1, n + 1)
    pre = a.prefix.lower()
    ctx_alias = f"{pre}_attribute_category"
    col_alias = lambda i: f"{pre}_{famlc}{i}"
    app, dff = a.app_id, a.flexfield
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    warnings = [f"alias {s} is {len(s)} bytes, over the 30-byte limit of databases before 12.2"
                for s in [ctx_alias, col_alias(n)] if len(s) > 30]
    warnings += [f"parameter {s} is {len(s)} bytes: the import truncates it to 30 and every upload fails with PLS-00306"
                 for s in [a.context_param, f"{a.param_prefix}{n}"] if len(s) > 30]

    def disp(alias, rowid):
        res = [f"xxen_util.display_flexfield_context({app},'{dff}',{alias}.{ctx}) {ctx_alias},"]
        res += [f"xxen_util.display_flexfield_value({app},'{dff}',{alias}.{ctx},'{fam}{i}',{rowid},{alias}.{famlc}{i}) {col_alias(i)},"
                for i in attrs]
        return "\n".join(res)

    ctx_lov = "\n".join(["select", "fdfcv.descriptive_flex_context_name value,", "fdfcv.description", "from",
        "fnd_descr_flex_contexts_vl fdfcv", "where", f"fdfcv.application_id={app} and",
        f"fdfcv.descriptive_flexfield_name='{dff}' and", "fdfcv.enabled_flag='Y' and", "fdfcv.global_flag='N'",
        "order by", "fdfcv.descriptive_flex_context_name"])

    def attr_lov(i):
        sib = ",\n".join([f"p_attribute{j}=>:$column$.{col_alias(j)}" for j in attrs])
        return "\n".join(["select", "substrb(lov.column_value,1,instrb(lov.column_value,'~',1,1)-1) value,",
            "substrb(lov.column_value,instrb(lov.column_value,'~',1,1)+1,lengthb(lov.column_value)) description",
            "from", "table(xxen_util.dff_attribute_lov(", f"p_application_id=>{app},",
            f"p_descriptive_flexfield_name=>'{dff}',", f"p_context_name=>:$column$.{ctx_alias},",
            f"p_column_name=>'{fam}{i}',", sib, ")) lov", "order by", "value"])

    def comment(i):
        return "\n".join(["select",
            "'(Context) '||initcap(y.application_column_name)||': '||listagg(y.entry,', ') within group (order by y.sort_key) comments",
            "from", "(", "select", "x.application_column_name,", "x.entry,", "x.sort_key,",
            "sum(lengthb(x.entry)+2) over (order by x.sort_key) len", "from", "(", "select", "fdfcu.application_column_name,",
            "decode(fdfc.descriptive_flex_context_code,'Global Data Elements','(Global)','('||fdfc.descriptive_flex_context_code||')')||' '||fdfcu.form_left_prompt entry,",
            "decode(fdfc.descriptive_flex_context_code,'Global Data Elements','1','2'||fdfc.descriptive_flex_context_code) sort_key",
            "from", "fnd_descr_flex_contexts fdfc,", "fnd_descr_flex_col_usage_vl fdfcu", "where",
            f"fdfc.application_id={app} and", f"fdfc.descriptive_flexfield_name='{dff}' and", "fdfc.enabled_flag='Y' and",
            "fdfc.application_id=fdfcu.application_id and", "fdfc.descriptive_flexfield_name=fdfcu.descriptive_flexfield_name and",
            "fdfc.descriptive_flex_context_code=fdfcu.descriptive_flex_context_code and", "fdfcu.enabled_flag='Y' and",
            f"fdfcu.application_column_name='{fam}{i}'", ") x", ") y", "where", "y.len<=3900", "group by", "y.application_column_name"])

    rule_sql = "\n".join(["select", f"'{pre.upper()}_'||z.application_column_name column_name,",
        "case when lengthb(z.prompts)>xxen_report.max_column_length then substrb(z.prompts,1,xxen_report.max_column_length-4)||'(..)' else z.prompts end translation",
        "from", "(", "select", "y.application_column_name,", "listagg(y.form_left_prompt,', ') within group (order by y.sort_key) prompts",
        "from", "(", "select", "x.application_column_name,", "x.form_left_prompt,", "x.sort_key,",
        "sum(lengthb(x.form_left_prompt)+2) over (partition by x.application_column_name order by x.sort_key) len", "from", "(",
        "select", "fdfcu.application_column_name,", "fdfcu.form_left_prompt,",
        "min(decode(fdfc.descriptive_flex_context_code,'Global Data Elements','1','2'||fdfc.descriptive_flex_context_code)) sort_key",
        "from", "fnd_descr_flex_contexts fdfc,", "fnd_descr_flex_col_usage_vl fdfcu", "where", f"fdfc.application_id={app} and",
        f"fdfc.descriptive_flexfield_name='{dff}' and", "fdfc.enabled_flag='Y' and", "fdfc.application_id=fdfcu.application_id and",
        "fdfc.descriptive_flexfield_name=fdfcu.descriptive_flexfield_name and",
        "fdfc.descriptive_flex_context_code=fdfcu.descriptive_flex_context_code and", "fdfcu.enabled_flag='Y' and",
        f"fdfcu.application_column_name like '{fam}%'", "group by", "fdfcu.application_column_name,", "fdfcu.form_left_prompt",
        ") x", ") y", "where", "y.len<=4000", "group by", "y.application_column_name", ") z"])

    def el(tag, val, ind=4):
        return f"{' ' * ind}<{tag}>{val}</{tag}>"

    cols = [(ctx_alias.upper(), {"VALIDATE_FROM_LIST_DSP": "Y", "LOV_QUERY_DSP": x(ctx_lov)})]
    cols += [(col_alias(i).upper(), {"VALIDATE_FROM_LIST_DSP": "Y", "LOV_QUERY_DSP": x(attr_lov(i)), "COMMENTS": x(comment(i))}) for i in attrs]
    ucols = []
    for k, (name, o) in enumerate(cols):
        r = ["   <UPLOAD_COLUMNS_ROW>", el("COLUMN_NUMBER", a.first_column + k), el("COLUMN_NAME", name),
             el("COLUMN_TYPE_DSP", "LOV custom"), el("DATA_TYPE", "varchar2")]
        r += [el(t, o[t]) for t in ("VALIDATE_FROM_LIST_DSP", "LOV_QUERY_DSP", "COMMENTS") if t in o]
        ucols.append("\n".join(r + ["   </UPLOAD_COLUMNS_ROW>"]))
    ups = [(a.context_param, ctx_alias.upper())] + [(f"{a.param_prefix}{i}", col_alias(i).upper()) for i in attrs]
    uparams = ["\n".join(["   <UPLOAD_PARAMETERS_ROW>", el("SOURCE", "U"), el("DISPLAY_SEQUENCE", a.first_sequence + k),
               el("PARAMETER_NAME", p), el("IN_OUT", "in"), el("PARAMETER_TYPE", "Char"), el("COLUMN_NAME", c),
               el("DEFAULTED", "Y"), "   </UPLOAD_PARAMETERS_ROW>"]) for k, (p, c) in enumerate(ups)]
    rule_xml = None
    if a.guid:
        rule_xml = "\n".join(["<ROOT>", "<DYNAMIC_COLUMN_TRANSLATION_RULES>", " <DYNAMIC_COLUMN_TRANSLATION_RULES_ROW>",
            f"  <RULE_NAME>{x(a.rule_name or (pre + ' DFF Attributes'))}</RULE_NAME>", f"  <RULE_SQL>{x(rule_sql)}</RULE_SQL>",
            "  <ENABLED>Y</ENABLED>", "  <REPORTS>", "   <REPORTS_ROW>", f"    <GUID>{a.guid}</GUID>", "   </REPORTS_ROW>",
            "  </REPORTS>", " </DYNAMIC_COLUMN_TRANSLATION_RULES_ROW>", "</DYNAMIC_COLUMN_TRANSLATION_RULES>", "</ROOT>", ""])
    tkeys = [k.strip().upper() for k in a.template_keys.split(",") if k.strip()]
    template_xml = None
    if tkeys:
        tcols = []
        for k, name in enumerate(tkeys + [c for c, _ in cols]):
            r = ["     <TEMPLATE_COLUMNS_ROW>", el("DISPLAY_SEQUENCE", k + 1, 6), el("COLUMN_NAME", name, 6)]
            if k == len(tkeys) - 1:
                r.append(el("FREEZE_PANES", "Y", 6))
            tcols.append("\n".join(r + ["     </TEMPLATE_COLUMNS_ROW>"]))
        template_xml = "\n".join(["   <TEMPLATES_ROW>", el("GUID", uuid.uuid4().hex.upper()), el("TEMPLATE_NAME", x(a.template_name)),
            el("DESCRIPTION", "Key and descriptive flexfield columns."), "    <TEMPLATE_COLUMNS>"] + tcols + ["    </TEMPLATE_COLUMNS>",
            "    <TEMPLATE_PARAMETER_DEFAULTS>", "     <TEMPLATE_PARAMETER_DEFAULTS_ROW>", el("PARAMETER_NAME", "Upload Mode", 6),
            el("DEFAULT_VALUE", "U", 6), "     </TEMPLATE_PARAMETER_DEFAULTS_ROW>", "    </TEMPLATE_PARAMETER_DEFAULTS>",
            "    <TEMPLATE_SHARING>", "     <TEMPLATE_SHARING_ROW>", el("SHARING_LEVEL", "S", 6), el("LEVEL_VALUE", "Site", 6),
            "     </TEMPLATE_SHARING_ROW>", "    </TEMPLATE_SHARING>", "   </TEMPLATES_ROW>", ""])

    # example package
    keys = [k.strip() for k in a.key_params.split(",") if k.strip()]
    params = ["status_ out varchar2,", "message_ out varchar2,"] + [f"{k} in varchar2," for k in keys]
    params += [f"{a.context_param} in varchar2 default null,"]
    params += [f"{a.param_prefix}{i} in varchar2 default null{',' if i < n else ''}" for i in attrs]
    header = f"procedure {a.procedure}(\n" + "\n".join(params) + "\n)"
    spec = f"create or replace package {a.package} as\n\n{header};\n\nend {a.package};\n/\n"
    sel = [f"  {a.alias}.{ctx}" + ("" if ctx == "attribute_category" else " attribute_category")]
    sel += [f"  {a.alias}.{famlc}{i}" + ("" if fam == "ATTRIBUTE" else f" attribute{i}") for i in attrs]
    frm = lines(a.cursor_from.split(",") if a.cursor_from else [f"{a.table} {a.alias}"], ",")
    whr = lines(a.cursor_where.split(" and ") if a.cursor_where else [], " and")
    hidden = [h.strip().upper() for h in a.hidden.split(",") if h.strip()]
    stored = ["    l_stored.attribute_category:=c.attribute_category;"] + [f"    l_stored.attribute{i}:=c.attribute{i};" for i in attrs]
    newv = [f"    l_dff.attribute_category:={a.context_param};"] + [f"    l_dff.attribute{i}:={a.param_prefix}{i};" for i in attrs]
    merge = [f"      l_dff.attribute_category:=merged('{a.context_param}','ATTRIBUTE_CATEGORY',l_dff.attribute_category,l_stored.attribute_category);"]
    merge += [f"      l_dff.attribute{i}:=merged('{a.param_prefix}{i}','{fam}{i}',l_dff.attribute{i},l_stored.attribute{i});" for i in attrs]
    cmp = " or\n".join(["    nvl(l_dff.attribute_category,fnd_api.g_miss_char)<>nvl(l_stored.attribute_category,fnd_api.g_miss_char)"] +
        [f"    nvl(l_dff.attribute{i},fnd_api.g_miss_char)<>nvl(l_stored.attribute{i},fnd_api.g_miss_char)" for i in attrs])
    api = ",\n".join([f"    {k}=>{k}" for k in keys] + ["    p_attribute_category=>l_dff.attribute_category"] +
        [f"    p_{famlc}{i}=>l_dff.attribute{i}" for i in attrs])

    def seg_fn(name, extra):
        return f"""function {name}(p_context_code in varchar2, p_column_name in varchar2) return boolean is
begin
  for c in (
  select
  null
  from
  fnd_descr_flex_column_usages fdfcu
  where
  fdfcu.application_id=g_application_id and
  fdfcu.descriptive_flexfield_name=g_flexfield_name and
  fdfcu.descriptive_flex_context_code in ('Global Data Elements',p_context_code) and
  fdfcu.application_column_name=p_column_name and
  fdfcu.enabled_flag='Y'{extra}
  ) loop
    return true;
  end loop;
  return false;
end {name};"""

    if a.dry_run:
        write = ("    --test build: report the stored values that would be passed to the API instead of writing them\n"
                 "    message_:=case when l_exists then 'Would update: ' else 'Would create: ' end||\n" + " ||\n".join(
                     ["    'Context='||l_dff.attribute_category"] +
                     [f"    case when l_dff.attribute{i} is not null then ', {fam}{i}='||l_dff.attribute{i} end" for i in attrs]) + ";")
    else:
        write = ("    --pass the context code and stored values to the API or table handler that writes the record\n"
                 "    --and check its return status: on failure set message_ and raise le_validation_error,\n"
                 "    --which rolls the row back to its savepoint\n"
                 f"    xx_my_api.create_or_update(\n{api}\n    );")
    hidden_fn = ("\n\n" + seg_fn("segment_hidden", " and\n  fdfcu.display_flag='N'")) if hidden else ""
    slot = lambda col: "attribute" + col[len(fam):] if col.startswith(fam) and col[len(fam):].isdigit() else None
    bad = [h for h in hidden if not slot(h)]
    if bad:
        sys.exit(f"--hidden columns must be {fam}<n>: {', '.join(bad)}")
    restore = "".join(f"""
    if segment_hidden(case when not l_context_changed then l_stored.attribute_category end,'{h}') then
      l_dff.{slot(h)}:=l_stored.{slot(h)};
    end if;""" for h in hidden)
    prefix_arg = "" if fam == "ATTRIBUTE" else f"\n    p_column_prefix=>'{fam}',"
    body = f"""create or replace package body {a.package} as

g_application_id constant fnd_application.application_id%type:={app};
g_application_short_name constant fnd_application.application_short_name%type:='{a.app_short_name}';
g_flexfield_name constant fnd_descriptive_flexs.descriptive_flexfield_name%type:='{dff}';


{header} is
l_exists boolean:=false;
l_rowid rowid;
l_stored xxen_fnd_upload.g_attribute_rec_type;
l_dff xxen_fnd_upload.g_attribute_rec_type;
l_dff_message varchar2(4000);
l_context_changed boolean:=false;
l_changed boolean:=false;
le_validation_error exception;

--a hand-built csv or xlsx counts every parameter as modified, also one whose column the upload's
--template leaves out
function modified(p_parameter_name in varchar2) return boolean is
begin
  return xxen_upload.parameter_exists(p_parameter_name) and xxen_upload.value_modified(p_parameter_name);
end modified;

function dff_modified return boolean is
begin
  if modified('{a.context_param}') then
    return true;
  end if;
  for i in 1..{n} loop
    if modified('{a.param_prefix}'||i) then
      return true;
    end if;
  end loop;
  return false;
end dff_modified;

{seg_fn("segment_enabled", "")}{hidden_fn}

--an unmodified cell keeps the stored value: in the display form the download shows if an enabled
--segment uses the column, unconverted otherwise; a context change clears the old context's segments
function merged(p_parameter_name in varchar2, p_column_name in varchar2, p_new_value in varchar2, p_stored_value in varchar2) return varchar2 is
begin
  if modified(p_parameter_name) then
    return p_new_value;
  elsif p_column_name='ATTRIBUTE_CATEGORY' then
    return xxen_util.display_flexfield_context(g_application_id,g_flexfield_name,p_stored_value);
  elsif segment_enabled(case when not l_context_changed then l_stored.attribute_category end,p_column_name) then
    return xxen_util.display_flexfield_value(g_application_id,g_flexfield_name,l_stored.attribute_category,p_column_name,l_rowid,p_stored_value);
  elsif not l_context_changed then
    return p_stored_value;
  end if;
  return null;
end merged;

begin
  status_:=xxen_upload.g_status_success;
  savepoint before_row;
  for c in (
  select
  {a.alias}.rowid row_id,
{(","+chr(10)).join(sel)}
  from
{chr(10).join('  '+l for l in frm)}
  where
{chr(10).join('  '+l for l in whr)}
  ) loop
    l_exists:=true;
    l_rowid:=c.row_id;
{chr(10).join(stored)}
  end loop;
  l_dff:=l_stored;

  if not l_exists or dff_modified then
{chr(10).join(newv)}
    if l_exists then
      l_context_changed:=modified('{a.context_param}') and
      nvl({a.context_param},fnd_api.g_miss_char)<>nvl(xxen_util.display_flexfield_context(g_application_id,g_flexfield_name,l_stored.attribute_category),fnd_api.g_miss_char);
{chr(10).join(merge)}
    end if;
    xxen_fnd_upload.validate_dff_attributes(
    p_appl_sn=>g_application_short_name,
    p_flexfield_name=>g_flexfield_name,
    p_values_or_ids_in=>'V',
    p_values_or_ids_out=>'I',{prefix_arg}
    px_attribute_rec=>l_dff,
    x_error_message=>l_dff_message
    );
    if l_dff_message is not null then
      message_:=l_dff_message;
      raise le_validation_error;
    end if;{restore}
    l_changed:=not l_exists or
{cmp};
  end if;

  --merge the entity's other columns here and set l_changed when one of them changed;
  --test each with modified(), since xxen_upload.new_value alone treats a column that
  --the csv/xlsx template omits as cleared

  if l_changed then
{write}
  else
    message_:='No change.';
  end if;
exception
  when le_validation_error then
    rollback to before_row;
    status_:=xxen_upload.g_status_error;
end {a.procedure};


end {a.package};
/
"""
    crlf = lambda s: s.replace("\r\n", "\n").replace("\n", "\r\n")
    files = {
        "main_sql_columns.sql": disp(a.alias, f"{a.alias}.rowid") + "\n",
        "success_sql_columns.sql": disp(a.success_alias, f"{a.success_alias}.row_id") + "\n",
        "upload_columns.xml": "\n".join(ucols) + "\n",
        "upload_parameters.xml": "\n".join(uparams) + "\n",
        f"{a.package}.pks": spec,
        f"{a.package}.pkb": body,
    }
    if rule_xml:
        files["translation_rule.xml"] = rule_xml
    if template_xml:
        files["template.xml"] = template_xml
    for name, text in files.items():
        (out / name).write_bytes(crlf(text).encode("utf-8"))
    print(f"written to {out}: " + ", ".join(sorted(files)))
    for w in warnings:
        print("WARNING: " + w)
    if not a.guid:
        print("NOTE: no --guid given, translation_rule.xml not written")
    if not tkeys:
        print("NOTE: no --template-keys given, template.xml not written")


if __name__ == "__main__":
    main()
