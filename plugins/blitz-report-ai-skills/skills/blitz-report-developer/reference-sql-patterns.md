# Common SQL Patterns for Blitz Reports

## EBS Module Tables Reference

### Accounts Payable (AP)
```sql
-- Suppliers
ap_suppliers aps
ap_supplier_sites_all assa

-- Invoices
ap_invoices_all aia
ap_invoice_lines_all aila
ap_invoice_distributions_all aida

-- Payments
ap_checks_all aca
ap_invoice_payments_all aipa
```

### Accounts Receivable (AR)
```sql
-- Customers
hz_parties hp
hz_cust_accounts hca
hz_cust_account_sites_all hcasa
hz_cust_site_uses_all hcsua

-- Transactions
ra_customer_trx_all rcta
ra_customer_trx_lines_all rctla
ar_payment_schedules_all apsa

-- Receipts
ar_cash_receipts_all acra
ar_receivable_applications_all araa
```

### General Ledger (GL)
```sql
-- Ledgers and COA
gl_ledgers gl
gl_code_combinations gcc
gl_code_combinations_kfv gcck  -- with concatenated segments

-- Journals
gl_je_batches gjb
gl_je_headers gjh
gl_je_lines gjl

-- Balances
gl_balances gb
```

### Inventory (INV)
```sql
-- Items
mtl_system_items_b msib
mtl_system_items_vl msiv

-- Organizations
mtl_parameters mp
hr_all_organization_units haou

-- Transactions
mtl_material_transactions mmt
mtl_transaction_types mtt

-- On-hand
mtl_onhand_quantities_detail moqd
```

### Order Management (OM/ONT)
```sql
-- Orders
oe_order_headers_all ooha
oe_order_lines_all oola

-- Lookups
oe_transaction_types_tl ottt
oe_lookups ol
```

### Purchasing (PO)
```sql
-- Purchase Orders
po_headers_all pha
po_lines_all pla
po_line_locations_all plla
po_distributions_all pda

-- Requisitions
po_requisition_headers_all prha
po_requisition_lines_all prla

-- Receipts
rcv_transactions rt
rcv_shipment_headers rsh
rcv_shipment_lines rsl
```

## Common Join Patterns

### Operating Unit Join
```sql
from
hr_all_organization_units_vl haouv,
ap_invoices_all aia
where
aia.org_id=haouv.organization_id and
haouv.name=:p_operating_unit
```

### Ledger Join
```sql
from
gl_ledgers gl,
gl_je_headers gjh
where
gjh.ledger_id=gl.ledger_id and
gl.name=:p_ledger
```

### Item Join with Inventory Org
```sql
from
mtl_parameters mp,
mtl_system_items_vl msiv
where
msiv.organization_id=mp.organization_id and
mp.organization_code=:p_organization
```

### Customer Join
```sql
from
hz_parties hp,
hz_cust_accounts hca,
ra_customer_trx_all rcta
where
rcta.bill_to_customer_id=hca.cust_account_id and
hca.party_id=hp.party_id
```

### Supplier Join
```sql
from
ap_suppliers aps,
ap_supplier_sites_all assa,
ap_invoices_all aia
where
aia.vendor_id=aps.vendor_id and
aia.vendor_site_id=assa.vendor_site_id
```

## Utility Functions

### Display Lookup Value
```sql
xxen_util.meaning(aia.invoice_type_lookup_code,'INVOICE TYPE',200) invoice_type
```

### Display Yes/No Flag
```sql
xxen_util.yes(aps.hold_flag) hold
```

### Display User Name
```sql
xxen_util.user_name(aia.created_by) created_by
```

### Display Date in Client Timezone
```sql
xxen_util.client_time(aia.creation_date) creation_date
```

### Get Concatenated Segments
```sql
(select gcck.concatenated_segments from gl_code_combinations_kfv gcck
 where gcck.code_combination_id=aida.dist_code_combination_id) account
```

### Get Description from KFV
```sql
(select gcck.concatenated_segments||' - '||gcck.description from gl_code_combinations_kfv gcck
 where gcck.code_combination_id=aida.dist_code_combination_id) account_desc
```

## Parameter Patterns

### Operating Unit LOV
```xml
<PARAMETER_TYPE_DSP>LOV</PARAMETER_TYPE_DSP>
<LOV_NAME>Operating Unit</LOV_NAME>
```

### Ledger LOV
```xml
<PARAMETER_TYPE_DSP>LOV</PARAMETER_TYPE_DSP>
<LOV_NAME>Ledger</LOV_NAME>
```

### Date Range
```xml
<PARAMETERS_ROW>
  <PARAMETER_TYPE_DSP>Date</PARAMETER_TYPE_DSP>
  <PARAMETER_TRANSLATIONS>
    <PARAMETER_TRANSLATIONS_ROW>
      <LANGUAGE>US</LANGUAGE>
      <PARAMETER_NAME>Date From</PARAMETER_NAME>
    </PARAMETER_TRANSLATIONS_ROW>
  </PARAMETER_TRANSLATIONS>
</PARAMETERS_ROW>
```

### Multi-Select LOV
Use anchor pattern with SQL injection:
```xml
<ANCHOR>:p_supplier_name</ANCHOR>
<SQL_TEXT>aps.vendor_name in (select regexp_substr(:p_supplier_name,'[^~]+',1,level) from dual connect by level&lt;=regexp_count(:p_supplier_name,'~')+1)</SQL_TEXT>
```

## Upload Standard Columns

Always start uploads with:
```sql
select
null action_,
null status_,
null message_,
null modified_columns_,
-- data columns follow
```

## Common Subqueries

### Last Invoice Date
```sql
(select trunc(max(aia.invoice_date)) from ap_invoices_all aia
 where aia.vendor_id=aps.vendor_id) last_invoice_date
```

### Open Balance
```sql
(select sum(apsa.amount_due_remaining) from ar_payment_schedules_all apsa
 where apsa.customer_trx_id=rcta.customer_trx_id) open_balance
```

### Item On-Hand
```sql
(select sum(moqd.transaction_quantity) from mtl_onhand_quantities_detail moqd
 where moqd.inventory_item_id=msib.inventory_item_id
 and moqd.organization_id=msib.organization_id) on_hand_qty
```
