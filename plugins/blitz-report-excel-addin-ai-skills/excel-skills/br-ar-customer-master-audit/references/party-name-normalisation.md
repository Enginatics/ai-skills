# Normalising a party name for comparison

Two names are the same party name when their normalised forms are equal. The formula (Excel 365,
the name in A2) upper-cases the name, cuts it at `(FORMERLY`, `(FORMALLY` or `(EARLIER`, removes
`M/S`, turns `&` into `AND`, drops apostrophes, turns `. , - / ( )` into spaces and drops the
legal-form words:

```
=LET(s," "&UPPER(A2)&" ",
 t,IFERROR(TEXTBEFORE(s,{"(FORMERLY","(FORMALLY","(EARLIER"}),s),
 r,{" M/S."," ";" M/S "," ";"&"," AND ";"."," ";","," ";"-"," ";"/"," ";"("," ";")"," ";"'",""},
 c,REDUCE(t,SEQUENCE(ROWS(r)),LAMBDA(a,i,SUBSTITUTE(a,INDEX(r,i,1),INDEX(r,i,2)))),
 w,TEXTSPLIT(TRIM(c)," "),
 k,FILTER(w,ISNA(XMATCH(w,{"PRIVATE","PVT","LIMITED","LTD","LLP","MS","MESSRS","THE","CO","COMPANY","CORPORATION","CORP","INC"})),""),
 TEXTJOIN(" ",TRUE,k))
```

Examples: `M/S. Vision Electricals Pvt. Ltd.` → `VISION ELECTRICALS`; `Acme Cables (India) Pvt. Ltd.`
→ `ACME CABLES INDIA`; `A&B Traders Co.` → `A AND B TRADERS`.

- INDIA stays in the name: it often tells two companies apart.
- Two different parties with the same normalised name are never a match for each other; they are
  candidates (in a duplicate check, a duplicate suspect).
- Beyond equal names, compare the remaining ones yourself: shared distinctive words (not a city,
  not a common word like INDUSTRIES or TRADERS), initials written out (`A B C` and `ABC`), a group
  name with a division. Claude may score them in script: word overlap as 2 × shared ÷ (words of A
  + words of B), and character similarity; 0.90 and clearly ahead of the next name is a
  suggestion, 0.75 a candidate. Copilot compares the lists itself. A suggestion is shown with its
  evidence and confirmed by the user, never applied on its own.
