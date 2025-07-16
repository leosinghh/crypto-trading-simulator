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
                original_currency TEXT DEFAULT 'USD',
                original_price REAL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Add new columns to existing trades table if they don't exist
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN original_currency TEXT DEFAULT "USD"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN original_price REAL')
        except sqlite3.OperationalError:
            pass
        
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
                VALUES (100000.00, 0.00, 30)
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
                       profit_loss, stock_name, timestamp, original_currency, original_price
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
                    'timestamp': datetime.strptime(row[9], '%Y-%m-%d %H:%M:%S'),
                    'original_currency': row[10] or 'USD',
                    'original_price': row[11] or row[4]
                })
            
            conn.close()
            return trades
        except Exception as e:
            st.error(f"Error getting trades: {str(e)}")
            return []
    
    def execute_trade(self, user_id: str, symbol: str, action: str, shares: int, price: float, stock_name: str, currency: str = 'USD', original_price: float = None) -> Dict:
        """Execute a trade and update database with currency conversion"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT commission FROM game_settings ORDER BY id DESC LIMIT 1')
            commission = cursor.fetchone()[0]
            
            cursor.execute('SELECT cash FROM users WHERE id = ?', (user_id,))
            current_cash = cursor.fetchone()[0]
            
            # Exchange rates
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
            
            if original_price is None:
                original_price = price
            
            total_cost_usd = price_usd * shares
            
            if action.upper() == 'BUY':
                if current_cash < total_cost_usd:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient funds'}
                
                new_cash = current_cash - total_cost_usd
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
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
                
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, stock_name, original_currency, original_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_cost_usd, 0.00, stock_name, currency, original_price))
                
                profit_loss = 0
                
            elif action.upper() == 'SELL':
                cursor.execute('''
                    SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?
                ''', (user_id, symbol))
                
                existing = cursor.fetchone()
                if not existing or existing[0] < shares:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient shares'}
                
                owned_shares, avg_price_usd = existing
                
                profit_loss = (price_usd - avg_price_usd) * shares
                
                total_proceeds_usd = price_usd * shares
                new_cash = current_cash + total_proceeds_usd
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
                new_shares = owned_shares - shares
                if new_shares > 0:
                    cursor.execute('''
                        UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?
                    ''', (new_shares, user_id, symbol))
                else:
                    cursor.execute('''
                        DELETE FROM portfolio WHERE user_id = ? AND symbol = ?
                    ''', (user_id, symbol))
                
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, profit_loss, stock_name, original_currency, original_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_proceeds_usd, 0.00, profit_loss, stock_name, currency, original_price))
                
                cursor.execute('''
                    UPDATE users SET total_profit_loss = total_profit_loss + ?,
                                   best_trade = CASE WHEN ? > best_trade THEN ? ELSE best_trade END,
                                   worst_trade = CASE WHEN ? < worst_trade THEN ? ELSE worst_trade END
                    WHERE id = ?
                ''', (profit_loss, profit_loss, profit_loss, profit_loss, profit_loss, user_id))
            
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
                total_value = row[2] + row[5]
                leaderboard.append({
                    'user_id': row[0],
                    'username': row[1],
                    'cash': row[2],
                    'total_trades': row[3],
                    'total_profit_loss': row[4],
                    'portfolio_value': total_value,
                    'rank': 0
                })
            
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
            return {'starting_cash': 100000, 'commission': 0.00, 'game_duration_days': 30}
        except Exception as e:
            st.error(f"Error getting settings: {str(e)}")
            return {'starting_cash': 100000, 'commission': 0.00, 'game_duration_days': 30}

# Configure Streamlit page
st.set_page_config(
    page_title="Leo's Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Professional Dark Theme CSS (Investopedia Style)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Dark Theme with Green Accents */
    .stApp {
        background-color: #0f1419;
        color: #ffffff;
    }
    
    .main .block-container {
        background-color: #0f1419;
        color: #ffffff;
        padding: 0;
        max-width: 100%;
    }
    
    /* Header Navigation */
    .header-nav {
        background: linear-gradient(135deg, #004B23 0%, #006400 100%);
        padding: 1rem 2rem;
        border-bottom: 1px solid #38B000;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0;
        box-shadow: 0 2px 10px rgba(0,75,35,0.3);
    }
    
    .logo {
        font-size: 1.5rem;
        font-weight: 700;
        color: #ffffff;
        font-family: 'Inter', sans-serif;
        text-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    
    .nav-buttons {
        display: flex;
        gap: 0.5rem;
    }
    
    .nav-button {
        background-color: transparent;
        color: #ffffff;
        border: 1px solid #38B000;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s;
        text-decoration: none;
        font-size: 0.9rem;
    }
    
    .nav-button:hover {
        background: linear-gradient(135deg, #38B000 0%, #70E000 100%);
        color: #000000;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(56,176,0,0.3);
    }
    
    .nav-button.active {
        background: linear-gradient(135deg, #70E000 0%, #9EF01A 100%);
        color: #000000;
        border-color: #70E000;
        box-shadow: 0 2px 8px rgba(112,224,0,0.3);
    }
    
    /* Main Content Layout */
    .main-content {
        background-color: #0f1419;
        min-height: 100vh;
        padding: 2rem;
    }
    
    /* Overview Cards */
    .overview-section {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 2rem;
        margin-bottom: 2rem;
    }
    
    .overview-card {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .overview-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(56,176,0,0.1) 0%, transparent 50%);
        pointer-events: none;
    }
    
    .overview-title {
        color: #70E000;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }
    
    .metric-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 1rem;
    }
    
    .metric-label {
        color: #9EF01A;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .metric-value {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
    }
    
    .metric-value.large {
        font-size: 2rem;
    }
    
    .metric-change {
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .metric-change.positive {
        color: #70E000;
    }
    
    .metric-change.negative {
        color: #ff4757;
    }
    
    .performance-chart {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1.5rem;
        height: 400px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .performance-chart::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(56,176,0,0.1) 0%, transparent 50%);
        pointer-events: none;
    }
    
    /* Holdings Section */
    .holdings-section {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1.5rem;
        margin-top: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .holdings-section::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(56,176,0,0.1) 0%, transparent 50%);
        pointer-events: none;
    }
    
    .holdings-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .holdings-title {
        color: #70E000;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .holdings-tabs {
        display: flex;
        gap: 1rem;
    }
    
    .holdings-tab {
        padding: 0.5rem 1rem;
        border: 1px solid #38B000;
        border-radius: 6px;
        background-color: transparent;
        color: #70E000;
        cursor: pointer;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .holdings-tab.active {
        background: linear-gradient(135deg, #70E000 0%, #9EF01A 100%);
        color: #000000;
        border-color: #70E000;
    }
    
    .holdings-tab:hover {
        background: linear-gradient(135deg, #38B000 0%, #70E000 100%);
        color: #000000;
    }
    
    /* Market Status */
    .market-status {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .market-status.open {
        border-color: #70E000;
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
    }
    
    .market-status.closed {
        border-color: #ff4757;
        background: linear-gradient(135deg, #2d1a1a 0%, #4a2d2d 100%);
    }
    
    .market-status-text {
        color: #70E000;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .market-status-text.open {
        color: #70E000;
    }
    
    .market-status-text.closed {
        color: #ff4757;
    }
    
    /* Data Tables */
    .stDataFrame {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .stDataFrame table {
        background-color: transparent;
        color: #ffffff;
    }
    
    .stDataFrame th {
        background: linear-gradient(135deg, #004B23 0%, #006400 100%);
        color: #ffffff;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
    }
    
    .stDataFrame td {
        background-color: transparent;
        color: #ffffff;
        border-bottom: 1px solid #38B000;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #006400 0%, #38B000 100%);
        color: #ffffff;
        border: 1px solid #38B000;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 15px rgba(56,176,0,0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #38B000 0%, #70E000 100%);
        border-color: #70E000;
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(112,224,0,0.4);
    }
    
    /* Form Elements */
    .stSelectbox > div > div {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    
    .stTextInput > div > div > input {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #70E000;
        box-shadow: 0 0 0 3px rgba(112,224,0,0.2);
    }
    
    .stNumberInput > div > div > input {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    
    .stNumberInput > div > div > input:focus {
        border-color: #70E000;
        box-shadow: 0 0 0 3px rgba(112,224,0,0.2);
    }
    
    /* Trade Form */
    .trade-form {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .trade-form::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(56,176,0,0.1) 0%, transparent 50%);
        pointer-events: none;
    }
    
    .trade-form-title {
        color: #70E000;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }
    
    /* Enhanced Login Container */
    .login-container {
        background: linear-gradient(135deg, #004B23 0%, #006400 25%, #38B000 50%, #70E000 75%, #9EF01A 100%);
        border-radius: 20px;
        padding: 3rem;
        max-width: 500px;
        margin: 3rem auto;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        position: relative;
        overflow: hidden;
    }
    
    .login-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: -50%;
        width: 200%;
        height: 100%;
        background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
        animation: shimmer 3s infinite;
    }
    
    @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .login-title {
        color: #ffffff;
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        background: linear-gradient(135deg, #ffffff, #f0f0f0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .login-subtitle {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    .login-form-container {
        background: rgba(255,255,255,0.1);
        border-radius: 15px;
        padding: 2rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .login-form-container .stTextInput > div > div > input {
        background: rgba(255,255,255,0.2);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 10px;
        color: #ffffff;
        font-size: 1rem;
        padding: 0.75rem 1rem;
        backdrop-filter: blur(5px);
    }
    
    .login-form-container .stTextInput > div > div > input::placeholder {
        color: rgba(255,255,255,0.7);
    }
    
    .login-form-container .stTextInput > div > div > input:focus {
        border-color: rgba(255,255,255,0.5);
        box-shadow: 0 0 0 3px rgba(255,255,255,0.1);
    }
    
    .login-form-container .stButton > button {
        background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%);
        color: #004B23;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        width: 100%;
        margin-top: 1rem;
    }
    
    .login-form-container .stButton > button:hover {
        background: linear-gradient(135deg, #f0f0f0 0%, #e0e0e0 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    
    /* Ghana Pride in Login */
    .login-ghana-pride {
        background: rgba(255,255,255,0.1);
        border-radius: 15px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 2rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .login-ghana-pride h3 {
        color: #ffd700;
        font-size: 1.3rem;
        margin-bottom: 0.5rem;
        font-weight: 600;
    }
    
    .login-ghana-pride p {
        color: rgba(255,255,255,0.9);
        margin: 0;
        font-size: 1rem;
    }
    
    /* Tab styling for login */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 0.5rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(5px);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: rgba(255,255,255,0.8);
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        transition: all 0.3s ease;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(255,255,255,0.2);
        color: #ffffff;
        font-weight: 700;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.15);
        color: #ffffff;
    }
    
    /* Ghana Pride */
    .ghana-pride {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    
    .ghana-pride h3 {
        color: #ffd700;
        margin-bottom: 0.5rem;
    }
    
    .ghana-pride p {
        color: #70E000;
        margin: 0;
    }
    
    /* Success/Error Messages */
    .stSuccess {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #70E000;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 10px rgba(112,224,0,0.2);
    }
    
    .stError {
        background: linear-gradient(135deg, #2d1a1a 0%, #4a2d2d 100%);
        border: 1px solid #ff4757;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 10px rgba(255,71,87,0.2);
    }
    
    .stInfo {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 10px rgba(56,176,0,0.2);
    }
    
    .stWarning {
        background: linear-gradient(135deg, #2d2a1a 0%, #4a472d 100%);
        border: 1px solid #ffd700;
        border-radius: 8px;
        color: #ffffff;
        box-shadow: 0 2px 10px rgba(255,215,0,0.2);
    }
    
    /* Charts */
    .chart-container {
        background: linear-gradient(135deg, #1a2f1a 0%, #2d4a2d 100%);
        border: 1px solid #38B000;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .chart-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(56,176,0,0.1) 0%, transparent 50%);
        pointer-events: none;
    }
    
    .chart-title {
        color: #70E000;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .header-nav {
            flex-direction: column;
            gap: 1rem;
        }
        
        .nav-buttons {
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .overview-section {
            grid-template-columns: 1fr;
        }
        
        .main-content {
            padding: 1rem;
        }
        
        .login-container {
            margin: 1rem;
            padding: 2rem;
        }
        
        .login-title {
            font-size: 2rem;
        }
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
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'Portfolio'
        
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
        """Get current fallback exchange rates"""
        return {
            'GHS': 12.80,
            'KES': 158.0,
            'NGN': 1600.0,
            'ZAR': 18.75,
            'EGP': 50.5,
            'USD': 1.0
        }
    
    def update_exchange_rates(self):
        """Update exchange rates with improved error handling"""
        current_time = datetime.now()
        
        if (current_time - st.session_state.exchange_rates_last_update).total_seconds() < 1800:
            return
        
        st.session_state.exchange_rates = self.get_fallback_exchange_rates()
        
        try:
            apis_to_try = [
                "https://api.exchangerate-api.com/v4/latest/USD",
                "https://api.fxratesapi.com/latest?base=USD",
                "https://open.er-api.com/v6/latest/USD"
            ]
            
            for api_url in apis_to_try:
                try:
                    response = requests.get(api_url, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        rates = data.get('rates', {})
                        
                        if rates:
                            st.session_state.exchange_rates.update({
                                'USD': 1.0,
                                'GHS': rates.get('GHS', st.session_state.exchange_rates['GHS']),
                                'KES': rates.get('KES', st.session_state.exchange_rates['KES']),
                                'NGN': rates.get('NGN', st.session_state.exchange_rates['NGN']),
                                'ZAR': rates.get('ZAR', st.session_state.exchange_rates['ZAR']),
                                'EGP': rates.get('EGP', st.session_state.exchange_rates['EGP'])
                            })
                            st.session_state.exchange_rates_last_update = current_time
                            st.session_state.exchange_rates_source = f"Live API: {api_url.split('//')[1].split('/')[0]}"
                            break
                        
                except Exception:
                    continue
            
            if 'exchange_rates_source' not in st.session_state:
                st.session_state.exchange_rates_source = "Fallback rates"
                
        except Exception as e:
            st.session_state.exchange_rates_source = f"Fallback (API Error: {str(e)[:50]})"
            
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
            return f"{symbol}{amount:,.0f}"
        else:
            return f"{symbol}{amount:,.2f}"
    
    def initialize_all_mock_data(self):
        """Initialize mock data for all African Stock Exchanges"""
        self.update_exchange_rates()
        
        # Base prices in local currencies
        ghana_stocks = {
            'GOIL.AC': {'base_price': 25.50, 'volatility': 0.02, 'trend': 0.001},
            'ECOBANK.AC': {'base_price': 74.25, 'volatility': 0.025, 'trend': 0.0005},
            'CAL.AC': {'base_price': 10.88, 'volatility': 0.03, 'trend': -0.001},
            'MTNGH.AC': {'base_price': 15.36, 'volatility': 0.02, 'trend': 0.002},
            'GWEB.AC': {'base_price': 5.76, 'volatility': 0.04, 'trend': 0.001},
            'SOGEGH.AC': {'base_price': 23.68, 'volatility': 0.02, 'trend': 0.0005},
            'AYRTN.AC': {'base_price': 9.60, 'volatility': 0.03, 'trend': -0.0005},
            'UNIL.AC': {'base_price': 236.80, 'volatility': 0.015, 'trend': 0.001},
            'CMLT.AC': {'base_price': 12.16, 'volatility': 0.035, 'trend': 0.002},
            'RBGH.AC': {'base_price': 8.32, 'volatility': 0.025, 'trend': 0.0005},
            'BOPP.AC': {'base_price': 30.72, 'volatility': 0.03, 'trend': 0.001},
            'TOTAL.AC': {'base_price': 48.64, 'volatility': 0.02, 'trend': 0.0005},
            'GGBL.AC': {'base_price': 22.40, 'volatility': 0.025, 'trend': 0.001},
            'SCBGH.AC': {'base_price': 194.56, 'volatility': 0.02, 'trend': 0.0005},
            'DIGP.AC': {'base_price': 3.20, 'volatility': 0.05, 'trend': -0.001},
            'CLYD.AC': {'base_price': 4.48, 'volatility': 0.04, 'trend': 0.002},
            'AADS.AC': {'base_price': 7.04, 'volatility': 0.035, 'trend': 0.001},
            'CAPL.AC': {'base_price': 5.76, 'volatility': 0.03, 'trend': 0.0005},
            'NICO.AC': {'base_price': 12.16, 'volatility': 0.025, 'trend': 0.001},
            'HORDS.AC': {'base_price': 1.92, 'volatility': 0.06, 'trend': 0.003},
            'TRANSOL.AC': {'base_price': 3.20, 'volatility': 0.05, 'trend': 0.002},
            'PRODUCE.AC': {'base_price': 4.48, 'volatility': 0.04, 'trend': 0.001},
            'PIONEER.AC': {'base_price': 10.88, 'volatility': 0.03, 'trend': 0.0015}
        }
        
        kenya_stocks = {
            'KCB.NR': {'base_price': 7189.00, 'volatility': 0.025, 'trend': 0.001},
            'EQTY.NR': {'base_price': 8334.50, 'volatility': 0.03, 'trend': 0.002},
            'SCBK.NR': {'base_price': 25596.00, 'volatility': 0.02, 'trend': 0.0005},
            'ABSA.NR': {'base_price': 2030.30, 'volatility': 0.025, 'trend': 0.001},
            'DTBK.NR': {'base_price': 13035.00, 'volatility': 0.03, 'trend': 0.0015},
            'BAT.NR': {'base_price': 76630.00, 'volatility': 0.02, 'trend': 0.001},
            'EABL.NR': {'base_price': 30810.00, 'volatility': 0.025, 'trend': 0.0005},
            'SAFCOM.NR': {'base_price': 4503.00, 'volatility': 0.02, 'trend': 0.002},
            'BRITAM.NR': {'base_price': 1019.10, 'volatility': 0.035, 'trend': 0.001},
            'JUBILEE.NR': {'base_price': 38710.00, 'volatility': 0.03, 'trend': 0.0015},
            'LIBERTY.NR': {'base_price': 1382.50, 'volatility': 0.04, 'trend': 0.002},
            'COOP.NR': {'base_price': 2243.60, 'volatility': 0.025, 'trend': 0.001},
            'UNGA.NR': {'base_price': 6083.00, 'volatility': 0.035, 'trend': 0.0005},
            'KAKUZI.NR': {'base_price': 67150.00, 'volatility': 0.04, 'trend': 0.002},
            'SASINI.NR': {'base_price': 1975.00, 'volatility': 0.05, 'trend': 0.001},
            'KAPCHORUA.NR': {'base_price': 22910.00, 'volatility': 0.045, 'trend': 0.0015},
            'WILLIAMSON.NR': {'base_price': 6715.00, 'volatility': 0.04, 'trend': 0.001},
            'BAMBURI.NR': {'base_price': 9164.00, 'volatility': 0.03, 'trend': 0.0005},
            'CROWN.NR': {'base_price': 3910.50, 'volatility': 0.035, 'trend': 0.001},
            'KENGEN.NR': {'base_price': 448.72, 'volatility': 0.025, 'trend': 0.0005},
            'KPLC.NR': {'base_price': 292.30, 'volatility': 0.04, 'trend': -0.001},
            'KEGN.NR': {'base_price': 466.10, 'volatility': 0.03, 'trend': 0.001},
            'KENOL.NR': {'base_price': 3555.00, 'volatility': 0.03, 'trend': 0.0015},
            'TPS.NR': {'base_price': 197.50, 'volatility': 0.05, 'trend': 0.002},
            'UMEME.NR': {'base_price': 7110.00, 'volatility': 0.025, 'trend': 0.001},
            'TOTAL.NR': {'base_price': 2923.00, 'volatility': 0.02, 'trend': 0.0005},
            'CARBACID.NR': {'base_price': 1240.30, 'volatility': 0.035, 'trend': 0.001},
            'BOC.NR': {'base_price': 6636.00, 'volatility': 0.03, 'trend': 0.0015},
            'OLYMPIA.NR': {'base_price': 829.50, 'volatility': 0.04, 'trend': 0.002},
            'CENTUM.NR': {'base_price': 2962.50, 'volatility': 0.035, 'trend': 0.001}
        }
        
        nigeria_stocks = {
            'GTCO.LG': {'base_price': 45600.00, 'volatility': 0.025, 'trend': 0.001},
            'ZENITHBANK.LG': {'base_price': 39600.00, 'volatility': 0.03, 'trend': 0.0015},
            'UBA.LG': {'base_price': 25360.00, 'volatility': 0.025, 'trend': 0.001},
            'ACCESS.LG': {'base_price': 19920.00, 'volatility': 0.03, 'trend': 0.002},
            'FBNH.LG': {'base_price': 29120.00, 'volatility': 0.035, 'trend': 0.0005},
            'FIDELITYBK.LG': {'base_price': 14000.00, 'volatility': 0.03, 'trend': 0.001},
            'STERLINGNG.LG': {'base_price': 3920.00, 'volatility': 0.04, 'trend': 0.0015},
            'WEMA.LG': {'base_price': 8400.00, 'volatility': 0.035, 'trend': 0.001},
            'UNITY.LG': {'base_price': 2960.00, 'volatility': 0.05, 'trend': 0.002},
            'STANBIC.LG': {'base_price': 68000.00, 'volatility': 0.025, 'trend': 0.0005},
            'DANGCEM.LG': {'base_price': 456000.00, 'volatility': 0.02, 'trend': 0.001},
            'BUA.LG': {'base_price': 152800.00, 'volatility': 0.025, 'trend': 0.0015},
            'MTNN.LG': {'base_price': 296000.00, 'volatility': 0.02, 'trend': 0.001},
            'AIRTELAFRI.LG': {'base_price': 2960000.00, 'volatility': 0.025, 'trend': 0.002},
            'SEPLAT.LG': {'base_price': 2000000.00, 'volatility': 0.03, 'trend': 0.0005},
            'OANDO.LG': {'base_price': 13520.00, 'volatility': 0.04, 'trend': 0.001},
            'TOTAL.LG': {'base_price': 776000.00, 'volatility': 0.02, 'trend': 0.0005},
            'CONOIL.LG': {'base_price': 56800.00, 'volatility': 0.03, 'trend': 0.001},
            'GUINNESS.LG': {'base_price': 78000.00, 'volatility': 0.025, 'trend': 0.0015},
            'NB.LG': {'base_price': 104000.00, 'volatility': 0.025, 'trend': 0.001},
            'INTBREW.LG': {'base_price': 9360.00, 'volatility': 0.035, 'trend': 0.002},
            'NESTLE.LG': {'base_price': 2376000.00, 'volatility': 0.015, 'trend': 0.001},
            'UNILEVER.LG': {'base_price': 26000.00, 'volatility': 0.025, 'trend': 0.0005},
            'DANGSUGAR.LG': {'base_price': 29600.00, 'volatility': 0.03, 'trend': 0.001},
            'FLOURMILL.LG': {'base_price': 52400.00, 'volatility': 0.025, 'trend': 0.0015},
            'HONEYFLOUR.LG': {'base_price': 6800.00, 'volatility': 0.04, 'trend': 0.002},
            'CADBURY.LG': {'base_price': 20560.00, 'volatility': 0.03, 'trend': 0.001},
            'VITAFOAM.LG': {'base_price': 24800.00, 'volatility': 0.035, 'trend': 0.0005},
            'JBERGER.LG': {'base_price': 61200.00, 'volatility': 0.025, 'trend': 0.001},
            'LIVESTOCK.LG': {'base_price': 3920.00, 'volatility': 0.05, 'trend': 0.002},
            'CHIPLC.LG': {'base_price': 1360.00, 'volatility': 0.06, 'trend': 0.003},
            'ELLAHLAKES.LG': {'base_price': 7600.00, 'volatility': 0.045, 'trend': 0.0015},
            'NAHCO.LG': {'base_price': 13600.00, 'volatility': 0.04, 'trend': 0.001},
            'RTBRISCOE.LG': {'base_price': 880.00, 'volatility': 0.055, 'trend': 0.002}
        }
        
        self.initialize_mock_data_for_market('ghana', ghana_stocks)
        self.initialize_mock_data_for_market('kenya', kenya_stocks)
        self.initialize_mock_data_for_market('nigeria', nigeria_stocks)
    
    def initialize_mock_data_for_market(self, market: str, stocks_config: dict):
        """Initialize mock data for a specific market"""
        session_key = f'{market}_mock_data'
        
        if session_key not in st.session_state or not st.session_state[session_key]:
            current_time = datetime.now()
            st.session_state[session_key] = {}
            
            for symbol, config in stocks_config.items():
                historical_data = []
                price = config['base_price']
                
                for i in range(30):
                    date = current_time - timedelta(days=29-i)
                    
                    price_change = (random.gauss(0, config['volatility']) + config['trend']) * price
                    price = max(0.01, price + price_change)
                    
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
    
    def update_mock_data_for_market(self, market: str, last_update_key: str):
        """Update mock data for a specific market"""
        current_time = datetime.now()
        session_key = f'{market}_mock_data'
        
        if (current_time - st.session_state[last_update_key]).total_seconds() < 30:
            return
        
        st.session_state[last_update_key] = current_time
        
        if market == 'ghana':
            gmt_time = current_time.utctimetuple()
            is_weekday = gmt_time.tm_wday < 5
            is_trading_hours = 9 <= gmt_time.tm_hour < 15
        elif market == 'kenya':
            eat_time = (current_time + timedelta(hours=3)).timetuple()
            is_weekday = eat_time.tm_wday < 5
            is_trading_hours = 9 <= eat_time.tm_hour < 15
        elif market == 'nigeria':
            wat_time = (current_time + timedelta(hours=1)).timetuple()
            is_weekday = wat_time.tm_wday < 5
            is_trading_hours = 10 <= wat_time.tm_hour < 14 or (wat_time.tm_hour == 14 and wat_time.tm_min <= 30)
        else:
            is_weekday = True
            is_trading_hours = True
        
        volatility_multiplier = 1.0 if (is_weekday and is_trading_hours) else 0.3
        
        for symbol, data in st.session_state[session_key].items():
            config = data['config']
            current_price = data['current_price']
            
            price_change = (random.gauss(0, config['volatility'] * volatility_multiplier) + 
                          config['trend'] * volatility_multiplier) * current_price
            
            new_price = max(0.01, current_price + price_change)
            
            if is_weekday and is_trading_hours:
                base_volume = random.randint(50000, 800000)
            else:
                base_volume = random.randint(5000, 100000)
            
            new_data_point = {
                'date': current_time,
                'open': current_price,
                'high': max(current_price, new_price) * random.uniform(1.0, 1.01),
                'low': min(current_price, new_price) * random.uniform(0.99, 1.0),
                'close': new_price,
                'volume': base_volume
            }
            
            data['historical_data'].append(new_data_point)
            cutoff_date = current_time - timedelta(days=30)
            data['historical_data'] = [
                d for d in data['historical_data'] 
                if d['date'] >= cutoff_date
            ]
            
            data['current_price'] = new_price
            data['last_update'] = current_time
    
    def get_currency_symbol(self, symbol: str) -> str:
        """Get currency symbol for different markets"""
        if symbol.endswith('.AC'):
            return 'GHS'
        elif symbol.endswith('.JO'):
            return 'ZAR'
        elif symbol.endswith('.NR'):
            return 'KES'
        elif symbol.endswith('.LG'):
            return 'NGN'
        elif symbol.endswith('.CA'):
            return 'EGP'
        elif symbol.endswith('-USD'):
            return 'USD'
        else:
            return 'USD'
    
    def get_mock_price_for_market(self, symbol: str, market: str) -> Dict:
        """Get mock price data for a specific market"""
        session_key = f'{market}_mock_data'
        
        if symbol not in st.session_state[session_key]:
            return None
        
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
        
        african_names = self.get_african_stock_names()
        stock_name = african_names.get(symbol, symbol)
        
        shares_outstanding = random.randint(100000000, 1000000000)
        market_cap = current_price * shares_outstanding
        
        currency = self.get_currency_symbol(symbol)
        
        return {
            'symbol': symbol,
            'name': stock_name,
            'price': float(current_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'volume': int(current_point['volume']),
            'market_cap': market_cap,
            'pe_ratio': random.uniform(8, 25),
            'day_high': float(current_point['high']),
            'day_low': float(current_point['low']),
            'sector': f'African Markets - {market.title()}',
            'industry': f'{market.title()} Stock Exchange',
            'is_crypto': False,
            'is_african': True,
            'is_mock': True,
            'country': market.title(),
            'currency': currency,
            'last_updated': datetime.now()
        }
    
    def get_ghana_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Ghana stocks"""
        return self.get_mock_price_for_market(symbol, 'ghana')
    
    def get_kenya_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Kenya stocks"""
        return self.get_mock_price_for_market(symbol, 'kenya')
    
    def get_nigeria_mock_price(self, symbol: str) -> Dict:
        """Get mock price data for Nigeria stocks"""
        return self.get_mock_price_for_market(symbol, 'nigeria')
    
    def get_mock_history_for_market(self, symbol: str, market: str, period: str = "3mo") -> pd.DataFrame:
        """Get historical mock data for a specific market"""
        session_key = f'{market}_mock_data'
        
        if symbol not in st.session_state[session_key]:
            return pd.DataFrame()
        
        self.update_mock_data_for_market(market, f'{market}_last_update')
        
        data = st.session_state[session_key][symbol]
        historical_data = data['historical_data']
        
        df = pd.DataFrame(historical_data)
        df['Date'] = pd.to_datetime(df['date'])
        df.set_index('Date', inplace=True)
        
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }, inplace=True)
        
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
            # Check if it's a mock data stock
            if symbol.endswith('.AC'):
                return _self.get_ghana_mock_price(symbol)
            elif symbol.endswith('.NR'):
                return _self.get_kenya_mock_price(symbol)
            elif symbol.endswith('.LG'):
                return _self.get_nigeria_mock_price(symbol)
            
            # For real data, implement rate limiting
            import time
            time.sleep(0.1)
            
            ticker = yf.Ticker(symbol)
            
            try:
                hist = ticker.history(period="5d")
                if hist.empty:
                    hist = ticker.history(period="1d")
                if hist.empty:
                    return None
                    
                info = ticker.info
            except Exception as e:
                return {
                    'symbol': symbol,
                    'name': symbol,
                    'price': 100.0,
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
            
            is_crypto = symbol.endswith('-USD')
            is_african = _self.is_african_stock(symbol)
            
            currency = _self.get_currency_symbol(symbol)
            
            if is_crypto:
                display_name = symbol.replace('-USD', '')
                long_name = info.get('longName', display_name)
                if long_name == display_name:
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
            return {
                'symbol': symbol,
                'name': symbol,
                'price': 100.0,
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
    
    def create_performance_chart(self, user_id: str):
        """Create performance chart for portfolio"""
        try:
            # Get user data
            user_data = self.db.get_user_data(user_id)
            starting_cash = st.session_state.game_settings['starting_cash']
            
            # Create sample performance data (in real app, this would come from historical data)
            dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
            performance_data = []
            
            current_value = self.get_portfolio_value(user_id)
            
            # Generate sample historical performance
            for i, date in enumerate(dates):
                # Simple random walk for demonstration
                value = starting_cash + (current_value - starting_cash) * (i / len(dates)) + random.uniform(-500, 500)
                performance_data.append({
                    'date': date,
                    'value': max(0, value)
                })
            
            df = pd.DataFrame(performance_data)
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['value'],
                mode='lines',
                name='Portfolio Value',
                line=dict(color='#4299e1', width=2)
            ))
            
            # Add S&P 500 benchmark (simplified)
            sp500_data = []
            for i, date in enumerate(dates):
                sp500_value = starting_cash * (1 + 0.001 * i + random.uniform(-0.01, 0.01))
                sp500_data.append(sp500_value)
            
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=sp500_data,
                mode='lines',
                name='S&P 500',
                line=dict(color='#a0aec0', width=1, dash='dash')
            ))
            
            fig.update_layout(
                title='Performance History',
                xaxis_title='Date',
                yaxis_title='Value ($)',
                template='plotly_dark',
                height=300,
                showlegend=True,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating performance chart: {str(e)}")
            return None

def show_login_page():
    """Show enhanced login and registration page"""
    st.markdown("""
    <div class="main-content">
        <div class="login-container">
            <div class="login-title">Leo's Trader</div>
            <div class="login-subtitle">Professional Trading Simulator</div>
            <div class="login-ghana-pride">
                <h3>Proudly Made in Ghana</h3>
                <p>Empowering African traders with world-class technology</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create a centered container for the tabs
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.markdown('<div class="login-form-container">', unsafe_allow_html=True)
            
            with st.form("login_form"):
                st.markdown("### Welcome Back")
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                col_login1, col_login2 = st.columns(2)
                with col_login1:
                    if st.form_submit_button("Login", use_container_width=True):
                        if username and password:
                            simulator = TradingSimulator()
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
                
                with col_login2:
                    if st.form_submit_button("Demo Mode", use_container_width=True):
                        st.info("Demo mode coming soon!")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tab2:
            st.markdown('<div class="login-form-container">', unsafe_allow_html=True)
            
            with st.form("register_form"):
                st.markdown("### Create Account")
                new_username = st.text_input("Username", placeholder="Choose a username")
                new_email = st.text_input("Email", placeholder="Enter your email")
                new_password = st.text_input("Password", type="password", placeholder="Create a password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
                
                if st.form_submit_button("Create Account", use_container_width=True):
                    if new_username and new_email and new_password and confirm_password:
                        if new_password == confirm_password:
                            simulator = TradingSimulator()
                            result = simulator.db.create_user(new_username, new_password, new_email)
                            if result['success']:
                                st.success("Account created successfully! Please login.")
                            else:
                                st.error(result['message'])
                        else:
                            st.error("Passwords do not match")
                    else:
                        st.error("Please fill in all fields")
            
            st.markdown('</div>', unsafe_allow_html=True)

def show_portfolio_page(simulator, current_user):
    """Show portfolio page - main page like Investopedia"""
    # Market status
    current_time = datetime.now()
    market_hours = 9 <= current_time.hour <= 16 and current_time.weekday() < 5
    status_class = "open" if market_hours else "closed"
    status_text = "Market is open" if market_hours else "Market is closed"
    
    st.markdown(f"""
    <div class="market-status {status_class}">
        <div class="market-status-text {status_class}">{status_text}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Get portfolio data
    portfolio_value = simulator.get_portfolio_value(current_user['id'])
    starting_cash = st.session_state.game_settings['starting_cash']
    total_return = portfolio_value - starting_cash
    return_percentage = (total_return / starting_cash) * 100
    
    # Portfolio summary
    portfolio = simulator.db.get_user_portfolio(current_user['id'])
    total_invested = sum([p['avg_price'] * p['shares'] for p in portfolio])
    
    # Overview section
    st.markdown(f"""
    <div class="main-content">
        <div class="overview-section">
            <div class="overview-card">
                <div class="overview-title">Overview</div>
                <div class="metric-row">
                    <div class="metric-label">ACCOUNT VALUE</div>
                    <div class="metric-value large">${portfolio_value:,.2f}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">TODAY'S CHANGE</div>
                    <div class="metric-value">${total_return:+,.2f}</div>
                    <div class="metric-change {'positive' if total_return >= 0 else 'negative'}">({return_percentage:+.2f}%)</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">BUYING POWER</div>
                    <div class="metric-value">${current_user['cash']:,.2f}</div>
                </div>
                <div class="metric-row">
                    <div class="metric-label">CASH</div>
                    <div class="metric-value">${current_user['cash']:,.2f}</div>
                </div>
            </div>
            <div class="performance-chart">
                <div class="chart-title">Performance</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Performance chart
    perf_chart = simulator.create_performance_chart(current_user['id'])
    if perf_chart:
        st.plotly_chart(perf_chart, use_container_width=True)
    
    # Holdings section
    st.markdown(f"""
    <div class="main-content">
        <div class="holdings-section">
            <div class="holdings-header">
                <div class="holdings-title">Holdings</div>
                <div class="holdings-tabs">
                    <div class="holdings-tab active">STOCKS & ETFS</div>
                    <div class="holdings-tab">CRYPTO</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Holdings table
    if portfolio:
        holdings_data = []
        
        for position in portfolio:
            current_data = simulator.get_stock_price(position['symbol'])
            if current_data:
                current_value = current_data['price'] * position['shares']
                invested_value = position['avg_price'] * position['shares']
                unrealized_pl = current_value - invested_value
                unrealized_pl_percent = (unrealized_pl / invested_value) * 100 if invested_value > 0 else 0
                
                # For African stocks, handle currency conversion
                if current_data.get('is_african') and current_data['currency'] != 'USD':
                    avg_price_local = simulator.convert_from_usd(position['avg_price'], current_data['currency'])
                    avg_price_display = simulator.format_currency_display(avg_price_local, current_data['currency'])
                    current_price_display = simulator.format_currency_display(current_data['price'], current_data['currency'])
                    
                    current_value_usd = simulator.convert_to_usd(current_data['price'], current_data['currency']) * position['shares']
                    current_value_local = current_data['price'] * position['shares']
                    market_value_display = f"{simulator.format_currency_display(current_value_local, current_data['currency'])}"
                    
                    unrealized_pl_usd = current_value_usd - (position['avg_price'] * position['shares'])
                    unrealized_pl_percent_usd = (unrealized_pl_usd / (position['avg_price'] * position['shares'])) * 100 if position['avg_price'] > 0 else 0
                    
                    holdings_data.append({
                        'Symbol': position['symbol'],
                        'Company': position['name'][:25],
                        'Shares': position['shares'],
                        'Avg Price': avg_price_display,
                        'Current Price': current_price_display,
                        'Market Value': market_value_display,
                        'Unrealized P&L': f"${unrealized_pl_usd:+,.2f}",
                        'P&L %': f"{unrealized_pl_percent_usd:+.2f}%"
                    })
                else:
                    holdings_data.append({
                        'Symbol': position['symbol'],
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
            st.dataframe(df_holdings, use_container_width=True, hide_index=True)
        else:
            st.info("No current holdings")
    else:
        st.info("No holdings. Start trading to build your portfolio!")

def show_trade_page(simulator, current_user):
    """Show trading page"""
    st.markdown("""
    <div class="main-content">
        <div class="trade-form">
            <div class="trade-form-title">Place Order</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Asset selection
    trade_asset_type = st.selectbox(
        "Asset Type",
        ["All Assets", "Stocks & ETFs", "Cryptocurrencies", "African Markets"],
        key="trade_asset_type"
    )
    
    # Filter assets based on type
    if trade_asset_type == "Stocks & ETFs":
        trade_available_assets = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
    elif trade_asset_type == "Cryptocurrencies":
        trade_available_assets = [s for s in simulator.available_stocks if s.endswith('-USD')]
    elif trade_asset_type == "African Markets":
        trade_available_assets = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
    else:
        trade_available_assets = simulator.available_stocks
    
    selected_asset = st.selectbox(
        "Select Asset",
        [''] + trade_available_assets[:100],
        key="selected_trade_asset"
    )
    
    if selected_asset:
        asset_data = simulator.get_stock_price(selected_asset)
        
        if asset_data:
            st.write(f"**{asset_data['name']} ({selected_asset})**")
            st.write(f"Current Price: {simulator.format_currency_display(asset_data['price'], asset_data['currency'])}")
            st.write(f"24h Change: {simulator.format_currency_display(asset_data['change'], asset_data['currency'])} ({asset_data['change_percent']:+.2f}%)")
            
            # Trade form
            with st.form("trade_form"):
                trade_action = st.selectbox("Action", ["BUY", "SELL"])
                shares = st.number_input("Number of Shares/Units", min_value=1, value=1, step=1)
                
                # Calculate trade cost
                if trade_action == "BUY":
                    if asset_data['currency'] != 'USD':
                        actual_cost_usd = simulator.convert_to_usd(asset_data['price'], asset_data['currency']) * shares
                        total_cost_local = asset_data['price'] * shares
                        cost_display = simulator.format_currency_display(total_cost_local, asset_data['currency'])
                        st.write(f"**Total Cost:** {cost_display}")
                        st.write(f"**Equivalent to:** ${actual_cost_usd:,.2f} USD")
                    else:
                        actual_cost_usd = asset_data['price'] * shares
                        st.write(f"**Total Cost:** ${actual_cost_usd:,.2f}")
                    
                    if actual_cost_usd > current_user['cash']:
                        st.error(f"Insufficient funds! You need ${actual_cost_usd:,.2f} USD but only have ${current_user['cash']:,.2f} USD")
                        can_trade = False
                    else:
                        can_trade = True
                
                else:  # SELL
                    portfolio = simulator.db.get_user_portfolio(current_user['id'])
                    owned_position = next((p for p in portfolio if p['symbol'] == selected_asset), None)
                    
                    if owned_position and owned_position['shares'] >= shares:
                        if asset_data['currency'] != 'USD':
                            actual_proceeds_usd = simulator.convert_to_usd(asset_data['price'], asset_data['currency']) * shares
                            total_proceeds_local = asset_data['price'] * shares
                            proceeds_display = simulator.format_currency_display(total_proceeds_local, asset_data['currency'])
                            
                            profit_loss_usd = actual_proceeds_usd - (owned_position['avg_price'] * shares)
                            
                            st.write(f"**Owned Shares:** {owned_position['shares']}")
                            st.write(f"**Total Proceeds:** {proceeds_display}")
                            st.write(f"**Equivalent to:** ${actual_proceeds_usd:,.2f} USD")
                        else:
                            actual_proceeds_usd = asset_data['price'] * shares
                            profit_loss_usd = (asset_data['price'] - owned_position['avg_price']) * shares
                            
                            st.write(f"**Owned Shares:** {owned_position['shares']}")
                            st.write(f"**Total Proceeds:** ${actual_proceeds_usd:,.2f}")
                        
                        st.write(f"**Estimated P&L:** ${profit_loss_usd:+,.2f} USD")
                        can_trade = True
                    else:
                        if owned_position:
                            st.error(f"Insufficient shares! You own {owned_position['shares']} shares but trying to sell {shares}")
                        else:
                            st.error("You don't own this asset")
                        can_trade = False
                
                # Submit trade
                if st.form_submit_button(f"Execute {trade_action}", disabled=not can_trade, use_container_width=True):
                    if can_trade:
                        result = simulator.db.execute_trade(
                            current_user['id'],
                            selected_asset,
                            trade_action,
                            shares,
                            simulator.convert_to_usd(asset_data['price'], asset_data['currency']) if asset_data['currency'] != 'USD' else asset_data['price'],
                            asset_data['name'],
                            asset_data['currency'],
                            asset_data['price']
                        )
                        
                        if result['success']:
                            st.success(result['message'])
                            if trade_action == "SELL" and result.get('profit_loss'):
                                profit_loss = result['profit_loss']
                                if profit_loss >= 0:
                                    st.success(f"Profit: ${profit_loss:+,.2f}")
                                else:
                                    st.error(f"Loss: ${profit_loss:+,.2f}")
                            st.rerun()
                        else:
                            st.error(result['message'])
        else:
            st.error("Unable to load asset data")

def show_research_page(simulator, current_user):
    """Show research page"""
    st.markdown("""
    <div class="main-content">
        <div class="chart-container">
            <div class="chart-title">Research & Analysis</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Research tools would go here
    st.write("Research tools and market analysis coming soon!")

def show_learn_page(simulator, current_user):
    """Show learn page"""
    st.markdown("""
    <div class="main-content">
        <div class="chart-container">
            <div class="chart-title">Learn</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("Educational content and tutorials coming soon!")

def show_games_page(simulator, current_user):
    """Show games page"""
    st.markdown("""
    <div class="main-content">
        <div class="chart-container">
            <div class="chart-title">Games</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Leaderboard
    leaderboard = simulator.db.get_leaderboard()
    
    if leaderboard:
        st.write("### Leaderboard")
        
        leaderboard_data = []
        for i, player in enumerate(leaderboard[:10]):
            username_display = player['username']
            if player['user_id'] == current_user['id']:
                username_display = f"YOU ({username_display})"
            
            leaderboard_data.append({
                'Rank': f"#{player['rank']}",
                'Trader': username_display,
                'Portfolio Value': f"${player['portfolio_value']:,.2f}",
                'Total Trades': player['total_trades'],
                'P&L': f"${player['total_profit_loss']:+,.2f}"
            })
        
        df_leaderboard = pd.DataFrame(leaderboard_data)
        st.dataframe(df_leaderboard, use_container_width=True, hide_index=True)
    else:
        st.info("No leaderboard data available")

def main():
    try:
        # Initialize simulator
        simulator = TradingSimulator()
        
        # Show login page if not logged in
        if not st.session_state.logged_in:
            show_login_page()
            return
        
        # Get current user
        current_user = st.session_state.current_user
        
        # Refresh user data
        current_user = simulator.db.get_user_data(current_user['id'])
        if current_user:
            st.session_state.current_user = current_user
        
        # Header Navigation
        st.markdown(f"""
        <div class="header-nav">
            <div class="logo">Leo's Trader</div>
            <div class="nav-buttons">
                <button class="nav-button {'active' if st.session_state.current_page == 'Portfolio' else ''}" onclick="window.location.reload()">PORTFOLIO</button>
                <button class="nav-button {'active' if st.session_state.current_page == 'Trade' else ''}">TRADE</button>
                <button class="nav-button {'active' if st.session_state.current_page == 'Research' else ''}">RESEARCH</button>
                <button class="nav-button {'active' if st.session_state.current_page == 'Learn' else ''}">LEARN</button>
                <button class="nav-button {'active' if st.session_state.current_page == 'Games' else ''}">GAMES</button>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            if st.button("PORTFOLIO", key="nav_portfolio", use_container_width=True):
                st.session_state.current_page = 'Portfolio'
                st.rerun()
        
        with col2:
            if st.button("TRADE", key="nav_trade", use_container_width=True):
                st.session_state.current_page = 'Trade'
                st.rerun()
        
        with col3:
            if st.button("RESEARCH", key="nav_research", use_container_width=True):
                st.session_state.current_page = 'Research'
                st.rerun()
        
        with col4:
            if st.button("LEARN", key="nav_learn", use_container_width=True):
                st.session_state.current_page = 'Learn'
                st.rerun()
        
        with col5:
            if st.button("GAMES", key="nav_games", use_container_width=True):
                st.session_state.current_page = 'Games'
                st.rerun()
        
        with col6:
            if st.button("LOGOUT", key="nav_logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.rerun()
        
        # Show selected page
        current_page = st.session_state.get('current_page', 'Portfolio')
        
        if current_page == 'Portfolio':
            show_portfolio_page(simulator, current_user)
        elif current_page == 'Trade':
            show_trade_page(simulator, current_user)
        elif current_page == 'Research':
            show_research_page(simulator, current_user)
        elif current_page == 'Learn':
            show_learn_page(simulator, current_user)
        elif current_page == 'Games':
            show_games_page(simulator, current_user)
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please refresh the page and try again.")

if __name__ == "__main__":
    main()
