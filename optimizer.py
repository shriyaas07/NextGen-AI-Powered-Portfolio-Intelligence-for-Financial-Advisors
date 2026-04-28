import pandas as pd
import numpy as np
import json
import os
import cvxpy as cp
from pypfopt import EfficientFrontier, expected_returns, risk_models

WEEKS_PER_YEAR = 52
RISK_FREE_RATE  = 0.065
DATA_DIR        = os.path.join(os.path.dirname(__file__), "data")

# ── Load data ─────────────────────────────────────────────────
returns_df = pd.read_csv(
    os.path.join(DATA_DIR, "master_returns.csv"),
    index_col=0, parse_dates=True)
cov_df     = pd.read_csv(
    os.path.join(DATA_DIR, "covariance_matrix.csv"),
    index_col=0)
stats_df   = pd.read_csv(
    os.path.join(DATA_DIR, "asset_statistics.csv"),
    index_col=0)
corr_df    = pd.read_csv(
    os.path.join(DATA_DIR, "correlation_matrix.csv"),
    index_col=0)
mc_df      = pd.read_csv(
    os.path.join(DATA_DIR, "monte_carlo.csv"))

try:
    with open(os.path.join(DATA_DIR, "portfolios.json")) as f:
        PRECOMPUTED = json.load(f)
except Exception:
    PRECOMPUTED = {}

all_cols = returns_df.columns.tolist()

# ── Asset class detection ─────────────────────────────────────
def identify_asset_class(col):
    c = col.upper()
    if c.startswith("CRYPTO_"):                              return "crypto"
    if c.startswith("ETF_"):                                 return "etf"
    if c.startswith("FI_"):                                  return "fi"
    if "GOLD"   in c:                                        return "gold"
    if "SILVER" in c:                                        return "silver"
    if "EMBASSY" in c or "REALESTATE" in c or "REIT" in c:  return "realestate"
    if c.endswith(".NS"):                                    return "equity"
    return "other"

ASSET_COLUMNS = {
    ac: [c for c in all_cols if identify_asset_class(c) == ac]
    for ac in ["equity","gold","silver","etf","crypto","realestate"]
}

print("Optimizer loaded")
for ac, cols in ASSET_COLUMNS.items():
    if cols:
        print(f"  {ac}: {len(cols)} assets")

# ── Helpers ───────────────────────────────────────────────────
def get_tickers_for_selection(selected_assets):
    tickers = []
    for ac in selected_assets:
        tickers.extend(ASSET_COLUMNS.get(ac, []))
    return list(set(tickers))

def prepare_returns(tickers):
    valid = [t for t in tickers if t in returns_df.columns]
    df    = returns_df[valid].copy()
    df    = df.ffill(limit=4).bfill(limit=4)
    df    = df.clip(-0.5, 3.0)
    df    = df.replace([np.inf, -np.inf], np.nan)
    df    = df.fillna(0)
    df    = df.loc[:, df.std() > 1e-6]
    return df.astype(np.float64)

def compute_covariance(df):
    try:
        S = risk_models.CovarianceShrinkage(
                df, frequency=WEEKS_PER_YEAR).ledoit_wolf()
    except Exception:
        S = df.cov() * WEEKS_PER_YEAR
    vals = np.nan_to_num(S.values, nan=1e-8,
                         posinf=1e-8, neginf=0.0)
    np.fill_diagonal(vals, np.maximum(vals.diagonal(), 1e-8))
    return pd.DataFrame(vals, index=S.index, columns=S.columns)

def normalize_amounts(weights, amount):
    w      = {k: v for k, v in weights.items() if v > 0.001}
    total  = sum(w.values())
    w_norm = {k: v/total for k, v in w.items()}
    amounts = {}
    rem     = float(amount)
    items   = list(w_norm.items())
    for i, (k, wt) in enumerate(items):
        if i == len(items) - 1:
            amounts[k] = round(rem, 2)
        else:
            val        = round(wt * amount, 2)
            amounts[k] = val
            rem       -= val
    return {k: round(v, 4) for k, v in w_norm.items()}, amounts

