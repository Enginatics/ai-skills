# Explaining an AR to GL difference

`AR Aging to GL Reconciliation` compares, per receivable account, the GL balance at the end of the
period with the open AR balance of the aging, and shows the reconciling items between them. Run it
for the ledger, period and Period From (always passed, the first period of the financial year)
with the template `Customer Differences` (Show Customers=Yes, Differences Only=Yes, Show Monthly
Movement=Yes) to get the customers behind a difference.

A drill with `GL Account Analysis` over several periods passes `Period=` empty with Period From and
Period To: omitted, the add-in adds the latest period as Period and the drill returns that one
period only.

## The reconciling items and what explains each
| Column | What it is | How to explain it | Action |
|---|---|---|---|
| Opening Difference | difference carried in from before Period From | run again with an earlier Period From until it is zero, then explain that period | none in this period |
| Manual Journals, Other Source Journals | GL journals on the receivable account that no Receivables accounting stands behind (manual, spreadsheet, revaluation, provisions) | `GL Account Analysis` for the account and range with Journal Source set to each source: list the journals | expected ones (revaluation, provisions) stay as reconciling items; a journal posted to the wrong account → reclass journal |
| Not Transferred to GL, Not Posted in GL | Receivables accounting that has not reached GL yet | timing | run Transfer Journal Entries to GL, post the journals |
| Not Accounted | transactions, receipts and adjustments without accounting | `AR Unaccounted Transaction Sweep` (Sweep Now = No) lists them | run Create Accounting |
| Subledger Manual Entries | manual subledger journal entries | list them from the subledger | as for manual journals |
| GL to Subledger Difference (account rows) | GL lines from Receivables that do not match their subledger lines: a journal imported twice, a GL line changed after transfer | `GL Account Analysis` with Journal Source = Receivables, per batch and period: the batch with no subledger counterpart | reverse the duplicate journal |
| AR to Subledger Difference (customer rows) | the customer's subledger accounting on the account differs from its open AR | `AR Transactions and Lines` for the customer and period, and `GL Account Analysis` with the customer's number on the account | depends on the cause, below |

Causes of an AR to Subledger Difference on a customer:
- **Cross-customer application**: a receipt of one customer applied to another customer's invoice.
  The two customers' differences on the same account cancel; the account is right. Pair them:
  same account, equal and opposite within 0.01, largest amounts first, each customer in one pair
  only. No action.
- **Transaction accounted to another account**: a credit or debit memo whose receivable or revenue
  line went to an account the aging does not hold it on (the memo's distribution set by hand). The
  transaction's distributions show it. Action: reclass journal.
- **Not accounted netting or adjustment**: an event the report could not classify as not
  accounted; check `AR Unaccounted Transaction Sweep` for the customer. Action: Create Accounting.

## Writing the explanation
One row per explained item on `AR_GL_Explained`: Account, Customer (blank for an account item),
Amount, Cause, Evidence (journal, batch, transaction or receipt numbers), Action, Who (`Run a
program`, `Reclass journal`, `None`). The explained amounts plus the unexplained remainder add back
to the account's Closing Difference; state the remainder.

## Act
This skill does not book anything. A reclass journal goes to **br-gl-account-coder**, whose gated
journal step stages it through the GL Journal Upload with the user's confirmation; programs (Create
Accounting, Transfer Journal Entries to GL, posting) are run by the user.
