---
description: "Deploy PL/SQL to the Development Instance: Deploy PL/SQL package changes to the development instance."
---

# Deploy PL/SQL to the Development Instance

Deploy PL/SQL package changes to the development instance.

## Connection

- Connect to the development instance as described in `blitz-environment.md` (SQL*Plus on its apps tier, or a SQL*Plus client that can read the package files). DB login is `apps/$APPS_PWD`.

## Instructions

1. Identify modified PL/SQL via `git status` / `git diff` (your packages, e.g. `sql/extensions/*.pks` / `*.pkb`).
2. Compile **spec (`.pks`) before body (`.pkb`)** when both changed — otherwise the body may fail (e.g. PLS-00307) and leave the package invalid → ORA-04063 at runtime.
3. Packages may contain `&` and some `.pkb` lack a trailing `/`, so always `set define off` and add an explicit `/`:
   ```bash
   printf 'set define off\nwhenever sqlerror continue\n@<path>/XXEN_MY_PKG.pks\n/\nshow errors\nexit\n' | sqlplus -s apps/$APPS_PWD
   ```
   Repeat for the `.pkb`.
4. After each file, check `show errors` and confirm the object is `VALID`:
   ```bash
   echo "select object_name,object_type,status from all_objects where owner='APPS' and object_name='XXEN_MY_PKG';" | sqlplus -s apps/$APPS_PWD
   ```
5. **If the package SPEC signature changed** (a public subprogram or its parameters added/changed/removed), every dependent is invalidated. Recompile them so users don't hit ORA-04063:
   ```bash
   echo "exec dbms_utility.compile_schema(schema=>'APPS', compile_all=>FALSE);" | sqlplus -s apps/$APPS_PWD
   ```
   (Pre-existing Vision invalids that fail with ORA-00942/PLS-00302/datatype errors are unrelated noise — only worry about objects your change touched.)
6. Report the deployment results (objects compiled, VALID status).

## Arguments

If a specific package name is provided as $ARGUMENTS, only deploy that package. Otherwise, deploy all modified packages found in git status.
