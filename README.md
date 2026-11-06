# Enginatics AI Skills for Oracle E-Business Suite

AI skills for [Blitz Report](https://www.enginatics.com), maintained by Enginatics and used daily by our own development team. Skills and rules here update with every Blitz Report release. This repository is generated; send feedback to support@enginatics.com.

| Plugin | For | Works with |
|---|---|---|
| `blitz-report-ai-skills` | Developers: build, convert, test and tune Blitz Reports and Blitz Uploads | Claude Code |
| `blitz-report-excel-addin-ai-skills` | Business users: run EBS business processes from Excel through the Blitz Report add-in | Claude in Excel, Microsoft 365 Copilot in Excel |

```
/plugin marketplace add enginatics/ai-skills
/plugin install blitz-report-ai-skills@enginatics
/plugin install blitz-report-excel-addin-ai-skills@enginatics
```

To receive updates automatically, enable auto-update for the `enginatics` marketplace in `/plugin` > Marketplaces, or run `/plugin marketplace update enginatics`.

## Development skills

Run `/blitz-report-ai-skills:blitz-environment-setup` once. It creates `.claude/rules/blitz-environment.md` in your project, describing how Claude reaches your EBS development instance. Never point it at production.

Main workflows:

| Command | What it does |
|---|---|
| `/blitz-report-ai-skills:migrate-custom-reports` | Turns the zip from the Blitz Report Custom Reports Converter into Blitz Reports on your conversion instance |
| `/blitz-report-ai-skills:convert-report` | Converts an Oracle RDF, BI Publisher or concurrent program report into a Blitz Report |
| `/blitz-report-ai-skills:build-upload` | Builds a Blitz Upload (XML and PL/SQL package) from an Oracle form or API |
| `/blitz-report-ai-skills:review-upload`, `/blitz-report-ai-skills:test-upload` | Reviews an upload against the Oracle form and tests it end to end |
| `/blitz-report-ai-skills:test-report` | Compares a converted report's output with the original |
| `/blitz-report-ai-skills:tune-report-performance` | Finds and fixes expensive report SQL |

The plugin also carries the rules our team works by (coding standards, report and upload development, EBS API patterns, 11i compatibility, migrations); Claude loads them when the task needs them.

Requirements: Blitz Report installed on the EBS development instance, and database access from Claude Code to that instance (Oracle SQLcl MCP server, SQLcl or SQL*Plus).

## Excel add-in skills

The skills run inside Excel through the Blitz Report Excel add-in. Run `/blitz-report-excel-addin-ai-skills:excel-skills-setup` to install or update them in Claude in Excel or Microsoft 365 Copilot in Excel and to see which skill does what.

Without Claude Code:
- Claude in Excel: upload `plugins/blitz-report-excel-addin-ai-skills/zips/<name>.zip` (Customize > Skills > Create skill).
- Microsoft 365 Copilot in Excel: copy the folder `plugins/blitz-report-excel-addin-ai-skills/excel-skills/<name>` into `Documents/Copilot/Microsoft Excel/Skills` in your OneDrive.
- All skill folders in one zip: `blitz-report-excel-addin-ai-skills.zip` in the latest release.

## Use cases

What to ask, and the skills and Blitz Reports that answer it. Skills marked *writes to EBS* stage the change in Excel and submit it only after you confirm.

### Month-End Close Command Centre

A finance lead asks one question and gets a red, amber or green scorecard per module, the ranked blockers and the recommended close sequence, assembled by an orchestrator that delegates to a specialist skill per module.

**Close readiness, one question**: "Are we ready to close May?" · "What is still blocking the period close, module by module?" · "Give me the close scorecard for AP, AR, inventory, assets and GL, with the blockers ranked."  
Skills: `br-month-end-readiness`, `br-ap-close-readiness`, `br-ar-close-readiness`, `br-inv-cost-close-readiness`, `br-fa-close-readiness`, `br-gl-close-readiness`  
Reports: AP Period Close Exceptions, AP Trial Balance, AR Unaccounted Transaction Sweep, AR Autoinvoice Interface Summary, INV Period Close Pending Transactions, CAC Inventory Pending Cost Adjustment, FA Unposted Mass Additions, GL Period Status, CAC Accounting Period Status

**Purchasing accrual leg**: "Does the receipt accrual tie out, and how big is the uninvoiced backlog?" · "Which uninvoiced receipts are the oldest and largest?" · "Is purchasing ready for the close?"  
Skills: `br-po-close-readiness`  
Reports: CST AP and PO Accrual Reconciliation, CST Uninvoiced Receipts, CAC Accounting Period Status

**Subledger-to-GL reconciliation**: "Do AP, AR, inventory and assets tie to the ledger for this period?" · "Where does the AP trial balance differ from the GL liability account?" · "Reconcile the subledgers to the general ledger for last month."  
Skills: `br-subledger-gl-reconciliation`  
Reports: AP Trial Balance, CST Period Close Subinventory Value, CST AP and PO Accrual Reconciliation, GL Trial Balance Detail

**Close-process health and bank reconciliation readiness**: "Are the close programs actually running clean, and is the bank reconciliation caught up?" · "Which concurrent programs failed or ran long during the close?" · "How many bank statement lines are still unreconciled, and how old are they?"  
Skills: `br-close-process-monitor`, `br-ce-recon-readiness`  
Reports: FND Concurrent Requests, CE Transactions Available for Reconciliation

**Financial statements and variance commentary**: "Refresh the income statement for this period and explain the main variances to last year." · "Why did operating expenses go up this month? Drill the largest movements to the journals." · "Compare actuals against budget by cost center and draft the variance commentary."  
Skills: `br-run-fsg`, `br-fsg-variance-analysis`  
Reports: GL Financial Statement and Drilldown (FSG), GL Account Analysis

**Finish a converted financial statement**: "Finish this statement converted from Spreadsheet Server: fix what the converter could not." · "Go through the conversion log of this workbook and tell me what still needs attention."  
Skills: `br-fsg-conversion-review`

### Cash and Working Capital

Four levers on the same goal, cash. Each is a standalone skill; the working-capital orchestrator runs them as one review.

**Duplicate payment recovery**: "Have we paid anyone twice in the last two years?" · "Find likely duplicate supplier invoices and rank them by amount at risk." · "Which duplicates are already paid and recoverable, and which can still be stopped?"  
Skills: `br-ap-duplicate-payments`  
Reports: AP Invoices and Lines, AP Invoice Payments

**Collections worklist with drafted follow-ups**: "Who do we chase this week, and what do we say to each of them?" · "Prioritise our overdue customers and draft a reminder for the top ten." · "Which customers have disputed invoices holding up collection?"  
Skills: `br-ar-collections-worklist`  
Reports: AR Aging, AR Disputed Invoice, AR Applied Receipts

**Customer credit risk and DSO**: "Which customers are a credit risk, and why is our DSO rising?" · "Which customers are close to or over their credit limit?" · "Break down DSO by customer segment and show the biggest contributors."  
Skills: `br-ar-credit-risk`  
Reports: AR Customer Credit Snapshot, AR Customer Credit Limits, AR Aging, AR Customer Open Balances Period Lookback, AR Applied Receipts

**Payment run optimization**: "What should this week's pay run look like: what do we capture, what can wait?" · "Which early payment discounts are worth taking this week?" · "Project the cash outflow for the next four weeks of supplier payments."  
Skills: `br-ap-payment-optimizer`  
Reports: AP Cash Requirement, AP Invoice on Hold

**AP holds analysis and working-capital review**: "What is stuck on hold, why, and what could we release?" · "Analyse our AP invoice holds: group them by reason and age, and show the oldest ones." · "Give me the full working-capital picture: payables, receivables and holds."  
Skills: `br-ap-holds-analysis`, `br-cash-working-capital`  
Reports: AP Invoice on Hold, AP Invoice Payments

**Payables dashboard**: "Build me a payables dashboard with invoices on hold, overdue and due this week." · "What needs action in AP today?"  
Skills: `br-ap-intelligence`  
Reports: AP Cash Requirement

### Closed Loops: From Analysis to Action

The AI finds it, stages the fix in EBS, and a human approves it. Every write goes through a shipped Blitz Upload: standard Oracle APIs, row-level validation, double confirmation with the money named, and a concurrent request audit trail.

**Invoice entry from documents** (writes to EBS): "Here are this week's supplier PDFs: stage them as AP invoices." · "Enter this invoice into Payables and tell me what does not match the supplier record." · "Load these scanned invoices, but stop if any of them already exists."  
Skills: `br-ap-invoice-upload`  
Reports: AP Invoice Upload

**Release the holds we can** (writes to EBS): "Action the holds analysis: release what qualifies." · "Release the price holds under our tolerance and tell me which ones you left."  
Skills: `br-ap-hold-release`  
Reports: AP Invoice Hold Upload

**Block the duplicates before they pay** (writes to EBS): "Put the unpaid duplicate suspects on hold before the next pay run." · "Hold the suspected duplicate invoices and note the evidence for the AP reviewer."  
Skills: `br-ap-duplicate-hold`  
Reports: AP Invoice Hold Upload

**Log the collections worklist into EBS** (writes to EBS): "Record those follow-ups in Advanced Collections so the team sees them." · "Save a collection note for each customer on this week's worklist."  
Skills: `br-ar-collections-notes`  
Reports: IEX Collection Note Upload

**Act on the payment optimization** (writes to EBS): "Defer what we agreed to defer, and give me the pay-now list for Payments." · "Put the invoices we decided to pay next week on a payment hold with the reason."  
Skills: `br-ap-payment-actions`  
Reports: AP Invoice Hold Upload

**Account coding from the ledger's own history** (writes to EBS): "Which account does this belong to, and draft the reclass journal." · "Suggest the GL coding for these transactions based on how we coded them before." · "Find postings that look miscoded this quarter."  
Skills: `br-gl-account-coder`  
Reports: GL Journal Upload, GL Account Analysis

### Operations and Supply Chain

**Inventory exception triage**: "What is broken in inventory: negative stock, stuck transactions, counts in limbo?" · "Which inventory interface errors are blocking costing?" · "List the cycle counts waiting for approval and how long they have waited."  
Skills: `br-inv-exception-triage`  
Reports: INV Onhand Quantities, CAC Interface Error Summary, INV Cycle counts pending approval

**WIP job health and cost exposure**: "Which jobs are stuck, where does the WIP value sit, and what can we close?" · "Which discrete jobs are short of components?" · "Show the jobs with the largest variances before we close them."  
Skills: `br-wip-variance-analysis`  
Reports: WIP Entities, WIP Value, WIP Discrete Job Shortage, WIP Account Distribution

**Supplier risk scoring**: "Which suppliers should procurement review this quarter, and why, in one line each?" · "Which suppliers cause the most invoice holds and price variances?" · "Score our top suppliers on dependency, delivery and price stability."  
Skills: `br-supplier-risk-scoring`  
Reports: AP Invoices and Lines, AP Invoice on Hold, PO Invoice Price Variance, AP Suppliers, PO Vendor Service Performance Analysis

**3-way match exception triage**: "Why are these invoices on match hold, and whose problem is each one?" · "Which match holds are waiting for a receipt, and which are price differences?" · "Route the quantity and price holds to receiving, buyers or AP."  
Skills: `br-po-match-exceptions`  
Reports: AP Invoice on Hold, AP Invoices and Lines, PO Headers and Lines, PO Receipts/Deliveries Discrepancy

**Stock level optimization** (writes to EBS): "Are our min/max and safety stock settings right, and apply the approved changes." · "Recommend reorder points from the last twelve months of demand." · "How much working capital would the new safety stock levels free up?"  
Skills: `br-inv-stock-optimizer`  
Reports: INV Item Subinventory Upload, INV Safety Stock Upload, INV Item Demand History, INV Onhand Quantities, INV Safety Stocks

**Cycle count planning**: "What should we count next, and why is accuracy slipping?" · "Which high-value items have not been counted this year?" · "Where do our counts miss most often?"  
Skills: `br-inv-cycle-count-planner`  
Reports: INV Physical inventory accuracy analysis, INV Onhand Quantities

**BOM accuracy validation** (writes to EBS): "Is the bill right, or does the shop floor consume something else?" · "Which BOM components are never issued to jobs?" · "Correct the quantities per assembly where actual usage differs, after I approve them."  
Skills: `br-bom-validator`  
Reports: BOM Bill of Materials Upload, BOM Bill of Material Structure, WIP Required Components, WIP Discrete Job Shortage

### Platform and Governance

**Find the right report by meaning**: "Which report shows unapplied receipts by operating unit?" · "Which report shows supplier invoices on hold with the hold reason?" · "I need open purchase orders that were received but not invoiced: which report?"  
Skills: `br-report-finder`

**Run any report by asking**: "Run GL Account Analysis for last period and summarise the largest movements by account." · "Show me the open sales orders of my largest customer." · "Run the AR aging for my operating unit and chart the buckets."  
Skills: `br-run-reports`  
Reports: GL Account Analysis

**Upload from Excel by asking** (writes to EBS): "Upload this journal entry to the general ledger." · "Create these new suppliers from the sheet." · "Update the list prices on these items from my spreadsheet."  
Skills: `br-run-uploads`  
Reports: GL Journal Upload

**Who changed what, when**: "Who changed this supplier's bank account, and give me the audit window evidence." · "Who changed profile options or responsibilities in production last week?" · "Which users logged in with the System Administrator responsibility this month?"  
Skills: `br-audit-trail`  
Reports: FND Audit Setup, FND User Login History, FND User Responsibilities

**Compare two instances**: "Did the upgrade change the numbers? Is TEST really a copy of PROD?" · "Compare the profile option values between TEST and PROD and list the differences." · "Run the trial balance in both environments and show where they differ."  
Skills: `br-instance-diff`

**Write your own skill**: "Make a skill that lists the invoices on hold entered in the last three months, ranked by amount." · "Give me the holds analysis skill with our own thresholds and our custom AP report." · "Turn what we just did into a skill my team can run."  
Skills: `br-skill-author`

### Analyst Toolkit

Reusable techniques that work on the output of any Blitz Report; the themed skills above compose them.

**Anomaly detection**: "Check this AP invoice data for possible duplicates and unusual amounts." · "Which transactions in this sheet look wrong?" · "Run a Benford's Law test on these journal amounts."  
Skills: `br-anomaly-detection`

**Segmentation**: "Segment our customers by buying behaviour and name each group." · "Group these suppliers by spend pattern." · "Which items behave alike?"  
Skills: `br-clustering`

**Forecasting**: "Forecast next quarter's sales from this order history." · "Project cash collections for the next eight weeks." · "Forecast monthly demand for these items with a confidence range."  
Skills: `br-forecasting`

**Customer and vendor value segments**: "Who are our best customers, and who is at risk of lapsing?" · "Run an RFM analysis on this year's invoices." · "Which customers should we target for win-back?"  
Skills: `br-rfm-analysis`

**Dashboards on any report**: "Build a dashboard from this sheet with KPI cards and slicers." · "Turn this report into an interactive summary for management."  
Skills: `br-data-dashboard`

### Blitz Report Development with Claude Code

For developers: Claude Code builds, converts, tests and tunes Blitz Reports and Uploads with the Enginatics development skills.

**Create a report**: "Create a Blitz Report listing open purchase orders with receipts and invoices per line." · "Add a supplier site parameter to this report." · "Turn this SQL into a Blitz Report with parameters and lists of values."  
Skills: `blitz-report-developer`

**Convert Oracle reports**: "Convert our custom RDF invoice register to a Blitz Report and test it." · "Convert this BI Publisher report to Blitz Report." · "Analyse this Oracle report and list its queries and parameters."  
Skills: `convert-bip-and-rdf-reports-to-blitz`, `rdf-analyzer`

**Migrate custom reports and WebADI integrators**: "Migrate the custom reports from this converter export to Blitz Reports." · "Turn our WebADI journal integrator into a Blitz Upload." · "Which of these custom reports are already covered by a standard Blitz Report?"  
Skills: `migrate-custom-reports`, `migrate-webadi`

**Test against the original**: "Test the new Blitz Report against the standard Oracle report with last month as parameters." · "Compare the output of both reports row by row and explain the differences."  
Skills: `report-tester`

**Tune a slow report**: "This report takes 10 minutes. Find what makes it slow and tune the SQL." · "Measure the buffer gets per row of this report and fix the expensive part."  
Skills: `tune-report-performance`

**Build and validate an upload**: "Build an upload to update supplier site payment terms through the public API." · "Analyse the Oracle form for this upload and list its validations." · "Review this upload against the Oracle form and test it end to end."  
Skills: `upload-builder`, `oracle-forms-analyzer`, `upload-validator`

**Extend an upload with flexfields**: "Add the invoice descriptive flexfield columns to this upload, with validation." · "Make attribute5 of this upload validate against its value set."  
Skills: `add-dff-to-upload`

**Fix a zip Oracle cannot read**: "The upload of this zip fails in Oracle: repack it so the import reads it."  
Skills: `fix-zip-compatibility`

**Set up the AI skills**: "Install the Blitz Report skills in Excel." · "Which Blitz Report skill fits reconciling AR to the general ledger?" · "Set up Claude Code for Blitz Report development on our instance."  
Skills: `excel-skills-setup`, `blitz-environment-setup`

## License

MIT, see [LICENSE](LICENSE). You may use, adapt and redistribute the skills, for example as reference material for your own assistant, keeping the copyright notice.

## Feedback

support@enginatics.com