def classify_risk(portfolio_type, volatility=None):
    if portfolio_type == "high_return": return "High Risk"
    if portfolio_type == "low_risk":    return "Low Risk"
    if volatility and volatility > 20:  return "High Risk"
    return "Medium Risk"

def project_corpus(amount, annual_return_pct, years):
    r      = annual_return_pct / 100
    corpus = amount * ((1 + r) ** years)
    gain   = corpus - amount
    return round(corpus, 2), round(gain, 2)

def build_portfolio(key, name, weights, perf, amount, years=5):
    w, amt       = normalize_amounts(weights, amount)
    ann_ret      = round(perf[0]*100, 2)
    vol          = round(perf[1]*100, 2)
    sharpe       = round(perf[2], 3)
    corpus, gain = project_corpus(amount, ann_ret, years)
    return {
        "label"            : name,
        "risk_label"       : classify_risk(key, vol),
        "weights"          : w,
        "amounts"          : amt,
        "expected_return"  : ann_ret,
        "volatility"       : vol,
        "sharpe_ratio"     : sharpe,
        "years"            : years,
        "projected_corpus" : corpus,
        "projected_gain"   : gain,
    }

# ── Risk buckets ──────────────────────────────────────────────
RISK_BUCKETS = {
    "low"    : ["gold", "silver", "realestate"],
    "medium" : ["etf"],
    "high"   : ["equity", "crypto"],
}

