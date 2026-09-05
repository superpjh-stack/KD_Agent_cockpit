# Company and process adaptation

Use this reference when changing companies, industries, or target processes.

## Required fact sheet

Capture the legal/company name, product family, end-to-end process, current systems, documents, equipment, identifiers, pain points, available measurements, confirmed baselines, target KPIs, users, and approval owners. If these are incomplete, create only a clearly labeled demo and list the gaps.

## Domain mapping

| Factory pattern | Primary identifier | Context rail | Useful recommendations |
|---|---|---|---|
| Food/fermentation | raw/process/pack LOT | CCP, temperature, pH, release | deviation, trace, inventory, release evidence |
| Printing/textile | order/fabric/print LOT | color, defects, stock, shipment | ΔE, LOT trace, rework, claims |
| Project fabrication | project/drawing/material LOT | due date, revision, procurement, FAT | margin, delay, material, FAT |
| Press/molding | work order/die/equipment/time | cycle, condition, maintenance, quality | anomaly, die life, downtime, inspection |
| Assembly/logistics | work order/serial/location | takt, shortages, WIP, shipment | bottleneck, picking, shortage, delivery |

Select only the row that fits the confirmed process. Do not import adjacent industry features for visual richness.

## Structured retrieval design

For every factory tool, define user decision, source, fields, units, update cycle, key, data-quality rule, output, exception path, and approval owner. Align Job/LOT/project/equipment/time consistently. Prefer read-only views or APIs. Include provenance such as `demo_data`, source system, and last-updated time.

## Recommended-question design

Create categories around actual decisions rather than system modules. Good categories include integrated situation, schedule, material/procurement, quality/release, equipment/maintenance, and claims. Each question should be answerable by at least one implemented tool or indexed document. Remove questions whose data path does not exist.

## KPI and model language

Keep confirmed baseline, target, prediction, and achieved result separate. A prototype score is never an achieved KPI. For prediction use cases, define label owner, time-based holdout, offline metric, operational KPI, alert lead time, approval action, drift, retraining, and rollback before suggesting production automation.

