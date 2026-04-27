from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    portfolios    = db.relationship("Portfolio", backref="user",
                                    lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"

class Portfolio(db.Model):
    __tablename__   = "portfolios"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer,
                                db.ForeignKey("users.id"),
                                nullable=False)
    name            = db.Column(db.String(100),
                                nullable=False,
                                default="My Portfolio")
    amount          = db.Column(db.Float, nullable=False)
    assets_selected = db.Column(db.String(200))
    portfolio_type  = db.Column(db.String(50))  # balanced/high_return/low_risk
    allocation_json = db.Column(db.Text)         # full portfolio dict as JSON
    expected_return = db.Column(db.Float)
    volatility      = db.Column(db.Float)
    sharpe_ratio    = db.Column(db.Float)
    risk_label      = db.Column(db.String(50))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def set_allocation(self, portfolio_dict):
        self.allocation_json = json.dumps(portfolio_dict)

    def get_allocation(self):
        return json.loads(self.allocation_json) if self.allocation_json else {}

    def __repr__(self):
        return f"<Portfolio {self.name} - {self.user_id}>"