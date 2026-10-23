# Independent review
A separate read-only reviewer reproduced two important bugs: amendment before-money recomputed after another period freed advance capacity; legacy financial readers retained reversed entries. Both corrections were re-reviewed with four focused tests passing. The optional deduction-rate correction review found a legacy advance-cap bypass; the cap now applies whenever explicit workflow terms exist, with a dedicated 25+10=35 regression. No identity authentication or Windows/Office acceptance is claimed.

The coordinator additionally reproduced and corrected counterparty float loss, accrued costs/commitments misclassified as cash, reuse of historical bank references, Qt native teardown corruption, missing direct statement export, engineering-unit localization, and amended previous-period report quantities.

No tests were deleted or newly skipped. Three existing tests were updated because they previously treated costs/commitments as cash or omitted the separate actual legacy settlement row; their previous document, cost and report assertions remain, with new actual-cash assertions.
