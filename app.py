from pathlib import Path
from io import BytesIO
import html
import json
import zipfile
import pandas as pd
import plotly.express as px
import streamlit as st
from analysis import (REQUIRED, demo_data, prepare, summarize, monthly_summary,
                      wilson_interval, permutation_comparison, findings)

st.set_page_config(page_title='StayScope · Hotel Booking Analytics', page_icon='🏨', layout='wide')
px.defaults.template = 'plotly_white'
px.defaults.color_discrete_sequence = ['#087f8c', '#ef8354', '#6854a3', '#a5be00', '#4361ee']
st.markdown('''<style>
.stApp {background:#f6f8fb;color:#16263b}
[data-testid="stSidebar"] {background:#fff;border-right:1px solid #e2e8f0}
.block-container {padding-top:2.3rem;max-width:1500px}
h1,h2,h3 {letter-spacing:-.035em}
[data-testid="stMetric"] {background:white;border:1px solid #e2e8f0;border-radius:16px;padding:18px 20px}
[data-testid="stMetricLabel"] {color:#627084;font-size:13px}
[data-testid="stMetricValue"] {color:#17334a;font-size:29px}
.hero {background:linear-gradient(115deg,#123347,#087f8c);border-radius:20px;padding:30px 34px;margin-bottom:20px;color:white}
.hero h1 {font-size:36px;color:white;margin:6px 0 8px;padding:0}
.hero p {color:#d5edf0;margin:0;max-width:760px;font-size:15px}
.eyebrow {font-size:11px;letter-spacing:.18em;font-weight:700;color:#98e5d5}
.insight {background:white;border:1px solid #e2e8f0;border-left:4px solid #087f8c;border-radius:12px;padding:16px 20px;margin-bottom:12px;min-height:100px}
.insight small {color:#087f8c;font-weight:700;letter-spacing:.08em}
.insight p {margin:7px 0 0;font-size:14px}
[data-testid="stPlotlyChart"] {background:white;border:1px solid #e2e8f0;border-radius:14px;padding:10px}
</style>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=3)
def load_csv(content):
    return pd.read_csv(BytesIO(content))


def chart(fig):
    fig.update_layout(margin=dict(l=15, r=15, t=50, b=20), font=dict(family='Arial', color='#34465a'),
        paper_bgcolor='white', plot_bgcolor='white', legend_title_text='', height=360)
    st.plotly_chart(fig, width='stretch')


def table_download(label, table, filename):
    st.download_button(label, table.to_csv(index=False).encode('utf-8'), filename, 'text/csv')


def reset_filters():
    for key in list(st.session_state):
        if key.startswith('filter_'):
            del st.session_state[key]


with st.sidebar:
    st.markdown('## 🏨 StayScope')
    st.caption('HOTEL BOOKING ANALYTICS')
    page = st.radio('Workspace', ['Overview', 'Seasonality', 'Cancellations', 'Guests & markets',
        'Hotel comparison', 'Statistics lab', 'Data explorer', 'Quality & methodology', 'Reports & Tableau'],
        label_visibility='collapsed')
    st.divider()
    upload = st.file_uploader('Your booking dataset', type=['csv'], help='Upload the raw hotel_bookings.csv.')
    with st.expander('Cleaning settings'):
        deduplicate = st.checkbox('Remove exact duplicate rows', value=True,
            help='Identical records may represent separate bookings. Compare both settings.')
        cap = st.checkbox('Cap ADR and lead-time outliers using IQR', value=False)
try:
    local_path = Path(__file__).parent / 'data' / 'hotel_bookings.csv'
    if upload is not None:
        raw, source = load_csv(upload.getvalue()), 'Uploaded dataset'
    elif local_path.exists():
        raw, source = load_csv(local_path.read_bytes()), 'Local dataset'
    else:
        raw, source = demo_data(), 'Synthetic demo'
    clean, audit = prepare(raw, deduplicate, cap)
except (ValueError, pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
    st.error(str(exc))
    st.write('Required CSV columns:', ', '.join(REQUIRED))
    st.stop()
if clean.empty:
    st.warning('No valid records remain after cleaning. Check your CSV.')
    st.dataframe(audit, hide_index=True)
    st.stop()

with st.sidebar:
    st.markdown('#### Dashboard filters')
    filtered = clean.copy()
    applied_filters = {}
    for col, label in [('hotel', 'Hotel'), ('market_segment', 'Market segment'), ('country', 'Country')]:
        if col in clean:
            options = sorted(clean[col].unique())
            selected = st.multiselect(label, options, default=options, key=f'filter_{col}')
            applied_filters[col] = selected
            filtered = filtered[filtered[col].isin(selected)]
    dates = st.date_input('Arrival dates', value=(clean.arrival_date.min().date(), clean.arrival_date.max().date()),
        min_value=clean.arrival_date.min().date(), max_value=clean.arrival_date.max().date(), key='filter_dates')
    if len(dates) == 2:
        filtered = filtered[filtered.arrival_date.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
        applied_filters['arrival_dates'] = [str(d) for d in dates]
    outcome = st.selectbox('Booking outcome', ['All bookings', 'Not canceled', 'Canceled'], key='filter_outcome')
    if outcome != 'All bookings':
        filtered = filtered[filtered.is_canceled.eq(int(outcome == 'Canceled'))]
    applied_filters['outcome'] = outcome
    minimum = st.number_input('Minimum bookings per comparison group', min_value=1, value=20, key='filter_minimum')
    st.button('Reset filters', on_click=reset_filters, width='stretch')
    st.caption(f'{len(filtered):,} / {len(clean):,} cleaned records')

st.markdown('''<div class="hero"><div class="eyebrow">BOOKINGS → EVIDENCE → INSIGHT</div>
<h1>See the story behind every stay.</h1>
<p>Your hotel booking research workspace. Explore demand, understand cancellations,
compare guests and turn your analysis into a clear report.</p></div>''', unsafe_allow_html=True)
if source == 'Synthetic demo':
    st.info('DEMO DATA · 1,500 synthetic bookings. Upload your CSV for actual findings. These examples are not notebook results.')
st.caption(f'{source}  /  {page}  /  {len(filtered):,} selected bookings')
if filtered.empty:
    st.warning('No bookings match these filters. Adjust your selections.')
    st.stop()

monthly = monthly_summary(filtered)
insights = findings(filtered, minimum)
groups = [c for c in ['hotel', 'market_segment', 'deposit_type', 'customer_type',
          'country', 'guest_profile', 'lead_time_band', 'stay_band'] if c in filtered]

if page == 'Overview':
    a, b, c, d = st.columns(4)
    a.metric('Bookings', f'{len(filtered):,}')
    b.metric('Cancellation rate', f'{filtered.is_canceled.mean():.1%}')
    c.metric('Average daily rate', f'{filtered.adr.mean():,.2f}')
    d.metric('Average stay', f'{filtered.total_nights.mean():.1f} nights')
    st.write('')
    left, right = st.columns([2, 1])
    with left:
        chart(px.area(monthly, x='month', y='bookings', title='Arrival demand over time',
            labels={'month':'Arrival month', 'bookings':'Bookings'}))
    with right:
        counts = filtered.is_canceled.map({0:'Not canceled', 1:'Canceled'}).value_counts().rename_axis('Outcome').reset_index(name='Bookings')
        chart(px.pie(counts, names='Outcome', values='Bookings', hole=.72, title='Booking outcomes'))
    st.subheader('What the selected data shows')
    columns = st.columns(2)
    for i, note in enumerate(insights):
        columns[i % 2].markdown(f'<div class="insight"><small>OBSERVATION {i+1:02d}</small><p>{html.escape(note)}</p></div>', unsafe_allow_html=True)
    st.caption('Descriptive observations are generated from current filters. They are not forecasts or causal findings.')

elif page == 'Seasonality':
    st.subheader('When do guests arrive?')
    measure = st.selectbox('Monthly measure', ['bookings', 'mean_adr', 'cancellation_rate_pct'],
        format_func=lambda x: {'bookings':'Booking volume', 'mean_adr':'Average daily rate', 'cancellation_rate_pct':'Cancellation rate (%)'}[x])
    chart(px.line(monthly, x='month', y=measure, markers=True, title='Monthly arrival trends'))
    seasonal = filtered.assign(year=filtered.arrival_date.dt.year, month_number=filtered.arrival_date.dt.month)
    heat = seasonal.groupby(['year', 'month_number']).size().unstack().reindex(columns=range(1,13))
    heat.columns = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    chart(px.imshow(heat, aspect='auto', color_continuous_scale='Teal', title='Arrival calendar · booking counts', labels={'color':'Bookings'}))
    st.caption('Blank cells have no observed records. Partial-year coverage and active filters affect comparisons.')
    weekday = filtered.arrival_date.dt.day_name().value_counts().reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'], fill_value=0).rename_axis('Arrival weekday').reset_index(name='Bookings')
    chart(px.bar(weekday, x='Arrival weekday', y='Bookings', title='Arrival patterns by weekday'))
    st.dataframe(monthly.round(2), hide_index=True, width='stretch')

elif page == 'Cancellations':
    st.subheader('Understand observed cancellation patterns')
    lo, hi = wilson_interval(filtered.is_canceled.sum(), len(filtered))
    a,b,c = st.columns(3)
    a.metric('Canceled bookings', f'{int(filtered.is_canceled.sum()):,}')
    b.metric('Observed cancellation rate', f'{filtered.is_canceled.mean():.1%}')
    c.metric('95% Wilson interval', f'{lo:.1%} – {hi:.1%}')
    if outcome != 'All bookings':
        st.warning('An outcome filter is active. Select All bookings to compare meaningful cancellation rates.')
    group = st.selectbox('Compare by', groups)
    table = summarize(filtered, group)
    eligible = table[table.bookings >= minimum].sort_values('cancellation_rate_pct', ascending=False)
    if eligible.empty:
        st.info('No groups meet the minimum booking count. Lower the threshold.')
    else:
        eligible = eligible.copy()
        eligible['error_above'] = (eligible.ci_upper_pct - eligible.cancellation_rate_pct).clip(lower=0)
        eligible['error_below'] = (eligible.cancellation_rate_pct - eligible.ci_lower_pct).clip(lower=0)
        chart(px.bar(eligible, x=group, y='cancellation_rate_pct', error_y='error_above', error_y_minus='error_below',
            hover_data=['bookings', 'cancellations'], title='Cancellation rate (%) · with 95% intervals'))
    st.dataframe(table.round(2), hide_index=True, width='stretch')
    table_download('Download this comparison', table, 'cancellation_comparison.csv')
    st.caption('Rates = canceled bookings / all selected bookings in each group. Wilson intervals assume independent bookings. Repeat guests or group bookings may violate that assumption. Associations do not establish causation.')

elif page == 'Guests & markets':
    st.subheader('Who books, and how do they stay?')
    left,right = st.columns(2)
    with left:
        chart(px.bar(summarize(filtered,'guest_profile'), x='guest_profile', y='bookings', color='guest_profile', title='Guest composition'))
    with right:
        chart(px.bar(summarize(filtered,'stay_band'), x='stay_band', y='bookings', title='Length of stay'))
    available = [c for c in ['market_segment','country','customer_type','deposit_type'] if c in filtered]
    if available:
        group = st.selectbox('Market breakdown', available)
        table = summarize(filtered, group).sort_values('bookings', ascending=False)
        chart(px.bar(table.head(15), x=group, y='bookings', color='mean_adr', color_continuous_scale='Teal',
            hover_data=['cancellation_rate_pct'], title='Top 15 groups by booking volume'))
        st.dataframe(table.round(2), hide_index=True, width='stretch')
    else:
        st.info('Add market_segment, country, customer_type or deposit_type to your CSV for market comparisons.')
    chart(px.box(filtered, x='guest_profile', y='adr', color='hotel', points=False, title='Daily rates by guest composition'))

elif page == 'Hotel comparison':
    st.subheader('Compare two hotels on the same filters')
    hotels = sorted(filtered.hotel.unique())
    if len(hotels) < 2:
        st.info('Select at least two hotel types in the sidebar to compare them.')
    else:
        left, right = st.columns(2)
        hotel_a = left.selectbox('Hotel A', hotels)
        hotel_b = right.selectbox('Hotel B', [h for h in hotels if h != hotel_a])
        parts = [filtered[filtered.hotel.eq(h)] for h in [hotel_a, hotel_b]]
        comparison = pd.DataFrame([{'Hotel':h, 'Bookings':len(data), 'Cancellation rate (%)':data.is_canceled.mean()*100,
            'Mean ADR':data.adr.mean(), 'Median ADR':data.adr.median(),
            'Average stay (nights)':data.total_nights.mean(), 'Average lead time (days)':data.lead_time.mean()}
            for h,data in zip([hotel_a,hotel_b],parts)])
        st.dataframe(comparison.round(2), hide_index=True, width='stretch')
        combined = pd.concat(parts)
        left,right = st.columns(2)
        with left:
            chart(px.box(combined, x='hotel', y='adr', color='hotel', points=False, title='Daily rate distribution'))
        with right:
            chart(px.histogram(combined, x='lead_time', color='hotel', barmode='overlay', opacity=.65, nbins=30, title='Booking lead times'))
        table_download('Download hotel comparison', comparison, 'hotel_comparison.csv')
        st.caption('Observed averages reflect guest mix, timing and selection. They do not measure hotel quality or prove an effect of hotel type.')

elif page == 'Statistics lab':
    st.subheader('Explore relationships and test differences')
    correlation_tab, test_tab = st.tabs(['Correlation explorer', 'Two-group comparison'])
    with correlation_tab:
        numeric = ['adr','lead_time','total_nights','adults','children','babies','guest_count','is_canceled']
        chosen = st.multiselect('Numeric features', numeric, default=['adr','lead_time','total_nights','is_canceled'])
        method = st.selectbox('Correlation method', ['pearson','spearman'])
        if len(chosen) >= 2:
            values = filtered[chosen].rank() if method == 'spearman' else filtered[chosen]
            corr = values.corr()
            chart(px.imshow(corr, zmin=-1, zmax=1, color_continuous_scale='RdBu_r', text_auto='.2f', title=f'{method.title()} correlation'))
            table_download('Download correlation matrix', corr.rename_axis('Feature').reset_index(), 'correlations.csv')
        else:
            st.info('Choose at least two numeric features.')
        st.caption('Blank cells indicate undefined correlations, usually constant features. Correlation does not establish causation.')
    with test_tab:
        st.write('Compare two groups using a two-sided permutation test of the difference in means.')
        group = st.selectbox('Grouping feature', ['hotel','guest_profile'] + (['market_segment'] if 'market_segment' in filtered else []))
        categories = sorted(filtered[group].unique())
        if len(categories) < 2:
            st.info('At least two groups are required. Broaden your filters.')
        else:
            left,right = st.columns(2)
            first = left.selectbox('Group A', categories)
            second = right.selectbox('Group B', [v for v in categories if v != first])
            metric = st.selectbox('Measure to compare', ['adr','lead_time','total_nights','is_canceled'])
            st.caption('Null hypothesis: group labels are exchangeable, with no group difference. Up to 2,000 randomly sampled observations per group and 2,000 permutations; fixed seed for reproducibility. Exploratory analysis with no correction for repeated comparisons.')
            if st.button('Run statistical comparison', type='primary'):
                try:
                    result = permutation_comparison(filtered.loc[filtered[group].eq(first),metric], filtered.loc[filtered[group].eq(second),metric])
                    a,b,c = st.columns(3)
                    a.metric('Mean A − mean B', f"{result['difference']:.4f}")
                    b.metric('Permutation p-value', f"{result['p_value']:.4f}")
                    c.metric('Sample sizes · A / B', f"{result['group_a_n']:,} / {result['group_b_n']:,}")
                    st.write('Evidence of a group difference at α = 0.05.' if result['p_value'] < .05 else 'Insufficient evidence of a group difference at α = 0.05.')
                    st.caption('Assess effect magnitude alongside the p-value. Non-significance does not prove equality. Selection and non-independent records limit inference. For is_canceled the difference is in proportions (multiply by 100 for percentage points).')
                except ValueError as exc:
                    st.warning(str(exc))

elif page == 'Data explorer':
    st.subheader('Inspect the records behind your charts')
    search = st.text_input('Search across text columns', placeholder='Try a hotel, country or market segment')
    view = filtered.copy()
    if search:
        mask = pd.Series(False, index=view.index)
        for col in view.select_dtypes(include=['object','category']).columns:
            mask |= view[col].astype(str).str.contains(search, case=False, regex=False, na=False)
        view = view.loc[mask]
    selected_columns = st.multiselect('Visible columns', list(view.columns), default=list(view.columns[:12]))
    order = st.selectbox('Sort records by', ['arrival_date','adr','lead_time','total_nights'])
    ascending = st.checkbox('Ascending order', value=True)
    st.caption(f'{len(view):,} matching records · first 1,000 displayed; download includes all matches')
    if selected_columns:
        view = view.sort_values(order, ascending=ascending)[selected_columns]
        st.dataframe(view.head(1000), hide_index=True, width='stretch')
        table_download('Download matching records', view, 'explorer_results.csv')
    else:
        st.info('Choose at least one visible column.')

elif page == 'Quality & methodology':
    st.subheader('Make every cleaning decision visible')
    st.caption('Full uploaded dataset before dashboard filters.')
    a,b,c = st.columns(3)
    a.metric('Rows uploaded', f'{len(raw):,}')
    b.metric('Rows retained', f'{len(clean):,}')
    c.metric('Retention', f'{len(clean)/len(raw):.1%}')
    st.dataframe(audit, hide_index=True, width='stretch')
    quality = pd.DataFrame({'Column':raw.columns, 'Type':raw.dtypes.astype(str).values,
        'Missing values':raw.isna().sum().values, 'Missing (%)':(raw.isna().mean()*100).values,
        'Unique values':raw.nunique().values})
    st.dataframe(quality.round(2), hide_index=True, width='stretch')
    missing = quality[quality['Missing values'] > 0]
    if not missing.empty:
        chart(px.bar(missing, x='Column', y='Missing (%)', title='Missing values in the uploaded data'))
    st.markdown('''**Cleaning rules**

- Missing children and babies become zero; missing categories become Unknown.
- Exclude missing, negative or fractional guest/night counts, zero-guest bookings, missing/negative ADR or lead time, and invalid arrival dates.
- Duplicate removal is optional. Identical records may represent separate bookings.
- Optional IQR capping applies to ADR and lead time and changes observed distributions.
- Keep zero-night bookings visible. No machine learning, encoding or scaling runs in the app.

**Interpretation**

Booking counts are not occupancy: room inventory and daily availability are absent.
ADR currency comes from the source. ADR × nights is an estimated booking value, not realized revenue.
Historical associations are not causal effects. Partial periods and small groups need care.
The original notebook remains unchanged, including its historical ML sections; those sections are not executed here.''')
    table_download('Download column quality report', quality, 'column_quality.csv')

elif page == 'Reports & Tableau':
    st.subheader('Take your findings into the review room')
    settings = {'source':source, 'filters':applied_filters, 'deduplicate':deduplicate,
        'iqr_capping':cap, 'minimum_group_size':int(minimum), 'selected_rows':len(filtered)}
    report = ('<!doctype html><html><head><meta charset="utf-8"><title>StayScope analysis report</title>'
        '<style>body{font:16px Arial;color:#183247;max-width:1000px;margin:50px auto;padding:24px}'
        'h1{color:#087f8c}table{border-collapse:collapse;width:100%;font-size:13px}'
        'td,th{padding:9px;border:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}</style></head><body>'
        '<h1>StayScope · Hotel booking analysis</h1><p>Source: '+html.escape(source)+'</p><h2>Findings</h2><ul>'
        + ''.join('<li>'+html.escape(note)+'</li>' for note in insights) + '</ul><h2>Analysis settings</h2><pre>'
        + html.escape(json.dumps(settings, indent=2)) + '</pre><h2>Hotel comparison</h2>'
        + summarize(filtered,'hotel').round(2).to_html(index=False, escape=True) + '<h2>Monthly trends</h2>'
        + monthly.round(2).to_html(index=False, escape=True) + '<h2>Cleaning audit (before filters)</h2>'
        + audit.to_html(index=False, escape=True) + '<p>Demo data is synthetic. No prediction or model training is performed. '
        'Results describe historical associations, not causation. Wilson intervals assume independent bookings. '
        'ADR currency is inherited from the source. Estimated booking values are not realized revenue.</p></body></html>')
    st.download_button('Download analysis report · HTML', report.encode(), 'hotel_analysis_report.html', 'text/html', type='primary')
    st.caption('Open the report in a browser to read, print, or save as PDF.')
    left,right = st.columns(2)
    with left:
        table_download('Filtered booking records · CSV', filtered, 'hotel_bookings_filtered.csv')
        table_download('Monthly trends · CSV', monthly, 'hotel_monthly_summary.csv')
    with right:
        table_download('Hotel summary · CSV', summarize(filtered,'hotel'), 'hotel_summary.csv')
        table_download('Cleaning audit · CSV', audit, 'cleaning_audit.csv')
    bundle = BytesIO()
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('bookings.csv', filtered.to_csv(index=False))
        archive.writestr('monthly_summary.csv', monthly.to_csv(index=False))
        archive.writestr('hotel_summary.csv', summarize(filtered,'hotel').to_csv(index=False))
        archive.writestr('cleaning_audit.csv', audit.to_csv(index=False))
        archive.writestr('settings.json', json.dumps(settings, indent=2))
        archive.writestr('report.html', report)
    st.download_button('Download complete analysis pack · ZIP', bundle.getvalue(), 'hotel_analysis_pack.zip', 'application/zip')
    st.markdown('''#### Build your Tableau dashboard

1. Connect → Text File → select the exported `bookings.csv`.
2. Set `arrival_date` to Date. Use Month on columns and record count on rows for demand.
3. Create **Cancellation rate** as `AVG([is_canceled])` and format as percentage.
4. Compare hotels using `hotel` and `AVG([adr])`; add hotel, market segment and date filters.
5. Show booking counts beside cancellation rates so the audience can assess sample size.

Exports reflect current filters and cleaning settings. Refresh by downloading a new pack; this is a manual Tableau export workflow.''')
    st.download_button('Download CSV template', demo_data().head(0).to_csv(index=False).encode(), 'hotel_bookings_template.csv', 'text/csv')

st.divider()
st.caption('STAYSCOPE  ·  Exploratory data science  ·  Original notebook preserved  ·  No predictive models')
