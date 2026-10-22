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
               | df[counts].mod(1).ne(0).any(axis=1)
               | df[['adults', 'children', 'babies']].sum(axis=1).le(0)
               | df['adr'].isna() | df['adr'].lt(0)
               | df['lead_time'].isna() | df['lead_time'].lt(0))
    invalid_count = int(invalid.sum())
    df = df.loc[~invalid].copy()
    year = df['arrival_date_year'].where(df['arrival_date_year'].mod(1).eq(0))
    day = df['arrival_date_day_of_month'].where(df['arrival_date_day_of_month'].mod(1).eq(0))
    df['arrival_date'] = pd.to_datetime(
        year.astype('Int64').astype(str) + '-' +
        df['arrival_date_month'].astype(str).str.strip() + '-' +
        day.astype('Int64').astype(str), format='%Y-%B-%d', errors='coerce')
    invalid_dates = int(df['arrival_date'].isna().sum())
    df = df.dropna(subset=['arrival_date']).copy()
    if cap:
        for col in ['lead_time', 'adr']:
            q1, q3 = df[col].quantile([.25, .75])
            df[col] = df[col].clip(max(0, q1 - 1.5 * (q3 - q1)), q3 + 1.5 * (q3 - q1))
    df['total_nights'] = df['stays_in_weekend_nights'] + df['stays_in_week_nights']
    df['booking_value_estimate'] = df['adr'] * df['total_nights']
    df['guest_count'] = df[['adults', 'children', 'babies']].sum(axis=1)
    df['guest_profile'] = np.select(
        [(df['children'] + df['babies']).gt(0), df['adults'].eq(1), df['adults'].eq(2)],
        ['Family with children', 'Solo adult', 'Two adults'], default='Adult group')
    df['lead_time_band'] = pd.cut(df['lead_time'], [-1, 7, 30, 90, 180, np.inf],
        labels=['0–7 days', '8–30 days', '31–90 days', '91–180 days', '181+ days'])
    df['stay_band'] = pd.cut(df['total_nights'], [-1, 0, 2, 5, 10, np.inf],
        labels=['Zero nights', '1–2 nights', '3–5 nights', '6–10 nights', '11+ nights'])
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
    low, high = wilson_interval(result['cancellations'], result['bookings'])
    result['ci_lower_pct'] = low * 100
    result['ci_upper_pct'] = high * 100
    return result


def wilson_interval(successes, count):
    """95% Wilson score interval for independent Bernoulli observations."""
    n = np.asarray(count, dtype=float)
    p = np.divide(successes, n, out=np.zeros_like(n), where=n > 0)
    z = 1.959963984540054
    denominator = 1 + z*z / np.maximum(n, 1)
    center = (p + z*z / (2 * np.maximum(n, 1))) / denominator
    half = z * np.sqrt(p*(1-p) / np.maximum(n, 1) + z*z/(4*np.maximum(n, 1)**2)) / denominator
    return np.where(n > 0, np.maximum(0, center-half), np.nan), np.where(n > 0, np.minimum(1, center+half), np.nan)


def monthly_summary(df):
    table = summarize(df.assign(month=df.arrival_date.dt.to_period('M').astype(str)), 'month')
    all_months = pd.period_range(df.arrival_date.min(), df.arrival_date.max(), freq='M').astype(str)
    table = table.set_index('month').reindex(all_months).rename_axis('month').reset_index()
    table[['bookings', 'cancellations']] = table[['bookings', 'cancellations']].fillna(0).astype(int)
    return table


def permutation_comparison(a, b, iterations=2000):
    """Two-sided Monte Carlo permutation test for a difference in means.

    Samples are deterministically capped at 2,000 per group for interactive use.
    Reported effect and group sizes refer to these same samples.
    """
    rng = np.random.default_rng(42)
    a = np.asarray(pd.to_numeric(pd.Series(a), errors='coerce').dropna(), dtype=float)
    b = np.asarray(pd.to_numeric(pd.Series(b), errors='coerce').dropna(), dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if min(len(a), len(b)) < 2:
        raise ValueError('Each group needs at least two valid observations.')
    a = rng.choice(a, min(len(a), 2000), replace=False)
    b = rng.choice(b, min(len(b), 2000), replace=False)
    observed = float(a.mean() - b.mean())
    pool = np.concatenate([a, b])
    exceed = 0
    for _ in range(iterations):
        shuffled = rng.permutation(pool)
        difference = shuffled[:len(a)].mean() - shuffled[len(a):].mean()
        exceed += abs(difference) >= abs(observed) - 1e-12
    return {'group_a_n': len(a), 'group_b_n': len(b), 'mean_a': a.mean(),
            'mean_b': b.mean(), 'difference': observed, 'p_value': (exceed+1)/(iterations+1)}


def findings(df, minimum=20):
    notes = [f'{len(df):,} bookings selected; observed cancellation rate is {df.is_canceled.mean():.1%}.']
    monthly = monthly_summary(df)
    peak = monthly.loc[monthly.bookings.idxmax()]
    notes.append(f'The busiest observed arrival month is {peak.month} with {int(peak.bookings):,} bookings.')
    table = summarize(df, 'hotel')
    table = table[table.bookings >= minimum]
    if not table.empty:
        row = table.loc[table.cancellation_rate_pct.idxmax()]
        notes.append(f'{row.hotel} has the highest eligible hotel cancellation rate: {row.cancellation_rate_pct:.1f}% across {int(row.bookings):,} bookings.')
    notes.append(f'Median daily rate is {df.adr.median():,.2f}; median booking lead time is {df.lead_time.median():.0f} days.')
    return notes


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