# ── Main optimizer ────────────────────────────────────────────
def run_optimizer(amount, selected_assets=None, years=5):
    try:
        print(f"\n{'='*50}")
        print(f"Amount: Rs.{float(amount):,.0f} | "
              f"Assets: {selected_assets} | Years: {years}")

        if not selected_assets:
            selected_assets = list(ASSET_COLUMNS.keys())

        tickers = get_tickers_for_selection(selected_assets)
        if not tickers:
            return {"error": "No valid assets found."}

        # Cap equity to 80 stocks to prevent memory crash on free hosting
        import random
        random.seed(42)
        equity_tickers  = [t for t in tickers if identify_asset_class(t) == "equity"]
        other_tickers   = [t for t in tickers if identify_asset_class(t) != "equity"]
        if len(equity_tickers) > 80:
            equity_tickers = random.sample(equity_tickers, 80)
        tickers = other_tickers + equity_tickers

        df = prepare_returns(tickers)
        if df.shape[1] < 2:
            return {"error": "Need at least 2 valid assets."}

        # Expected returns
        mu = expected_returns.mean_historical_return(
                 df, frequency=WEEKS_PER_YEAR)
        mu = mu.replace([np.inf, -np.inf], np.nan)

        # Fill NaN per asset class
        for col in mu.index[mu.isna()]:
            ac      = identify_asset_class(col)
            ac_cols = [c for c in mu.index
                       if identify_asset_class(c) == ac
                       and not np.isnan(mu[c])]
            mu[col] = mu[ac_cols].mean() if ac_cols else 0.05

        mu = mu.clip(0.01, 1.5)

        # Remove very bad equities
        non_eq = [c for c in mu.index
                  if identify_asset_class(c) != "equity"]
        eq     = [c for c in mu.index
                  if identify_asset_class(c) == "equity"
                  and mu[c] > -0.10]
        mu     = mu[list(set(non_eq + eq))]

        if len(mu) < 2:
            return {"error": "Not enough assets."}

        # Covariance
        df_mu  = df[[c for c in mu.index if c in df.columns]]
        S      = compute_covariance(df_mu)
        common = [a for a in mu.index if a in S.index]
        mu     = mu[common]
        S      = S.loc[common, common]
        n      = len(common)

        # Asset groups + risk index mapping
        ac_groups  = {}
        ticker_idx = {t: i for i, t in enumerate(common)}
        for t in common:
            ac = identify_asset_class(t)
            ac_groups.setdefault(ac, []).append(t)

        # Build risk bucket index lists
        risk_idx = {"low": [], "medium": [], "high": []}
        for t in common:
            ac = identify_asset_class(t)
            i  = ticker_idx[t]
            if   ac in RISK_BUCKETS["low"]:    risk_idx["low"].append(i)
            elif ac in RISK_BUCKETS["medium"]:  risk_idx["medium"].append(i)
            else:                               risk_idx["high"].append(i)

        # Which risk buckets are actually present
        has_low  = len(risk_idx["low"])  > 0
        has_med  = len(risk_idx["medium"]) > 0
        has_high = len(risk_idx["high"]) > 0

        print(f"Risk buckets present: "
              f"low={has_low}({len(risk_idx['low'])}) "
              f"med={has_med}({len(risk_idx['medium'])}) "
              f"high={has_high}({len(risk_idx['high'])})")

        for c in mu.index:
            if not c.endswith(".NS"):
                print(f"  {c}: {mu[c]*100:.2f}%")

        positive_mu = mu[mu > 0]
        if len(positive_mu) == 0:
            positive_mu = mu

        target_high     = float(positive_mu.max()) * 0.75
        target_balanced = float(positive_mu.mean())
        max_w           = min(0.40, max(1.0/n + 0.05, 0.15))

        # ── Core optimize function ────────────────────────────
        def optimize(obj, portfolio_type, target=None):

            def run_ef(with_constraints):
                # Low risk gets higher max per asset
                # so gold/silver can take big allocations
                if portfolio_type == "low_risk":
                    wb = (0.0, 0.80)
                else:
                    wb = (0.0, max_w)

                ef = EfficientFrontier(mu, S, weight_bounds=wb)

                if with_constraints:
                    low_i  = risk_idx["low"]
                    high_i = risk_idx["high"]

                    # ── LOW RISK: heavy in safe assets ────────
                    if portfolio_type == "low_risk":
                        if has_low:
                            # Safe assets get AT LEAST 60%
                            ef.add_constraint(
                                lambda w, i=low_i:
                                    cp.sum(w[i]) >= 0.60)
                        if has_high:
                            # Risky assets get AT MOST 25%
                            ef.add_constraint(
                                lambda w, i=high_i:
                                    cp.sum(w[i]) <= 0.25)

                    # ── BALANCED: moderate safe allocation ────
                    elif portfolio_type == "balanced":
                        if has_low:
                            # Safe assets get AT LEAST 20%
                            ef.add_constraint(
                                lambda w, i=low_i:
                                    cp.sum(w[i]) >= 0.20)
                        if has_high:
                            # Risky assets get AT MOST 65%
                            ef.add_constraint(
                                lambda w, i=high_i:
                                    cp.sum(w[i]) <= 0.65)

                    # ── HIGH RETURN: heavy in risky assets ────
                    elif portfolio_type == "high_return":
                        if has_high:
                            # Risky assets get AT LEAST 65%
                            ef.add_constraint(
                                lambda w, i=high_i:
                                    cp.sum(w[i]) >= 0.65)

                    # ── Min 3% per selected non-equity class ──
                    for ac, ac_tickers in ac_groups.items():
                        if ac == "equity":
                            continue
                        idx = [ticker_idx[t] for t in ac_tickers
                               if t in ticker_idx]
                        if idx:
                            ef.add_constraint(
                                lambda w, i=idx:
                                    cp.sum(w[i]) >= 0.03)

                # Objective
                if obj == "min_vol":
                    ef.min_volatility()
                elif obj == "target":
                    ef.efficient_return(target_return=target)
                elif obj == "sharpe":
                    ef.max_sharpe(risk_free_rate=RISK_FREE_RATE)

                w = ef.clean_weights()
                p = ef.portfolio_performance(
                        risk_free_rate=RISK_FREE_RATE,
                        verbose=False)
                return w, p

            # Try constrained
            try:
                w, p = run_ef(with_constraints=True)
                print(f"  [{portfolio_type}] Constrained OK")
                for bucket, idx in risk_idx.items():
                    wt = sum(w.get(common[i], 0) for i in idx)
                    if wt > 0.001:
                        print(f"    {bucket}: {wt*100:.1f}%")
                return w, p
            except Exception as e:
                print(f"  [{portfolio_type}] Constrained failed: {e}")

            # Fallback unconstrained
            try:
                w, p = run_ef(with_constraints=False)
                print(f"  [{portfolio_type}] Unconstrained OK")
                return w, p
            except Exception as e2:
                print(f"  [{portfolio_type}] Both failed: {e2}")
                return None, None

        portfolios = {}

        # ── Low Risk ──────────────────────────────────────────
        print("Optimizing Low Risk...")
        w3, p3 = optimize("min_vol", "low_risk")
        if w3 and p3:
            portfolios["low_risk"] = build_portfolio(
                "low_risk", "Low Risk Portfolio",
                dict(w3), p3, amount, years)
            print(f"  Return: {portfolios['low_risk']['expected_return']}% "
                  f"| Vol: {portfolios['low_risk']['volatility']}%")

        # ── Balanced ──────────────────────────────────────────
        print("Optimizing Balanced...")
        w1, p1 = optimize("target", "balanced", target_balanced)
        if w1 and p1:
            portfolios["balanced"] = build_portfolio(
                "balanced", "Balanced Portfolio",
                dict(w1), p1, amount, years)
            print(f"  Return: {portfolios['balanced']['expected_return']}% "
                  f"| Vol: {portfolios['balanced']['volatility']}%")

        # ── High Return ───────────────────────────────────────
        print("Optimizing High Return...")
        for pct in [0.75, 0.70, 0.65, 0.60, 0.55, 0.50]:
            t      = float(positive_mu.max()) * pct
            w2, p2 = optimize("target", "high_return", t)
            if w2 and p2:
                portfolios["high_return"] = build_portfolio(
                    "high_return", "High Return Portfolio",
                    dict(w2), p2, amount, years)
                print(f"  Return: "
                      f"{portfolios['high_return']['expected_return']}%")
                break

        if not portfolios:
            return {"error": "Optimization failed. Try different assets."}

        return portfolios

    except Exception as e:
        print(f"Optimizer error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Optimization error: {str(e)}"}

