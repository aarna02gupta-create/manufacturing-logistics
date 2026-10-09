"""Generate an independent, reproducible synthetic portfolio dataset. Python 3.10+."""
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar
import csv
import hashlib
import json
import random


ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
SQL = ROOT / 'sql'
DATA.mkdir(exist_ok=True)
SQL.mkdir(exist_ok=True)
RNG = random.Random(20260923)

def money(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def write_csv(name, rows):
    with (DATA / f'{name}.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

customers = [dict(customer_id=i, customer_name=f'Demo Customer {i:02d}',
                  segment=['Automotive', 'Industrial', 'Agricultural'][(i-1)%3], data_type='SYNTHETIC')
             for i in range(1,13)]
carriers = [dict(carrier_id=i, carrier_name=f'Demo Forwarder {i:02d}', data_type='SYNTHETIC')
            for i in range(1,6)]
route_specs = [('Pune','Chennai','India','Domestic',1.0),
               ('Pune','Delhi','India','Domestic',1.4),
               ('Pune','Bengaluru','India','Domestic',1.1),
               ('Pune','Ahmedabad','India','Domestic',0.8),
               ('Mumbai','Hamburg','Germany','Export',1.2),
               ('Mumbai','Houston','United States','Export',1.6),
               ('Mumbai','Dubai','United Arab Emirates','Export',0.8),
               ('Mumbai','Singapore','Singapore','Export',0.9)]
routes = [dict(route_id=i, origin_city=a, destination_city=b, destination_country=c,
               route_type=d, rate_factor=money(e), data_type='SYNTHETIC')
          for i,(a,b,c,d,e) in enumerate(route_specs,1)]
dates=[]
day=date(2025,1,1)
while day <= date(2026,12,31):
    dates.append(dict(date_key=int(day.strftime('%Y%m%d')), calendar_date=day,
                      calendar_year=day.year, month_number=day.month,
                      month_name=day.strftime('%B'), year_month=day.strftime('%Y-%m'),
                      quarter_number=(day.month-1)//3+1))
    day+=timedelta(days=1)

# Illustrative assumptions only. No internal records or real freight tariffs are read.
mode_rate={'Road':18, 'Sea':32, 'Air':210}
mode_days={'Road':5, 'Sea':24, 'Air':4}
rate_rows=[dict(mode=m, reference_rate_inr_kg=rate, planned_transit_days=mode_days[m],
               baseline_fuel_fraction='0.12', baseline_handling_inr='1800.00',
               data_type='SYNTHETIC_ASSUMPTION') for m,rate in mode_rate.items()]
months=[(2025+i//12, i%12+1) for i in range(20)]
shipments=[]
for _ in range(2400):
    mi=RNG.choices(range(20), weights=[95+i*2+(15 if i%12 in [2,8,9] else 0) for i in range(20)])[0]
    year,month=months[mi]
    # Through August 20, permitting all completed deliveries by the fixed September 23 snapshot.
    last=20 if (year,month)==(2026,8) else calendar.monthrange(year,month)[1]
    shipped=date(year,month,RNG.randint(1,last))
    route=RNG.choice(routes)
    carrier=RNG.choice(carriers)
    planned='Road' if route['route_type']=='Domestic' else RNG.choices(['Sea','Air'],[0.78,0.22])[0]
    expedited=RNG.random()<0.14
    actual='Air' if expedited and planned=='Sea' else planned
    weight=money(RNG.uniform(80,900) if actual=='Air' else RNG.uniform(500,6000))
    reference=money(mode_rate[planned]*float(route['rate_factor']))
    planned_base=money(weight*reference)
    planned_fuel=money(planned_base*Decimal('0.12'))
    planned_handling=Decimal('1800.00')
    # The baseline is a planned-mode budget, not a causal counterfactual.
    baseline=planned_base+planned_fuel+planned_handling
    market_factor=1+0.003*mi+(0.08 if month in [7,8,9] else 0)
    carrier_factor=[0.95,1.0,1.04,1.08,0.98][carrier['carrier_id']-1]
    base=money(float(weight)*mode_rate[actual]*float(route['rate_factor'])*market_factor*carrier_factor*RNG.uniform(0.86,1.10))
    fuel=money(base*Decimal(str(round(RNG.uniform(0.08,0.17),4))))
    handling=money(RNG.uniform(1100,2900))
    expedite=money(base*Decimal(str(round(RNG.uniform(0.06,0.18),4)))) if expedited else Decimal('0.00')
    invoice=base+fuel+handling+expedite
    planned_days=mode_days[planned]+(3 if route['destination_country']=='United States' else 0)
    transit=mode_days[actual]+(3 if route['destination_country']=='United States' else 0)
    late_chance=0.20+(0.12 if month in [7,8,9] else 0)+(0.06 if carrier['carrier_id']==4 else 0)
    extra=RNG.randint(1,7) if RNG.random()<late_chance else RNG.choice([-1,0,0])
    if expedited and actual==planned:
        transit=max(1,transit-2)
    delivered=shipped+timedelta(days=max(1,transit+extra))
    promised=shipped+timedelta(days=planned_days)
    reason=RNG.choice(['Weather','Capacity constraint','Documentation']) if delivered>promised else 'None'
    shipments.append(dict(shipment_id='',ship_date_key=int(shipped.strftime('%Y%m%d')),
        customer_id=RNG.choice(customers)['customer_id'],carrier_id=carrier['carrier_id'],route_id=route['route_id'],
        planned_mode=planned,actual_mode=actual,weight_kg=weight,
        promised_delivery_date=promised,actual_delivery_date=delivered,
        base_freight_inr=base,fuel_surcharge_inr=fuel,handling_charge_inr=handling,
        expedite_fee_inr=expedite,recorded_freight_inr=invoice,
        baseline_rate_inr_kg=reference,baseline_fuel_inr=planned_fuel,
        baseline_handling_inr=planned_handling,modeled_baseline_inr=baseline,
        expedited_flag=int(expedited),delay_reason=reason,data_type='SYNTHETIC'))
shipments.sort(key=lambda r:r['ship_date_key'])
for i,r in enumerate(shipments,1):
    r['shipment_id']=f'SIM-{i:05d}'

datasets={'dim_customer':customers,'dim_carrier':carriers,'dim_route':routes,
          'dim_date':dates,'fact_shipment':shipments,'generation_assumptions':rate_rows}
for name,rows in datasets.items():
    write_csv(name,rows)

# Validate independently of the SQL calculation views.
assert len(shipments)==2400
assert len({r['shipment_id'] for r in shipments})==2400
assert len({str(r['ship_date_key'])[:6] for r in shipments})==20
ids={name:{row[next(iter(row))] for row in datasets[name]} for name in ['dim_customer','dim_carrier','dim_route','dim_date']}
for r in shipments:
    for column,dim in [('customer_id','dim_customer'),('carrier_id','dim_carrier'),('route_id','dim_route'),('ship_date_key','dim_date')]:
        assert r[column] in ids[dim]
    assert r['recorded_freight_inr']==sum(r[x] for x in ['base_freight_inr','fuel_surcharge_inr','handling_charge_inr','expedite_fee_inr'])
    assert r['modeled_baseline_inr']==money(r['weight_kg']*r['baseline_rate_inr_kg'])+r['baseline_fuel_inr']+r['baseline_handling_inr']
    assert date.fromisoformat(str(r['ship_date_key'])[:4]+'-'+str(r['ship_date_key'])[4:6]+'-'+str(r['ship_date_key'])[6:]) <= r['actual_delivery_date'] <= date(2026,9,23)
    assert r['weight_kg']>0
    assert r['data_type']=='SYNTHETIC'
    assert all(v is not None and v!='' for v in r.values())

def literal(v):
    if isinstance(v,(int,Decimal)): return str(v)
    return "'"+str(v).replace("'","''")+"'"

load=['-- Generated by build_dataset.py. Independent synthetic data only.',
      '-- Run 01_create_schema.sql first. Re-running this seed load retains existing keyed records.',
      'USE portfolio_logistics;','START TRANSACTION;']
for table in ['dim_customer','dim_carrier','dim_route','dim_date','fact_shipment']:
    rows=datasets[table]
    for offset in range(0,len(rows),200):
        chunk=rows[offset:offset+200]
        columns=list(chunk[0])
        pk=columns[0]
        quoted_columns=', '.join('`'+column+'`' for column in columns)
        load.append(f"INSERT INTO {table} ({quoted_columns}) VALUES\n"+
                    ',\n'.join('('+', '.join(literal(r[k]) for k in columns)+')' for r in chunk)+
                    f'\nON DUPLICATE KEY UPDATE {pk}={table}.{pk};')
load+=['COMMIT;','SELECT COUNT(*) AS shipment_count FROM fact_shipment;']
(SQL/'02_load_synthetic_data.sql').write_text('\n\n'.join(load)+'\n',encoding='utf-8')
report={'dataset_version':'1.0','seed':20260923,'as_of_date':'2026-09-23',
        'all_records_synthetic':True,'shipment_count':len(shipments),'months':20,
        'ship_date_min':min(r['ship_date_key'] for r in shipments),
        'ship_date_max':max(r['ship_date_key'] for r in shipments),
        'recorded_freight_inr':str(sum(r['recorded_freight_inr'] for r in shipments)),
        'modeled_baseline_inr':str(sum(r['modeled_baseline_inr'] for r in shipments)),
        'late_shipments':sum(r['actual_delivery_date']>r['promised_delivery_date'] for r in shipments),
        'expedited_shipments':sum(r['expedited_flag'] for r in shipments),
        'validation':'Passed: unique shipment IDs, foreign keys, required values, positive weights, dates and cost reconciliation.',
        'mysql_execution':'This generator report validates CSVs only; it does not test MySQL execution.',
        'csv_hash_normalization':'LF line endings before SHA-256',
        'csv_sha256':{p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sorted(DATA.glob('*.csv'))}}
(ROOT/'validation_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
