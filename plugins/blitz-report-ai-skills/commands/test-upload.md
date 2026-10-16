---
description: "Test Upload E2E: Run a full end-to-end upload test on the development instance (see `blitz-environment.md`)."
---

# Test Upload E2E

Run a full end-to-end upload test on the development instance (see `blitz-environment.md`).

## Arguments

$ARGUMENTS should contain the report/upload name (e.g., "AR Transaction Upload") and optionally test data specifications.

## Instructions

### Phase 1: Download Template

1. Connect as described in `blitz-environment.md` and run a PL/SQL block to download a fresh template:
   ```sql
   declare
   l_run_id number;
   l_request_id number;
   l_message varchar2(4000);
   begin
   fnd_global.apps_initialize(<user_id>,50553,101);
   mo_global.init('S');
   l_run_id:=xxen_api.create_run_id(<report_id>);
   -- Set required parameters (Operating Unit, Source, etc.) using:
   -- xxen_api.set_parameter_value_(p_parameter_name=>'Param', p_value=>'Value', p_report_name=>'Report Name', p_run_id=>l_run_id);
   l_message:=xxen_api.report_submit_concurrent(<report_id>, l_run_id, x_request_id=>l_request_id);
   commit;
   dbms_output.put_line('request_id: '||l_request_id);
   end;
   ```
2. Wait for request to complete, then locate the output XLSM file

### Phase 2: Modify Template

1. Extract the XLSM (it's a ZIP file) to a working directory on the server
2. Read the template headers from `xl/worksheets/sheet1.xml` to map column positions
3. Add test data rows by modifying shared strings and worksheet XML
4. Key rules:
   - Use shared string format (t="s" cells with shared string index references)
   - Column A = Action (set to "Create"), Column B = Status (set to "Valid")
   - Map data to correct column positions based on header names
   - Hidden columns (Operating Unit, Source, etc.) are at the END of the Excel
5. Repack the XLSM

### Phase 3: Upload

1. Copy the modified XLSM to /tmp on the server
2. Load into fnd_lobs via PL/SQL using bfilename('TMP', filename)
3. Submit via xxen_upload.submit_upload_process with p_template_name=>null
4. Wait for the concurrent request to complete

### Phase 4: Verify Results

1. Check the **main upload request** (from submit_upload_process) status — `status_code='C'` (Normal completion) is required
2. Check the **result report sub-request** — look in the main request log for "Request id: NNNNN" after "Report completed". Check that sub-request also completed normally (`status_code='C'`). A `status_code='E'` (Error) on the result report means the Success SQL or output generation failed.
3. Check upload data results in `xxen_upload_data` — verify `column2` (status) = 'S' and `column3` (message) shows expected outcome
4. Verify the actual data was created/updated in the target Oracle tables
5. Report success/failure with details

**CRITICAL: A "Normal completion" on the upload process request does NOT mean the upload succeeded end-to-end.** Always check:
- The result report sub-request status (errors here mean the Success SQL failed, e.g. ORA-01799 if outer join used with subquery)
- The row-level status in `xxen_upload_data`
- The actual database records

## Key IDs for Vision Instance

- User: your own EBS user (`select fu.user_id from fnd_user fu where fu.user_name='<YOUR_USER>'`). Not OPERATIONS: it has no `ICX_SESSIONS` rows, so the template download fails with `ORA-06502` in `DBMS_LOB`.
- Responsibility: responsibility_id=50553, application_id=101
- Operating Unit "Vision Operations": org_id=204
- AR Transaction Upload: report_id=515
- Batch Source "BR Manual": batch_source_id=1188

## Gotchas

- Python 2.7 on server (not 3), no Archive::Zip perl module
- openpyxl creates inline strings that Blitz parser can't read
- Oracle directory 'TMP' maps to /tmp for bfilename()
- set serveroutput on size 1000000 (not unlimited)
- Pass p_template_name=>null when no custom templates exist
