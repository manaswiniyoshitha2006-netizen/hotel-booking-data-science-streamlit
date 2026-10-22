from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from analysis import REQUIRED, demo_data, prepare, summarize

st.set_page_config(page_title='Hotel Booking Observatory', page_icon='🏨', layout='wide')
st.title('Hotel Booking Observatory')
st.caption('Explore booking behavior, seasonality, pricing and cancellations')
with st.sidebar:
    st.header('Your dataset')
    upload = st.file_uploader('Upload hotel_bookings.csv', type=['csv'])
    deduplicate = st.checkbox('Remove exact duplicate rows', value=True,
        help='Identical records can represent separate bookings. Compare both settings.')
    cap = st.checkbox('Cap ADR and lead-time outliers using IQR', value=False)
    st.caption('Cleaning settings apply before dashboard filters.')
try:
    if upload is not None:
        raw = pd.read_csv(upload)
        source = 'Uploaded dataset'
    elif Path('data/hotel_bookings.csv').exists():
        raw = pd.read_csv('data/hotel_bookings.csv')
        source = 'Local dataset'
    else:
        raw = demo_data()
        source = 'Synthetic demo'
    clean, audit = prepare(raw, deduplicate, cap)
except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(str(exc))
    st.write('Required CSV columns:', ', '.join(REQUIRED))
    st.stop()
if source == 'Synthetic demo':
    st.info('DEMO DATA · 1,500 synthetic bookings. Upload your CSV for actual findings. These examples are not notebook results.')
if clean.empty:
    st.warning('No valid records remain after cleaning. Check your CSV.')
    st.dataframe(audit, hide_index=True)
    st.stop()
filtered = clean.copy()
with st.sidebar:
    st.header('Explore')
    for col, label in [('hotel', 'Hotel'), ('market_segment', 'Market segment'), ('country', 'Country')]:
        if col in clean:
            options = sorted(clean[col].unique())
            selected = st.multiselect(label, options, default=options)
            filtered = filtered[filtered[col].isin(selected)]
    dates = st.date_input('Arrival dates', value=(clean.arrival_date.min().date(), clean.arrival_date.max().date()),
        min_value=clean.arrival_date.min().date(), max_value=clean.arrival_date.max().date())
    if len(dates) == 2:
        filtered = filtered[filtered.arrival_date.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
    minimum = st.number_input('Minimum bookings per comparison group', min_value=1, value=20)
st.caption(f'{source} · {len(filtered):,} of {len(clean):,} cleaned bookings selected')
if filtered.empty:
    st.warning('No bookings match these filters. Adjust your selections.')
    st.stop()
a, b, c, d = st.columns(4)
a.metric('Bookings', f'{len(filtered):,}')
b.metric('Cancellation rate', f'{filtered.is_canceled.mean():.1%}')
c.metric('Average daily rate', f'{filtered.adr.mean():,.2f}')
d.metric('Average stay', f'{filtered.total_nights.mean():.1f} nights')
overview, cancellation, quality, export = st.tabs(['Booking trends', 'Cancellation patterns', 'Data quality', 'Downloads & Tableau'])
with overview:
    monthly = summarize(filtered.assign(month=filtered.arrival_date.dt.to_period('M').astype(str)), 'month')
    st.plotly_chart(px.line(monthly, x='month', y='bookings', markers=True, title='Bookings by arrival month'), use_container_width=True)
    left, right = st.columns(2)
    left.plotly_chart(px.histogram(filtered, x='adr', color='hotel', nbins=40, title='Daily room rates', barmode='overlay'), use_container_width=True)
    right.plotly_chart(px.histogram(filtered, x='lead_time', color='hotel', nbins=40, title='Days booked in advance'), use_container_width=True)
    st.dataframe(filtered[['adr', 'lead_time', 'total_nights']].describe().round(2), use_container_width=True)
with cancellation:
    groups = [c for c in ['hotel', 'market_segment', 'deposit_type', 'customer_type', 'country'] if c in filtered]
    group = st.selectbox('Compare cancellation rates by', groups)
    table = summarize(filtered, group)
    eligible = table[table.bookings >= minimum].sort_values('cancellation_rate_pct', ascending=False)
    if eligible.empty:
        st.info('No groups meet the minimum booking count. Lower the threshold.')
    else:
        st.plotly_chart(px.bar(eligible, x=group, y='cancellation_rate_pct',
            hover_data=['bookings', 'cancellations'], title='Observed cancellation rate (%)'), use_container_width=True)
    st.dataframe(table.round(2), hide_index=True, use_container_width=True)
    st.caption('Rates = canceled bookings / all bookings in each group. Associations do not establish causation. Small groups may have unstable rates.')
with quality:
    st.subheader('Cleaning audit · before dashboard filters')
    st.dataframe(audit, hide_index=True)
    st.dataframe(pd.DataFrame({'Missing values (uploaded)': raw.isna().sum(),
        'Missing values (cleaned)': clean.isna().sum()}).fillna(0).astype(int), use_container_width=True)
    st.write('Missing children and babies are treated as zero; missing categories are Unknown. Invalid guest counts, negative or missing ADR/lead time, and invalid dates are excluded. Zero-night stays remain visible. Outlier capping is optional; no encoding, scaling or prediction is performed.')
    st.caption('The original notebook is preserved as supplied. Its historical ML sections are not executed by this application.')
with export:
    st.download_button('Download filtered bookings', filtered.to_csv(index=False).encode(), 'hotel_bookings_filtered.csv', 'text/csv')
    st.download_button('Download monthly summary', monthly.to_csv(index=False).encode(), 'hotel_monthly_summary.csv', 'text/csv')
    st.download_button('Download cleaning audit', audit.to_csv(index=False).encode(), 'cleaning_audit.csv', 'text/csv')
    st.write('In Tableau: Connect → Text file → select the filtered bookings CSV. Use arrival_date for timelines and hotel / market_segment as filters. Define Cancellation rate as AVG([is_canceled]) and format as a percentage. The CSV is a manual data handoff; refresh by downloading a new export.')
    st.caption('booking_value_estimate = ADR × nights; it is an estimate, not recognized revenue. Currency is inherited from the source dataset.')
