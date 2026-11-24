# Checks of the customer master audit

Columns are those of `AR Customers and Sites` (Level=Site Use). The report repeats account and
party values on every site-use row: count a party- or account-level finding once per party or
account, a site finding once per site. Inactive rows are out unless a check says otherwise.

## Generic checks
| Check | Severity | Test | Fix Route |
|---|---|---|---|
| Same tax id, different parties | Review | Taxpayer Id equal on two or more Party Numbers | Master data team |
| Same name, different parties | Review | normalised Party Name equal on two or more Party Numbers (`party-name-normalisation.md`); near-identical names found by comparison are listed as suspects with their evidence | Master data team |
| Payment terms missing | Error | active account whose Account Profile Payment Term is blank and whose bill-to site uses have no Site Use Payment Term either | Payment Terms |
| No bill-to site | Error | active account without an active site use whose Site Use is Bill To | Master data team |
| No primary bill-to | Review | active account with bill-to site uses, none of them Primary Flag = Yes | Master data team |
| Address line too short | Error | Address1 shorter than 3 characters on an active site | Master data team |
| Postal code missing | Review | Postal Code blank on an active site, in a country that uses postal codes | Master data team |
| State missing | Error | State blank on an active site in a country with states (India) | Master data team |
| Inactive party, active account | Error | Party Status inactive while Account Status is active | Master data team |
| Credit check without a limit | Review | Credit Check = Yes and no Credit Limit (blank or 0) on the account profile | Credit Limit |
| Limit without credit check | Review | Credit Limit > 0 and Credit Check not Yes | Credit Check |
| Credit limit on advance terms | Policy | Credit Limit > 0 on an account whose payment term is in the user's advance list | Credit Limit |
| Collector missing | Policy | Collector Name blank on an active account (only when the user requires it) | Master data team |
| Default warehouse missing | Policy | Warehouse blank on an active account (only when the user requires it) | Master data team |

A missing value compares as an empty string: test it with `=LEN(TRIM(x))=0`, never `x=""` on a
number column, and score blanks as 0 in any ranking.

## India checks (GSTIN and PAN)
| Check | Severity | Test | Fix Route |
|---|---|---|---|
| GSTIN invalid | Error | GSTIN formula below gives `Length`, `Format`, `PAN entity type` or `Check digit` | Master data team |
| GSTIN missing | Review | active Bill To or Ship To site in India without a GSTIN (the customer may be unregistered; the user decides) | Master data team |
| GSTIN state mismatch | Error | the GSTIN's first two digits differ from the GST state code of the site's State | Master data team |
| PAN invalid | Error | PAN formula below gives `Format` or `PAN entity type` on Taxpayer Id | Taxpayer Id, proposed value the PAN of the party's valid GSTINs when they all carry the same one |
| PAN missing | Review | Taxpayer Id blank | Taxpayer Id, proposed value as above |
| PAN differs from GSTIN | Error | a valid GSTIN whose characters 3 to 12 are not the Taxpayer Id | Master data team (which of the two is right is a judgement) |

GSTIN in A2 (result `OK`, `Missing`, `Length`, `Format`, `PAN entity type` or `Check digit`):
```
=LET(g,UPPER(TRIM(A2)),c,"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
 IF(g="","Missing",IF(LEN(g)<>15,"Length",
 LET(ch,MID(g,SEQUENCE(15),1),cd,CODE(ch),dg,(cd>=48)*(cd<=57),lt,(cd>=65)*(cd<=90),
  pat,{1;1;2;2;2;2;2;1;1;1;1;2;3;2;3},
  okf,AND(IF(pat=1,dg,IF(pat=2,lt,dg+lt))=1,MID(g,13,1)<>"0"),
  IF(NOT(okf),"Format",IF(ISERROR(FIND(MID(g,6,1),"ABCFGHJLPT")),"PAN entity type",
  LET(v,SEARCH(MID(g,SEQUENCE(14),1),c)-1,p,v*IF(ISODD(SEQUENCE(14)),1,2),s,SUM(QUOTIENT(p,36)+MOD(p,36)),
   IF(MID(c,MOD(36-MOD(s,36),36)+1,1)=MID(g,15,1),"OK","Check digit"))))))))
```
PAN in A2 (result `OK`, `Missing`, `Format` or `PAN entity type`):
```
=LET(p,UPPER(TRIM(A2)),IF(p="","Missing",IF(LEN(p)<>10,"Format",
 LET(cd,CODE(MID(p,SEQUENCE(10),1)),pat,{2;2;2;2;2;1;1;1;1;2},
  IF(NOT(AND(IF(pat=1,(cd>=48)*(cd<=57),(cd>=65)*(cd<=90))=1)),"Format",
  IF(ISERROR(FIND(MID(p,4,1),"ABCFGHJLPT")),"PAN entity type","OK"))))))
```
The PAN inside a GSTIN is `MID(g,3,10)`.

## GST state codes
Write this table on the helper sheet and look the site's State up in it (upper case, trimmed). A
state that is not in the table is `State not checked`, never a mismatch.

| Code | State (and spellings found in customer masters) |
|---|---|
| 01 | JAMMU AND KASHMIR |
| 02 | HIMACHAL PRADESH |
| 03 | PUNJAB |
| 04 | CHANDIGARH |
| 05 | UTTARAKHAND, UTTARANCHAL |
| 06 | HARYANA |
| 07 | DELHI, NEW DELHI |
| 08 | RAJASTHAN |
| 09 | UTTAR PRADESH |
| 10 | BIHAR |
| 11 | SIKKIM |
| 12 | ARUNACHAL PRADESH |
| 13 | NAGALAND |
| 14 | MANIPUR |
| 15 | MIZORAM |
| 16 | TRIPURA |
| 17 | MEGHALAYA |
| 18 | ASSAM |
| 19 | WEST BENGAL |
| 20 | JHARKHAND |
| 21 | ODISHA, ORISSA |
| 22 | CHHATTISGARH |
| 23 | MADHYA PRADESH |
| 24 | GUJARAT |
| 26 | DADRA AND NAGAR HAVELI AND DAMAN AND DIU, DADRA AND NAGAR HAVELI, DAMAN AND DIU (older GSTINs of Daman and Diu start with 25: accept both) |
| 27 | MAHARASHTRA |
| 29 | KARNATAKA |
| 30 | GOA |
| 31 | LAKSHADWEEP |
| 32 | KERALA |
| 33 | TAMIL NADU |
| 34 | PUDUCHERRY, PONDICHERRY |
| 35 | ANDAMAN AND NICOBAR ISLANDS |
| 36 | TELANGANA |
| 37 | ANDHRA PRADESH |
| 38 | LADAKH (registrations made before Ladakh became a union territory start with 01: accept both) |
| 97 | OTHER TERRITORY |
