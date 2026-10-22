# Hotel Booking Analytics

An interactive descriptive data science app based on the cleaning and exploratory analysis in `FODS_REVIEW2.ipynb`. Explore booking volume, seasonality, ADR, lead time and cancellation rates with sample counts. The app performs no model training or prediction. The notebook is archived byte-for-byte unchanged, including its original ML sections and original local dataset path.

## Research workspace

| Section | Features |
| --- | --- |
| Overview | Source benchmarks, monthly demand and pricing, hotel performance table, booking economics and cancellation matrix |
| Seasonality | Monthly booking/ADR/cancellation trends, arrival calendar heatmap, weekday analysis |
| Cancellations | Group rates, booking counts, 95% Wilson intervals, configurable group-size threshold |
| Guests & markets | Guest composition, stay-length bands, top markets, rates by guest profile |
| Hotel comparison | Side-by-side averages, cancellation rates, ADR distributions and lead times |
| Statistics lab | Pearson/Spearman correlation; reproducible two-sided permutation tests |
| Data explorer | Text search, column selection, sorting and complete matching-record download |
| Quality & methodology | Cleaning audit, retention, column types, missingness, unique counts and rules |
| Reports & Tableau | Printable HTML report, CSV exports, input template and complete ZIP analysis pack |

All sections respect hotel/market/country/date/outcome filters, except data quality which audits the complete source. Reset filters restores defaults. An outcome filter makes cancellation rates conditional; the cancellation page flags that setting.

Permutation tests use a fixed seed, 2,000 permutations and at most 2,000 sampled observations per group. The reported effect and counts use the same sampled observations. No multiple-comparison correction is applied; this is exploratory inference. Wilson intervals assume independent bookings. Correlations for constant features remain undefined. Missing calendar months have zero observed bookings and undefined rates.

## Run

Requires Python 3.11 or later.

```sh
pip install -r requirements.txt
streamlit run app.py
```

The app starts with **explicitly labeled synthetic demo data**. Upload the original `hotel_bookings.csv`, or put it at `data/hotel_bookings.csv` before starting. The original CSV was not available during creation and is not bundled. Required columns are listed in `analysis.py`; optional market segment, country, deposit type and customer type enable additional comparisons. Upload raw categorical data, not a one-hot encoded/scaled export.

## Analysis and Tableau

- CSV ingestion and validation, transparent cleaning audit, configurable duplicate removal and optional IQR capping.
- Hotel, market and country filters, arrival date range, monthly booking trends, ADR and lead-time distributions.
- Cancellation rates alongside counts, with a minimum sample-size threshold.
- Download filtered records, monthly summaries and cleaning audit. Connect the CSV to Tableau via Text File; use `AVG(is_canceled)` as the cancellation rate and format as percentage. This is an export workflow, not a live Tableau connection.

Streamlit provides the interface and Python session backend; pandas performs analysis in memory. Uploaded files are not written to disk. No database or external service is required. On a hosted instance, uploads are processed by that hosting server.

## Method and limitations

Missing children/babies become zero and missing categories become Unknown. Invalid guest/night counts, missing or negative ADR/lead time and invalid arrival dates are removed. Duplicate removal defaults on; identical bookings may be legitimate, so compare both settings. IQR capping defaults off to preserve observed prices. Missing optional fields remain visible in the audit. Historical observational patterns do not prove causation. Demo results are illustrative. ADR currency comes from the input; ADR × nights is only an estimated booking value.

## Deploy

Push this folder to GitHub, then choose the repository and `app.py` in Streamlit Community Cloud. Install dependencies from `requirements.txt`. The demo works without any dataset; users can upload a CSV. The notebook does not need to run to use the app.
