import os
import json
from flask import (Flask, render_template, request,
                   jsonify, redirect, url_for,
                   flash, session)
from flask_login import (LoginManager, login_user,
                         logout_user, login_required,
                         current_user)
from models import db, User, Portfolio
from optimizer import (run_optimizer, get_correlation_heatmap,
                       get_monte_carlo_data, get_asset_stats,
                       PRECOMPUTED)
from dotenv import load_dotenv
load_dotenv()
# ── App setup ─────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nextgen_secret_key_2026")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "nextgen.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Extensions ────────────────────────────────────────────────
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login to access this page."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── Create DB tables ──────────────────────────────────────────
with app.app_context():
    db.create_all()
    print("Database ready")

# ════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email")
        password = request.form.get("password")
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name     = request.form.get("name")
        email    = request.form.get("email")
        password = request.form.get("password")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return render_template("signup.html")
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Account created successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("signup.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

# ── All other pages — login required ─────────────────────────
@app.route("/optimizer")
@login_required
def optimizer_page():
    return render_template("optimizer.html")

@app.route("/results")
@login_required
def results_page():
    return render_template("results.html")

@app.route("/screener")
@login_required
def screener():
    return render_template("screener.html")

@app.route("/news")
@login_required
def news():
    return render_template("news.html")

@app.route("/sip")
@login_required
def sip():
    return render_template("sip.html")

@app.route("/compare")
@login_required
def compare():
    user_portfolios = Portfolio.query.filter_by(
        user_id=current_user.id).all()
    return render_template("compare.html",
                           portfolios=user_portfolios)

@app.route("/dashboard")
@login_required
def dashboard():
    user_portfolios = Portfolio.query.filter_by(
        user_id=current_user.id)\
        .order_by(Portfolio.created_at.desc()).all()
    return render_template("dashboard.html",
                           portfolios=user_portfolios)

@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from io import BytesIO
    from flask import send_file
    import datetime

    data         = request.get_json()
    portfolios   = data.get("portfolios", {})
    amount       = float(data.get("amount", 0))
    client_name  = data.get("client_name", "Valued Client")
    advisor_name = data.get("advisor_name", "NextGen Advisor")
    years        = int(data.get("years", 5))

    INDIGO = colors.HexColor("#6366f1")
    DARK   = colors.HexColor("#1e293b")
    GRAY   = colors.HexColor("#64748b")
    LIGHT  = colors.HexColor("#f8fafc")
    GREEN  = colors.HexColor("#16a34a")
    WHITE  = colors.white

    PORTFOLIO_COLORS = {
        "balanced"    : colors.HexColor("#6366f1"),
        "high_return" : colors.HexColor("#ef4444"),
        "low_risk"    : colors.HexColor("#16a34a"),
    }

    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=15*mm,  bottomMargin=15*mm
    )

    def style(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    label_style = style("L", fontSize=8,  textColor=GRAY,  fontName="Helvetica", spaceAfter=1)
    value_style = style("V", fontSize=12, textColor=DARK,  fontName="Helvetica-Bold")
    head_style  = style("H", fontSize=12, textColor=INDIGO, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
    body_style  = style("B", fontSize=9,  textColor=GRAY,  fontName="Helvetica", leading=14)
    disc_style  = style("D", fontSize=7.5,textColor=GRAY,  fontName="Helvetica-Oblique", leading=11)

    story = []
    W     = A4[0] - 40*mm

    today = datetime.datetime.now().strftime("%d %B %Y")

    # ── COVER PAGE ───────────────────────────────────────────────
    story.append(Spacer(1, 20*mm))

    cover_table = Table([[
        Paragraph("NextGen",
                  style("CT", fontSize=36, textColor=WHITE,
                        fontName="Helvetica-Bold", alignment=TA_CENTER)),
    ],[
        Paragraph("Automated Investment Intelligence",
                  style("CS", fontSize=13, textColor=colors.HexColor("#c7d2fe"),
                        fontName="Helvetica", alignment=TA_CENTER)),
    ]], colWidths=[W])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  INDIGO),
        ("BACKGROUND",    (0,1), (-1,1),  DARK),
        ("TOPPADDING",    (0,0), (-1,0),  28),
        ("BOTTOMPADDING", (0,0), (-1,0),  28),
        ("TOPPADDING",    (0,1), (-1,1),  14),
        ("BOTTOMPADDING", (0,1), (-1,1),  14),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 14*mm))

    story.append(Paragraph("Portfolio Analysis Report",
                            style("PR", fontSize=20, textColor=DARK,
                                  fontName="Helvetica-Bold", alignment=TA_CENTER,
                                  spaceAfter=6)))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("Comprehensive Investment Overview — All 3 Portfolios",
                            style("PS", fontSize=11, textColor=GRAY,
                                  fontName="Helvetica", alignment=TA_CENTER,
                                  spaceAfter=0)))
    story.append(Spacer(1, 14*mm))

    # Cover meta box
    meta_data = [[
        Paragraph("Prepared for",  label_style),
        Paragraph("Prepared by",   label_style),
        Paragraph("Date",          label_style),
        Paragraph("Investment",    label_style),
    ],[
        Paragraph(client_name,     value_style),
        Paragraph(advisor_name,    value_style),
        Paragraph(today,           value_style),
        Paragraph(f"Rs. {amount:,.0f}", value_style),
    ]]
    meta_table = Table(meta_data, colWidths=[W/4]*4)
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), LIGHT),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("LINEAFTER",     (0,0), (2,1),   0.5, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [6,6,6,6]),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10*mm))

    # At a glance comparison table
    story.append(Paragraph("At a Glance — Portfolio Comparison",
                            style("AG", fontSize=11, textColor=DARK,
                                  fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=6)))

    overview_header = [[
        Paragraph("Portfolio",       style("OH", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold")),
        Paragraph("Expected Return", style("OH2", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("Volatility",      style("OH3", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("Sharpe Ratio",    style("OH4", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("Risk",            style("OH5", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph(f"Projected ({years}yr)", style("OH6", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ]]

    overview_rows = []
    port_order = ["balanced", "high_return", "low_risk"]
    for key in port_order:
        p   = portfolios.get(key, {})
        if not p:
            continue
        col  = PORTFOLIO_COLORS.get(key, INDIGO)
        exp  = p.get("expected_return", 0)
        proj = amount * ((1 + float(exp)/100)**years)
        overview_rows.append([
            Paragraph(p.get("label",""),
                      style(f"OL{key}", fontSize=9, textColor=col, fontName="Helvetica-Bold")),
            Paragraph(f"{exp}%",
                      style(f"OR{key}", fontSize=9, textColor=GREEN, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
            Paragraph(f"{p.get('volatility',0)}%",
                      style(f"OV{key}", fontSize=9, textColor=DARK, fontName="Helvetica", alignment=TA_RIGHT)),
            Paragraph(f"{p.get('sharpe_ratio',0)}",
                      style(f"OS{key}", fontSize=9, textColor=INDIGO, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
            Paragraph(p.get("risk_label",""),
                      style(f"ORK{key}", fontSize=9, textColor=GRAY, fontName="Helvetica", alignment=TA_RIGHT)),
            Paragraph(f"Rs. {proj:,.0f}",
                      style(f"OPJ{key}", fontSize=9, textColor=DARK, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        ])

    overview_data  = overview_header + overview_rows
    overview_table = Table(overview_data,
                           colWidths=[W*0.22, W*0.14, W*0.12, W*0.13, W*0.14, W*0.25])
    ots = [
        ("BACKGROUND",    (0,0), (-1,0),  DARK),
        ("LINEBELOW",     (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]
    for i, _ in enumerate(overview_rows):
        if i % 2 == 0:
            ots.append(("BACKGROUND", (0,i+1), (-1,i+1), LIGHT))
    overview_table.setStyle(TableStyle(ots))
    story.append(overview_table)

    story.append(PageBreak())

    # ── ONE PAGE PER PORTFOLIO ───────────────────────────────────
    for idx, key in enumerate(port_order):
        p = portfolios.get(key, {})
        if not p:
            continue

        port_color = PORTFOLIO_COLORS.get(key, INDIGO)
        exp_ret    = p.get("expected_return", 0)
        vol        = p.get("volatility", 0)
        sharpe     = p.get("sharpe_ratio", 0)
        risk_lbl   = p.get("risk_label", "")
        weights    = p.get("weights", {})
        amounts    = p.get("amounts", {})
        proj       = p.get("projected_corpus", amount * ((1 + float(exp_ret)/100)**years))
        gain       = proj - amount

        # Section header
        sec_header = Table([[
            Paragraph(p.get("label","Portfolio"),
                      style(f"SH{key}", fontSize=16, textColor=WHITE,
                            fontName="Helvetica-Bold")),
            Paragraph(risk_lbl,
                      style(f"SR{key}", fontSize=10,
                            textColor=colors.HexColor("#e0e7ff"),
                            fontName="Helvetica", alignment=TA_RIGHT)),
        ]], colWidths=[W*0.7, W*0.3])
        sec_header.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), port_color),
            ("LEFTPADDING",   (0,0), (-1,-1), 14),
            ("RIGHTPADDING",  (0,0), (-1,-1), 14),
            ("TOPPADDING",    (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("ROUNDEDCORNERS",(0,0), (-1,-1), [8,8,8,8]),
        ]))
        story.append(sec_header)
        story.append(Spacer(1, 4*mm))

        # Stats
        stats_data = [[
            Paragraph("Return",       label_style),
            Paragraph("Volatility",   label_style),
            Paragraph("Sharpe",       label_style),
            Paragraph("Holdings",     label_style),
        ],[
            Paragraph(f"{exp_ret}% p.a.",
                      style(f"SGR{key}", fontSize=13, textColor=GREEN, fontName="Helvetica-Bold")),
            Paragraph(f"{vol}%",      value_style),
            Paragraph(f"{sharpe}",
                      style(f"SGS{key}", fontSize=13, textColor=INDIGO, fontName="Helvetica-Bold")),
            Paragraph(f"{len(weights)}", value_style),
        ]]
        stats_table = Table(stats_data, colWidths=[W/4]*4)
        stats_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), LIGHT),
            ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEAFTER",     (0,0), (2,1),   0.5, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 3*mm))

        # Projected corpus
        proj_data = [[
            Paragraph(f"Projected Corpus in {years} years",
                      style(f"PL{key}", fontSize=9, textColor=WHITE, fontName="Helvetica")),
            Paragraph(f"Rs. {proj:,.0f}",
                      style(f"PV{key}", fontSize=14, textColor=WHITE,
                            fontName="Helvetica-Bold", alignment=TA_RIGHT)),
            Paragraph(f"Gain: Rs. {gain:,.0f}",
                      style(f"PG{key}", fontSize=9,
                            textColor=colors.HexColor("#a5f3b4"),
                            fontName="Helvetica", alignment=TA_RIGHT)),
        ]]
        proj_table = Table(proj_data, colWidths=[W*0.35, W*0.35, W*0.30])
        proj_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), DARK),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0), (-1,-1), 12),
            ("RIGHTPADDING",  (0,0), (-1,-1), 12),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("ROUNDEDCORNERS",(0,0), (-1,-1), [6,6,6,6]),
        ]))
        story.append(proj_table)
        story.append(Spacer(1, 4*mm))

        # Allocation table
        story.append(Paragraph("Top Holdings", head_style))
        story.append(HRFlowable(width=W, thickness=0.5,
                                color=colors.HexColor("#e2e8f0"), spaceAfter=3))

        alloc_header = [[
            Paragraph("Asset / Ticker",
                      style(f"AH{key}", fontSize=8, textColor=WHITE, fontName="Helvetica-Bold")),
            Paragraph("Weight (%)",
                      style(f"AHW{key}", fontSize=8, textColor=WHITE,
                            fontName="Helvetica-Bold", alignment=TA_RIGHT)),
            Paragraph("Amount (Rs.)",
                      style(f"AHA{key}", fontSize=8, textColor=WHITE,
                            fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        ]]

        all_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_weights = all_weights[:10]
        remaining   = len(all_weights) - 10

        alloc_rows = []
        for i, (ticker, w) in enumerate(top_weights):
            name = ticker.replace(".NS","").replace("_"," ")
            amt  = amounts.get(ticker, w * amount)
            alloc_rows.append([
                Paragraph(name,
                          style(f"AN{key}{i}", fontSize=8, textColor=DARK,
                                fontName="Helvetica-Bold")),
                Paragraph(f"{w*100:.1f}%",
                          style(f"AW{key}{i}", fontSize=8, textColor=port_color,
                                fontName="Helvetica-Bold", alignment=TA_RIGHT)),
                Paragraph(f"Rs. {amt:,.0f}",
                          style(f"AA{key}{i}", fontSize=8, textColor=DARK,
                                fontName="Helvetica", alignment=TA_RIGHT)),
            ])

        alloc_data  = alloc_header + alloc_rows
        alloc_table = Table(alloc_data, colWidths=[W*0.50, W*0.20, W*0.30])
        ats = [
            ("BACKGROUND",    (0,0), (-1,0),  port_color),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("RIGHTPADDING",  (0,0), (-1,-1), 10),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LINEBELOW",     (0,0), (-1,-1), 0.3, colors.HexColor("#e2e8f0")),
            ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ]
        for i, _ in enumerate(alloc_rows):
            if i % 2 == 0:
                ats.append(("BACKGROUND", (0,i+1), (-1,i+1), LIGHT))
        alloc_table.setStyle(TableStyle(ats))
        story.append(alloc_table)

        if remaining > 0:
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                f"+ {remaining} more holdings. Full allocation available on the platform.",
                style(f"RM{key}", fontSize=7.5, textColor=GRAY, fontName="Helvetica-Oblique")
            ))

        story.append(Spacer(1, 4*mm))

        # Explanations
        sharpe_f = float(sharpe)
        if sharpe_f >= 1.0:
            sharpe_note = "Excellent — well above the 1.0 benchmark."
        elif sharpe_f >= 0.5:
            sharpe_note = "Good — above 0.5 is generally considered satisfactory."
        elif sharpe_f >= 0:
            sharpe_note = "Moderate — positive but below the ideal threshold of 0.5."
        else:
            sharpe_note = "Negative — return is currently below the risk-free rate. Consider reviewing the asset mix."

        explains = [
            ("Return",
             f"Projected to grow at {exp_ret}% per year. Rs. {amount:,.0f} could become Rs. {proj:,.0f} over {years} years."),
            ("Volatility",
             f"{vol}% annual fluctuation. {'Low risk — relatively stable.' if float(vol) < 15 else 'Moderate risk — expect some ups and downs.'}"),
            ("Sharpe Ratio", sharpe_note),
            ("Diversification",
             f"Spread across {len(weights)} assets, reducing impact of any single holding."),
        ]
        for term, explanation in explains:
            row = Table([[
                Paragraph(term,
                          style(f"ET{key}{term}", fontSize=8, textColor=port_color,
                                fontName="Helvetica-Bold")),
                Paragraph(explanation, body_style),
            ]], colWidths=[W*0.20, W*0.80])
            row.setStyle(TableStyle([
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                ("TOPPADDING",    (0,0), (-1,-1), 3),
                ("BOTTOMPADDING", (0,0), (-1,-1), 3),
                ("LINEBELOW",     (0,0), (-1,-1), 0.3, colors.HexColor("#f1f5f9")),
            ]))
            story.append(row)

        if idx < len(port_order) - 1:
            story.append(PageBreak())

    # ── DISCLAIMER PAGE ──────────────────────────────────────────
    story.append(PageBreak())
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Disclaimer & Terms",
                            style("DT", fontSize=14, textColor=DARK,
                                  fontName="Helvetica-Bold", spaceAfter=6)))
    story.append(HRFlowable(width=W, thickness=0.5,
                            color=colors.HexColor("#e2e8f0"), spaceAfter=8))

    disc_box = Table([[
        Paragraph(
            "This report has been generated by NextGen — Automated Investment Intelligence "
            "for informational and educational purposes only. It does not constitute financial advice, "
            "investment advice, trading advice, or any other type of professional advice. "
            "All portfolio recommendations are generated using Modern Portfolio Theory (MPT) "
            "based on historical market data and do not guarantee future performance. "
            "Past performance of any asset or portfolio does not guarantee or predict future results. "
            "All investments carry risk including the possible loss of principal invested. "
            "The expected returns, volatility, and Sharpe ratios shown are derived from historical data "
            "and actual future performance may differ materially. "
            "Please consult a SEBI-registered investment advisor before making any investment decisions. "
            "NextGen and its developers are not liable for any financial losses arising directly "
            "or indirectly from the use of this report. "
            "This report is intended for use by licensed financial advisors and investment professionals only. "
            "It should not be distributed directly to retail investors without review and approval by a "
            "SEBI-registered Investment Adviser. Final investment decisions remain solely the responsibility "
            "of the licensed advisor.",
            disc_style)
    ]], colWidths=[W])
    disc_box.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#fef9c3")),
        ("BOX",           (0,0), (-1,-1), 0.5, colors.HexColor("#fde68a")),
        ("LEFTPADDING",   (0,0), (-1,-1), 14),
        ("RIGHTPADDING",  (0,0), (-1,-1), 14),
        ("TOPPADDING",    (0,0), (-1,-1), 12),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [4,4,4,4]),
    ]))
    story.append(disc_box)
    story.append(Spacer(1, 6*mm))

    footer = Table([[
        Paragraph("Generated by NextGen — Automated Investment Intelligence",
                  style("FL", fontSize=7.5, textColor=GRAY, fontName="Helvetica")),
        Paragraph(f"For professional advisor use only  |  {today}",
                  style("FR", fontSize=7.5, textColor=GRAY, fontName="Helvetica",
                        alignment=TA_RIGHT)),
    ]], colWidths=[W*0.6, W*0.4])
    footer.setStyle(TableStyle([
        ("LINEABOVE",     (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 0),
        ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(footer)

    doc.build(story)
    buffer.seek(0)

    filename = f"NextGen_Report_{client_name.replace(' ','_')}_{today.replace(' ','_')}.pdf"
    return send_file(buffer, mimetype="application/pdf",
                     as_attachment=True, download_name=filename)


# ════════════════════════════════════════════════════════════════
#  API ROUTES
# ════════════════════════════════════════════════════════════════

@app.route("/api/optimize", methods=["POST"])
def optimize():
    data   = request.get_json()
    amount = float(data.get("amount", 500000))
    assets = data.get("assets", [])
    years  = int(data.get("years", 5))
    result = run_optimizer(amount, assets, years)
    return jsonify(result)

@app.route("/api/save-portfolio", methods=["POST"])
@login_required
def save_portfolio():
    data         = request.get_json()
    port_type    = data.get("type")       # balanced/high_return/low_risk
    port_data    = data.get("portfolio")
    amount       = float(data.get("amount", 0))
    assets       = data.get("assets", [])
    name         = data.get("name", "My Portfolio")
    p = Portfolio(
        user_id         = current_user.id,
        name            = name,
        amount          = amount,
        assets_selected = ",".join(assets),
        portfolio_type  = port_type,
        expected_return = port_data.get("expected_return"),
        volatility      = port_data.get("volatility"),
        sharpe_ratio    = port_data.get("sharpe_ratio"),
        risk_label      = port_data.get("risk_label"),
    )
    p.set_allocation(port_data)
    db.session.add(p)
    db.session.commit()
    return jsonify({"success": True,
                    "portfolio_id": p.id})

@app.route("/api/portfolio/<int:portfolio_id>")
@login_required
def get_portfolio(portfolio_id):
    p = Portfolio.query.filter_by(
            id=portfolio_id,
            user_id=current_user.id).first_or_404()
    return jsonify(p.get_allocation())

@app.route("/api/portfolio/<int:portfolio_id>/delete",
           methods=["POST"])
@login_required
def delete_portfolio(portfolio_id):
    p = Portfolio.query.filter_by(
            id=portfolio_id,
            user_id=current_user.id).first_or_404()
    db.session.delete(p)
    db.session.commit()
    return jsonify({"success": True})

@app.route("/api/correlation")
def correlation():
    return jsonify(get_correlation_heatmap())

@app.route("/api/frontier")
def frontier():
    return jsonify(get_monte_carlo_data())

@app.route("/api/screener")
def screener_api():
    filters = {
        "min_sharpe" : request.args.get("min_sharpe"),
        "max_vol"    : request.args.get("max_vol"),
        "min_return" : request.args.get("min_return"),
    }
    return jsonify(get_asset_stats(filters))
from datetime import datetime
import pytz

def is_market_open():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    return (now.hour > 9 or (now.hour == 9 and now.minute >= 15)) and \
           (now.hour < 15 or (now.hour == 15 and now.minute <= 30))


@app.route("/api/screener/live/<ticker>")
def live_stock_data(ticker):
    try:
        import yfinance as yf
        t    = yf.Ticker(ticker)
        info = t.fast_info

        # Get price — try multiple fields
        price = 0
        for field in ["last_price", "regular_market_price"]:
            try:
                val = getattr(info, field, None)
                if val and float(val) > 0:
                    price = float(val)
                    break
            except Exception:
                continue

        # If still 0 fall back to previous close
        if price == 0:
            try:
                price = float(info.previous_close or 0)
            except Exception:
                price = 0

        # Previous close for day change
        try:
            prev_close = float(info.previous_close or price or 1)
        except Exception:
            prev_close = price or 1

        # Day change
        day_change = round((price / prev_close - 1) * 100, 2) \
                     if prev_close and prev_close > 0 and price > 0 \
                     else 0.0

        # 52 week high/low
        try:
            high52 = round(float(info.fifty_two_week_high or 0), 2)
            low52  = round(float(info.fifty_two_week_low  or 0), 2)
        except Exception:
            high52 = 0
            low52  = 0

        return jsonify({
            "ticker"        : ticker,
            "current_price" : round(price, 2),
            "day_change_pct": day_change,
            "week_52_high"  : high52,
            "week_52_low"   : low52,
            "status"        : "live" if price > 0 else "unavailable"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/news")
def news_api():
    try:
        from newsapi import NewsApiClient

        api = NewsApiClient(api_key=os.environ.get("NEWS_API_KEY"))

        articles = api.get_everything(
            q="india stock market",
            language="en",
            sort_by="publishedAt",
            page_size=20
        )

        return jsonify(articles.get("articles", []))

    except Exception as e:
        return jsonify({"error": str(e)}), 400
@app.route("/api/market-prices")
def market_prices():
    try:
        import yfinance as yf
        USD_INR = 83.5  # fallback rate

        # Get USD/INR rate
        try:
            forex     = yf.Ticker("USDINR=X")
            USD_INR   = forex.fast_info.last_price
        except Exception:
            pass

        results = {}

        # NIFTY 50
        try:
            nifty         = yf.Ticker("^NSEI")
            results["NIFTY 50"] = {
                "price" : round(nifty.fast_info.last_price, 2),
                "unit"  : "pts"
            }
        except Exception:
            results["NIFTY 50"] = {"price": "N/A", "unit": "pts"}

        # Gold — per 10 grams in INR
        # GC=F is USD per troy oz. 1 troy oz = 31.1035g
        try:
            gold_usd      = yf.Ticker("GC=F").fast_info.last_price
            gold_per_10g  = round(gold_usd * USD_INR * 10 / 31.1035, 2)
            results["Gold (10g)"] = {
                "price" : gold_per_10g,
                "unit"  : "INR"
            }
        except Exception:
            results["Gold (10g)"] = {"price": "N/A", "unit": "INR"}

        # Silver — per kg in INR
        # SI=F is USD per troy oz. 1 troy oz = 31.1035g → 1kg = 1000g
        try:
            silver_usd     = yf.Ticker("SI=F").fast_info.last_price
            silver_per_kg  = round(silver_usd * USD_INR * 1000 / 31.1035, 2)
            results["Silver (1kg)"] = {
                "price" : silver_per_kg,
                "unit"  : "INR"
            }
        except Exception:
            results["Silver (1kg)"] = {"price": "N/A", "unit": "INR"}

        # Bitcoin in INR
        try:
            btc_usd       = yf.Ticker("BTC-USD").fast_info.last_price
            results["Bitcoin"] = {
                "price" : round(btc_usd * USD_INR, 2),
                "unit"  : "INR"
            }
        except Exception:
            results["Bitcoin"] = {"price": "N/A", "unit": "INR"}

        # FD Rate — SBI standard 1yr FD rate (hardcoded, updated quarterly)
        results["SBI FD Rate (1yr)"] = {
            "price" : 6.80,
            "unit"  : "% p.a."
        }

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ════════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True)