import pandas as pd
import pytest
from analysis import demo_data, prepare, summarize


def test_cleaning_audit_and_rates():
    raw = demo_data().head(10)
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    raw.loc[1, 'adr'] = -10
    raw.loc[2, 'arrival_date_month'] = 'invalid'
    clean, audit = prepare(raw)
    assert len(clean) == 8
    counts = audit.set_index('Measure').Rows
    assert counts['Duplicates removed'] == 1
    assert counts['Invalid records removed'] == 1
    assert counts['Invalid dates removed'] == 1
    table = summarize(clean, 'hotel')
    assert table.bookings.sum() == len(clean)
    assert table.cancellations.sum() == clean.is_canceled.sum()
    assert table.cancellation_rate_pct.between(0, 100).all()


def test_validation_and_options():
    raw = demo_data().head(10)
    with pytest.raises(ValueError, match='Missing required columns'):
        prepare(raw.drop(columns='hotel'))
    raw.loc[0, 'is_canceled'] = 2
    with pytest.raises(ValueError, match='is_canceled'):
        prepare(raw)
    raw = demo_data().head(10)
    duplicate = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    assert len(prepare(duplicate, deduplicate=False)[0]) == 11
    assert len(prepare(duplicate, cap=True)[0]) == 10


def test_streamlit_demo_and_empty_filters():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('app.py').run(timeout=30)
    assert not app.exception
    assert app.metric[0].value == '1,500'
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('No bookings match' in w.value for w in app.warning)


def test_every_workspace_page_and_statistics():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('app.py').run(timeout=30)
    for page in ['Overview','Seasonality','Cancellations','Guests & markets','Hotel comparison',
                 'Statistics lab','Data explorer','Quality & methodology','Reports & Tableau']:
        app.radio[0].set_value(page).run(timeout=30)
        assert not app.exception, (page, [e.value for e in app.exception])
    app.radio[0].set_value('Statistics lab').run()
    next(b for b in app.button if b.label == 'Run statistical comparison').click().run(timeout=30)
    assert not app.exception
    assert any(m.label == 'Permutation p-value' for m in app.metric)
    next(s for s in app.selectbox if s.label == 'Correlation method').set_value('spearman').run()
    assert not app.exception


def test_reset_and_single_hotel():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file('app.py').run(timeout=30)
    app.multiselect[0].set_value(['City Hotel']).run()
    app.radio[0].set_value('Hotel comparison').run()
    assert not app.exception
    assert any('at least two hotel' in i.value for i in app.info)
    next(b for b in app.button if b.label == 'Reset filters').click().run()
    assert len(app.multiselect[0].value) == 2
    assert not app.exception


def test_intervals_permutations_and_calendar_gaps():
    from analysis import wilson_interval, permutation_comparison, monthly_summary
    lo,hi = wilson_interval(0, 10)
    assert lo == pytest.approx(0, abs=1e-14)
    assert hi == pytest.approx(.2775328, abs=1e-6)
    result = permutation_comparison([1]*20, [10]*20, iterations=199)
    assert result['difference'] == -9
    assert result['p_value'] <= .01
    assert permutation_comparison([1]*20,[1]*20,iterations=99)['p_value'] == 1
    raw = demo_data().head(2)
    raw['arrival_date_year'] = 2024
    raw['arrival_date_month'] = ['January','March']
    raw['arrival_date_day_of_month'] = 1
    clean,_ = prepare(raw)
    summary = monthly_summary(clean)
    assert summary.bookings.tolist() == [1,0,1]
    assert pd.isna(summary.iloc[1].cancellation_rate_pct)


def test_malformed_dates_and_fractional_guests():
    raw = demo_data().head(3)
    raw[['arrival_date_year','adults']] = raw[['arrival_date_year','adults']].astype(float)
    raw.loc[0,'arrival_date_year'] = 2024.5
    raw.loc[1,'adults'] = 1.5
    clean,audit = prepare(raw)
    assert len(clean) == 1
    assert clean.iloc[0].guest_count >= 1
