"""Pure calculations. Adjusted Close drives returns; OHLC remains unadjusted."""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

REQUIRED = ['date', 'symbol', 'open', 'high', 'low', 'close', 'adj_close', 'volume']

def clean_prices(frame):
    missing = set(REQUIRED) - set(frame.columns)
    if missing:
        raise ValueError('缺少字段：' + ', '.join(sorted(missing)))
    df = frame[REQUIRED].copy()
    df['date'] = pd.to_datetime(df.date, errors='coerce').dt.normalize()
    df['symbol'] = df.symbol.astype(str).str.upper().str.strip()
    for col in REQUIRED[2:]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    bad = (df[REQUIRED].isna().any(axis=1) | (df.close <= 0) | (df.adj_close <= 0)
           | (df.open <= 0) | (df.low <= 0) | (df.volume < 0)
           | (df.high < df[['open', 'close', 'low']].max(axis=1))
           | (df.low > df[['open', 'close', 'high']].min(axis=1)) | df.symbol.eq(''))
    rejected = int(bad.sum())
    df = df.loc[~bad].sort_values(['symbol', 'date'])
    duplicates = int(df.duplicated(['symbol', 'date']).sum())
    df = df.drop_duplicates(['symbol', 'date'], keep='last').reset_index(drop=True)
    return df, {'invalid_rows': rejected, 'duplicate_rows': duplicates, 'valid_rows': len(df)}

def price_matrix(df):
    # No forward filling: a missing observation must not become a zero return.
    return df.pivot(index='date', columns='symbol', values='adj_close').sort_index()

def daily_returns(prices):
    return prices.pct_change(fill_method=None)

def metrics(df):
    rows = []
    for symbol, part in df.groupby('symbol'):
        p = part.sort_values('date').set_index('date').adj_close
        if len(p) < 3:
            continue
        r = p.pct_change(fill_method=None).dropna()
        rows.append(dict(symbol=symbol, total_return=p.iloc[-1]/p.iloc[0]-1,
                         annual_volatility=r.std(ddof=1)*np.sqrt(252),
                         max_drawdown=(p/p.cummax()-1).min(),
                         mean_daily_return=r.mean(), observations=len(p),
                         first_date=p.index.min(), last_date=p.index.max()))
    return pd.DataFrame(rows).set_index('symbol') if rows else pd.DataFrame()

def common_window(df):
    bounds = df.groupby('symbol').date.agg(['min', 'max'])
    start, end = bounds['min'].max(), bounds['max'].min()
    return df[df.date.between(start, end)], start, end

def cluster_stocks(stats, k):
    features = ['total_return', 'annual_volatility', 'max_drawdown']
    x = stats[features].replace([np.inf, -np.inf], np.nan).dropna()
    if len(x) < k + 1 or x.drop_duplicates().shape[0] < k:
        raise ValueError('聚类至少需要K+1只股票，且特征不能全部相同。')
    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    model = KMeans(n_clusters=k, random_state=42, n_init=20)
    labels = model.fit_predict(z)
    if len(set(labels)) < 2:
        raise ValueError('数据无法形成两个不同的分组。')
    result = stats.loc[x.index].copy()
    result['cluster'] = ['组 '+str(v+1) for v in labels]
    return result, float(silhouette_score(z, labels)), model, scaler
