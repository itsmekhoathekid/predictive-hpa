# UCI Real Estate Ridge v1

This model is a compact Ridge-regression demonstration trained on the
[UCI Real Estate Valuation dataset](https://archive.ics.uci.edu/dataset/477/real%26),
licensed under CC BY 4.0.

The dataset contains 414 transactions from Sindian District, New Taipei City,
Taiwan. Its target is the house price per unit area in 10,000 New Taiwan Dollars
per Ping, where one Ping is 3.3 square metres.

The training pipeline uses six source features, two deterministic derived
features, `StandardScaler`, and `RidgeCV`. The exported JSON contains the full
feature order, scaler parameters, coefficients, evaluation metrics, dataset URL,
and dataset checksum.

With the deterministic 80/20 split (`random_state=42`), version 1 selected
`alpha=10` and achieved MAE `4.368`, RMSE `6.528`, and R² `0.746` on 83 holdout
rows. MAE and RMSE use the dataset target unit of 10,000 TWD per Ping.

## Intended use and limitations

This artifact exists to demonstrate a transparent inference service and
Kubernetes autoscaling. The observations are geographically limited and date
from 2012-2013. It must not be used for current financial, lending, investment,
or property-purchase decisions.
