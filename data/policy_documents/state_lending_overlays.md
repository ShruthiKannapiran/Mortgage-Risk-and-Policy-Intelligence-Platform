# State-Specific Lending Overlays

## Overview
Certain states impose additional requirements beyond federal and investor guidelines.

## Section 1: Notable State Overlays
- **New York**: requires a state-specific pre-closing disclosure at least 3 business
  days before closing, in addition to federal TRID timing.
- **Texas**: home-equity (Section 50(a)(6)) loans are capped at 80% LTV regardless of
  loan program, and require a 12-day cooling-off period after application.
- **California**: higher-cost mortgage loans are subject to additional disclosure and
  are reviewed by the compliance team before approval.
- **Illinois**: predatory-lending database checks are mandatory for all loans in Cook
  County prior to closing.

## Section 2: Application
State overlays apply based on `property_state`, not the borrower's mailing address, and
are enforced in addition to (never in place of) federal requirements.
