"""Descriptive hotel booking analysis; no prediction or model training."""
import numpy as np
import pandas as pd

REQUIRED = ['hotel', 'is_canceled', 'arrival_date_year', 'arrival_date_month',
            'arrival_date_day_of_month', 'stays_in_weekend_nights',
            'stays_in_week_nights', 'adults', 'children', 'babies', 'adr', 'lead_time']


def prepare(raw, deduplicate=True, cap=False):
    missing = sorted(set(REQUIRED) - set(raw.columns))
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    df = raw.copy()
    numeric = [c for c in REQUIRED if c not in ['hotel', 'arrival_date_month']]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors='coerce').replace([np.inf, -np.inf], np.nan)
    if not df['is_canceled'].isin([0, 1]).all():
        raise ValueError('is_canceled must contain only 0 (not canceled) or 1 (canceled).')
    for col in ['children', 'babies']:
        df[col] = df[col].fillna(0)
    for col in ['hotel', 'country', 'market_segment', 'deposit_type', 'customer_type']:
        if col in df:
            df[col] = df[col].fillna('Unknown').astype(str).str.strip().replace('', 'Unknown')
    duplicates = int(df.duplicated().sum())
    if deduplicate:
        df = df.drop_duplicates().copy()
    counts = ['adults', 'children', 'babies', 'stays_in_weekend_nights', 'stays_in_week_nights']
    invalid = (df[counts].isna().any(axis=1) | df[counts].lt(0).any(axis=1)
               | df[['adults', 'children', 'babies']].sum(axis=1).le(0)
               | df['adr'].isna() | df['adr'].lt(0)
               | df['lead_time'].isna() | df['lead_time'].lt(0))
    invalid_count = int(invalid.sum())
    df = df.loc[~invalid].copy()
    df['arrival_date'] = pd.to_datetime(
        df['arrival_date_year'].astype('Int64').astype(str) + '-' +
        df['arrival_date_month'].astype(str) + '-' +
        df['arrival_date_day_of_month'].astype('Int64').astype(str), errors='coerce')
    invalid_dates = int(df['arrival_date'].isna().sum())
    df = df.dropna(subset=['arrival_date']).copy()
    if cap:
        for col in ['lead_time', 'adr']:
            q1, q3 = df[col].quantile([.25, .75])
            df[col] = df[col].clip(max(0, q1 - 1.5 * (q3 - q1)), q3 + 1.5 * (q3 - q1))
    df['total_nights'] = df['stays_in_weekend_nights'] + df['stays_in_week_nights']
    df['booking_value_estimate'] = df['adr'] * df['total_nights']
    audit = pd.DataFrame({'Measure': ['Uploaded rows', 'Duplicate rows detected',
        'Duplicates removed', 'Invalid records removed', 'Invalid dates removed', 'Analysis rows'],
        'Rows': [len(raw), duplicates, duplicates if deduplicate else 0,
                 invalid_count, invalid_dates, len(df)]})
    return df, audit


def summarize(df, group):
    result = df.groupby(group, dropna=False, observed=True).agg(
        bookings=('is_canceled', 'size'), cancellations=('is_canceled', 'sum'),
        mean_adr=('adr', 'mean'), mean_lead_days=('lead_time', 'mean')).reset_index()
    result['cancellation_rate_pct'] = result['cancellations'] / result['bookings'] * 100
    return result


def demo_data():
    rng = np.random.default_rng(42)
    n = 1500
    dates = pd.Series(pd.to_datetime('2024-01-01') + pd.to_timedelta(rng.integers(0, 730, n), unit='D'))
    return pd.DataFrame({
        'hotel': rng.choice(['City Hotel', 'Resort Hotel'], n),
        'is_canceled': rng.binomial(1, .3, n),
        'arrival_date_year': dates.dt.year, 'arrival_date_month': dates.dt.month_name(),
        'arrival_date_day_of_month': dates.dt.day,
        'stays_in_weekend_nights': rng.integers(0, 3, n),
        'stays_in_week_nights': rng.integers(1, 8, n),
        'adults': rng.integers(1, 4, n), 'children': rng.integers(0, 3, n), 'babies': 0,
        'adr': rng.gamma(5, 22, n).round(2), 'lead_time': rng.integers(0, 300, n),
        'market_segment': rng.choice(['Direct', 'Online TA', 'Offline TA/TO', 'Groups'], n),
        'deposit_type': rng.choice(['No Deposit', 'Non Refund', 'Refundable'], n),
        'country': rng.choice(['PRT', 'GBR', 'FRA', 'ESP', 'DEU'], n)})
