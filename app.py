from pathlib import Path
from io import BytesIO
import html
import json
import zipfile
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from analysis import (REQUIRED, demo_data, prepare, summarize, monthly_summary,
                      wilson_interval, permutation_comparison, findings)

st.set_page_config(page_title='Hotel Booking Analytics', page_icon='▦', layout='wide')
px.defaults.template = 'plotly_white'
px.defaults.color_discrete_sequence = ['#3455ff', '#ff925e', '#a28aff', '#bad954', '#a9b8dd']
st.markdown('<style>' + (Path(__file__).parent / 'ui.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=3)
def load_csv(content):
    return pd.read_csv(BytesIO(content))


def chart(fig, height=340):
    fig.update_layout(margin=dict(l=20, r=20, t=55, b=30), font=dict(family='Arial, sans-serif', color='#77819a', size=11),
        title_font=dict(size=14, color='#242c41'), paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        legend_title_text='', height=height, hoverlabel=dict(bgcolor='#1c2230',font_color='white'),
        legend=dict(orientation='h',y=-.2,x=0), colorway=px.defaults.color_discrete_sequence)
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor='#e1e6f0')
    fig.update_yaxes(gridcolor='#edf0f6', zeroline=False)
    st.plotly_chart(fig, width='stretch')


def section(title, detail):
    st.markdown(f'<div class="section-heading"><strong>{html.escape(title)}</strong><span>{html.escape(detail)}</span></div>',unsafe_allow_html=True)


def table_download(label, table, filename):
    st.download_button(label, table.to_csv(index=False).encode('utf-8'), filename, 'text/csv')


def reset_filters():
    for key in list(st.session_state):
        if key.startswith('filter_'):
            del st.session_state[key]


with st.sidebar:
    st.markdown('<div class="identity"><div class="identity-mark">HB</div><strong>Hotel Booking Analytics</strong><span>RESEARCH WORKSPACE</span></div>',unsafe_allow_html=True)
    page = st.radio('Workspace', ['Overview', 'Seasonality', 'Cancellations', 'Guests & markets',
        'Hotel comparison', 'Statistics lab', 'Data explorer', 'Quality & methodology', 'Reports & Tableau'],
        label_visibility='collapsed',format_func=lambda p: {'Overview':'01  Portfolio overview','Seasonality':'02  Demand & seasonality','Cancellations':'03  Cancellation analysis','Guests & markets':'04  Guest & market mix','Hotel comparison':'05  Hotel benchmarking','Statistics lab':'06  Statistical analysis','Data explorer':'07  Booking register','Quality & methodology':'08  Data quality','Reports & Tableau':'09  Reporting & exports'}[p])
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

page_titles = {'Overview':('Portfolio overview','Booking demand, commercial indicators and cancellation exposure.'),
    'Seasonality':('Demand & seasonality','Arrival patterns across months, years and weekdays.'),
    'Cancellations':('Cancellation analysis','Observed outcomes with sample sizes and statistical uncertainty.'),
    'Guests & markets':('Guest & market mix','Composition, booking channels and stay characteristics.'),
    'Hotel comparison':('Hotel benchmarking','Compare observed performance under a consistent set of filters.'),
    'Statistics lab':('Statistical analysis','Relationships and differences between observed booking groups.'),
    'Data explorer':('Booking register','Search, inspect and export the records behind the analysis.'),
    'Quality & methodology':('Data quality & methodology','Source coverage, validation and preparation decisions.'),
    'Reports & Tableau':('Reporting & exports','Analysis reports, supporting tables and Tableau data handoffs.')}
heading, description = page_titles[page]
page_number = list(page_titles).index(page) + 1
status = 'SYNTHETIC DATA' if source == 'Synthetic demo' else 'SOURCE DATA'
st.markdown(f'<div class="masthead"><div class="page-number">{page_number:02d}</div><div><div class="overline">Hotel booking research / {html.escape(heading)}</div><h1>{html.escape(heading)}</h1><p>{description}</p></div><div class="status">{status}</div></div>', unsafe_allow_html=True)
if source == 'Synthetic demo':
    st.markdown('<div class="source-note">Illustrative dataset · Upload the original booking CSV to use actual project data. All figures below currently use synthetic records.</div>',unsafe_allow_html=True)
st.caption(f'{filtered.arrival_date.min():%d %b %Y} – {filtered.arrival_date.max():%d %b %Y} · {len(filtered):,} selected records · {filtered.hotel.nunique()} hotel types' if len(filtered) else 'No records selected')
if filtered.empty:
    st.warning('No bookings match these filters. Adjust your selections.')
    st.stop()

monthly = monthly_summary(filtered)
insights = findings(filtered, minimum)
groups = [c for c in ['hotel', 'market_segment', 'deposit_type', 'customer_type',
          'country', 'guest_profile', 'lead_time_band', 'stay_band'] if c in filtered]

if page == 'Overview':
    with st.container(key='kpi_strip'):
        a, b, c, d = st.columns([1.15,1,1,1])
        a.metric('Bookings', f'{len(filtered):,}',delta=f'{len(filtered)/len(clean):.1%} of source',delta_color='off')
        b.metric('Cancellation rate', f'{filtered.is_canceled.mean():.1%}',
            delta=f'{(filtered.is_canceled.mean()-clean.is_canceled.mean())*100:+.1f} pp vs source',delta_color='off')
        c.metric('Average daily rate', f'{filtered.adr.mean():,.2f}',
            delta=f'{filtered.adr.mean()-clean.adr.mean():+.2f} vs source',delta_color='off')
        d.metric('Average stay', f'{filtered.total_nights.mean():.1f} nights',
            delta=f'{filtered.total_nights.mean()-clean.total_nights.mean():+.1f} vs source',delta_color='off')
    st.caption('Benchmark: all cleaned source records, before dashboard filters. ADR is expressed in source currency. Booking volume is not occupancy.')
    summary_tab, economics_tab, detail_tab = st.tabs(['Performance summary','Booking economics','Portfolio detail'])
    with summary_tab:
        section('Demand and pricing','Monthly arrivals · observed bookings')
        trend = make_subplots(specs=[[{'secondary_y':True}]])
        trend.add_trace(go.Bar(x=monthly.month,y=monthly.bookings-monthly.cancellations,name='Not canceled',marker_color='#3455ff'),secondary_y=False)
        trend.add_trace(go.Bar(x=monthly.month,y=monthly.cancellations,name='Canceled',marker_color='#ff925e'),secondary_y=False)
        trend.add_trace(go.Scatter(x=monthly.month,y=monthly.mean_adr,name='Mean ADR',mode='lines+markers',line=dict(color='#8a74db',width=2),marker=dict(size=4)),secondary_y=True)
        trend.update_layout(barmode='stack',title='Booking volume and average daily rate')
        trend.update_yaxes(title_text='Bookings',secondary_y=False)
        trend.update_yaxes(title_text='ADR · source currency',secondary_y=True,showgrid=False)
        chart(trend,380)
        left,right = st.columns([1.25,1])
        with left:
            market_col = 'market_segment' if 'market_segment' in filtered else 'guest_profile'
            market = summarize(filtered,market_col).sort_values('bookings').tail(8)
            chart(px.bar(market,x='bookings',y=market_col,orientation='h',title='Booking mix by '+market_col.replace('_',' '),
                color_discrete_sequence=['#3455ff'],hover_data=['cancellation_rate_pct','mean_adr'],labels={'bookings':'Bookings',market_col:''}))
        with right:
            hotel_rates=summarize(filtered,'hotel')
            chart(px.bar(hotel_rates,x='hotel',y='cancellation_rate_pct',text_auto='.1f',title='Cancellation rate by hotel',
                color='hotel',hover_data=['bookings'],labels={'hotel':'','cancellation_rate_pct':'Cancellation rate (%)'}))
        section('Hotel performance','Rates and volumes under the current selection')
        portfolio=summarize(filtered,'hotel')
        portfolio['Booking share (%)']=portfolio.bookings/len(filtered)*100
        st.dataframe(portfolio.rename(columns={'hotel':'Hotel','bookings':'Bookings','cancellations':'Canceled','mean_adr':'Mean ADR','mean_lead_days':'Lead time (days)','cancellation_rate_pct':'Cancellation (%)','ci_lower_pct':'95% lower (%)','ci_upper_pct':'95% upper (%)'}).round(2),hide_index=True,width='stretch',
            column_config={'Booking share (%)':st.column_config.ProgressColumn(min_value=0,max_value=100,format='%.1f%%')})
    with economics_tab:
        section('Booking value composition','ADR × nights · estimates, not realized revenue')
        value=filtered.assign(Outcome=filtered.is_canceled.map({0:'Not canceled',1:'Canceled'})).groupby('Outcome',as_index=False).agg(
            Bookings=('adr','size'),Estimated_value=('booking_value_estimate','sum'),Room_nights=('total_nights','sum'))
        left,right=st.columns(2)
        with left:
            chart(px.bar(value,x='Outcome',y='Estimated_value',color='Outcome',title='Estimated booked value by outcome',labels={'Estimated_value':'ADR × nights · source currency'}))
        with right:
            chart(px.box(filtered,x='hotel',y='adr',color='hotel',points=False,title='Rate distribution by hotel',labels={'hotel':'Hotel','adr':'ADR · source currency'}))
        st.dataframe(value.rename(columns={'Estimated_value':'Estimated booking value','Room_nights':'Booked nights'}).round(2),hide_index=True,width='stretch')
        section('Price distribution','Selected booking records')
        chart(px.histogram(filtered,x='adr',color='hotel',nbins=45,barmode='overlay',opacity=.7,title='Daily rate distribution',labels={'adr':'ADR · source currency'}))
        st.markdown('<div class="analysis-note">Estimated value uses the daily rate and stated length of stay. It does not account for taxes, refunds, room quantity, no-shows or actual payments. A non-canceled reservation is not evidence of collected revenue.</div>',unsafe_allow_html=True)
    with detail_tab:
        section('Cancellation by booking window and stay length','Cell values show rate; hover for sample size')
        cell=filtered.groupby(['lead_time_band','stay_band'],observed=True).is_canceled.agg(['mean','size']).reset_index()
        rates=cell.pivot(index='lead_time_band',columns='stay_band',values='mean')*100
        counts=cell.pivot(index='lead_time_band',columns='stay_band',values='size').reindex(index=rates.index,columns=rates.columns)
        heat=go.Figure(go.Heatmap(z=rates.values,x=rates.columns.astype(str),y=rates.index.astype(str),customdata=counts.values,
            colorscale=[[0,'#edf0ff'],[1,'#3455ff']],zmin=0,zmax=100,colorbar=dict(title='Rate %'),
            hovertemplate='Lead time: %{y}<br>Stay: %{x}<br>Cancellation: %{z:.1f}%<br>Bookings: %{customdata}<extra></extra>'))
        heat.update_layout(title='Cancellation profile · booking lead time × stay length')
        chart(heat,380)
        section('Monthly operating table','Blank rates indicate months with no observations')
        st.dataframe(monthly.rename(columns={'month':'Arrival month','bookings':'Bookings','cancellations':'Canceled','mean_adr':'Mean ADR','mean_lead_days':'Lead time (days)','cancellation_rate_pct':'Cancellation (%)','ci_lower_pct':'95% lower (%)','ci_upper_pct':'95% upper (%)'}).round(2),hide_index=True,width='stretch')
        table_download('Export monthly performance',monthly,'monthly_performance.csv')

elif page == 'Seasonality':
    st.subheader('Arrival demand by period')
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
    st.subheader('Cancellation exposure by booking segment')
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
    st.subheader('Guest composition and distribution channels')
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
    st.subheader('Comparative hotel performance')
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
    st.subheader('Correlation and group comparisons')
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
    st.subheader('Selected booking records')
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
    st.subheader('Data preparation and validation')
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
    st.subheader('Analysis deliverables')
    settings = {'source':source, 'filters':applied_filters, 'deduplicate':deduplicate,
        'iqr_capping':cap, 'minimum_group_size':int(minimum), 'selected_rows':len(filtered)}
    report = ('<!doctype html><html><head><meta charset="utf-8"><title>Hotel Booking Analysis Report</title>'
        '<style>body{font:16px Arial;color:#183247;max-width:1000px;margin:50px auto;padding:24px}'
        'h1{color:#087f8c}table{border-collapse:collapse;width:100%;font-size:13px}'
        'td,th{padding:9px;border:1px solid #ddd;text-align:left}pre{white-space:pre-wrap}</style></head><body>'
        '<h1>Hotel Booking Analysis</h1><p>Source: '+html.escape(source)+'</p><h2>Findings</h2><ul>'
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
st.caption('HOTEL BOOKING ANALYTICS  /  Historical booking research  /  Source currency applies to all monetary values')
