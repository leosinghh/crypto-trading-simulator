import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import json
import time
from typing import Dict, List, Optional
import uuid
import warnings
import sqlite3
import hashlib
import os
import random
import math
import requests
warnings.filterwarnings('ignore')

# Database Manager Class
class TradingGameDatabase:
    def __init__(self, db_path: str = "trading_game.db"):
        """Initialize the database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                cash REAL DEFAULT 100000.00,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                total_trades INTEGER DEFAULT 0,
                total_profit_loss REAL DEFAULT 0.0,
                best_trade REAL DEFAULT 0.0,
                worst_trade REAL DEFAULT 0.0
            )
        ''')
        
        # Create portfolio table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                symbol TEXT NOT NULL,
                shares INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                stock_name TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, symbol)
            )
        ''')
        
        # Create trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                trade_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                total_cost REAL NOT NULL,
                commission REAL NOT NULL,
                profit_loss REAL DEFAULT 0.0,
                stock_name TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create game_settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_settings (
                id INTEGER PRIMARY KEY,
                starting_cash REAL DEFAULT 100000.00,
                commission REAL DEFAULT 9.99,
                game_duration_days INTEGER DEFAULT 30,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings if none exist
        cursor.execute('SELECT COUNT(*) FROM game_settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO game_settings (starting_cash, commission, game_duration_days)
                VALUES (100000.00, 9.99, 30)
            ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password: str) -> str:
        """Hash a password for secure storage."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, password: str, email: str) -> Dict:
        """Create a new user account."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            user_id = str(uuid.uuid4())[:8]
            password_hash = self.hash_password(password)
            
            # Get starting cash from settings
            cursor.execute('SELECT starting_cash FROM game_settings ORDER BY id DESC LIMIT 1')
            starting_cash = cursor.fetchone()[0]
            
            cursor.execute('''
                INSERT INTO users (id, username, password_hash, email, cash) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, password_hash, email, starting_cash))
            
            conn.commit()
            conn.close()
            return {'success': True, 'user_id': user_id, 'message': 'User created successfully'}
        except sqlite3.IntegrityError:
            return {'success': False, 'message': 'Username or email already exists'}
        except Exception as e:
            return {'success': False, 'message': f'Error creating user: {str(e)}'}
    
    def authenticate_user(self, username: str, password: str) -> Dict:
        """Authenticate user and return user data if successful."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            password_hash = self.hash_password(password)
            cursor.execute('''
                SELECT id, username, email, cash, created_at, last_login, total_trades, 
                       total_profit_loss, best_trade, worst_trade
                FROM users 
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))
            
            user = cursor.fetchone()
            if user:
                # Update last login
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
                ''', (user[0],))
                conn.commit()
                
                user_data = {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'cash': user[3],
                    'created_at': user[4],
                    'last_login': user[5],
                    'total_trades': user[6],
                    'total_profit_loss': user[7],
                    'best_trade': user[8],
                    'worst_trade': user[9]
                }
                conn.close()
                return {'success': True, 'user': user_data}
            
            conn.close()
            return {'success': False, 'message': 'Invalid username or password'}
        except Exception as e:
            return {'success': False, 'message': f'Login error: {str(e)}'}
    
    def get_user_data(self, user_id: str) -> Dict:
        """Get user data by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, username, email, cash, created_at, last_login, total_trades, 
                       total_profit_loss, best_trade, worst_trade
                FROM users WHERE id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            conn.close()
            
            if user:
                return {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'cash': user[3],
                    'created_at': user[4],
                    'last_login': user[5],
                    'total_trades': user[6],
                    'total_profit_loss': user[7],
                    'best_trade': user[8],
                    'worst_trade': user[9]
                }
            return None
        except Exception as e:
            st.error(f"Error getting user data: {str(e)}")
            return None
    
    def get_user_portfolio(self, user_id: str) -> List[Dict]:
        """Get user's portfolio."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT symbol, shares, avg_price, stock_name
                FROM portfolio 
                WHERE user_id = ? AND shares > 0
            ''', (user_id,))
            
            portfolio = []
            for row in cursor.fetchall():
                portfolio.append({
                    'symbol': row[0],
                    'shares': row[1],
                    'avg_price': row[2],
                    'name': row[3] or row[0]
                })
            
            conn.close()
            return portfolio
        except Exception as e:
            st.error(f"Error getting portfolio: {str(e)}")
            return []
    
    def get_user_trades(self, user_id: str) -> List[Dict]:
        """Get user's trade history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, trade_type, symbol, shares, price, total_cost, commission, 
                       profit_loss, stock_name, timestamp
                FROM trades 
                WHERE user_id = ? 
                ORDER BY timestamp DESC
            ''', (user_id,))
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    'id': row[0],
                    'type': row[1],
                    'symbol': row[2],
                    'shares': row[3],
                    'price': row[4],
                    'total_cost': row[5],
                    'commission': row[6],
                    'profit_loss': row[7],
                    'name': row[8] or row[2],
                    'timestamp': datetime.strptime(row[9], '%Y-%m-%d %H:%M:%S')
                })
            
            conn.close()
            return trades
        except Exception as e:
            st.error(f"Error getting trades: {str(e)}")
            return []
    
    def execute_trade(self, user_id: str, symbol: str, action: str, shares: int, price: float, stock_name: str, currency: str = 'USD') -> Dict:
        """Execute a trade and update database with currency conversion"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get commission from settings
            cursor.execute('SELECT commission FROM game_settings ORDER BY id DESC LIMIT 1')
            commission = cursor.fetchone()[0]
            
            # Get current user data
            cursor.execute('SELECT cash FROM users WHERE id = ?', (user_id,))
            current_cash = cursor.fetchone()[0]
            
            # Convert price to USD for internal calculations
            # Simple conversion based on exchange rates
            exchange_rates = {
                'USD': 1.0,
                'GHS': 12.50,
                'KES': 155.0,
                'NGN': 1580.0,
                'ZAR': 18.50,
                'EGP': 49.0
            }
            
            rate = exchange_rates.get(currency, 1.0)
            price_usd = price / rate
            
            total_cost_usd = (price_usd * shares) + commission
            
            if action.upper() == 'BUY':
                if current_cash < total_cost_usd:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient funds'}
                
                # Update cash (stored in USD)
                new_cash = current_cash - total_cost_usd
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
                # Update portfolio (store prices in USD)
                cursor.execute('''
                    SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?
                ''', (user_id, symbol))
                
                existing = cursor.fetchone()
                if existing:
                    old_shares, old_avg_price = existing
                    new_shares = old_shares + shares
                    new_avg_price = ((old_shares * old_avg_price) + (shares * price_usd)) / new_shares
                    
                    cursor.execute('''
                        UPDATE portfolio SET shares = ?, avg_price = ?, stock_name = ?
                        WHERE user_id = ? AND symbol = ?
                    ''', (new_shares, new_avg_price, stock_name, user_id, symbol))
                else:
                    cursor.execute('''
                        INSERT INTO portfolio (user_id, symbol, shares, avg_price, stock_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, symbol, shares, price_usd, stock_name))
                
                # Record trade (store in USD)
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_cost_usd, commission, stock_name))
                
                profit_loss = 0
                
            elif action.upper() == 'SELL':
                # Check if user owns enough shares
                cursor.execute('''
                    SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?
                ''', (user_id, symbol))
                
                existing = cursor.fetchone()
                if not existing or existing[0] < shares:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient shares'}
                
                owned_shares, avg_price_usd = existing
                
                # Calculate profit/loss in USD
                profit_loss = (price_usd - avg_price_usd) * shares - commission
                
                # Update cash (in USD)
                total_proceeds_usd = (price_usd * shares) - commission
                new_cash = current_cash + total_proceeds_usd
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
                # Update portfolio
                new_shares = owned_shares - shares
                if new_shares > 0:
                    cursor.execute('''
                        UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?
                    ''', (new_shares, user_id, symbol))
                else:
                    cursor.execute('''
                        DELETE FROM portfolio WHERE user_id = ? AND symbol = ?
                    ''', (user_id, symbol))
                
                # Record trade (in USD)
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, profit_loss, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_proceeds_usd, commission, profit_loss, stock_name))
                
                # Update user statistics
                cursor.execute('''
                    UPDATE users SET total_profit_loss = total_profit_loss + ?,
                                   best_trade = CASE WHEN ? > best_trade THEN ? ELSE best_trade END,
                                   worst_trade = CASE WHEN ? < worst_trade THEN ? ELSE worst_trade END
                    WHERE id = ?
                ''', (profit_loss, profit_loss, profit_loss, profit_loss, profit_loss, user_id))
            
            # Update total trades
            cursor.execute('UPDATE users SET total_trades = total_trades + 1 WHERE id = ?', (user_id,))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': f'{action.upper()} order executed successfully',
                'trade_id': trade_id,
                'profit_loss': profit_loss if action.upper() == 'SELL' else 0
            }
            
        except Exception as e:
            return {'success': False, 'message': f'Error executing trade: {str(e)}'}
    
    def get_leaderboard(self) -> List[Dict]:
        """Get leaderboard data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT u.id, u.username, u.cash, u.total_trades, u.total_profit_loss,
                       COALESCE(SUM(p.shares * p.avg_price), 0) as portfolio_value
                FROM users u
                LEFT JOIN portfolio p ON u.id = p.user_id
                GROUP BY u.id, u.username, u.cash, u.total_trades, u.total_profit_loss
                ORDER BY (u.cash + COALESCE(SUM(p.shares * p.avg_price), 0)) DESC
            ''')
            
            leaderboard = []
            for row in cursor.fetchall():
                total_value = row[2] + row[5]  # cash + portfolio value
                leaderboard.append({
                    'user_id': row[0],
                    'username': row[1],
                    'cash': row[2],
                    'total_trades': row[3],
                    'total_profit_loss': row[4],
                    'portfolio_value': total_value,
                    'rank': 0  # Will be assigned later
                })
            
            # Assign ranks
            for i, player in enumerate(leaderboard):
                player['rank'] = i + 1
            
            conn.close()
            return leaderboard
        except Exception as e:
            st.error(f"Error getting leaderboard: {str(e)}")
            return []
    
    def get_game_settings(self) -> Dict:
        """Get game settings."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT starting_cash, commission, game_duration_days FROM game_settings ORDER BY id DESC LIMIT 1')
            settings = cursor.fetchone()
            conn.close()
            
            if settings:
                return {
                    'starting_cash': settings[0],
                    'commission': settings[1],
                    'game_duration_days': settings[2]
                }
            return {'starting_cash': 100000, 'commission': 9.99, 'game_duration_days': 30}
        except Exception as e:
            st.error(f"Error getting settings: {str(e)}")
            return {'starting_cash': 100000, 'commission': 9.99, 'game_duration_days': 30}

# Configure Streamlit page
st.set_page_config(
    page_title="Leo's Trader",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for gaming aesthetics
st.markdown("""
<style>
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem 0;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    
    .ghana-pride {
        text-align: center;
        background: linear-gradient(135deg, #ff6b6b 0%, #ffd60a 50%, #28a745 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        font-weight: bold;
        font-size: 1.2em;
    }
    
    .portfolio-card {
        background: linear-gradient(135deg, #ff6b6b 0%, #ffa500 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 8px 25px rgba(255,107,107,0.3);
        border: 2px solid rgba(255,255,255,0.2);
    }
    
    .profit-card {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 8px 25px rgba(40,167,69,0.3);
    }
    
    .loss-card {
        background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 8px 25px rgba(220,53,69,0.3);
    }
    
    .african-card {
        background: linear-gradient(135deg, #fd7e14 0%, #ffc107 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 8px 25px rgba(253,126,20,0.3);
    }
    
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
    
    .chart-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
</style>
""", unsafe_allow_html=True)

class TradingSimulator:
    def __init__(self):
        self.db = TradingGameDatabase()
        self.initialize_session_state()
        self.available_stocks = self.get_available_stocks()
        self.initialize_exchange_rates()
        self.initialize_all_mock_data()
        
    def initialize_session_state(self):
        """Initialize session state for the trading game"""
        if 'current_user' not in st.session_state:
            st.session_state.current_user = None
        if 'logged_in' not in st.session_state:
            st.session_state.logged_in = False
        if 'game_settings' not in st.session_state:
            st.session_state.game_settings = self.db.get_game_settings()
        if 'market_data_cache' not in st.session_state:
            st.session_state.market_data_cache = {}
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        
        # Initialize mock data for all markets
        if 'ghana_mock_data' not in st.session_state:
            st.session_state.ghana_mock_data = {}
        if 'ghana_last_update' not in st.session_state:
            st.session_state.ghana_last_update = datetime.now()
        
        if 'kenya_mock_data' not in st.session_state:
            st.session_state.kenya_mock_data = {}
        if 'kenya_last_update' not in st.session_state:
            st.session_state.kenya_last_update = datetime.now()
        
        if 'nigeria_mock_data' not in st.session_state:
            st.session_state.nigeria_mock_data = {}
        if 'nigeria_last_update' not in st.session_state:
            st.session_state.nigeria_last_update = datetime.now()
        
        # Initialize exchange rates
        if 'exchange_rates' not in st.session_state:
            st.session_state.exchange_rates = {}
        if 'exchange_rates_last_update' not in st.session_state:
            st.session_state.exchange_rates_last_update = datetime.now() - timedelta(hours=1)
    
    def initialize_exchange_rates(self):
        """Initialize and update exchange rates"""
        self.update_exchange_rates()
    
    def get_fallback_exchange_rates(self) -> Dict[str, float]:
        """Get fallback exchange rates if API fails"""
        return {
            'GHS': 12.50,  # Ghana Cedi to USD
            'KES': 155.0,  # Kenyan Shilling to USD
            'NGN': 1580.0, # Nigerian Naira to USD
            'ZAR': 18.50,  # South African Rand to USD
            'EGP': 49.0,   # Egyptian Pound to USD
            'USD': 1.0     # US Dollar base
        }
    
    def update_exchange_rates(self):
        """Update exchange rates from free API with fallback"""
        current_time = datetime.now()
        
        # Update every hour
        if (current_time - st.session_state.exchange_rates_last_update).total_seconds() < 3600:
            return
        
        try:
            # Using exchangerate-api.com free tier (1500 requests/month)
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates', {})
                
                # Convert to USD rates (since API gives USD to other currency)
                st.session_state.exchange_rates = {
                    'USD': 1.0,
                    'GHS': rates.get('GHS', 12.50),
                    'KES': rates.get('KES', 155.0),
                    'NGN': rates.get('NGN', 1580.0),
                    'ZAR': rates.get('ZAR', 18.50),
                    'EGP': rates.get('EGP', 49.0)
                }
                st.session_state.exchange_rates_last_update = current_time
                
            else:
                # Use fallback rates
                st.session_state.exchange_rates = self.get_fallback_exchange_rates()
                
        except Exception as e:
            # Use fallback rates if API fails
            st.session_state.exchange_rates = self.get_fallback_exchange_rates()
            st.session_state.exchange_rates_last_update = current_time
    
    def convert_to_usd(self, amount: float, currency: str) -> float:
        """Convert amount from local currency to USD"""
        self.update_exchange_rates()
        
        if currency == 'USD':
            return amount
        
        rate = st.session_state.exchange_rates.get(currency, 1.0)
        return amount / rate
    
    def convert_from_usd(self, amount_usd: float, currency: str) -> float:
        """Convert amount from USD to local currency"""
        self.update_exchange_rates()
        
        if currency == 'USD':
            return amount_usd
        
        rate = st.session_state.exchange_rates.get(currency, 1.0)
        return amount_usd * rate
    
    def format_currency_display(self, amount: float, currency: str) -> str:
        """Format currency for display with proper symbol and formatting"""
        currency_symbols = {
            'USD': '$',
            'GHS': '₵',
            'KES': 'KSh',
            'NGN': '₦',
            'ZAR': 'R',
            'EGP': 'E£'
        }
        
        symbol = currency_symbols.get(currency, currency + ' ')
        
        if currency in ['KES', 'NGN']:
            # For currencies with larger numbers, use commas
            return f"{symbol}{amount:,.0f}"
        else:
            # For others, use 2 decimal places
            return f"{symbol}{amount:,.2f}"
    
    def initialize_all_mock_data(self):
        """Initialize mock data for all African Stock Exchanges"""
        ghana_stocks = {
            'GOIL.AC': {'base_price': 2.15, 'volatility': 0.02, 'trend': 0.001},
            'ECOBANK.AC': {'base_price': 5.80, 'volatility': 0.025, 'trend': 0.0005},
            'CAL.AC': {'base_price': 0.85, 'volatility': 0.03, 'trend': -0.001},
            'MTNGH.AC': {'base_price': 1.20, 'volatility': 0.02, 'trend': 0.002},
            'GWEB.AC': {'base_price': 0.45, 'volatility': 0.04, 'trend': 0.001},
            'SOGEGH.AC': {'base_price': 1.85, 'volatility': 0.02, 'trend': 0.0005},
            'AYRTN.AC': {'base_price': 0.75, 'volatility': 0.03, 'trend': -0.0005},
            'UNIL.AC': {'base_price': 18.50, 'volatility': 0.015, 'trend': 0.001},
            'CMLT.AC': {'base_price': 0.95, 'volatility': 0.035, 'trend': 0.002},
            'RBGH.AC': {'base_price': 0.65, 'volatility': 0.025, 'trend': 0.0005},
            'BOPP.AC': {'base_price': 2.40, 'volatility': 0.03, 'trend': 0.001},
            'TOTAL.AC': {'base_price': 3.80, 'volatility': 0.02, 'trend': 0.0005},
            'GGBL.AC': {'base_price': 1.75, 'volatility': 0.025, 'trend': 0.001},
            'SCBGH.AC': {'base_price': 15.20, 'volatility': 0.02, 'trend': 0.0005},
            'DIGP.AC': {'base_price': 0.25, 'volatility': 0.05, 'trend': -0.001},
            'CLYD.AC': {'base_price': 0.35, 'volatility': 0.04, 'trend': 0.002},
            'AADS.AC': {'base_price': 0.55, 'volatility': 0.035, 'trend': 0.001},
            'CAPL.AC': {'base_price': 0.45, 'volatility': 0.03, 'trend': 0.0005},
            'NICO.AC': {'base_price': 0.95, 'volatility': 0.025, 'trend': 0.001},
            'HORDS.AC': {'base_price': 0.15, 'volatility': 0.06, 'trend': 0.003},
            'TRANSOL.AC': {'base_price': 0.25, 'volatility': 0.05, 'trend': 0.002},
            'PRODUCE.AC': {'base_price': 0.35, 'volatility': 0.04, 'trend': 0.001},
            'PIONEER.AC': {'base_price': 0.85, 'volatility': 0.03, 'trend': 0.0015}
        }
        
        # Initialize Kenya stocks data
        kenya_stocks = {
            'KCB.NR': {'base_price': 45.50, 'volatility': 0.025, 'trend': 0.001},
            'EQTY.NR': {'base_price': 52.75, 'volatility': 0.03, 'trend': 0.002},
            'SCBK.NR': {'base_price': 162.00, 'volatility': 0.02, 'trend': 0.0005},
            'ABSA.NR': {'base_price': 12.85, 'volatility': 0.025, 'trend': 0.001},
            'DTBK.NR': {'base_price': 82.50, 'volatility': 0.03, 'trend': 0.0015},
            'BAT.NR': {'base_price': 485.00, 'volatility': 0.02, 'trend': 0.001},
            'EABL.NR': {'base_price': 195.00, 'volatility': 0.025, 'trend': 0.0005},
            'SAFCOM.NR': {'base_price': 28.50, 'volatility': 0.02, 'trend': 0.002},
            'BRITAM.NR': {'base_price': 6.45, 'volatility': 0.035, 'trend': 0.001},
            'JUBILEE.NR': {'base_price': 245.00, 'volatility': 0.03, 'trend': 0.0015},
            'LIBERTY.NR': {'base_price': 8.75, 'volatility': 0.04, 'trend': 0.002},
            'COOP.NR': {'base_price': 14.20, 'volatility': 0.025, 'trend': 0.001},
            'UNGA.NR': {'base_price': 38.50, 'volatility': 0.035, 'trend': 0.0005},
            'KAKUZI.NR': {'base_price': 425.00, 'volatility': 0.04, 'trend': 0.002},
            'SASINI.NR': {'base_price': 12.50, 'volatility': 0.05, 'trend': 0.001},
            'KAPCHORUA.NR': {'base_price': 145.00, 'volatility': 0.045, 'trend': 0.0015},
            'WILLIAMSON.NR': {'base_price': 42.50, 'volatility': 0.04, 'trend': 0.001},
            'BAMBURI.NR': {'base_price': 58.00, 'volatility': 0.03, 'trend': 0.0005},
            'CROWN.NR': {'base_price': 24.75, 'volatility': 0.035, 'trend': 0.001},
            'KENGEN.NR': {'base_price': 2.84, 'volatility': 0.025, 'trend': 0.0005},
            'KPLC.NR': {'base_price': 1.85, 'volatility': 0.04, 'trend': -0.001},
            'KEGN.NR': {'base_price': 2.95, 'volatility': 0.03, 'trend': 0.001},
            'KENOL.NR': {'base_price': 22.50, 'volatility': 0.03, 'trend': 0.0015},
            'TPS.NR': {'base_price': 1.25, 'volatility': 0.05, 'trend': 0.002},
            'UMEME.NR': {'base_price': 45.00, 'volatility': 0.025, 'trend': 0.001},
            'TOTAL.NR': {'base_price': 18.50, 'volatility': 0.02, 'trend': 0.0005},
            'CARBACID.NR': {'base_price': 7.85, 'volatility': 0.035, 'trend': 0.001},
            'BOC.NR': {'base_price': 42.00, 'volatility': 0.03, 'trend': 0.0015},
            'OLYMPIA.NR': {'base_price': 5.25, 'volatility': 0.04, 'trend': 0.002},
            'CENTUM.NR': {'base_price': 18.75, 'volatility': 0.035, 'trend': 0.001}
        }
        
        # Initialize Nigeria stocks data
        nigeria_stocks = {
            'GTCO.LG': {'base_price': 28.50, 'volatility': 0.025, 'trend': 0.001},
            'ZENITHBANK.LG': {'base_price': 24.75, 'volatility': 0.03, 'trend': 0.0015},
            'UBA.LG': {'base_price': 15.85, 'volatility': 0.025, 'trend': 0.001},
            'ACCESS.LG': {'base_price': 12.45, 'volatility': 0.03, 'trend': 0.002},
            'FBNH.LG': {'base_price': 18.20, 'volatility': 0.035, 'trend': 0.0005},
            'FIDELITYBK.LG': {'base_price': 8.75, 'volatility': 0.03, 'trend': 0.001},
            'STERLINGNG.LG': {'base_price': 2.45, 'volatility': 0.04, 'trend': 0.0015},
            'WEMA.LG': {'base_price': 5.25, 'volatility': 0.035, 'trend': 0.001},
            'UNITY.LG': {'base_price': 1.85, 'volatility': 0.05, 'trend': 0.002},
            'STANBIC.LG': {'base_price': 42.50, 'volatility': 0.025, 'trend': 0.0005},
            'DANGCEM.LG': {'base_price': 285.00, 'volatility': 0.02, 'trend': 0.001},
            'BUA.LG': {'base_price': 95.50, 'volatility': 0.025, 'trend': 0.0015},
            'MTNN.LG': {'base_price': 185.00, 'volatility': 0.02, 'trend': 0.001},
            'AIRTELAFRI.LG': {'base_price': 1850.00, 'volatility': 0.025, 'trend': 0.002},
            'SEPLAT.LG': {'base_price': 1250.00, 'volatility': 0.03, 'trend': 0.0005},
            'OANDO.LG': {'base_price': 8.45, 'volatility': 0.04, 'trend': 0.001},
            'TOTAL.LG': {'base_price': 485.00, 'volatility': 0.02, 'trend': 0.0005},
            'CONOIL.LG': {'base_price': 35.50, 'volatility': 0.03, 'trend': 0.001},
            'GUINNESS.LG': {'base_price': 48.75, 'volatility': 0.025, 'trend': 0.0015},
            'NB.LG': {'base_price': 65.00, 'volatility': 0.025, 'trend': 0.001},
            'INTBREW.LG': {'base_price': 5.85, 'volatility': 0.035, 'trend': 0.002},
            'NESTLE.LG': {'base_price': 1485.00, 'volatility': 0.015, 'trend': 0.001},
            'UNILEVER.LG': {'base_price': 16.25, 'volatility': 0.025, 'trend': 0.0005},
            'DANGSUGAR.LG': {'base_price': 18.50, 'volatility': 0.03, 'trend': 0.001},
            'FLOURMILL.LG': {'base_price': 32.75, 'volatility': 0.025, 'trend': 0.0015},
            'HONEYFLOUR.LG': {'base_price': 4.25, 'volatility': 0.04, 'trend': 0.002},
            'CADBURY.LG': {'base_price': 12.85, 'volatility': 0.03, 'trend': 0.001},
            'VITAFOAM.LG': {'base_price': 15.50, 'volatility': 0.035, 'trend': 0.0005},
            'JBERGER.LG': {'base_price': 38.25, 'volatility': 0.025, 'trend': 0.001},
            'LIVESTOCK.LG': {'base_price': 2.45, 'volatility': 0.05, 'trend': 0.002},
            'CHIPLC.LG': {'base_price': 0.85, 'volatility': 0.06, 'trend': 0.003},
            'ELLAHLAKES.LG': {'base_price': 4.75, 'volatility': 0.045, 'trend': 0.0015},
            'NAHCO.LG': {'base_price': 8.50, 'volatility': 0.04, 'trend': 0.001},
            'RTBRISCOE.LG': {'base_price': 0.55, 'volatility': 0.055, 'trend': 0.002}
        }
        
        self.initialize_mock_data_for_market('ghana', ghana_stocks)
        self.initialize_mock_data_for_market('kenya', kenya_stocks)
        self.initialize_mock_data_for_market('nigeria', nigeria_stocks)
    
    def initialize_mock_data_for_market(self, market: str, stocks_config: dict):
        """Initialize mock data for a specific market"""
        session_key = f'{market}_mock_data'
        
        # Initialize mock data if not exists
        if session_key not in st.session_state or not st.session_state[session_key]:
            current_time = datetime.now()
            st.session_state[session_key] = {}
            
            for symbol, config in stocks_config.items():
                # Generate 30 days of historical data
                historical_data = []
                price = config['base_price']
                
                for i in range(30):
                    date = current_time - timedelta(days=29-i)
                    
                    # Add trend and random walk
                    price_change = (random.gauss(0, config['volatility']) + config['trend']) * price
                    price = max(0.01, price + price_change)  # Ensure price doesn't go below 0.01
                    
                    # Generate volume (random but realistic)
                    volume = random.randint(10000, 500000)
                    
                    historical_data.append({
                        'date': date,
                        'open': price * random.uniform(0.995, 1.005),
                        'high': price * random.uniform(1.005, 1.02),
                        'low': price * random.uniform(0.98, 0.995),
                        'close': price,
                        'volume': volume
                    })
                
                st.session_state[session_key][symbol] = {
                    'config': config,
                    'historical_data': historical_data,
                    'current_price': price,
                    'last_update': current_time
                }
    
    def update_ghana_mock_data(self):
        """Update Ghana mock data with new prices"""
        self.update_mock_data_for_market('ghana', 'ghana_last_update')
    
    def update_mock_data_for_market(self, market: str, last_update_key: str):
        """Update mock data for a specific market"""
        current_time = datetime.now()
        session_key = f'{market}_mock_data'
        
        # Update every 30 seconds to simulate real-time updates
        if (current_time - st.session_state[last_update_key]).total_seconds() < 30:
            return
        
        st.session_state[last_update_key] = current_time
        
        # Check if it's trading hours based on market
        if market == 'ghana':
            # Ghana: 9:00 AM - 3:00 PM GMT
            gmt_time = current_time.utctimetuple()
            is_weekday = gmt_time.tm_wday < 5
            is_trading_hours = 9 <= gmt_time.tm_hour < 15
        elif market == 'kenya':
            # Kenya: 9:00 AM - 3:00 PM EAT (GMT+3)
            eat_time = (current_time + timedelta(hours=3)).timetuple()
            is_weekday = eat_time.tm_wday < 5
            is_trading_hours = 9 <= eat_time.tm_hour < 15
        elif market == 'nigeria':
            # Nigeria: 10:00 AM - 2:30 PM WAT (GMT+1)
            wat_time = (current_time + timedelta(hours=1)).timetuple()
            is_weekday = wat_time.tm_wday < 5
            is_trading_hours = 10 <= wat_time.tm_hour < 14 or (wat_time.tm_hour == 14 and wat_time.tm_min <= 30)
        else:
            is_weekday = True
            is_trading_hours = True
        
        # If not trading hours, use smaller price movements
        volatility_multiplier = 1.0 if (is_weekday and is_trading_hours) else 0.3
        
        for symbol, data in st.session_state[session_key].items():
            config = data['config']
            current_price = data['current_price']
            
            # Generate new price with trend and volatility
            price_change = (random.gauss(0, config['volatility'] * volatility_multiplier) + 
                          config['trend'] * volatility_multiplier) * current_price
            
            new_price = max(0.01, current_price + price_change)
            
            # Generate realistic volume
            if is_weekday and is_trading_hours:
                base_volume = random.randint(50000, 800000)
            else:
                base_volume = random.randint(5000, 100000)
            
            # Add new data point
            new_data_point = {
                'date': current_time,
                'open': current_price,
                'high': max(current_price, new_price) * random.uniform(1.0, 1.01),
                'low': min(current_price, new_price) * random.uniform(0.99, 1.0),
                'close': new_price,
                'volume': base_volume
            }
            
            # Keep only last 30 days of data
            data['historical_data'].append(new_data_point)
            cutoff_date = current_time - timedelta(days=30)
            data['historical_data'] = [
                d for d in data['historical_data'] 
                if d['date'] >= cutoff_date
            ]
            
            # Update current price
            data['current_price'] = new_price
            data['last_update'] = current_time
    
    def get_currency_symbol(self, symbol: str) -> str:
        """Get currency symbol for different markets"""
        if symbol.endswith('.AC'):
            return 'GHS'  # Ghana Cedi
        elif symbol.endswith('.JO'):
            return 'ZAR'  # South African Rand
        elif symbol.endswith('.NR'):
            return 'KES'  # Kenyan Shilling
        elif symbol.endswith('.LG'):
            return 'NGN'  # Nigerian Naira
        elif symbol.endswith('.CA'):
            return 'EGP'  # Egyptian Pound
        elif symbol.endswith('-USD'):
            return 'USD'  # US Dollar for crypto
        else:
            return 'USD'  # US Dollar for US stocks
    
    def get_ghana_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Ghana stocks"""
        return self.get_mock_price_for_market(symbol, 'ghana')
    
    def get_kenya_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Kenya stocks"""
        return self.get_mock_price_for_market(symbol, 'kenya')
    
    def get_nigeria_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Nigeria stocks"""
        return self.get_mock_price_for_market(symbol, 'nigeria')
    
    def get_mock_price_for_market(self, symbol: str, market: str) -> Dict:
        """Get mock price data for a specific market"""
        session_key = f'{market}_mock_data'
        
        if symbol not in st.session_state[session_key]:
            return None
        
        # Update mock data
        self.update_mock_data_for_market(market, f'{market}_last_update')
        
        data = st.session_state[session_key][symbol]
        historical_data = data['historical_data']
        
        if len(historical_data) < 2:
            return None
        
        current_point = historical_data[-1]
        previous_point = historical_data[-2]
        
        current_price = current_point['close']
        previous_price = previous_point['close']
        
        change = current_price - previous_price
        change_percent = (change / previous_price) * 100 if previous_price > 0 else 0
        
        # Get stock name
        african_names = self.get_african_stock_names()
        stock_name = african_names.get(symbol, symbol)
        
        # Calculate market cap (mock value based on price)
        shares_outstanding = random.randint(100000000, 1000000000)  # Mock shares outstanding
        market_cap = current_price * shares_outstanding
        
        # Get currency symbol
        currency = self.get_currency_symbol(symbol)
        
        return {
            'symbol': symbol,
            'name': stock_name,
            'price': float(current_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'volume': int(current_point['volume']),
            'market_cap': market_cap,
            'pe_ratio': random.uniform(8, 25),  # Mock P/E ratio
            'day_high': float(current_point['high']),
            'day_low': float(current_point['low']),
            'sector': f'African Markets - {market.title()}',
            'industry': f'{market.title()} Stock Exchange',
            'is_crypto': False,
            'is_african': True,
            'is_mock': True,  # Flag to indicate this is mock data
            'country': market.title(),
            'currency': currency,
            'last_updated': datetime.now()
        }
    
    def get_ghana_mock_history(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Get historical mock data for Ghana stocks"""
        return self.get_mock_history_for_market(symbol, 'ghana', period)
    
    def get_kenya_mock_history(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Get historical mock data for Kenya stocks"""
        return self.get_mock_history_for_market(symbol, 'kenya', period)
    
    def get_nigeria_mock_history(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Get historical mock data for Nigeria stocks"""
        return self.get_mock_history_for_market(symbol, 'nigeria', period)
    
    def get_mock_history_for_market(self, symbol: str, market: str, period: str = "3mo") -> pd.DataFrame:
        """Get historical mock data for a specific market"""
        session_key = f'{market}_mock_data'
        
        if symbol not in st.session_state[session_key]:
            return pd.DataFrame()
        
        self.update_mock_data_for_market(market, f'{market}_last_update')
        
        data = st.session_state[session_key][symbol]
        historical_data = data['historical_data']
        
        # Convert to DataFrame
        df = pd.DataFrame(historical_data)
        df['Date'] = pd.to_datetime(df['date'])
        df.set_index('Date', inplace=True)
        
        # Rename columns to match yfinance format
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }, inplace=True)
        
        # Filter by period
        current_time = datetime.now()
        if period == "1mo":
            cutoff = current_time - timedelta(days=30)
        elif period == "3mo":
            cutoff = current_time - timedelta(days=90)
        elif period == "6mo":
            cutoff = current_time - timedelta(days=180)
        elif period == "1y":
            cutoff = current_time - timedelta(days=365)
        elif period == "2y":
            cutoff = current_time - timedelta(days=730)
        elif period == "5y":
            cutoff = current_time - timedelta(days=1825)
        else:
            cutoff = current_time - timedelta(days=90)
        
        df = df[df.index >= cutoff]
        
        return df
    
    def get_available_stocks(self) -> List[str]:
        """Get list of available stocks and cryptocurrencies for trading"""
        return [
            # Large Cap Tech
            'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX', 'ADBE',
            'CRM', 'ORCL', 'IBM', 'INTC', 'AMD', 'QCOM', 'AVGO', 'TXN', 'AMAT', 'LRCX',
            'NOW', 'INTU', 'PANW', 'CRWD', 'ZS', 'SNOW', 'PLTR', 'DDOG', 'OKTA', 'ZM',
            
            # Finance
            'BRK-B', 'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'USB', 'PNC', 'TFC',
            'COF', 'AXP', 'BLK', 'SCHW', 'SPGI', 'ICE', 'CME', 'CB', 'AIG', 'PGR',
            'V', 'MA', 'PYPL', 'SQ', 'FIS', 'FISV', 'COIN',
            
            # Healthcare & Biotech
            'UNH', 'JNJ', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN', 'GILD',
            'BIIB', 'REGN', 'VRTX', 'ILMN', 'ISRG', 'DXCM', 'ZTS', 'MRNA', 'BNTX', 'CVS',
            
            # Consumer & Retail
            'HD', 'WMT', 'PG', 'KO', 'PEP', 'COST', 'NKE', 'SBUX', 'MCD', 'DIS',
            'LOW', 'TJX', 'TGT', 'LULU', 'CMG', 'YUM', 'ULTA', 'ROST', 'BBY',
            
            # Energy
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'VLO', 'PSX', 'OXY', 'KMI',
            
            # ETFs
            'SPY', 'QQQ', 'IWM', 'VTI', 'VOO', 'VEA', 'VWO', 'BND', 'AGG',
            'XLE', 'XLF', 'XLK', 'XLV', 'XLI', 'XLU', 'XLP', 'XLY', 'XLB',
            
            # Cryptocurrencies (USD pairs)
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'SOL-USD', 'ADA-USD', 'AVAX-USD',
            'DOT-USD', 'DOGE-USD', 'SHIB-USD', 'MATIC-USD', 'LTC-USD', 'BCH-USD', 'LINK-USD',
            'UNI-USD', 'ATOM-USD', 'XLM-USD', 'VET-USD', 'FIL-USD', 'TRX-USD', 'ETC-USD',
            'ALGO-USD', 'MANA-USD', 'SAND-USD', 'AXS-USD', 'THETA-USD', 'AAVE-USD', 'COMP-USD',
            'MKR-USD', 'SNX-USD', 'SUSHI-USD', 'YFI-USD', 'BAT-USD', 'ZRX-USD', 'ENJ-USD',
            'CRV-USD', 'GALA-USD', 'CHZ-USD', 'FLOW-USD', 'ICP-USD', 'NEAR-USD', 'APT-USD',
            'ARB-USD', 'OP-USD', 'PEPE-USD', 'FLOKI-USD', 'BONK-USD',
            
            # African Markets
            # Ghana (GSE)
            'GOIL.AC', 'ECOBANK.AC', 'CAL.AC', 'MTNGH.AC', 'GWEB.AC', 'SOGEGH.AC',
            'AYRTN.AC', 'UNIL.AC', 'CMLT.AC', 'RBGH.AC', 'BOPP.AC', 'TOTAL.AC',
            'GGBL.AC', 'SCBGH.AC', 'DIGP.AC', 'CLYD.AC', 'AADS.AC', 'CAPL.AC',
            'NICO.AC', 'HORDS.AC', 'TRANSOL.AC', 'PRODUCE.AC', 'PIONEER.AC',
            
            # South Africa (JSE)
            'NPN.JO', 'PRX.JO', 'ABG.JO', 'SHP.JO', 'BVT.JO', 'MTN.JO', 'VOD.JO',
            'DSY.JO', 'TKG.JO', 'REM.JO', 'BID.JO', 'SBK.JO', 'FSR.JO', 'NED.JO',
            'AGL.JO', 'IMP.JO', 'SOL.JO', 'CPI.JO', 'RNI.JO', 'APN.JO', 'MCG.JO',
            'PIK.JO', 'WHL.JO', 'TBS.JO', 'GFI.JO', 'HAR.JO', 'SLM.JO', 'AMS.JO',
            'CFR.JO', 'INP.JO', 'BTI.JO', 'ARI.JO', 'SPP.JO', 'MRP.JO', 'RBX.JO',
            
            # Kenya (NSE)
            'KCB.NR', 'EQTY.NR', 'SCBK.NR', 'ABSA.NR', 'DTBK.NR', 'BAT.NR', 'EABL.NR',
            'SAFCOM.NR', 'BRITAM.NR', 'JUBILEE.NR', 'LIBERTY.NR', 'COOP.NR', 'UNGA.NR',
            'KAKUZI.NR', 'SASINI.NR', 'KAPCHORUA.NR', 'WILLIAMSON.NR', 'BAMBURI.NR',
            'CROWN.NR', 'KENGEN.NR', 'KPLC.NR', 'KEGN.NR', 'KENOL.NR', 'TPS.NR',
            'UMEME.NR', 'TOTAL.NR', 'CARBACID.NR', 'BOC.NR', 'OLYMPIA.NR', 'CENTUM.NR',
            
            # Nigeria (NGX)
            'GTCO.LG', 'ZENITHBANK.LG', 'UBA.LG', 'ACCESS.LG', 'FBNH.LG', 'FIDELITYBK.LG',
            'STERLINGNG.LG', 'WEMA.LG', 'UNITY.LG', 'STANBIC.LG', 'DANGCEM.LG', 'BUA.LG',
            'MTNN.LG', 'AIRTELAFRI.LG', 'SEPLAT.LG', 'OANDO.LG', 'TOTAL.LG', 'CONOIL.LG',
            'GUINNESS.LG', 'NB.LG', 'INTBREW.LG', 'NESTLE.LG', 'UNILEVER.LG', 'DANGSUGAR.LG',
            'FLOURMILL.LG', 'HONEYFLOUR.LG', 'CADBURY.LG', 'VITAFOAM.LG', 'JBERGER.LG',
            'LIVESTOCK.LG', 'CHIPLC.LG', 'ELLAHLAKES.LG', 'NAHCO.LG', 'RTBRISCOE.LG',
            
            # Egypt (EGX)
            'CIB.CA', 'COMI.CA', 'ALEX.CA', 'ABUK.CA', 'SAIB.CA', 'ADIB.CA', 'QNBK.CA',
            'ELSWEDY.CA', 'HRHO.CA', 'TMGH.CA', 'OTMT.CA', 'PHDC.CA', 'PALM.CA', 'MNHD.CA',
            'MOPCO.CA', 'EGAS.CA', 'EGTS.CA', 'EGCH.CA', 'SKPC.CA', 'IRON.CA', 'EZDK.CA',
            'AMOC.CA', 'ETEL.CA', 'ORWE.CA', 'EAST.CA', 'JUFO.CA', 'AMER.CA', 'SPMD.CA',
            'EMFD.CA', 'CLHO.CA', 'EKHO.CA', 'DOMTY.CA', 'EDBE.CA', 'IDBE.CA', 'MTIE.CA'
        ]
    
    def get_african_markets(self) -> Dict[str, List[str]]:
        """Get African markets categorized by country"""
        return {
            "🇬🇭 Ghana Stock Exchange (GSE)": [
                'GOIL.AC', 'ECOBANK.AC', 'CAL.AC', 'MTNGH.AC', 'GWEB.AC', 'SOGEGH.AC',
                'AYRTN.AC', 'UNIL.AC', 'CMLT.AC', 'RBGH.AC', 'BOPP.AC', 'TOTAL.AC',
                'GGBL.AC', 'SCBGH.AC', 'DIGP.AC', 'CLYD.AC', 'AADS.AC', 'CAPL.AC',
                'NICO.AC', 'HORDS.AC', 'TRANSOL.AC', 'PRODUCE.AC', 'PIONEER.AC'
            ],
            "🇿🇦 Johannesburg Stock Exchange (JSE)": [
                'NPN.JO', 'PRX.JO', 'ABG.JO', 'SHP.JO', 'BVT.JO', 'MTN.JO', 'VOD.JO',
                'DSY.JO', 'TKG.JO', 'REM.JO', 'BID.JO', 'SBK.JO', 'FSR.JO', 'NED.JO',
                'AGL.JO', 'IMP.JO', 'SOL.JO', 'CPI.JO', 'RNI.JO', 'APN.JO', 'MCG.JO',
                'PIK.JO', 'WHL.JO', 'TBS.JO', 'GFI.JO', 'HAR.JO', 'SLM.JO', 'AMS.JO',
                'CFR.JO', 'INP.JO', 'BTI.JO', 'ARI.JO', 'SPP.JO', 'MRP.JO', 'RBX.JO'
            ],
            "🇰🇪 Nairobi Securities Exchange (NSE)": [
                'KCB.NR', 'EQTY.NR', 'SCBK.NR', 'ABSA.NR', 'DTBK.NR', 'BAT.NR', 'EABL.NR',
                'SAFCOM.NR', 'BRITAM.NR', 'JUBILEE.NR', 'LIBERTY.NR', 'COOP.NR', 'UNGA.NR',
                'KAKUZI.NR', 'SASINI.NR', 'KAPCHORUA.NR', 'WILLIAMSON.NR', 'BAMBURI.NR',
                'CROWN.NR', 'KENGEN.NR', 'KPLC.NR', 'KEGN.NR', 'KENOL.NR', 'TPS.NR',
                'UMEME.NR', 'TOTAL.NR', 'CARBACID.NR', 'BOC.NR', 'OLYMPIA.NR', 'CENTUM.NR'
            ],
            "🇳🇬 Nigerian Exchange (NGX)": [
                'GTCO.LG', 'ZENITHBANK.LG', 'UBA.LG', 'ACCESS.LG', 'FBNH.LG', 'FIDELITYBK.LG',
                'STERLINGNG.LG', 'WEMA.LG', 'UNITY.LG', 'STANBIC.LG', 'DANGCEM.LG', 'BUA.LG',
                'MTNN.LG', 'AIRTELAFRI.LG', 'SEPLAT.LG', 'OANDO.LG', 'TOTAL.LG', 'CONOIL.LG',
                'GUINNESS.LG', 'NB.LG', 'INTBREW.LG', 'NESTLE.LG', 'UNILEVER.LG', 'DANGSUGAR.LG',
                'FLOURMILL.LG', 'HONEYFLOUR.LG', 'CADBURY.LG', 'VITAFOAM.LG', 'JBERGER.LG',
                'LIVESTOCK.LG', 'CHIPLC.LG', 'ELLAHLAKES.LG', 'NAHCO.LG', 'RTBRISCOE.LG'
            ],
            "🇪🇬 Egyptian Exchange (EGX)": [
                'CIB.CA', 'COMI.CA', 'ALEX.CA', 'ABUK.CA', 'SAIB.CA', 'ADIB.CA', 'QNBK.CA',
                'ELSWEDY.CA', 'HRHO.CA', 'TMGH.CA', 'OTMT.CA', 'PHDC.CA', 'PALM.CA', 'MNHD.CA',
                'MOPCO.CA', 'EGAS.CA', 'EGTS.CA', 'EGCH.CA', 'SKPC.CA', 'IRON.CA', 'EZDK.CA',
                'AMOC.CA', 'ETEL.CA', 'ORWE.CA', 'EAST.CA', 'JUFO.CA', 'AMER.CA', 'SPMD.CA',
                'EMFD.CA', 'CLHO.CA', 'EKHO.CA', 'DOMTY.CA', 'EDBE.CA', 'IDBE.CA', 'MTIE.CA'
            ]
        }
    
    def get_african_stock_names(self) -> Dict[str, str]:
        """Get African stock names mapping"""
        return {
            # Ghana
            'GOIL.AC': 'Ghana Oil Company Limited',
            'ECOBANK.AC': 'Ecobank Ghana Limited',
            'CAL.AC': 'CAL Bank Limited',
            'MTNGH.AC': 'MTN Ghana Limited',
            'GWEB.AC': 'Golden Web Limited',
            'SOGEGH.AC': 'Societe Generale Ghana',
            'AYRTN.AC': 'Ayrton Drug Manufacturing',
            'UNIL.AC': 'Unilever Ghana Limited',
            'CMLT.AC': 'Camelot Ghana Limited',
            'RBGH.AC': 'Republic Bank Ghana',
            'BOPP.AC': 'Benso Oil Palm Plantation',
            'TOTAL.AC': 'Total Petroleum Ghana',
            'GGBL.AC': 'Ghana Breweries Limited',
            'SCBGH.AC': 'Standard Chartered Bank Ghana',
            'DIGP.AC': 'Dalex Finance & Leasing',
            'CLYD.AC': 'Clydestone Ghana Limited',
            'AADS.AC': 'Aluworks Limited',
            'CAPL.AC': 'Cocoa Processing Company',
            'NICO.AC': 'NICO Insurance Company',
            'HORDS.AC': 'Hords Investment Limited',
            'TRANSOL.AC': 'Transol Solutions Limited',
            'PRODUCE.AC': 'Produce Buying Company',
            'PIONEER.AC': 'Pioneer Kitchenware Limited',
            
            # South Africa
            'NPN.JO': 'Naspers Limited',
            'PRX.JO': 'Prosus NV',
            'ABG.JO': 'Absa Group Limited',
            'SHP.JO': 'Shoprite Holdings Limited',
            'BVT.JO': 'Bidvest Group Limited',
            'MTN.JO': 'MTN Group Limited',
            'VOD.JO': 'Vodacom Group Limited',
            'DSY.JO': 'Discovery Limited',
            'TKG.JO': 'Telkom SA SOC Limited',
            'REM.JO': 'Remgro Limited',
            'BID.JO': 'Bid Corporation Limited',
            'SBK.JO': 'Standard Bank Group Limited',
            'FSR.JO': 'FirstRand Limited',
            'NED.JO': 'Nedbank Group Limited',
            'AGL.JO': 'Anglo American plc',
            'IMP.JO': 'Impala Platinum Holdings Limited',
            'SOL.JO': 'Sasol Limited',
            'CPI.JO': 'Capitec Bank Holdings Limited',
            'RNI.JO': 'Reinet Investments SCA',
            'APN.JO': 'Aspen Pharmacare Holdings Limited',
            'MCG.JO': 'Multichoice Group Limited',
            'PIK.JO': 'Pick n Pay Stores Limited',
            'WHL.JO': 'Woolworths Holdings Limited',
            'TBS.JO': 'Tiger Brands Limited',
            'GFI.JO': 'Gold Fields Limited',
            'HAR.JO': 'Harmony Gold Mining Company Limited',
            'SLM.JO': 'Sanlam Limited',
            'AMS.JO': 'Anglo American Platinum Limited',
            'CFR.JO': 'Cartrack Holdings Limited',
            'INP.JO': 'Investec plc',
            'BTI.JO': 'Brait SE',
            'ARI.JO': 'African Rainbow Minerals Limited',
            'SPP.JO': 'Spar Group Limited',
            'MRP.JO': 'Mr Price Group Limited',
            'RBX.JO': 'Raubex Group Limited',
            
            # Kenya
            'KCB.NR': 'KCB Group Limited',
            'EQTY.NR': 'Equity Group Holdings Limited',
            'SCBK.NR': 'Standard Chartered Bank Kenya Limited',
            'ABSA.NR': 'Absa Bank Kenya Limited',
            'DTBK.NR': 'Diamond Trust Bank Kenya Limited',
            'BAT.NR': 'British American Tobacco Kenya Limited',
            'EABL.NR': 'East African Breweries Limited',
            'SAFCOM.NR': 'Safaricom Limited',
            'BRITAM.NR': 'Britam Holdings Limited',
            'JUBILEE.NR': 'Jubilee Holdings Limited',
            'LIBERTY.NR': 'Liberty Kenya Holdings Limited',
            'COOP.NR': 'Co-operative Bank of Kenya Limited',
            'UNGA.NR': 'Unga Group Limited',
            'KAKUZI.NR': 'Kakuzi Limited',
            'SASINI.NR': 'Sasini Limited',
            'KAPCHORUA.NR': 'Kapchorua Tea Company Limited',
            'WILLIAMSON.NR': 'Williamson Tea Kenya Limited',
            'BAMBURI.NR': 'Bamburi Cement Limited',
            'CROWN.NR': 'Crown Berger Limited',
            'KENGEN.NR': 'Kenya Electricity Generating Company Limited',
            'KPLC.NR': 'Kenya Power and Lighting Company Limited',
            'KEGN.NR': 'KenGen Limited',
            'KENOL.NR': 'KenolKobil Limited',
            'TPS.NR': 'TPS Eastern Africa Limited',
            'UMEME.NR': 'Umeme Limited',
            'TOTAL.NR': 'Total Kenya Limited',
            'CARBACID.NR': 'Carbacid Investments Limited',
            'BOC.NR': 'BOC Kenya Limited',
            'OLYMPIA.NR': 'Olympia Capital Holdings Limited',
            'CENTUM.NR': 'Centum Investment Company Limited',
            
            # Nigeria
            'GTCO.LG': 'Guaranty Trust Holding Company Plc',
            'ZENITHBANK.LG': 'Zenith Bank Plc',
            'UBA.LG': 'United Bank for Africa Plc',
            'ACCESS.LG': 'Access Holdings Plc',
            'FBNH.LG': 'FBN Holdings Plc',
            'FIDELITYBK.LG': 'Fidelity Bank Plc',
            'STERLINGNG.LG': 'Sterling Bank Plc',
            'WEMA.LG': 'Wema Bank Plc',
            'UNITY.LG': 'Unity Bank Plc',
            'STANBIC.LG': 'Stanbic IBTC Holdings Plc',
            'DANGCEM.LG': 'Dangote Cement Plc',
            'BUA.LG': 'BUA Cement Plc',
            'MTNN.LG': 'MTN Nigeria Communications Plc',
            'AIRTELAFRI.LG': 'Airtel Africa Plc',
            'SEPLAT.LG': 'Seplat Petroleum Development Company Plc',
            'OANDO.LG': 'Oando Plc',
            'TOTAL.LG': 'Total Nigeria Plc',
            'CONOIL.LG': 'Conoil Plc',
            'GUINNESS.LG': 'Guinness Nigeria Plc',
            'NB.LG': 'Nigerian Breweries Plc',
            'INTBREW.LG': 'International Breweries Plc',
            'NESTLE.LG': 'Nestle Nigeria Plc',
            'UNILEVER.LG': 'Unilever Nigeria Plc',
            'DANGSUGAR.LG': 'Dangote Sugar Refinery Plc',
            'FLOURMILL.LG': 'Flour Mills of Nigeria Plc',
            'HONEYFLOUR.LG': 'Honeywell Flour Mill Plc',
            'CADBURY.LG': 'Cadbury Nigeria Plc',
            'VITAFOAM.LG': 'Vitafoam Nigeria Plc',
            'JBERGER.LG': 'Julius Berger Nigeria Plc',
            'LIVESTOCK.LG': 'Livestock Feeds Plc',
            'CHIPLC.LG': 'Champion Breweries Plc',
            'ELLAHLAKES.LG': 'Ellah Lakes Plc',
            'NAHCO.LG': 'Nigerian Aviation Handling Company Plc',
            'RTBRISCOE.LG': 'RT Briscoe Plc',
            
            # Egypt
            'CIB.CA': 'Commercial International Bank Egypt',
            'COMI.CA': 'Commercial Bank of Egypt',
            'ALEX.CA': 'Bank of Alexandria',
            'ABUK.CA': 'Arab Bank of Egypt',
            'SAIB.CA': 'Suez Canal Bank',
            'ADIB.CA': 'Abu Dhabi Islamic Bank Egypt',
            'QNBK.CA': 'QNB Egypt',
            'ELSWEDY.CA': 'El Sewedy Electric Company',
            'HRHO.CA': 'Hassan Allam Holding',
            'TMGH.CA': 'TMG Holding',
            'OTMT.CA': 'Orascom Telecom Media Technology',
            'PHDC.CA': 'Palm Hills Developments',
            'PALM.CA': 'Palm Trees Development Company',
            'MNHD.CA': 'Madinet Nasr Housing and Development',
            'MOPCO.CA': 'Middle East Oil Refinery',
            'EGAS.CA': 'Egyptian Gas Company',
            'EGTS.CA': 'Egyptian Gulf Company',
            'EGCH.CA': 'Egyptian Chemicals Company',
            'SKPC.CA': 'Suez Canal Container Terminal',
            'IRON.CA': 'Iron & Steel for Mines and Quarries',
            'EZDK.CA': 'Ezz Dekheila Steel Company',
            'AMOC.CA': 'Arab Moltaka Investment Company',
            'ETEL.CA': 'Egyptian Telecommunications Company',
            'ORWE.CA': 'Orascom West El Balad',
            'EAST.CA': 'Eastern Company',
            'JUFO.CA': 'Juhayna Food Industries',
            'AMER.CA': 'Amer Group Holding',
            'SPMD.CA': 'Sphinx Medical Development',
            'EMFD.CA': 'Egyptian Media Production City',
            'CLHO.CA': 'Cairo for Hotels Company',
            'EKHO.CA': 'Egyptian Kuwaiti Holding Company',
            'DOMTY.CA': 'Domty Company',
            'EDBE.CA': 'Egyptian Drugs and Beverages Company',
            'IDBE.CA': 'Egyptian Drinks and Beverages Company',
            'MTIE.CA': 'Misr for Trade and Investment Company'
        }
    
    def get_crypto_categories(self) -> Dict[str, List[str]]:
        """Get categorized cryptocurrency list"""
        return {
            "Major Cryptocurrencies": [
                'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'SOL-USD', 'ADA-USD', 'AVAX-USD', 'DOT-USD'
            ],
            "DeFi Tokens": [
                'UNI-USD', 'AAVE-USD', 'COMP-USD', 'MKR-USD', 'SNX-USD', 'SUSHI-USD', 'YFI-USD', 'CRV-USD'
            ],
            "Meme Coins": [
                'DOGE-USD', 'SHIB-USD', 'PEPE-USD', 'FLOKI-USD', 'BONK-USD'
            ],
            "Layer 1 & 2": [
                'MATIC-USD', 'ATOM-USD', 'NEAR-USD', 'APT-USD', 'ARB-USD', 'OP-USD', 'ICP-USD'
            ],
            "Altcoins": [
                'LTC-USD', 'BCH-USD', 'LINK-USD', 'XLM-USD', 'VET-USD', 'FIL-USD', 'TRX-USD', 'ETC-USD', 'ALGO-USD'
            ],
            "Gaming & NFT": [
                'MANA-USD', 'SAND-USD', 'AXS-USD', 'THETA-USD', 'GALA-USD', 'CHZ-USD', 'FLOW-USD', 'ENJ-USD'
            ],
            "Utility Tokens": [
                'BAT-USD', 'ZRX-USD'
            ]
        }
    
    def is_crypto(self, symbol: str) -> bool:
        """Check if symbol is a cryptocurrency"""
        return symbol.endswith('-USD')
    
    def is_african_stock(self, symbol: str) -> bool:
        """Check if symbol is an African stock"""
        african_suffixes = ['.AC', '.JO', '.NR', '.LG', '.CA']
        return any(symbol.endswith(suffix) for suffix in african_suffixes)
    
    def get_african_country_from_symbol(self, symbol: str) -> str:
        """Get African country from stock symbol"""
        if symbol.endswith('.AC'):
            return "Ghana"
        elif symbol.endswith('.JO'):
            return "South Africa"
        elif symbol.endswith('.NR'):
            return "Kenya"
        elif symbol.endswith('.LG'):
            return "Nigeria"
        elif symbol.endswith('.CA'):
            return "Egypt"
        return "Unknown"
    
    @st.cache_data(ttl=300)
    def get_stock_price(_self, symbol: str) -> Dict:
        """Get current stock/crypto price and info with error handling and rate limiting"""
        try:
            # Check if it's a mock data stock (these don't use API calls)
            if symbol.endswith('.AC'):
                return _self.get_ghana_mock_price(symbol)
            elif symbol.endswith('.NR'):
                return _self.get_kenya_mock_price(symbol)
            elif symbol.endswith('.LG'):
                return _self.get_nigeria_mock_price(symbol)
            
            # For real data, implement rate limiting and better error handling
            import time
            time.sleep(0.1)  # Small delay to avoid rate limiting
            
            # For all other stocks, use yfinance with error handling
            ticker = yf.Ticker(symbol)
            
            # Try to get data with fallback options
            try:
                hist = ticker.history(period="5d")
                if hist.empty:
                    hist = ticker.history(period="1d")
                if hist.empty:
                    return None
                    
                info = ticker.info
            except Exception as e:
                # If real-time data fails, return a fallback structure
                st.warning(f"Limited data for {symbol}: {str(e)}")
                return {
                    'symbol': symbol,
                    'name': symbol,
                    'price': 100.0,  # Fallback price
                    'change': 0.0,
                    'change_percent': 0.0,
                    'volume': 0,
                    'market_cap': 0,
                    'pe_ratio': 0,
                    'day_high': 100.0,
                    'day_low': 100.0,
                    'sector': 'Unknown',
                    'industry': 'Unknown',
                    'is_crypto': symbol.endswith('-USD'),
                    'is_african': _self.is_african_stock(symbol),
                    'is_mock': False,
                    'country': _self.get_african_country_from_symbol(symbol) if _self.is_african_stock(symbol) else None,
                    'currency': _self.get_currency_symbol(symbol),
                    'last_updated': datetime.now(),
                    'error': True
                }
            
            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            if prev_close == 0:
                prev_close = current_price
                
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
            
            # Determine asset type
            is_crypto = symbol.endswith('-USD')
            is_african = _self.is_african_stock(symbol)
            
            # Get currency symbol
            currency = _self.get_currency_symbol(symbol)
            
            # Get appropriate name
            if is_crypto:
                display_name = symbol.replace('-USD', '')
                long_name = info.get('longName', display_name)
                if long_name == display_name:
                    # Create better display names for crypto
                    crypto_names = {
                        'BTC': 'Bitcoin',
                        'ETH': 'Ethereum',
                        'BNB': 'Binance Coin',
                        'XRP': 'XRP',
                        'SOL': 'Solana',
                        'ADA': 'Cardano',
                        'AVAX': 'Avalanche',
                        'DOT': 'Polkadot',
                        'DOGE': 'Dogecoin',
                        'SHIB': 'Shiba Inu',
                        'MATIC': 'Polygon',
                        'LTC': 'Litecoin',
                        'BCH': 'Bitcoin Cash',
                        'LINK': 'Chainlink',
                        'UNI': 'Uniswap',
                        'ATOM': 'Cosmos',
                        'XLM': 'Stellar',
                        'VET': 'VeChain',
                        'FIL': 'Filecoin',
                        'TRX': 'TRON',
                        'ETC': 'Ethereum Classic',
                        'ALGO': 'Algorand',
                        'MANA': 'Decentraland',
                        'SAND': 'The Sandbox',
                        'AXS': 'Axie Infinity',
                        'THETA': 'Theta Network',
                        'AAVE': 'Aave',
                        'COMP': 'Compound',
                        'MKR': 'Maker',
                        'SNX': 'Synthetix',
                        'SUSHI': 'SushiSwap',
                        'YFI': 'yearn.finance',
                        'BAT': 'Basic Attention Token',
                        'ZRX': '0x Protocol',
                        'ENJ': 'Enjin Coin',
                        'CRV': 'Curve DAO',
                        'GALA': 'Gala',
                        'CHZ': 'Chiliz',
                        'FLOW': 'Flow',
                        'ICP': 'Internet Computer',
                        'NEAR': 'NEAR Protocol',
                        'APT': 'Aptos',
                        'ARB': 'Arbitrum',
                        'OP': 'Optimism',
                        'PEPE': 'Pepe',
                        'FLOKI': 'Floki Inu',
                        'BONK': 'Bonk'
                    }
                    long_name = crypto_names.get(display_name, display_name)
            elif is_african:
                african_names = _self.get_african_stock_names()
                long_name = african_names.get(symbol, symbol)
            else:
                long_name = info.get('longName', symbol)
            
            # Determine sector
            if is_crypto:
                sector = 'Cryptocurrency'
                industry = 'Digital Currency'
            elif is_african:
                country = _self.get_african_country_from_symbol(symbol)
                sector = f'African Markets - {country}'
                industry = info.get('industry', 'African Stock')
            else:
                sector = info.get('sector', 'Unknown')
                industry = info.get('industry', 'Unknown')
            
            return {
                'symbol': symbol,
                'name': long_name[:50],
                'price': float(current_price),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': int(hist['Volume'].iloc[-1]) if len(hist) > 0 and not pd.isna(hist['Volume'].iloc[-1]) else 0,
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0) if not is_crypto else None,
                'day_high': float(hist['High'].iloc[-1]) if len(hist) > 0 else current_price,
                'day_low': float(hist['Low'].iloc[-1]) if len(hist) > 0 else current_price,
                'sector': sector,
                'industry': industry,
                'is_crypto': is_crypto,
                'is_african': is_african,
                'is_mock': False,
                'country': _self.get_african_country_from_symbol(symbol) if is_african else None,
                'currency': currency,
                'last_updated': datetime.now()
            }
        except Exception as e:
            # Return fallback data instead of None to prevent crashes
            st.warning(f"Error fetching data for {symbol}: Rate limited or API issue")
            return {
                'symbol': symbol,
                'name': symbol,
                'price': 100.0,  # Fallback price
                'change': 0.0,
                'change_percent': 0.0,
                'volume': 0,
                'market_cap': 0,
                'pe_ratio': 0,
                'day_high': 100.0,
                'day_low': 100.0,
                'sector': 'Unknown',
                'industry': 'Unknown',
                'is_crypto': symbol.endswith('-USD'),
                'is_african': _self.is_african_stock(symbol),
                'is_mock': False,
                'country': _self.get_african_country_from_symbol(symbol) if _self.is_african_stock(symbol) else None,
                'currency': _self.get_currency_symbol(symbol),
                'last_updated': datetime.now(),
                'error': True
            }
    
    def get_portfolio_value(self, user_id: str) -> float:
        """Calculate total portfolio value"""
        try:
            user_data = self.db.get_user_data(user_id)
            if not user_data:
                return 0
            
            total_value = user_data['cash']
            portfolio = self.db.get_user_portfolio(user_id)
            
            for position in portfolio:
                stock_data = self.get_stock_price(position['symbol'])
                if stock_data:
                    total_value += stock_data['price'] * position['shares']
            
            return total_value
        except Exception as e:
            st.error(f"Error calculating portfolio value: {str(e)}")
            return 0
    
    def create_comprehensive_chart(self, symbol: str, period: str = "3mo"):
        """Create comprehensive stock/crypto chart with technical analysis"""
        try:
            # Check if it's a mock data stock
            if symbol.endswith('.AC'):
                hist = self.get_ghana_mock_history(symbol, period)
                currency = 'GHS'
            elif symbol.endswith('.NR'):
                hist = self.get_kenya_mock_history(symbol, period)
                currency = 'KES'
            elif symbol.endswith('.LG'):
                hist = self.get_nigeria_mock_history(symbol, period)
                currency = 'NGN'
            else:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=period)
                    if hist.empty:
                        hist = ticker.history(period="1mo")  # Fallback to shorter period
                    currency = self.get_currency_symbol(symbol)
                except Exception as e:
                    st.warning(f"Unable to fetch chart data for {symbol}: {str(e)}")
                    return None
            
            if hist.empty:
                st.warning(f"No data available for {symbol} for the selected period")
                return None
            
            # Create subplots
            fig = go.Figure()
            
            # Determine asset type
            is_crypto = symbol.endswith('-USD')
            is_african = self.is_african_stock(symbol)
            is_mock = symbol.endswith('.AC') or symbol.endswith('.NR') or symbol.endswith('.LG')
            
            if is_crypto:
                display_name = symbol.replace('-USD', '')
                asset_type = "Cryptocurrency"
                asset_icon = "🪙"
            elif symbol.endswith('.AC'):
                display_name = symbol
                asset_type = "Ghana Stock Exchange (GSE) - Live Mock Data"
                asset_icon = "🇬🇭"
            elif symbol.endswith('.NR'):
                display_name = symbol
                asset_type = "Kenya NSE - Live Mock Data"
                asset_icon = "🇰🇪"
            elif symbol.endswith('.LG'):
                display_name = symbol
                asset_type = "Nigeria NGX - Live Mock Data"
                asset_icon = "🇳🇬"
            elif is_african:
                display_name = symbol
                country = self.get_african_country_from_symbol(symbol)
                asset_type = f"African Stock - {country}"
                asset_icon = "🌍"
            else:
                display_name = symbol
                asset_type = "Stock"
                asset_icon = "📈"
            
            # Main candlestick chart
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='Price',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
                increasing_fillcolor='rgba(38, 166, 154, 0.3)',
                decreasing_fillcolor='rgba(239, 83, 80, 0.3)'
            ))
            
            # Add moving averages
            if len(hist) >= 20:
                hist['SMA20'] = hist['Close'].rolling(window=20).mean()
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=hist['SMA20'],
                    mode='lines',
                    name='SMA 20',
                    line=dict(color='orange', width=2)
                ))
            
            if len(hist) >= 50:
                hist['SMA50'] = hist['Close'].rolling(window=50).mean()
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=hist['SMA50'],
                    mode='lines',
                    name='SMA 50',
                    line=dict(color='blue', width=2)
                ))
            
            # Add volume bars as secondary y-axis
            fig.add_trace(go.Bar(
                x=hist.index,
                y=hist['Volume'],
                name='Volume',
                marker_color='rgba(158, 158, 158, 0.3)',
                yaxis='y2'
            ))
            
            # Calculate RSI
            if len(hist) >= 14:
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                
                # Add RSI as text annotation
                current_rsi = rsi.iloc[-1]
                if not pd.isna(current_rsi):
                    fig.add_annotation(
                        x=hist.index[-1],
                        y=hist['High'].max(),
                        text=f"RSI: {current_rsi:.1f}",
                        showarrow=False,
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="black",
                        borderwidth=1
                    )
            
            # Add mock data indicator for mock data stocks
            if is_mock:
                if symbol.endswith('.AC'):
                    mock_text = "🇬🇭 LIVE MOCK DATA"
                elif symbol.endswith('.NR'):
                    mock_text = "🇰🇪 LIVE MOCK DATA"
                elif symbol.endswith('.LG'):
                    mock_text = "🇳🇬 LIVE MOCK DATA"
                else:
                    mock_text = "LIVE MOCK DATA"
                
                fig.add_annotation(
                    x=hist.index[0],
                    y=hist['High'].max(),
                    text=mock_text,
                    showarrow=False,
                    bgcolor="rgba(255,193,7,0.8)",
                    bordercolor="orange",
                    borderwidth=2,
                    font=dict(color="black", size=12)
                )
            
            # Price formatting
            if (is_crypto and hist['Close'].iloc[-1] < 1) or (is_african and hist['Close'].iloc[-1] < 10):
                price_format = ".4f"
            else:
                price_format = ".2f"
            
            # Update layout
            fig.update_layout(
                title=f"{asset_icon} {display_name} - {asset_type} Technical Analysis ({period})",
                yaxis_title=f"Price ({currency})",
                xaxis_title="Date",
                template="plotly_white",
                height=600,
                showlegend=True,
                yaxis=dict(
                    tickformat=f"{currency} {price_format}",
                    side="left"
                ),
                yaxis2=dict(
                    title="Volume",
                    overlaying="y",
                    side="right",
                    showgrid=False
                ),
                xaxis=dict(
                    rangeslider=dict(visible=False),
                    type="date"
                ),
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating chart for {symbol}: {str(e)}")
            return None
    
    def create_comparison_chart(self, symbols: List[str], period: str = "3mo"):
        """Create comparison chart for multiple assets"""
        try:
            fig = go.Figure()
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
            
            for i, symbol in enumerate(symbols):
                try:
                    # Check if it's a mock data stock
                    if symbol.endswith('.AC'):
                        hist = self.get_ghana_mock_history(symbol, period)
                    elif symbol.endswith('.NR'):
                        hist = self.get_kenya_mock_history(symbol, period)
                    elif symbol.endswith('.LG'):
                        hist = self.get_nigeria_mock_history(symbol, period)
                    else:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period=period)
                        if hist.empty:
                            hist = ticker.history(period="1mo")  # Fallback
                    
                    if not hist.empty:
                        # Normalize prices to percentage change from start
                        normalized_prices = ((hist['Close'] / hist['Close'].iloc[0]) - 1) * 100
                        
                        # Get display name based on asset type
                        if symbol.endswith('-USD'):
                            display_name = symbol.replace('-USD', '')
                        elif symbol.endswith('.AC'):
                            display_name = f"🇬🇭 {symbol}"
                        elif symbol.endswith('.NR'):
                            display_name = f"🇰🇪 {symbol}"
                        elif symbol.endswith('.LG'):
                            display_name = f"🇳🇬 {symbol}"
                        elif self.is_african_stock(symbol):
                            display_name = f"{symbol} ({self.get_african_country_from_symbol(symbol)})"
                        else:
                            display_name = symbol
                        
                        fig.add_trace(go.Scatter(
                            x=hist.index,
                            y=normalized_prices,
                            mode='lines',
                            name=display_name,
                            line=dict(color=colors[i % len(colors)], width=2)
                        ))
                except Exception as e:
                    st.warning(f"Skipping {symbol}: {str(e)}")
                    continue
            
            fig.update_layout(
                title=f"Asset Comparison - Normalized Performance ({period})",
                xaxis_title="Date",
                yaxis_title="Percentage Change (%)",
                template="plotly_white",
                height=500,
                showlegend=True,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating comparison chart: {str(e)}")
            return None
    
    def create_portfolio_pie_chart(self, user_id: str):
        """Create portfolio allocation pie chart"""
        try:
            portfolio = self.db.get_user_portfolio(user_id)
            
            if not portfolio:
                return None
            
            portfolio_data = []
            total_portfolio_value = 0
            
            for position in portfolio:
                stock_data = self.get_stock_price(position['symbol'])
                if stock_data:
                    current_value = stock_data['price'] * position['shares']
                    total_portfolio_value += current_value
                    
                    # Add appropriate icon based on asset type
                    if stock_data.get('is_crypto'):
                        symbol_display = f"🪙 {position['symbol'].replace('-USD', '')}"
                    elif stock_data.get('is_african'):
                        symbol_display = f"🌍 {position['symbol']}"
                    else:
                        symbol_display = f"📈 {position['symbol']}"
                    
                    portfolio_data.append({
                        'Symbol': symbol_display,
                        'Name': position['name'][:20],
                        'Value': current_value,
                        'Shares': position['shares'],
                        'Price': stock_data['price']
                    })
            
            if not portfolio_data or total_portfolio_value == 0:
                return None
            
            df = pd.DataFrame(portfolio_data)
            
            fig = px.pie(
                df,
                values='Value',
                names='Symbol',
                title=f'Portfolio Allocation<br>Total Value: ${total_portfolio_value:,.2f}',
                hover_data=['Name', 'Shares', 'Price'],
                labels={'Value': 'Value ($)', 'Symbol': 'Holdings'}
            )
            
            fig.update_traces(
                textposition='inside', 
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>' +
                              'Company: %{customdata[0]}<br>' +
                              'Value: $%{value:,.0f}<br>' +
                              'Shares: %{customdata[1]:,.0f}<br>' +
                              'Price: $%{customdata[2]:,.2f}<br>' +
                              'Percentage: %{percent}<br>' +
                              '<extra></extra>',
                textfont_size=12,
                marker=dict(line=dict(color='#FFFFFF', width=2))
            )
            
            fig.update_layout(
                height=500,
                font=dict(size=12),
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="middle",
                    y=0.5,
                    xanchor="left",
                    x=1.05
                ),
                margin=dict(l=20, r=120, t=70, b=20)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating portfolio pie chart: {str(e)}")
            return None
    
    def get_portfolio_summary(self, user_id: str) -> Dict:
        """Get portfolio summary statistics"""
        try:
            portfolio = self.db.get_user_portfolio(user_id)
            user_data = self.db.get_user_data(user_id)
            
            if not portfolio or not user_data:
                return {}
            
            total_invested = 0
            total_current_value = 0
            total_unrealized_pl = 0
            holdings_count = len(portfolio)
            
            for position in portfolio:
                stock_data = self.get_stock_price(position['symbol'])
                if stock_data:
                    invested_value = position['avg_price'] * position['shares']
                    current_value = stock_data['price'] * position['shares']
                    unrealized_pl = current_value - invested_value
                    
                    total_invested += invested_value
                    total_current_value += current_value
                    total_unrealized_pl += unrealized_pl
            
            return {
                'cash': user_data['cash'],
                'total_invested': total_invested,
                'total_current_value': total_current_value,
                'total_unrealized_pl': total_unrealized_pl,
                'holdings_count': holdings_count,
                'total_portfolio_value': user_data['cash'] + total_current_value
            }
            
        except Exception as e:
            st.error(f"Error getting portfolio summary: {str(e)}")
            return {}

def main():
    try:
        simulator = TradingSimulator()
        
        # Header
        st.markdown("""
        <div class="main-header">
            <h1>Leo's Trader</h1>
            <p>🎮 Learn trading with virtual money • 📈 Build your portfolio • 🪙 Trade crypto 24/7 • 🌍 Explore African markets • 🏆 Compete with friends</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Ghana Pride Section
        st.markdown("""
        <div class="ghana-pride">
            <h3>🇬🇭 Proudly Made in Ghana 🇬🇭</h3>
            <p>Developed with passion from the Gateway to Africa</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Authentication
        if not st.session_state.logged_in:
            st.subheader("🔐 Login or Register")
            
            tab1, tab2 = st.tabs(["Login", "Register"])
            
            with tab1:
                with st.form("login_form"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    
                    if st.form_submit_button("Login"):
                        if username and password:
                            result = simulator.db.authenticate_user(username, password)
                            if result['success']:
                                st.session_state.current_user = result['user']
                                st.session_state.logged_in = True
                                st.success(f"Welcome back, {result['user']['username']}!")
                                st.rerun()
                            else:
                                st.error(result['message'])
                        else:
                            st.error("Please enter username and password")
            
            with tab2:
                with st.form("register_form"):
                    new_username = st.text_input("Choose Username")
                    new_email = st.text_input("Email")
                    new_password = st.text_input("Choose Password", type="password")
                    confirm_password = st.text_input("Confirm Password", type="password")
                    
                    if st.form_submit_button("Register"):
                        if new_username and new_email and new_password and confirm_password:
                            if new_password == confirm_password:
                                result = simulator.db.create_user(new_username, new_password, new_email)
                                if result['success']:
                                    st.success("Registration successful! Please login.")
                                else:
                                    st.error(result['message'])
                            else:
                                st.error("Passwords do not match")
                        else:
                            st.error("Please fill in all fields")
        
        else:
            # Main application for logged-in users
            current_user = st.session_state.current_user
            
            # Sidebar
            with st.sidebar:
                st.header(f"👨‍💼 {current_user['username']}")
                
                # User stats
                st.write(f"**Cash:** ${current_user['cash']:,.2f}")
                st.write(f"**Total Trades:** {current_user['total_trades']}")
                st.write(f"**P&L:** ${current_user['total_profit_loss']:+,.2f}")
                
                if st.button("Logout"):
                    st.session_state.logged_in = False
                    st.session_state.current_user = None
                    st.rerun()
            
            # Refresh user data
            current_user = simulator.db.get_user_data(current_user['id'])
            if current_user:
                st.session_state.current_user = current_user
            
            # Portfolio overview
            portfolio_value = simulator.get_portfolio_value(current_user['id'])
            total_return = portfolio_value - st.session_state.game_settings['starting_cash']
            return_percentage = (total_return / st.session_state.game_settings['starting_cash']) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                card_class = "profit-card" if total_return >= 0 else "loss-card"
                st.markdown(f"""
                <div class="{card_class}">
                    <h3>💰 Portfolio Value</h3>
                    <h2>${portfolio_value:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="portfolio-card">
                    <h3>💵 Cash Available</h3>
                    <h2>${current_user['cash']:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                card_class = "profit-card" if total_return >= 0 else "loss-card"
                st.markdown(f"""
                <div class="{card_class}">
                    <h3>📈 Total Return</h3>
                    <h2>${total_return:,.2f}</h2>
                    <p>({return_percentage:+.2f}%)</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="portfolio-card">
                    <h3>🔄 Total Trades</h3>
                    <h2>{current_user['total_trades']}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            # Main tabs
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Research", "💰 Trade", "📈 Portfolio", "📋 History", "🏆 Leaderboard", "⚙️ Settings"])
            
            with tab1:
                st.subheader("📊 Research & Technical Analysis")
                
                # Research mode selector
                research_mode = st.selectbox(
                    "Research Mode",
                    ["Single Asset Analysis", "Compare Multiple Assets", "Market Overview", "🌍 African Markets"],
                    key="research_mode"
                )
                
                if research_mode == "Single Asset Analysis":
                    # Asset type selector
                    asset_type = st.selectbox(
                        "Select Asset Type",
                        ["All Assets", "Stocks & ETFs", "Cryptocurrencies", "🌍 African Markets"],
                        key="asset_type_filter"
                    )
                    
                    # Filter available assets based on selection
                    if asset_type == "Stocks & ETFs":
                        available_assets = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
                    elif asset_type == "Cryptocurrencies":
                        available_assets = [s for s in simulator.available_stocks if s.endswith('-USD')]
                    elif asset_type == "🌍 African Markets":
                        available_assets = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
                    else:
                        available_assets = simulator.available_stocks
                    
                    # For crypto, show by categories
                    if asset_type == "Cryptocurrencies":
                        st.write("### 🪙 Cryptocurrency Categories")
                        crypto_categories = simulator.get_crypto_categories()
                        
                        selected_category = st.selectbox(
                            "Select Category",
                            ["All Cryptocurrencies"] + list(crypto_categories.keys()),
                            key="crypto_category"
                        )
                        
                        if selected_category != "All Cryptocurrencies":
                            available_assets = crypto_categories[selected_category]
                    
                    # For African markets, show by country
                    elif asset_type == "🌍 African Markets":
                        st.write("### 🌍 African Markets by Country")
                        african_markets = simulator.get_african_markets()
                        
                        selected_market = st.selectbox(
                            "Select Market",
                            ["All African Markets"] + list(african_markets.keys()),
                            key="african_market"
                        )
                        
                        if selected_market != "All African Markets":
                            available_assets = african_markets[selected_market]
                    
                    # Asset selector for analysis
                    analysis_asset = st.selectbox(
                        "Select Asset for Analysis",
                        [''] + available_assets[:100],
                        key="analysis_asset"
                    )
                    
                    if analysis_asset:
                        # Time period selector
                        period_options = {
                            '1 Month': '1mo',
                            '3 Months': '3mo',
                            '6 Months': '6mo',
                            '1 Year': '1y',
                            '2 Years': '2y',
                            '5 Years': '5y'
                        }
                        
                        selected_period = st.selectbox(
                            "Time Period",
                            list(period_options.keys()),
                            index=1
                        )
                        
                        period = period_options[selected_period]
                        
                        # Get asset info
                        asset_data = simulator.get_stock_price(analysis_asset)
                        if asset_data:
                            # Display asset info
                            if asset_data.get('is_crypto'):
                                asset_display_name = analysis_asset.replace('-USD', '')
                                asset_type_icon = "🪙"
                            elif asset_data.get('is_african'):
                                asset_display_name = analysis_asset
                                asset_type_icon = "🌍"
                            else:
                                asset_display_name = analysis_asset
                                asset_type_icon = "📈"
                            
                            # Asset header with mock data indicator
                            asset_header = f"{asset_type_icon} {asset_data['name']} ({asset_display_name})"
                            if asset_data.get('is_mock'):
                                asset_header += " - Live Mock Data"
                            
                            st.markdown(f"""
                            <div class="metric-card">
                                <h2>{asset_header}</h2>
                                <p><strong>Sector:</strong> {asset_data['sector']}</p>
                                <p><strong>Industry:</strong> {asset_data['industry']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Current price metrics
                            col_price1, col_price2, col_price3, col_price4 = st.columns(4)
                            
                            with col_price1:
                                if asset_data.get('is_crypto') and asset_data['price'] < 1:
                                    price_display = f"{asset_data['currency']} {asset_data['price']:.6f}"
                                else:
                                    price_display = f"{asset_data['currency']} {asset_data['price']:.2f}"
                                st.metric("Current Price", price_display)
                            
                            with col_price2:
                                change_color = "normal" if asset_data['change'] >= 0 else "inverse"
                                st.metric(
                                    "24h Change", 
                                    f"{asset_data['currency']} {asset_data['change']:+.2f}",
                                    f"{asset_data['change_percent']:+.2f}%",
                                    delta_color=change_color
                                )
                            
                            with col_price3:
                                st.metric("Volume", f"{asset_data['volume']:,}")
                            
                            with col_price4:
                                if asset_data['market_cap'] > 0:
                                    if asset_data['market_cap'] > 1_000_000_000:
                                        cap_display = f"{asset_data['currency']} {asset_data['market_cap']/1_000_000_000:.1f}B"
                                    else:
                                        cap_display = f"{asset_data['currency']} {asset_data['market_cap']/1_000_000:.1f}M"
                                    st.metric("Market Cap", cap_display)
                                else:
                                    st.metric("Market Cap", "N/A")
                            
                            # Additional metrics
                            col_info1, col_info2, col_info3 = st.columns(3)
                            with col_info1:
                                st.metric("Day High", f"{asset_data['currency']} {asset_data['day_high']:.2f}")
                            with col_info2:
                                st.metric("Day Low", f"{asset_data['currency']} {asset_data['day_low']:.2f}")
                            with col_info3:
                                if asset_data.get('pe_ratio') and not asset_data.get('is_crypto'):
                                    st.metric("P/E Ratio", f"{asset_data['pe_ratio']:.2f}")
                                else:
                                    daily_change = ((asset_data['day_high'] - asset_data['day_low']) / asset_data['day_low']) * 100
                                    st.metric("Daily Range", f"{daily_change:.2f}%")
                            
                            # Comprehensive chart
                            st.markdown("""
                            <div class="chart-container">
                                <h3>📊 Technical Analysis Chart</h3>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            with st.spinner("Loading comprehensive chart..."):
                                comprehensive_chart = simulator.create_comprehensive_chart(analysis_asset, period)
                                if comprehensive_chart:
                                    st.plotly_chart(comprehensive_chart, use_container_width=True)
                                else:
                                    st.error("Unable to load chart data")
                            
                            # Quick trade section
                            st.write("### ⚡ Quick Trade")
                            quick_col1, quick_col2 = st.columns(2)
                            
                            with quick_col1:
                                buy_button_text = f"🛒 Buy {asset_display_name}"
                                if st.button(buy_button_text, key="research_buy"):
                                    st.session_state.quick_trade_asset = analysis_asset
                                    st.session_state.quick_trade_action = 'BUY'
                                    st.info(f"Go to Trade tab to buy {asset_display_name}")
                            
                            with quick_col2:
                                # Check if user owns this asset
                                portfolio = simulator.db.get_user_portfolio(current_user['id'])
                                owns_asset = any(p['symbol'] == analysis_asset for p in portfolio)
                                
                                sell_button_text = f"💰 Sell {asset_display_name}"
                                if owns_asset:
                                    if st.button(sell_button_text, key="research_sell"):
                                        st.session_state.quick_trade_asset = analysis_asset
                                        st.session_state.quick_trade_action = 'SELL'
                                        st.info(f"Go to Trade tab to sell {asset_display_name}")
                                else:
                                    st.button(sell_button_text, key="research_sell", disabled=True, help="You don't own this asset")
                        
                        else:
                            st.error("Unable to load asset data")
                
                elif research_mode == "Compare Multiple Assets":
                    st.write("### 📊 Asset Comparison")
                    
                    # Asset selector for comparison
                    comparison_assets = st.multiselect(
                        "Select Assets to Compare (max 5)",
                        simulator.available_stocks[:100],
                        max_selections=5,
                        key="comparison_assets"
                    )
                    
                    if comparison_assets:
                        # Time period for comparison
                        period_options = {
                            '1 Month': '1mo',
                            '3 Months': '3mo',
                            '6 Months': '6mo',
                            '1 Year': '1y',
                            '2 Years': '2y'
                        }
                        
                        comparison_period = st.selectbox(
                            "Time Period",
                            list(period_options.keys()),
                            index=1,
                            key="comparison_period"
                        )
                        
                        period = period_options[comparison_period]
                        
                        # Create comparison chart
                        st.markdown("""
                        <div class="chart-container">
                            <h3>📈 Normalized Performance Comparison</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.spinner("Loading comparison chart..."):
                            comparison_chart = simulator.create_comparison_chart(comparison_assets, period)
                            if comparison_chart:
                                st.plotly_chart(comparison_chart, use_container_width=True)
                            else:
                                st.error("Unable to load comparison chart")
                        
                        # Comparison table
                        st.write("### 📋 Asset Comparison Table")
                        comparison_data = []
                        
                        for asset in comparison_assets:
                            asset_data = simulator.get_stock_price(asset)
                            if asset_data:
                                if asset_data.get('is_crypto'):
                                    display_name = asset.replace('-USD', '')
                                    asset_type_icon = "🪙"
                                elif asset_data.get('is_african'):
                                    display_name = asset
                                    asset_type_icon = "🌍"
                                else:
                                    display_name = asset
                                    asset_type_icon = "📈"
                                
                                comparison_data.append({
                                    'Asset': f"{asset_type_icon} {display_name}",
                                    'Name': asset_data['name'][:30],
                                    'Price': f"{asset_data['currency']} {asset_data['price']:.2f}",
                                    'Change': f"{asset_data['change']:+.2f}",
                                    'Change %': f"{asset_data['change_percent']:+.2f}%",
                                    'Volume': f"{asset_data['volume']:,}",
                                    'Market Cap': f"{asset_data['currency']} {asset_data['market_cap']/1_000_000_000:.1f}B" if asset_data['market_cap'] > 1_000_000_000 else f"{asset_data['currency']} {asset_data['market_cap']/1_000_000:.1f}M" if asset_data['market_cap'] > 0 else "N/A"
                                })
                        
                        if comparison_data:
                            df = pd.DataFrame(comparison_data)
                            st.dataframe(df, use_container_width=True)
                
                elif research_mode == "Market Overview":
                    st.write("### 🌐 Market Overview")
                    
                    # Market indices
                    indices = ['SPY', 'QQQ', 'IWM', 'VTI']
                    crypto_major = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD']
                    african_major = ['NPN.JO', 'SAFCOM.NR', 'GTCO.LG', 'CIB.CA', 'MTNGH.AC']
                    
                    # Market indices overview
                    st.write("#### 📈 Market Indices")
                    indices_data = []
                    for index in indices:
                        data = simulator.get_stock_price(index)
                        if data:
                            indices_data.append({
                                'Index': index,
                                'Price': f"${data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%"
                            })
                    
                    if indices_data:
                        df_indices = pd.DataFrame(indices_data)
                        st.dataframe(df_indices, use_container_width=True)
                    
                    # Crypto overview
                    st.write("#### 🪙 Major Cryptocurrencies")
                    crypto_data = []
                    for crypto in crypto_major:
                        data = simulator.get_stock_price(crypto)
                        if data:
                            display_name = crypto.replace('-USD', '')
                            crypto_data.append({
                                'Crypto': f"🪙 {display_name}",
                                'Name': data['name'][:20],
                                'Price': f"${data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%",
                                'Volume': f"{data['volume']:,}"
                            })
                    
                    if crypto_data:
                        df_crypto = pd.DataFrame(crypto_data)
                        st.dataframe(df_crypto, use_container_width=True)
                    
                    # African markets overview
                    st.write("#### 🌍 African Markets Highlights")
                    african_data = []
                    for african in african_major:
                        data = simulator.get_stock_price(african)
                        if data:
                            country = simulator.get_african_country_from_symbol(african)
                            african_data.append({
                                'Stock': f"🌍 {african}",
                                'Company': data['name'][:25],
                                'Country': country,
                                'Price': f"{data['currency']} {data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%"
                            })
                    
                    if african_data:
                        df_african = pd.DataFrame(african_data)
                        st.dataframe(df_african, use_container_width=True)
                
                elif research_mode == "🌍 African Markets":
                    st.write("### 🌍 African Stock Exchanges")
                    
                    # African markets selector
                    african_markets = simulator.get_african_markets()
                    selected_african_market = st.selectbox(
                        "Select African Market",
                        list(african_markets.keys()),
                        key="selected_african_market"
                    )
                    
                    if selected_african_market:
                        st.write(f"#### {selected_african_market}")
                        
                        market_stocks = african_markets[selected_african_market]
                        market_data = []
                        
                        with st.spinner(f"Loading {selected_african_market} data..."):
                            for stock in market_stocks[:20]:  # Limit to first 20 for performance
                                data = simulator.get_stock_price(stock)
                                if data:
                                    market_data.append({
                                        'Symbol': stock,
                                        'Company': data['name'][:30],
                                        'Price': f"{data['currency']} {data['price']:.2f}",
                                        'Change': f"{data['change']:+.2f}",
                                        'Change %': f"{data['change_percent']:+.2f}%",
                                        'Volume': f"{data['volume']:,}",
                                        'Sector': data.get('sector', 'N/A')[:20]
                                    })
                        
                        if market_data:
                            df_market = pd.DataFrame(market_data)
                            st.dataframe(df_market, use_container_width=True)
                            
                            # Market stats
                            positive_count = len([d for d in market_data if '+' in d['Change']])
                            total_count = len(market_data)
                            
                            col_stat1, col_stat2, col_stat3 = st.columns(3)
                            with col_stat1:
                                st.metric("Stocks Tracked", total_count)
                            with col_stat2:
                                st.metric("Gainers", positive_count)
                            with col_stat3:
                                st.metric("Losers", total_count - positive_count)
                        else:
                            st.info("Loading market data...")
            
            with tab2:
                st.subheader("💰 Trade Stocks & Crypto")
                
                # Quick trade setup if coming from research
                if hasattr(st.session_state, 'quick_trade_asset') and st.session_state.quick_trade_asset:
                    st.info(f"Quick Trade: {st.session_state.quick_trade_action} {st.session_state.quick_trade_asset}")
                
                # Trading interface
                trade_col1, trade_col2 = st.columns([1, 1])
                
                with trade_col1:
                    st.write("### 🛒 Buy/Sell Assets")
                    
                    # Asset selection
                    trade_asset_type = st.selectbox(
                        "Asset Type",
                        ["All Assets", "Stocks & ETFs", "Cryptocurrencies", "🌍 African Markets"],
                        key="trade_asset_type"
                    )
                    
                    # Filter assets based on type
                    if trade_asset_type == "Stocks & ETFs":
                        trade_available_assets = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
                    elif trade_asset_type == "Cryptocurrencies":
                        trade_available_assets = [s for s in simulator.available_stocks if s.endswith('-USD')]
                    elif trade_asset_type == "🌍 African Markets":
                        trade_available_assets = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
                    else:
                        trade_available_assets = simulator.available_stocks
                    
                    # Pre-select asset if coming from quick trade
                    default_asset = ""
                    if hasattr(st.session_state, 'quick_trade_asset') and st.session_state.quick_trade_asset:
                        if st.session_state.quick_trade_asset in trade_available_assets:
                            default_asset = st.session_state.quick_trade_asset
                    
                    selected_asset = st.selectbox(
                        "Select Asset",
                        [''] + trade_available_assets[:100],
                        index=trade_available_assets.index(default_asset) + 1 if default_asset else 0,
                        key="selected_trade_asset"
                    )
                    
                    if selected_asset:
                        # Get current price
                        asset_data = simulator.get_stock_price(selected_asset)
                        
                        if asset_data:
                            # Display current asset info
                            if asset_data.get('is_crypto'):
                                display_name = selected_asset.replace('-USD', '')
                                asset_type_icon = "🪙"
                            elif asset_data.get('is_african'):
                                display_name = selected_asset
                                asset_type_icon = "🌍"
                            else:
                                display_name = selected_asset
                                asset_type_icon = "📈"
                            
                            st.markdown(f"""
                            <div class="metric-card">
                                <h3>{asset_type_icon} {asset_data['name']} ({display_name})</h3>
                                <p><strong>Current Price:</strong> {asset_data['currency']} {asset_data['price']:.2f}</p>
                                <p><strong>24h Change:</strong> <span class="{'positive' if asset_data['change'] >= 0 else 'negative'}">{asset_data['change']:+.2f} ({asset_data['change_percent']:+.2f}%)</span></p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Trade form
                            with st.form("trade_form"):
                                # Pre-select action if coming from quick trade
                                default_action_index = 0
                                if hasattr(st.session_state, 'quick_trade_action') and st.session_state.quick_trade_action:
                                    if st.session_state.quick_trade_action == 'BUY':
                                        default_action_index = 0
                                    elif st.session_state.quick_trade_action == 'SELL':
                                        default_action_index = 1
                                
                                trade_action = st.selectbox(
                                    "Action",
                                    ["BUY", "SELL"],
                                    index=default_action_index
                                )
                                
                                shares = st.number_input(
                                    "Number of Shares/Units",
                                    min_value=1,
                                    value=1,
                                    step=1
                                )
                                
                                # Calculate trade cost
                                commission = st.session_state.game_settings['commission']
                                
                                if trade_action == "BUY":
                                    total_cost = (asset_data['price'] * shares) + commission
                                    st.write(f"**Total Cost:** ${total_cost:,.2f} (including ${commission:.2f} commission)")
                                    
                                    # Check if user has enough cash
                                    if total_cost > current_user['cash']:
                                        st.error(f"Insufficient funds! You need ${total_cost:,.2f} but only have ${current_user['cash']:,.2f}")
                                        can_trade = False
                                    else:
                                        can_trade = True
                                
                                else:  # SELL
                                    portfolio = simulator.db.get_user_portfolio(current_user['id'])
                                    owned_position = next((p for p in portfolio if p['symbol'] == selected_asset), None)
                                    
                                    if owned_position and owned_position['shares'] >= shares:
                                        total_proceeds = (asset_data['price'] * shares) - commission
                                        profit_loss = (asset_data['price'] - owned_position['avg_price']) * shares - commission
                                        
                                        st.write(f"**Owned Shares:** {owned_position['shares']}")
                                        st.write(f"**Average Price:** ${owned_position['avg_price']:.2f}")
                                        st.write(f"**Total Proceeds:** ${total_proceeds:,.2f} (after ${commission:.2f} commission)")
                                        
                                        profit_color = "positive" if profit_loss >= 0 else "negative"
                                        st.markdown(f"**Estimated P&L:** <span class='{profit_color}'>${profit_loss:+,.2f}</span>", unsafe_allow_html=True)
                                        
                                        can_trade = True
                                    else:
                                        if owned_position:
                                            st.error(f"Insufficient shares! You own {owned_position['shares']} shares but trying to sell {shares}")
                                        else:
                                            st.error("You don't own this asset")
                                        can_trade = False
                                
                                # Submit trade
                                if st.form_submit_button(f"Execute {trade_action}", disabled=not can_trade):
                                    if can_trade:
                                        result = simulator.db.execute_trade(
                                            current_user['id'],
                                            selected_asset,
                                            trade_action,
                                            shares,
                                            asset_data['price'],
                                            asset_data['name'],
                                            asset_data['currency']
                                        )
                                        
                                        if result['success']:
                                            st.success(result['message'])
                                            if trade_action == "SELL" and result.get('profit_loss'):
                                                profit_loss = result['profit_loss']
                                                if profit_loss >= 0:
                                                    st.success(f"Profit: ${profit_loss:+,.2f}")
                                                else:
                                                    st.error(f"Loss: ${profit_loss:+,.2f}")
                                            
                                            # Clear quick trade session state
                                            if hasattr(st.session_state, 'quick_trade_asset'):
                                                del st.session_state.quick_trade_asset
                                            if hasattr(st.session_state, 'quick_trade_action'):
                                                del st.session_state.quick_trade_action
                                            
                                            st.rerun()
                                        else:
                                            st.error(result['message'])
                        else:
                            st.error("Unable to load asset data")
                
                with trade_col2:
                    st.write("### 📊 Market Movers")
                    
                    # Show some trending assets
                    trending_assets = ['AAPL', 'TSLA', 'BTC-USD', 'ETH-USD', 'MTNGH.AC', 'SAFCOM.NR']
                    
                    for asset in trending_assets:
                        data = simulator.get_stock_price(asset)
                        if data:
                            if data.get('is_crypto'):
                                icon = "🪙"
                                display_name = asset.replace('-USD', '')
                            elif data.get('is_african'):
                                icon = "🌍"
                                display_name = asset
                            else:
                                icon = "📈"
                                display_name = asset
                            
                            change_class = "positive" if data['change'] >= 0 else "negative"
                            
                            st.markdown(f"""
                            <div class="metric-card">
                                <p><strong>{icon} {display_name}</strong></p>
                                <p>{data['currency']} {data['price']:.2f} <span class="{change_class}">({data['change_percent']:+.2f}%)</span></p>
                            </div>
                            """, unsafe_allow_html=True)
            
            with tab3:
                st.subheader("📈 Portfolio Management")
                
                # Portfolio summary
                portfolio_summary = simulator.get_portfolio_summary(current_user['id'])
                
                if portfolio_summary:
                    col_port1, col_port2, col_port3, col_port4 = st.columns(4)
                    
                    with col_port1:
                        st.metric("Cash", f"${portfolio_summary['cash']:,.2f}")
                    
                    with col_port2:
                        st.metric("Invested", f"${portfolio_summary['total_invested']:,.2f}")
                    
                    with col_port3:
                        st.metric("Current Value", f"${portfolio_summary['total_current_value']:,.2f}")
                    
                    with col_port4:
                        unrealized_pl = portfolio_summary['total_unrealized_pl']
                        color = "normal" if unrealized_pl >= 0 else "inverse"
                        st.metric("Unrealized P&L", f"${unrealized_pl:+,.2f}", delta_color=color)
                    
                    # Portfolio pie chart
                    st.write("### 🥧 Portfolio Allocation")
                    pie_chart = simulator.create_portfolio_pie_chart(current_user['id'])
                    if pie_chart:
                        st.plotly_chart(pie_chart, use_container_width=True)
                    else:
                        st.info("No portfolio positions to display")
                
                # Holdings table
                st.write("### 📋 Current Holdings")
                portfolio = simulator.db.get_user_portfolio(current_user['id'])
                
                if portfolio:
                    holdings_data = []
                    
                    for position in portfolio:
                        current_data = simulator.get_stock_price(position['symbol'])
                        if current_data:
                            current_value = current_data['price'] * position['shares']
                            invested_value = position['avg_price'] * position['shares']
                            unrealized_pl = current_value - invested_value
                            unrealized_pl_percent = (unrealized_pl / invested_value) * 100 if invested_value > 0 else 0
                            
                            # Asset type icon
                            if current_data.get('is_crypto'):
                                icon = "🪙"
                            elif current_data.get('is_african'):
                                icon = "🌍"
                            else:
                                icon = "📈"
                            
                            holdings_data.append({
                                'Asset': f"{icon} {position['symbol']}",
                                'Company': position['name'][:25],
                                'Shares': position['shares'],
                                'Avg Price': f"${position['avg_price']:.2f}",
                                'Current Price': f"${current_data['price']:.2f}",
                                'Market Value': f"${current_value:,.2f}",
                                'Unrealized P&L': f"${unrealized_pl:+,.2f}",
                                'P&L %': f"{unrealized_pl_percent:+.2f}%"
                            })
                    
                    if holdings_data:
                        df_holdings = pd.DataFrame(holdings_data)
                        st.dataframe(df_holdings, use_container_width=True)
                    else:
                        st.info("No current holdings")
                else:
                    st.info("Your portfolio is empty. Start trading to build your portfolio!")
            
            with tab4:
                st.subheader("📋 Trade History")
                
                # Get trade history
                trades = simulator.db.get_user_trades(current_user['id'])
                
                if trades:
                    # Trade statistics
                    total_trades = len(trades)
                    buy_trades = len([t for t in trades if t['type'] == 'BUY'])
                    sell_trades = len([t for t in trades if t['type'] == 'SELL'])
                    total_realized_pl = sum([t['profit_loss'] for t in trades if t['profit_loss'] != 0])
                    
                    col_hist1, col_hist2, col_hist3, col_hist4 = st.columns(4)
                    
                    with col_hist1:
                        st.metric("Total Trades", total_trades)
                    
                    with col_hist2:
                        st.metric("Buy Orders", buy_trades)
                    
                    with col_hist3:
                        st.metric("Sell Orders", sell_trades)
                    
                    with col_hist4:
                        color = "normal" if total_realized_pl >= 0 else "inverse"
                        st.metric("Realized P&L", f"${total_realized_pl:+,.2f}", delta_color=color)
                    
                    # Trades table
                    st.write("### 📊 Recent Trades")
                    
                    trades_data = []
                    for trade in trades[:50]:  # Show last 50 trades
                        # Asset type icon
                        if trade['symbol'].endswith('-USD'):
                            icon = "🪙"
                        elif simulator.is_african_stock(trade['symbol']):
                            icon = "🌍"
                        else:
                            icon = "📈"
                        
                        trades_data.append({
                            'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                            'Type': '🛒 BUY' if trade['type'] == 'BUY' else '💰 SELL',
                            'Asset': f"{icon} {trade['symbol']}",
                            'Company': trade['name'][:20],
                            'Shares': trade['shares'],
                            'Price': f"${trade['price']:.2f}",
                            'Total': f"${trade['total_cost']:,.2f}",
                            'Commission': f"${trade['commission']:.2f}",
                            'P&L': f"${trade['profit_loss']:+,.2f}" if trade['profit_loss'] != 0 else "-"
                        })
                    
                    if trades_data:
                        df_trades = pd.DataFrame(trades_data)
                        st.dataframe(df_trades, use_container_width=True)
                else:
                    st.info("No trades yet. Start trading to see your history!")
            
            with tab5:
                st.subheader("🏆 Leaderboard")
                
                # Get leaderboard data
                leaderboard = simulator.db.get_leaderboard()
                
                if leaderboard:
                    st.write("### 🥇 Top Traders")
                    
                    leaderboard_data = []
                    for i, player in enumerate(leaderboard[:20]):  # Top 20 players
                        # Determine rank emoji
                        if player['rank'] == 1:
                            rank_display = "🥇"
                        elif player['rank'] == 2:
                            rank_display = "🥈"
                        elif player['rank'] == 3:
                            rank_display = "🥉"
                        else:
                            rank_display = f"#{player['rank']}"
                        
                        # Highlight current user
                        username_display = player['username']
                        if player['user_id'] == current_user['id']:
                            username_display = f"👤 {username_display}"
                        
                        leaderboard_data.append({
                            'Rank': rank_display,
                            'Trader': username_display,
                            'Portfolio Value': f"${player['portfolio_value']:,.2f}",
                            'Cash': f"${player['cash']:,.2f}",
                            'Total Trades': player['total_trades'],
                            'P&L': f"${player['total_profit_loss']:+,.2f}"
                        })
                    
                    df_leaderboard = pd.DataFrame(leaderboard_data)
                    st.dataframe(df_leaderboard, use_container_width=True)
                    
                    # Current user stats
                    current_user_rank = next((p['rank'] for p in leaderboard if p['user_id'] == current_user['id']), None)
                    if current_user_rank:
                        st.info(f"Your current rank: #{current_user_rank} out of {len(leaderboard)} traders")
                else:
                    st.info("No leaderboard data available")
            
            with tab6:
                st.subheader("⚙️ Game Settings & Info")
                
                # Game settings display
                settings = st.session_state.game_settings
                
                st.write("### 🎮 Game Configuration")
                
                col_set1, col_set2, col_set3 = st.columns(3)
                
                with col_set1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>💰 Starting Cash</h4>
                        <p>${settings['starting_cash']:,.2f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_set2:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>💸 Commission</h4>
                        <p>${settings['commission']:.2f} per trade</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_set3:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>⏰ Game Duration</h4>
                        <p>{settings['game_duration_days']} days</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # User account info
                st.write("### 👤 Account Information")
                
                col_acc1, col_acc2 = st.columns(2)
                
                with col_acc1:
                    st.write(f"**Username:** {current_user['username']}")
                    st.write(f"**Email:** {current_user['email']}")
                    st.write(f"**Member Since:** {current_user['created_at']}")
                
                with col_acc2:
                    st.write(f"**Total Trades:** {current_user['total_trades']}")
                    st.write(f"**Best Trade:** ${current_user['best_trade']:+,.2f}")
                    st.write(f"**Worst Trade:** ${current_user['worst_trade']:+,.2f}")
                
                # About section
                st.write("### ℹ️ About Leo's Trader")
                
                st.markdown("""
                **Leo's Trader** is a comprehensive trading simulation game that allows you to:
                
                - 📈 **Trade Real Stocks**: Practice with live market data from major US exchanges
                - 🪙 **Cryptocurrency Trading**: Trade major cryptocurrencies with real-time prices
                - 🌍 **African Markets**: Explore opportunities in Ghana, Kenya, Nigeria, South Africa, and Egypt
                - 📊 **Technical Analysis**: Use advanced charting tools and indicators
                - 🏆 **Compete**: Join the leaderboard and compete with other traders
                - 📱 **Learn**: Risk-free environment to learn trading strategies
                
                **Features:**
                - Real-time market data for stocks and crypto
                - Live mock data for African stock exchanges
                - Portfolio management and tracking
                - Comprehensive trade history
                - Technical analysis charts
                - Multi-currency support
                
                **🇬🇭 Proudly developed in Ghana** to promote financial literacy and trading education across Africa and beyond.
                """)
                
                # Reset account section
                st.write("### 🔄 Reset Account")
                st.warning("⚠️ This will reset your account to starting conditions. This action cannot be undone!")
                
                if st.button("🔄 Reset My Account", key="reset_account"):
                    st.error("Account reset feature will be implemented in a future update.")
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please refresh the page and try again.")

if __name__ == "__main__":
    main()
