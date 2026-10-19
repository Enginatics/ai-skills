--Query 1: flexfield definition (replace <TABLE_NAME>)
select
fa.application_id,
fa.application_short_name,
fdfv.descriptive_flexfield_name,
fdfv.title,
fdfv.application_table_name,
fdfv.context_column_name,
fdfv.context_user_override_flag,
fdfv.default_context_field_name
from
fnd_descriptive_flexs_vl fdfv,
fnd_application fa
where
fdfv.application_table_name='<TABLE_NAME>' and
fdfv.descriptive_flexfield_name not like '$SRS$.%' and
fdfv.application_id=fa.application_id;

--Query 2: contexts and segments (replace <APPLICATION_ID> and <FLEXFIELD_NAME>)
select
fdfcv.descriptive_flex_context_code context_code,
fdfcv.descriptive_flex_context_name context_name,
fdfcu.application_column_name,
fdfcu.form_left_prompt,
ffvs.flex_value_set_name,
ffvs.validation_type,
ffvs.format_type,
fdfcu.required_flag,
fdfcu.display_flag
from
fnd_descr_flex_contexts_vl fdfcv,
fnd_descr_flex_col_usage_vl fdfcu,
fnd_flex_value_sets ffvs
where
fdfcv.application_id=<APPLICATION_ID> and
fdfcv.descriptive_flexfield_name='<FLEXFIELD_NAME>' and
fdfcv.enabled_flag='Y' and
fdfcv.application_id=fdfcu.application_id and
fdfcv.descriptive_flexfield_name=fdfcu.descriptive_flexfield_name and
fdfcv.descriptive_flex_context_code=fdfcu.descriptive_flex_context_code and
fdfcu.enabled_flag='Y' and
fdfcu.flex_value_set_id=ffvs.flex_value_set_id(+)
order by
fdfcv.global_flag desc,
fdfcv.descriptive_flex_context_code,
fdfcu.column_seq_num;

--Query 3: attribute columns of the table and their length (replace <TABLE_NAME> and <FAMILY>, e.g. ATTRIBUTE)
select
atc.owner,
count(*) attribute_columns,
max(atc.data_length) max_length
from
all_tab_columns atc
where
atc.table_name='<TABLE_NAME>' and
regexp_like(atc.column_name,'^<FAMILY>\d+$')
group by
atc.owner;

--Is the Blitz Report build recent enough? Must return P_COLUMN_PREFIX.
select
aa.argument_name
from
all_arguments aa
where
aa.package_name='XXEN_FND_UPLOAD' and
aa.object_name='VALIDATE_DFF_ATTRIBUTES' and
aa.argument_name='P_COLUMN_PREFIX';
