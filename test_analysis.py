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