# ── Flask helpers ─────────────────────────────────────────────
def get_correlation_heatmap(top_n=30):
    top   = stats_df["sharpe_ratio"]\
                .sort_values(ascending=False)\
                .head(top_n).index.tolist()
    valid = [a for a in top if a in corr_df.index]
    sub   = corr_df.loc[valid, valid].round(3)
    return {"labels": valid, "data": sub.values.tolist()}

def get_monte_carlo_data():
    return {
        "returns"     : mc_df["return"].round(2).tolist(),
        "volatilities": mc_df["volatility"].round(2).tolist(),
        "sharpes"     : mc_df["sharpe"].round(3).tolist(),
    }

def get_asset_stats(filters=None):
    df = stats_df.copy()
    df = df[df["sharpe_ratio"] <= 3.0]
    df = df[df["annual_vol"]   >  0]
    if filters:
        if filters.get("min_sharpe"):
            df = df[df["sharpe_ratio"] >=
                    float(filters["min_sharpe"])]
        if filters.get("max_vol"):
            df = df[df["annual_vol"] <=
                    float(filters["max_vol"])]
        if filters.get("min_return"):
            df = df[df["annual_return"] >=
                    float(filters["min_return"])]
    return df.sort_values("sharpe_ratio", ascending=False)\
             .head(100).reset_index()\
             .to_dict(orient="records")
