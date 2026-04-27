# NextGen — Portfolio Intelligence for Financial Advisors

NextGen is a fintech decision-support tool built for financial advisors and investment professionals. It automates client portfolio construction using Nobel Prize-winning Modern Portfolio Theory (MPT), reducing hours of manual work to under 30 seconds.

> Not intended as direct investment advice. For professional advisor and educational use only.

---

## Features

- **Portfolio Optimizer** — Generates 3 optimized portfolios (Balanced, High Return, Low Risk) across equities, gold, silver, crypto, ETFs and real estate using MPT
- **Stock Screener** — Filter NIFTY 500 stocks by Sharpe ratio, volatility and annual return with live prices
- **SIP Calculator** — Interactive compounding calculator with year-by-year corpus growth chart
- **Market News** — Live Indian financial news with keyword-based sentiment analysis
- **Portfolio Comparison** — Side-by-side comparison of any two saved portfolios
- **PDF Report Generator** — Client-ready professional PDF report covering all 3 portfolios with allocation breakdown, projections and disclaimer

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask, Flask-Login, SQLAlchemy |
| Optimization | NumPy, SciPy, Pandas |
| Market Data | yfinance |
| News | NewsAPI |
| PDF Generation | ReportLab |
| Frontend | Tailwind CSS, Alpine.js, Chart.js |
| Database | SQLite |
| Deployment | Render |

---

## How It Works

1. User selects investment amount, time horizon and asset classes
2. Optimizer runs 1,000+ Monte Carlo simulations using historical return and covariance data
3. Three portfolios are generated — Balanced (max Sharpe), High Return (max return), Low Risk (min volatility)
4. Advisor reviews the Efficient Frontier chart and allocation breakdown
5. Advisor saves the portfolio and downloads a branded client PDF report


---

## Disclaimer

NextGen is a decision-support tool designed for use by financial professionals and for educational purposes only. It does not constitute investment advice. All outputs are algorithmic and based on historical market data. Past performance does not guarantee future results. Final investment decisions remain the responsibility of the licensed advisor. Not intended for direct distribution to retail investors without advisor review.

---

## Author
Shriyaa Srivastav 

---

