USE portfolio_logistics;
-- Expect 2400, 20 and the totals in validation_report.json.
SELECT COUNT(*) AS shipment_count,COUNT(DISTINCT d.`year_month`) AS months,
 SUM(f.recorded_freight_inr) AS recorded_freight_inr,
 SUM(f.modeled_baseline_inr) AS modeled_baseline_inr
FROM fact_shipment f JOIN dim_date d ON d.date_key=f.ship_date_key;

-- Each issue count should be zero.
SELECT 'delivery_before_dispatch' AS check_name, COUNT(*) AS issues
FROM fact_shipment f JOIN dim_date d ON f.ship_date_key=d.date_key
WHERE f.actual_delivery_date<d.calendar_date OR f.promised_delivery_date<d.calendar_date
UNION ALL
SELECT 'invoice_mismatch',COUNT(*) FROM fact_shipment
WHERE recorded_freight_inr<>base_freight_inr+fuel_surcharge_inr+handling_charge_inr+expedite_fee_inr
UNION ALL
SELECT 'baseline_mismatch',COUNT(*) FROM fact_shipment
WHERE modeled_baseline_inr<>ROUND(weight_kg*baseline_rate_inr_kg,2)+baseline_fuel_inr+baseline_handling_inr
UNION ALL
SELECT 'reason_date_mismatch',COUNT(*) FROM fact_shipment
WHERE (actual_delivery_date>promised_delivery_date AND delay_reason='None')
OR (actual_delivery_date<=promised_delivery_date AND delay_reason<>'None')
UNION ALL
SELECT 'non_synthetic_rows',COUNT(*) FROM fact_shipment WHERE data_type<>'SYNTHETIC';
