---
description: "Test Report: Test a Blitz Report by running the original Oracle standard report and the Blitz version with the same parameters, then comparing output."
---

# Test Report

Test a Blitz Report by running the original Oracle standard report and the Blitz version with the same parameters, then comparing output.

## Arguments

$ARGUMENTS should contain the Blitz Report name (e.g., "FA Tax Reserve Ledger") and optionally the original concurrent program name (e.g., "FADTXA").

## Instructions

Load and follow the `report-tester` skill. It provides the complete methodology for:
1. Finding test data that produces output (query data, check previous runs)
2. Running the Oracle standard report via `fnd_request.submit_request`
3. Running the Blitz Report via `xxen_api.report_submit_concurrent`
4. Comparing outputs: row counts, key aggregates, column presence, data spot-checks
5. Documenting discrepancies with root cause and fix suggestions

## Output

A comparison report showing:
- Whether both reports run successfully
- Row count and aggregate matches
- Any discrepancies with severity and suggested fixes
- Parameters used (for reproducibility)
