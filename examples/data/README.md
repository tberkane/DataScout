# Example datasets

The data for the three data collection tasks evaluated in the EMNLP 2025 paper
([Berkane et al., 2025](https://doi.org/10.18653/v1/2025.findings-emnlp.674)). Each row is one data point
with the web page it comes from. Dates are given as written in the source, so their formats vary.

| File | Task | Columns |
| --- | --- | --- |
| `app_downloads.csv` | Reported download counts of COVID-19 contact-tracing apps in five U.S. states | `state, date, downloads, url` |
| `climate_events.csv` | Earthquakes, floods and droughts in Haiti and Cameroon | `country, event_type, date, url` |
| `police_misconduct.csv` | Reported incidents of police misconduct | `date, description, url` |

The rows were taken from public web pages, mostly news reports. They are not part of the installed package.
