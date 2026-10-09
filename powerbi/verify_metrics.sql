-- Read-only checks for comparison with unfiltered Power BI cards.
USE portfolio_logistics;

SELECT
    COUNT(*) AS total_shipments,
    COUNT(*) - COUNT(DISTINCT shipment_id) AS duplicate_or_null_ids,
    SUM(CASE WHEN actual_delivery_date IS NULL OR promised_delivery_date IS NULL
        THEN 1 ELSE 0 END) AS missing_delivery_dates,
    SUM(CASE WHEN data_type IS NULL OR UPPER(TRIM(data_type)) <> 'SYNTHETIC'
        THEN 1 ELSE 0 END) AS non_synthetic_rows,
    SUM(recorded_freight_inr) AS recorded_freight_inr,
    SUM(modeled_baseline_inr) AS modeled_baseline_inr,
    SUM(recorded_freight_inr) - SUM(modeled_baseline_inr) AS cost_variance_inr,
    100.0 * (SUM(recorded_freight_inr) - SUM(modeled_baseline_inr))
        / NULLIF(SUM(modeled_baseline_inr), 0) AS cost_variance_pct,
    SUM(recorded_freight_inr) / NULLIF(COUNT(*), 0) AS freight_per_shipment_inr
FROM fact_shipment;

SELECT
    SUM(CASE WHEN actual_delivery_date <= promised_delivery_date
        THEN 1 ELSE 0 END) AS on_time_shipments,
    SUM(CASE WHEN actual_delivery_date > promised_delivery_date
        THEN 1 ELSE 0 END) AS delayed_shipments,
    100.0 * SUM(CASE WHEN actual_delivery_date <= promised_delivery_date
        THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN actual_delivery_date IS NOT NULL
            AND promised_delivery_date IS NOT NULL THEN 1 ELSE 0 END), 0)
        AS on_time_delivery_pct,
    AVG(CASE WHEN actual_delivery_date > promised_delivery_date
        THEN DATEDIFF(actual_delivery_date, promised_delivery_date) END)
        AS average_delay_days_delayed_only
FROM fact_shipment;

-- README finding 3: group by the executed transport mode.
SELECT actual_mode, COUNT(*) AS shipments,
    SUM(actual_delivery_date > promised_delivery_date) AS delayed_shipments,
    ROUND(100.0 * SUM(actual_delivery_date > promised_delivery_date)
        / NULLIF(COUNT(*), 0), 2) AS delay_rate_pct
FROM fact_shipment
GROUP BY actual_mode
ORDER BY actual_mode;

-- README key findings: carrier rates and route cost variance.
SELECT c.carrier_name, COUNT(*) AS shipments,
    SUM(f.actual_delivery_date <= f.promised_delivery_date) AS on_time_shipments,
    ROUND(100.0 * SUM(f.actual_delivery_date <= f.promised_delivery_date)
        / NULLIF(COUNT(*), 0), 2) AS on_time_delivery_pct
FROM fact_shipment f JOIN dim_carrier c ON c.carrier_id = f.carrier_id
GROUP BY c.carrier_id, c.carrier_name
ORDER BY on_time_delivery_pct DESC, c.carrier_id;

SELECT r.origin_city, r.destination_city, COUNT(*) AS shipments,
    SUM(f.recorded_freight_inr - f.modeled_baseline_inr) AS cost_variance_inr,
    ROUND(100.0 * SUM(f.recorded_freight_inr - f.modeled_baseline_inr)
        / NULLIF(SUM(f.modeled_baseline_inr), 0), 2) AS cost_variance_pct
FROM fact_shipment f JOIN dim_route r ON r.route_id = f.route_id
GROUP BY r.route_id, r.origin_city, r.destination_city
ORDER BY cost_variance_inr DESC, r.route_id;
