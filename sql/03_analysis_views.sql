USE portfolio_logistics;

-- One row per completed fictional shipment. Ratios are fractions, formatted as % in Power BI.
CREATE OR REPLACE VIEW vw_shipment_analysis AS
SELECT f.*, d.calendar_date AS ship_date, d.`year_month`,
 c.customer_name,c.segment,k.carrier_name,
 r.origin_city,r.destination_city,r.destination_country,r.route_type,
 GREATEST(DATEDIFF(f.actual_delivery_date,f.promised_delivery_date),0) AS delay_days,
 CASE WHEN f.actual_delivery_date<=f.promised_delivery_date THEN 1 ELSE 0 END AS on_time_flag,
 f.recorded_freight_inr-f.modeled_baseline_inr AS cost_variance_inr,
 (f.recorded_freight_inr-f.modeled_baseline_inr)/NULLIF(f.modeled_baseline_inr,0) AS cost_variance_ratio
FROM fact_shipment f
JOIN dim_date d ON f.ship_date_key=d.date_key
JOIN dim_customer c ON f.customer_id=c.customer_id
JOIN dim_carrier k ON f.carrier_id=k.carrier_id
JOIN dim_route r ON f.route_id=r.route_id;

-- Cohort basis: shipment/dispatch month, including those delivered in a subsequent month.
CREATE OR REPLACE VIEW vw_monthly_logistics AS
SELECT `year_month`,COUNT(*) AS shipments,
 SUM(recorded_freight_inr) AS recorded_freight_inr,
 SUM(modeled_baseline_inr) AS modeled_baseline_inr,
 SUM(cost_variance_inr) AS cost_variance_inr,
 SUM(cost_variance_inr)/NULLIF(SUM(modeled_baseline_inr),0) AS cost_variance_ratio,
 SUM(recorded_freight_inr)/NULLIF(SUM(weight_kg),0) AS freight_per_kg_inr,
 AVG(on_time_flag) AS on_time_delivery_ratio,
 SUM(expedite_fee_inr) AS expedite_fees_inr,
 SUM(expedited_flag) AS expedited_shipments
FROM vw_shipment_analysis
GROUP BY `year_month`;

CREATE OR REPLACE VIEW vw_monthly_growth AS
WITH prior AS (
 SELECT m.*,LAG(recorded_freight_inr) OVER(ORDER BY `year_month`) AS previous_month_freight_inr
 FROM vw_monthly_logistics m
)
SELECT prior.*,
 (recorded_freight_inr-previous_month_freight_inr)/NULLIF(previous_month_freight_inr,0) AS freight_growth_ratio
FROM prior;

SELECT * FROM vw_monthly_logistics ORDER BY `year_month`;
