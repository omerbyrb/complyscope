# Risk scoring methodology

complyscope turns every failed control into a **risk**: something that could go wrong
because the control is not in place. This page defines how those risks are scored. The
code implements exactly these tables, and a test keeps the two in sync.

The approach follows the risk assessment process required by ISO/IEC 27001:2022 clause
6.1.2 (identify, analyse and evaluate risks, with an owner for each) using a simple,
widely used 5 × 5 likelihood and impact matrix that a small organisation can apply without
specialist tooling.

## Likelihood

How likely the risk is to happen within the next 12 months.

| Score | Label | Meaning |
|---|---|---|
| 1 | Rare | Would need unusual circumstances; no known exposure |
| 2 | Unlikely | Could happen, but no sign of exposure or interest |
| 3 | Possible | Exposed, but exploitation needs effort or insider knowledge |
| 4 | Likely | Exposed and exploitable with commonly available tools |
| 5 | Almost certain | Exposed to the internet and trivially or actively exploited |

## Impact

The worst realistic effect on the organisation if the risk happens.

| Score | Label | Meaning |
|---|---|---|
| 1 | Negligible | No meaningful effect on operations, customers or data |
| 2 | Minor | Limited, internal disruption; quickly recovered |
| 3 | Moderate | Disruption to customers, or a small exposure of personal data |
| 4 | Major | Significant data breach, regulator notification or multi-day outage |
| 5 | Severe | Threatens the survival of the organisation |

## Risk score and level

**Risk score = likelihood × impact**, from 1 to 25.

| Level | Score | Review within |
|---|---|---|
| Low | 1–3 | 180 days |
| Medium | 4–6 | 90 days |
| High | 8–12 | 30 days |
| Critical | 15–25 | 14 days |

The 14 days for critical risks mirror the Cyber Essentials deadline for critical security
updates.

## Risk appetite

Risk appetite is the level of risk the organisation is willing to accept without further
action. The default appetite is:

- **Low** risks may be accepted.
- **Medium** risks may be accepted only by the risk owner, with a review date.
- **High** and **Critical** risks exceed the appetite and must be treated.

## Treatment

Each risk gets one treatment (ISO/IEC 27005 terms in brackets):

| Treatment | Meaning |
|---|---|
| Mitigate (modify) | Put controls in place to lower likelihood or impact |
| Accept (retain) | Knowingly keep the risk, within the risk appetite |
| Transfer (share) | Move part of the risk to a third party, e.g. insurance or a provider |
| Avoid | Stop the activity that creates the risk |

## Ownership

Every risk needs a **risk owner**: a named person with the authority to decide its
treatment and the budget to carry it out. complyscope never assigns owners itself.

## How complyscope drafts a risk

When a control fails, complyscope drafts one risk for it:

- **Likelihood** comes from the most severe finding behind the failure. All redscope
  evidence is seen from the internet, so exposure is already established:

  | Worst finding severity | Likelihood |
  |---|---|
  | critical | 5 |
  | high | 4 |
  | medium | 3 |
  | low | 2 |
  | info | 1 |

- **Impact** cannot be measured by a scan, because it depends on what the system does for
  the business. It is drafted as **3 (Moderate)** and marked *unconfirmed*.
- **Owner** is left empty, **treatment** defaults to *mitigate* and the **plan** is empty.
- The review date follows the level table above.

A drafted risk is a starting point. It is flagged until the owner is named, the impact is
confirmed and a plan is written. Accepting a risk above the appetite is flagged too.
