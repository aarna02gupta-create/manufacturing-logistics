# Data dictionary

All logistics data are synthetic. Currency is INR; weight is kg. No foreign exchange conversion is involved.

| Table | Grain | Key | Purpose |
|---|---|---|---|
| dim_customer | One fictional customer | customer_id | Name and customer segment |
| dim_carrier | One fictional forwarder | carrier_id | Carrier comparisons; forwarders can arrange all modes |
| dim_route | One origin/destination lane | route_id | Geography, domestic/export classification and fictional rate multiplier |
| dim_date | One calendar day | date_key | Dispatch-date filtering and chronological sorting |
| pipeline_run_log | One automated pipeline execution | run_id | Start/end time, status, processed-row count and diagnostic message |
| fact_shipment | One completed shipment | shipment_id | Dates, weights, modes and costs |

## Shipment fields

| Field | Meaning |
|---|---|
| shipment_id | Unique generated SIM identifier |
| ship_date_key | YYYYMMDD integer linked to dim_date; use calendar_date for date calculations |
| customer_id, carrier_id, route_id | Required foreign keys |
| planned_mode | Original assumed transport plan: Road, Sea or Air |
| actual_mode | Simulated executed transport mode; may upgrade Sea to Air |
| weight_kg | Positive shipment weight with two decimal places |
| promised_delivery_date | Dispatch plus assumed planned-mode transit time |
| actual_delivery_date | Simulated completed delivery date |
| base_freight_inr | Simulated transport charge before other components |
| fuel_surcharge_inr | Simulated fuel surcharge |
| handling_charge_inr | Simulated handling fee |
| expedite_fee_inr | Explicit simulated expedite fee, zero if not expedited |
| recorded_freight_inr | Sum of the four recorded charge components |
| baseline_rate_inr_kg | Illustrative planned-mode reference rate including route multiplier |
| baseline_fuel_inr | 12% of the rounded planned transport amount |
| baseline_handling_inr | Illustrative INR 1,800 handling assumption |
| modeled_baseline_inr | Rounded weight × baseline rate + baseline fuel + baseline handling |
| expedited_flag | 1 expedited; 0 standard. Expedited does not necessarily mean late |
| delay_reason | Fictional reason only for a late delivery; otherwise None |
| data_type | SYNTHETIC on every shipment, customer, carrier and route |

## Date dimension

`calendar_year` and `quarter_number` are calendar periods, not Indian financial years. `month_number` sorts month names; `year_month` is chronological YYYY-MM. A full date dimension does not establish shipment coverage in every month. Filter/report through the last included dispatch date.

## Analysis views

`vw_shipment_analysis` adds joined descriptions, ship_date, year_month, delay_days, on_time_flag, signed cost_variance_inr and cost_variance_ratio.

`vw_monthly_logistics` aggregates by dispatch month, calculates weighted freight per kg and ratio-of-totals cost variance. `on_time_delivery_ratio` uses all completed shipments in that cohort.

`vw_monthly_growth` adds the previous available month's recorded freight and freight_growth_ratio. All 20 observed months are present in version 1.0. If future loads have gaps, LAG means previous row, not necessarily previous calendar month; validate continuity before interpreting it as monthly growth.
