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
        
        # Create trades table - UPDATED to store original currency and local price
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
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN original_price REAL')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
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
                    'price': row[4],  # USD price (stored)
                    'total_cost': row[5],  # USD total cost (stored)
                    'commission': row[6],
                    'profit_loss': row[7],
                    'name': row[8] or row[2],
                    'timestamp': datetime.strptime(row[9], '%Y-%m-%d %H:%M:%S'),
                    'original_currency': row[10] or 'USD',
                    'original_price': row[11] or row[4]  # Fallback to USD price if no original price
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
            
            # Get commission from settings
            cursor.execute('SELECT commission FROM game_settings ORDER BY id DESC LIMIT 1')
            commission = cursor.fetchone()[0]
            
            # Get current user data
            cursor.execute('SELECT cash FROM users WHERE id = ?', (user_id,))
            current_cash = cursor.fetchone()[0]
            
            # Convert price to USD for internal calculations
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
            
            # Store the original price in local currency for display purposes
            if original_price is None:
                original_price = price
            
            total_cost_usd = price_usd * shares
            
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
                
                # Record trade (store in USD but also save original price and currency)
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, stock_name, original_currency, original_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_cost_usd, 0.00, stock_name, currency, original_price))
                
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
                
                # Calculate profit/loss in USD (no commission)
                profit_loss = (price_usd - avg_price_usd) * shares
                
                # Update cash (in USD)
                total_proceeds_usd = price_usd * shares
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
                
                # Record trade (in USD but also save original price and currency)
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, profit_loss, stock_name, original_currency, original_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price_usd, total_proceeds_usd, 0.00, profit_loss, stock_name, currency, original_price))
                
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
            return {'starting_cash': 100000, 'commission': 0.00, 'game_duration_days': 30}
        except Exception as e:
            st.error(f"Error getting settings: {str(e)}")
            return {'starting_cash': 100000, 'commission': 0.00, 'game_duration_days': 30}

# Configure Streamlit page
st.set_page_config(
    page_title="Leo's Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS with updated color palette and enhanced sidebar user info
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap');
    
    /* Global Styles */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    .main .block-container {
        padding: 1rem 2rem;
        background: #DDCECD;
        min-height: 100vh;
        transition: all 0.3s ease-in-out;
    }
    
    /* Page transition animations */
    .page-content {
        animation: slideInFromRight 0.4s ease-out;
        transform-origin: center;
    }
    
    @keyframes slideInFromRight {
        0% {
            opacity: 0;
            transform: translateX(30px);
        }
        100% {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* Header Styles */
    .trading-header {
        background: #37392E;
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(55,57,46,0.3);
        text-align: center;
    }
    
    .trading-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        color: white;
    }
    
    .trading-header p {
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        opacity: 0.95;
        color: white;
    }
    
    /* Ghana Pride Section */
    .ghana-pride {
        background: #19647E;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        text-align: center;
        font-weight: 600;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    
    .ghana-pride h3 {
        color: white;
        margin: 0;
    }
    
    .ghana-pride p {
        color: white;
        margin: 0.5rem 0 0 0;
    }
    
    /* Card Styles */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border: 1px solid #e9ecef;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        transform: translateY(0);
    }
    
    .metric-card:hover {
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        transform: translateY(-4px);
    }
    
    .summary-card {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border-left: 4px solid #19647E;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        transform: translateY(0);
    }
    
    .summary-card:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 10px 30px rgba(0,0,0,0.12);
    }
    
    .summary-card h3 {
        color: #37392E;
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    .summary-card h2 {
        color: #19647E;
        font-size: 2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    .summary-card .delta {
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    .portfolio-value {
        background: #28AFB0;
        color: white;
        border-left: 4px solid #19647E;
    }
    
    .portfolio-value h3,
    .portfolio-value h2 {
        color: white;
    }
    
    .cash-available {
        background: #DDCECD;
        color: #37392E;
        border-left: 4px solid #28AFB0;
    }
    
    .cash-available h3,
    .cash-available h2 {
        color: #37392E;
    }
    
    .total-return {
        background: #28AFB0;
        color: white;
        border-left: 4px solid #19647E;
    }
    
    .total-return h3,
    .total-return h2 {
        color: white;
    }
    
    .total-trades {
        background: #37392E;
        color: white;
        border-left: 4px solid #28AFB0;
    }
    
    .total-trades h3,
    .total-trades h2 {
        color: white;
    }
    
    /* Button Styles */
    .stButton > button {
        background: #19647E;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-weight: 600;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 2px 8px rgba(25,100,126,0.3);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-height: 3rem;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.9rem;
        position: relative;
    }
    
    .stButton > button:hover {
        background: #37392E;
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 20px rgba(55,57,46,0.4);
    }
    
    .stButton > button:active {
        transform: translateY(0) scale(0.98);
        transition: all 0.1s ease;
    }
    
    /* Form Styles */
    .stSelectbox > div > div {
        background: white;
        border-radius: 8px;
        border: 1px solid #ddd;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .stTextInput > div > div > input {
        background: white;
        border-radius: 8px;
        border: 1px solid #ddd;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .stNumberInput > div > div > input {
        background: white;
        border-radius: 8px;
        border: 1px solid #ddd;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* DataFrames */
    .stDataFrame {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border: 1px solid #e9ecef;
    }
    
    /* Colors */
    .positive { 
        color: #19647E; 
        font-weight: 600; 
    }
    
    .negative { 
        color: #dc3545; 
        font-weight: 600; 
    }
    
    .neutral { 
        color: #6c757d; 
        font-weight: 500; 
    }
    
    /* Modern Collapsible Sidebar Styling */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 1rem;
        margin: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: all 0.3s ease;
        width: auto !important;
        min-width: 280px;
    }
    
    /* Sidebar Header with Company Info */
    .sidebar-header {
        display: flex;
        align-items: center;
        padding: 1rem;
        margin-bottom: 1rem;
        background: rgba(55, 57, 46, 0.05);
        border-radius: 12px;
        border: 1px solid rgba(55, 57, 46, 0.1);
    }
    
    .sidebar-header .company-avatar {
        width: 40px;
        height: 40px;
        background: #37392E;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 1rem;
        margin-right: 1rem;
        flex-shrink: 0;
    }
    
    .sidebar-header .company-info h4 {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
        color: #37392E;
        line-height: 1.2;
    }
    
    .sidebar-header .company-info p {
        margin: 0;
        font-size: 0.75rem;
        color: #666;
        opacity: 0.8;
    }
    
    /* Modern Navigation Menu */
    .modern-nav {
        margin-bottom: 1.5rem;
    }
    
    .modern-nav .nav-item {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin-bottom: 0.25rem;
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s ease;
        color: #37392E;
        font-weight: 500;
        font-size: 0.9rem;
        position: relative;
        overflow: hidden;
    }
    
    .modern-nav .nav-item:hover {
        background: rgba(25, 100, 126, 0.08);
        transform: translateX(2px);
    }
    
    .modern-nav .nav-item.active {
        background: #19647E;
        color: white;
        box-shadow: 0 2px 8px rgba(25, 100, 126, 0.3);
    }
    
    .modern-nav .nav-item .nav-icon {
        width: 20px;
        height: 20px;
        margin-right: 0.75rem;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* Sidebar navigation override for Streamlit buttons */
    .sidebar-nav {
        background: transparent;
        padding: 0;
        border-radius: 0;
        margin-bottom: 1rem;
    }
    
    .sidebar-nav .stButton > button {
        background: transparent;
        color: #37392E;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        font-weight: 500;
        transition: all 0.2s ease;
        width: 100%;
        text-align: left;
        margin-bottom: 0.25rem;
        font-size: 0.9rem;
        box-shadow: none;
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: flex-start;
    }
    
    .sidebar-nav .stButton > button:hover {
        background: rgba(25, 100, 126, 0.08);
        color: #19647E;
        transform: translateX(2px);
        box-shadow: none;
    }
    
    .sidebar-nav .stButton > button:focus {
        background: #19647E;
        color: white;
        box-shadow: 0 2px 8px rgba(25, 100, 126, 0.3);
    }
    
    /* Enhanced User Info Card */
    .sidebar-user-info {
        background: linear-gradient(135deg, #28AFB0 0%, #19647E 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(40, 175, 176, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }
    
    .sidebar-user-info::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
    }
    
    .sidebar-user-info h4 {
        color: white;
        margin: 0 0 0.5rem 0;
        font-size: 1rem;
        font-weight: 600;
    }
    
    .sidebar-user-info p {
        color: white;
        margin: 0.2rem 0;
        font-size: 0.8rem;
        opacity: 0.9;
    }
    
    .sidebar-user-info .portfolio-summary {
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        padding-top: 1rem;
        margin-top: 1rem;
    }
    
    .sidebar-user-info .portfolio-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 0.5rem 0;
        font-size: 0.8rem;
        padding: 0.25rem 0;
    }
    
    .sidebar-user-info .portfolio-value {
        font-weight: 600;
        font-size: 0.85rem;
    }
    
    .sidebar-user-info .positive {
        color: #90EE90;
        font-weight: 600;
    }
    
    .sidebar-user-info .negative {
        color: #FFB6C1;
        font-weight: 600;
    }
    
    /* User Profile Section */
    .user-profile {
        display: flex;
        align-items: center;
        padding: 1rem;
        background: rgba(55, 57, 46, 0.05);
        border-radius: 12px;
        margin-top: 1rem;
        border: 1px solid rgba(55, 57, 46, 0.1);
    }
    
    .user-profile .user-avatar {
        width: 36px;
        height: 36px;
        background: #37392E;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 0.9rem;
        margin-right: 0.75rem;
        flex-shrink: 0;
    }
    
    .user-profile .user-info h5 {
        margin: 0;
        font-size: 0.85rem;
        font-weight: 600;
        color: #37392E;
        line-height: 1.2;
    }
    
    .user-profile .user-info p {
        margin: 0;
        font-size: 0.7rem;
        color: #666;
        opacity: 0.8;
    }
    
    /* Logout Button */
    .logout-btn .stButton > button {
        background: rgba(220, 53, 69, 0.1);
        color: #dc3545;
        border: 1px solid rgba(220, 53, 69, 0.2);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        font-weight: 500;
        transition: all 0.2s ease;
        width: 100%;
        font-size: 0.85rem;
    }
    
    .logout-btn .stButton > button:hover {
        background: #dc3545;
        color: white;
        border-color: #dc3545;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(220, 53, 69, 0.3);
    }
    
    /* Ghana Pride Section - Modernized */
    .ghana-pride-sidebar {
        background: linear-gradient(135deg, #DDCECD 0%, #19647E 100%);
        color: #37392E;
        padding: 1rem;
        border-radius: 12px;
        margin-top: 1rem;
        text-align: center;
        border: 1px solid rgba(25, 100, 126, 0.1);
        position: relative;
        overflow: hidden;
    }
    
    .ghana-pride-sidebar::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(55, 57, 46, 0.2), transparent);
    }
    
    .ghana-pride-sidebar h4 {
        color: #37392E;
        margin: 0 0 0.25rem 0;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .ghana-pride-sidebar p {
        color: #37392E;
        margin: 0;
        font-size: 0.7rem;
        opacity: 0.8;
    }
    
    /* Login/Register forms */
    .login-container {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        max-width: 400px;
        margin: 2rem auto;
    }
    
    .login-container h2 {
        color: #37392E;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    /* Chart containers */
    .chart-container {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        border: 1px solid #e9ecef;
    }
    
    .chart-container h3 {
        color: #37392E;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
    }
    
    .stError {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        border-radius: 8px;
    }
    
    .stInfo {
        background: #cce7f0;
        color: #0c5460;
        border: 1px solid #b8daff;
        border-radius: 8px;
    }
    
    .stWarning {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
        border-radius: 8px;
    }
    
    /* Page section headers */
    .page-header {
        background: #EEE5E5;
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        border-left: 4px solid #19647E;
    }
    
    .page-header h2 {
        color: #37392E;
        margin: 0;
        font-weight: 600;
    }
    
    .page-header p {
        color: #37392E;
        margin: 0.5rem 0 0 0;
        opacity: 0.8;
    }
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .trading-header h1 {
            font-size: 2rem;
        }
        
        .trading-header p {
            font-size: 1rem;
        }
        
        .main .block-container {
            padding: 1rem;
        }
        
        .metric-card {
            padding: 1rem;
        }
        
        .summary-card {
            padding: 1.5rem;
        }
        
        .sidebar-user-info .portfolio-item {
            flex-direction: column;
            align-items: flex-start;
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
            st.session_state.current_page = 'Dashboard'
        
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
        """Get current fallback exchange rates (updated regularly)"""
        return {
            'GHS': 12.80,  # Ghana Cedi to USD (updated)
            'KES': 158.0,  # Kenyan Shilling to USD (updated)
            'NGN': 1600.0, # Nigerian Naira to USD (updated)
            'ZAR': 18.75,  # South African Rand to USD (updated)
            'EGP': 50.5,   # Egyptian Pound to USD (updated)
            'USD': 1.0     # US Dollar base
        }
    
    def update_exchange_rates(self):
        """Update exchange rates with improved error handling"""
        current_time = datetime.now()
        
        # Update every 30 minutes for more current rates
        if (current_time - st.session_state.exchange_rates_last_update).total_seconds() < 1800:
            return
        
        # Start with fallback rates
        st.session_state.exchange_rates = self.get_fallback_exchange_rates()
        
        try:
            # Try multiple free APIs for better reliability
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
                        
                        # Update with live rates if available
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
                            break  # Success, stop trying other APIs
                        
                except Exception:
                    continue  # Try next API
            
            # If no API worked, note that we're using fallback
            if 'exchange_rates_source' not in st.session_state:
                st.session_state.exchange_rates_source = "Fallback rates"
                
        except Exception as e:
            # Use fallback rates if all APIs fail
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
            # For currencies with larger numbers, use commas
            return f"{symbol}{amount:,.0f}"
        else:
            # For others, use 2 decimal places
            return f"{symbol}{amount:,.2f}"
    
    def initialize_all_mock_data(self):
        """Initialize mock data for all African Stock Exchanges"""
        # Update exchange rates first
        self.update_exchange_rates()
        
        # Base prices in local currencies (realistic values)
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
        
        # Initialize Kenya stocks data (in KES)
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
        
        # Initialize Nigeria stocks data (in NGN)
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
            "Ghana Stock Exchange (GSE)": [
                'GOIL.AC', 'ECOBANK.AC', 'CAL.AC', 'MTNGH.AC', 'GWEB.AC', 'SOGEGH.AC',
                'AYRTN.AC', 'UNIL.AC', 'CMLT.AC', 'RBGH.AC', 'BOPP.AC', 'TOTAL.AC',
                'GGBL.AC', 'SCBGH.AC', 'DIGP.AC', 'CLYD.AC', 'AADS.AC', 'CAPL.AC',
                'NICO.AC', 'HORDS.AC', 'TRANSOL.AC', 'PRODUCE.AC', 'PIONEER.AC'
            ],
            "Johannesburg Stock Exchange (JSE)": [
                'NPN.JO', 'PRX.JO', 'ABG.JO', 'SHP.JO', 'BVT.JO', 'MTN.JO', 'VOD.JO',
                'DSY.JO', 'TKG.JO', 'REM.JO', 'BID.JO', 'SBK.JO', 'FSR.JO', 'NED.JO',
                'AGL.JO', 'IMP.JO', 'SOL.JO', 'CPI.JO', 'RNI.JO', 'APN.JO', 'MCG.JO',
                'PIK.JO', 'WHL.JO', 'TBS.JO', 'GFI.JO', 'HAR.JO', 'SLM.JO', 'AMS.JO',
                'CFR.JO', 'INP.JO', 'BTI.JO', 'ARI.JO', 'SPP.JO', 'MRP.JO', 'RBX.JO'
            ],
            "Nairobi Securities Exchange (NSE)": [
                'KCB.NR', 'EQTY.NR', 'SCBK.NR', 'ABSA.NR', 'DTBK.NR', 'BAT.NR', 'EABL.NR',
                'SAFCOM.NR', 'BRITAM.NR', 'JUBILEE.NR', 'LIBERTY.NR', 'COOP.NR', 'UNGA.NR',
                'KAKUZI.NR', 'SASINI.NR', 'KAPCHORUA.NR', 'WILLIAMSON.NR', 'BAMBURI.NR',
                'CROWN.NR', 'KENGEN.NR', 'KPLC.NR', 'KEGN.NR', 'KENOL.NR', 'TPS.NR',
                'UMEME.NR', 'TOTAL.NR', 'CARBACID.NR', 'BOC.NR', 'OLYMPIA.NR', 'CENTUM.NR'
            ],
            "Nigerian Exchange (NGX)": [
                'GTCO.LG', 'ZENITHBANK.LG', 'UBA.LG', 'ACCESS.LG', 'FBNH.LG', 'FIDELITYBK.LG',
                'STERLINGNG.LG', 'WEMA.LG', 'UNITY.LG', 'STANBIC.LG', 'DANGCEM.LG', 'BUA.LG',
                'MTNN.LG', 'AIRTELAFRI.LG', 'SEPLAT.LG', 'OANDO.LG', 'TOTAL.LG', 'CONOIL.LG',
                'GUINNESS.LG', 'NB.LG', 'INTBREW.LG', 'NESTLE.LG', 'UNILEVER.LG', 'DANGSUGAR.LG',
                'FLOURMILL.LG', 'HONEYFLOUR.LG', 'CADBURY.LG', 'VITAFOAM.LG', 'JBERGER.LG',
                'LIVESTOCK.LG', 'CHIPLC.LG', 'ELLAHLAKES.LG', 'NAHCO.LG', 'RTBRISCOE.LG'
            ],
            "Egyptian Exchange (EGX)": [
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
            elif symbol.endswith('.AC'):
                display_name = symbol
                asset_type = "Ghana Stock Exchange (GSE) - Live Mock Data"
            elif symbol.endswith('.NR'):
                display_name = symbol
                asset_type = "Kenya NSE - Live Mock Data"
            elif symbol.endswith('.LG'):
                display_name = symbol
                asset_type = "Nigeria NGX - Live Mock Data"
            elif is_african:
                display_name = symbol
                country = self.get_african_country_from_symbol(symbol)
                asset_type = f"African Stock - {country}"
            else:
                display_name = symbol
                asset_type = "Stock"
            
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
                title=f"{display_name} - {asset_type} Technical Analysis ({period})",
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
                            display_name = f"{symbol}"
                        elif symbol.endswith('.NR'):
                            display_name = f"{symbol}"
                        elif symbol.endswith('.LG'):
                            display_name = f"{symbol}"
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
                    
                    # Add appropriate label based on asset type
                    if stock_data.get('is_crypto'):
                        symbol_display = f"{position['symbol'].replace('-USD', '')}"
                    elif stock_data.get('is_african'):
                        symbol_display = f"{position['symbol']}"
                    else:
                        symbol_display = f"{position['symbol']}"
                    
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

def show_login_page():
    """Show login and registration page"""
    st.markdown("""
    <div class="trading-header">
        <h1>Leo's Trader</h1>
        <p>Professional Trading Simulator - Master the Markets with Virtual Money</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Ghana Pride Section
    st.markdown("""
    <div class="ghana-pride">
        <h3>Proudly Made in Ghana</h3>
        <p>Developed with passion from the Gateway to Africa</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Login/Register tabs
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.markdown("""
        <div class="login-container">
            <h2>Welcome Back</h2>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col1, col2 = st.columns(2)
            with col1:
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
            
            with col2:
                if st.form_submit_button("Demo Mode", use_container_width=True):
                    st.info("Demo mode coming soon!")
    
    with tab2:
        st.markdown("""
        <div class="login-container">
            <h2>Join Leo's Trader</h2>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("register_form"):
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

def show_dashboard(simulator, current_user):
    """Show main dashboard"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Trading Dashboard</h2>
        <p>Your complete trading overview and market summary</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Portfolio overview
    portfolio_value = simulator.get_portfolio_value(current_user['id'])
    total_return = portfolio_value - st.session_state.game_settings['starting_cash']
    return_percentage = (total_return / st.session_state.game_settings['starting_cash']) * 100
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card portfolio-value">
            <h3>Portfolio Value</h3>
            <h2>${portfolio_value:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="summary-card cash-available">
            <h3>Cash Available</h3>
            <h2>${current_user['cash']:,.2f}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        return_color = "total-return" if total_return >= 0 else "total-return"
        st.markdown(f"""
        <div class="summary-card {return_color}">
            <h3>Total Return</h3>
            <h2>${total_return:,.2f}</h2>
            <div class="delta {'positive' if total_return >= 0 else 'negative'}">({return_percentage:+.2f}%)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="summary-card total-trades">
            <h3>Total Trades</h3>
            <h2>{current_user['total_trades']}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Market overview section
    st.markdown("""
    <div class="chart-container">
        <h3>Market Overview</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Market indices
    col_idx1, col_idx2 = st.columns(2)
    
    with col_idx1:
        st.write("#### Major Indices")
        indices = ['SPY', 'QQQ', 'IWM', 'VTI']
        indices_data = []
        for index in indices:
            data = simulator.get_stock_price(index)
            if data:
                indices_data.append({
                    'Symbol': index,
                    'Price': f"${data['price']:.2f}",
                    'Change': f"{data['change']:+.2f}",
                    'Change %': f"{data['change_percent']:+.2f}%"
                })
        
        if indices_data:
            df_indices = pd.DataFrame(indices_data)
            st.dataframe(df_indices, use_container_width=True, hide_index=True)
    
    with col_idx2:
        st.write("#### Top Cryptocurrencies")
        crypto_major = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD']
        crypto_data = []
        for crypto in crypto_major:
            data = simulator.get_stock_price(crypto)
            if data:
                display_name = crypto.replace('-USD', '')
                crypto_data.append({
                    'Crypto': display_name,
                    'Price': f"${data['price']:.2f}",
                    'Change': f"{data['change']:+.2f}",
                    'Change %': f"{data['change_percent']:+.2f}%"
                })
        
        if crypto_data:
            df_crypto = pd.DataFrame(crypto_data)
            st.dataframe(df_crypto, use_container_width=True, hide_index=True)
    
    # Recent portfolio performance
    portfolio = simulator.db.get_user_portfolio(current_user['id'])
    if portfolio:
        st.markdown("""
        <div class="chart-container">
            <h3>Portfolio Allocation</h3>
        </div>
        """, unsafe_allow_html=True)
        
        pie_chart = simulator.create_portfolio_pie_chart(current_user['id'])
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)
    
    # Recent trades
    trades = simulator.db.get_user_trades(current_user['id'])
    if trades:
        st.markdown("""
        <div class="chart-container">
            <h3>Recent Trades</h3>
        </div>
        """, unsafe_allow_html=True)
        
        recent_trades = trades[:5]  # Show last 5 trades
        trades_data = []
        for trade in recent_trades:
            # Asset type display
            if trade['symbol'].endswith('-USD'):
                symbol_display = f"CRYPTO {trade['symbol'].replace('-USD', '')}"
            elif simulator.is_african_stock(trade['symbol']):
                symbol_display = f"AFRICAN {trade['symbol']}"
            else:
                symbol_display = f"STOCK {trade['symbol']}"
            
            trades_data.append({
                'Time': trade['timestamp'].strftime('%m/%d %H:%M'),
                'Action': 'BUY' if trade['type'] == 'BUY' else 'SELL',
                'Asset': symbol_display,
                'Shares': trade['shares'],
                'Price': f"${trade['price']:.2f}",
                'P&L': f"${trade['profit_loss']:+,.2f}" if trade['profit_loss'] != 0 else "-"
            })
        
        if trades_data:
            df_trades = pd.DataFrame(trades_data)
            st.dataframe(df_trades, use_container_width=True, hide_index=True)

def show_research_page(simulator, current_user):
    """Show research and analysis page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Research & Analysis</h2>
        <p>Professional market research tools and technical analysis</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Research mode selector
    research_mode = st.selectbox(
        "Research Mode",
        ["Single Asset Analysis", "Compare Multiple Assets", "Market Screener", "African Markets"],
        key="research_mode"
    )
    
    if research_mode == "Single Asset Analysis":
        # Asset type selector
        asset_type = st.selectbox(
            "Select Asset Type",
            ["All Assets", "Stocks & ETFs", "Cryptocurrencies", "African Markets"],
            key="asset_type_filter"
        )
        
        # Filter available assets based on selection
        if asset_type == "Stocks & ETFs":
            available_assets = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
        elif asset_type == "Cryptocurrencies":
            available_assets = [s for s in simulator.available_stocks if s.endswith('-USD')]
        elif asset_type == "African Markets":
            available_assets = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
        else:
            available_assets = simulator.available_stocks
        
        # Asset selector for analysis
        analysis_asset = st.selectbox(
            "Select Asset for Analysis",
            [''] + available_assets[:100],
            key="analysis_asset"
        )
        
        if analysis_asset:
            # Get asset info
            asset_data = simulator.get_stock_price(analysis_asset)
            if asset_data:
                # Display asset info
                col_info1, col_info2 = st.columns([2, 1])
                
                with col_info1:
                    # Asset header
                    if asset_data.get('is_crypto'):
                        asset_display_name = analysis_asset.replace('-USD', '')
                        asset_type_label = "Cryptocurrency"
                    elif asset_data.get('is_african'):
                        asset_display_name = analysis_asset
                        asset_type_label = "African Stock"
                    else:
                        asset_display_name = analysis_asset
                        asset_type_label = "Stock"
                    
                    asset_header = f"{asset_data['name']} ({asset_display_name})"
                    if asset_data.get('is_mock'):
                        asset_header += " - Live Mock Data"
                    
                    st.markdown(f"""
                    <div class="metric-card">
                        <h2>{asset_header}</h2>
                        <p><strong>Type:</strong> {asset_type_label}</p>
                        <p><strong>Sector:</strong> {asset_data.get('sector', 'N/A')}</p>
                        <p><strong>Industry:</strong> {asset_data.get('industry', 'N/A')}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_info2:
                    # Quick action buttons
                    if st.button("Quick Buy", key="research_buy", use_container_width=True):
                        st.session_state.current_page = 'Trade'
                        st.session_state.quick_trade_asset = analysis_asset
                        st.session_state.quick_trade_action = 'BUY'
                        st.rerun()
                    
                    # Check if user owns this asset
                    portfolio = simulator.db.get_user_portfolio(current_user['id'])
                    owns_asset = any(p['symbol'] == analysis_asset for p in portfolio)
                    
                    if owns_asset:
                        if st.button("Quick Sell", key="research_sell", use_container_width=True):
                            st.session_state.current_page = 'Trade'
                            st.session_state.quick_trade_asset = analysis_asset
                            st.session_state.quick_trade_action = 'SELL'
                            st.rerun()
                    else:
                        st.button("Quick Sell", key="research_sell", disabled=True, use_container_width=True, help="You don't own this asset")
                
                # Current price metrics
                col_price1, col_price2, col_price3, col_price4 = st.columns(4)
                
                with col_price1:
                    if asset_data.get('is_crypto') and asset_data['price'] < 1:
                        price_display = f"{asset_data['currency']} {asset_data['price']:.6f}"
                    else:
                        price_display = simulator.format_currency_display(asset_data['price'], asset_data['currency'])
                    st.metric("Current Price", price_display)
                
                with col_price2:
                    change_color = "normal" if asset_data['change'] >= 0 else "inverse"
                    change_display = simulator.format_currency_display(asset_data['change'], asset_data['currency'])
                    st.metric(
                        "24h Change", 
                        change_display,
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
                
                # Technical analysis chart
                st.markdown("""
                <div class="chart-container">
                    <h3>Technical Analysis</h3>
                </div>
                """, unsafe_allow_html=True)
                
                # Time period selector
                period_options = {
                    '1 Month': '1mo',
                    '3 Months': '3mo',
                    '6 Months': '6mo',
                    '1 Year': '1y',
                    '2 Years': '2y'
                }
                
                selected_period = st.selectbox(
                    "Chart Period",
                    list(period_options.keys()),
                    index=1
                )
                
                period = period_options[selected_period]
                
                with st.spinner("Loading chart..."):
                    comprehensive_chart = simulator.create_comprehensive_chart(analysis_asset, period)
                    if comprehensive_chart:
                        st.plotly_chart(comprehensive_chart, use_container_width=True)
                    else:
                        st.error("Unable to load chart data")
            else:
                st.error("Unable to load asset data")
    
    elif research_mode == "Compare Multiple Assets":
        st.write("### Asset Comparison")
        
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
                "Comparison Period",
                list(period_options.keys()),
                index=1,
                key="comparison_period"
            )
            
            period = period_options[comparison_period]
            
            # Create comparison chart
            st.markdown("""
            <div class="chart-container">
                <h3>Performance Comparison</h3>
            </div>
            """, unsafe_allow_html=True)
            
            with st.spinner("Loading comparison..."):
                comparison_chart = simulator.create_comparison_chart(comparison_assets, period)
                if comparison_chart:
                    st.plotly_chart(comparison_chart, use_container_width=True)
                else:
                    st.error("Unable to load comparison chart")
            
            # Comparison table
            st.markdown("""
            <div class="chart-container">
                <h3>Asset Comparison Table</h3>
            </div>
            """, unsafe_allow_html=True)
            
            comparison_data = []
            for asset in comparison_assets:
                asset_data = simulator.get_stock_price(asset)
                if asset_data:
                    if asset_data.get('is_crypto'):
                        display_name = asset.replace('-USD', '')
                        asset_type_label = "CRYPTO"
                    elif asset_data.get('is_african'):
                        display_name = asset
                        asset_type_label = "AFRICAN"
                    else:
                        display_name = asset
                        asset_type_label = "STOCK"
                    
                    comparison_data.append({
                        'Asset': f"{asset_type_label} {display_name}",
                        'Name': asset_data['name'][:30],
                        'Price': simulator.format_currency_display(asset_data['price'], asset_data['currency']),
                        'Change': simulator.format_currency_display(asset_data['change'], asset_data['currency']),
                        'Change %': f"{asset_data['change_percent']:+.2f}%",
                        'Volume': f"{asset_data['volume']:,}",
                        'Market Cap': f"{asset_data['currency']} {asset_data['market_cap']/1_000_000_000:.1f}B" if asset_data['market_cap'] > 1_000_000_000 else f"{asset_data['currency']} {asset_data['market_cap']/1_000_000:.1f}M" if asset_data['market_cap'] > 0 else "N/A"
                    })
            
            if comparison_data:
                df = pd.DataFrame(comparison_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
    
    elif research_mode == "Market Screener":
        st.write("### Market Screener")
        
        # Market screener filters
        col_filter1, col_filter2 = st.columns(2)
        
        with col_filter1:
            market_filter = st.selectbox(
                "Market",
                ["All Markets", "US Stocks", "Cryptocurrencies", "African Markets"],
                key="market_filter"
            )
        
        with col_filter2:
            sort_by = st.selectbox(
                "Sort By",
                ["Price", "Change %", "Volume", "Market Cap"],
                key="sort_by"
            )
        
        # Filter assets based on selection
        if market_filter == "US Stocks":
            filtered_assets = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
        elif market_filter == "Cryptocurrencies":
            filtered_assets = [s for s in simulator.available_stocks if s.endswith('-USD')]
        elif market_filter == "African Markets":
            filtered_assets = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
        else:
            filtered_assets = simulator.available_stocks
        
        # Show market data
        st.markdown("""
        <div class="chart-container">
            <h3>Market Data</h3>
        </div>
        """, unsafe_allow_html=True)
        
        screener_data = []
        with st.spinner("Loading market data..."):
            for asset in filtered_assets[:30]:  # Limit to first 30 for performance
                data = simulator.get_stock_price(asset)
                if data:
                    if data.get('is_crypto'):
                        asset_type_label = "CRYPTO"
                        display_name = asset.replace('-USD', '')
                    elif data.get('is_african'):
                        asset_type_label = "AFRICAN"
                        display_name = asset
                    else:
                        asset_type_label = "STOCK"
                        display_name = asset
                    
                    screener_data.append({
                        'Symbol': f"{asset_type_label} {display_name}",
                        'Name': data['name'][:25],
                        'Price': simulator.format_currency_display(data['price'], data['currency']),
                        'Change': simulator.format_currency_display(data['change'], data['currency']),
                        'Change %': f"{data['change_percent']:+.2f}%",
                        'Volume': f"{data['volume']:,}",
                        'Sector': data.get('sector', 'N/A')[:20]
                    })
        
        if screener_data:
            df_screener = pd.DataFrame(screener_data)
            st.dataframe(df_screener, use_container_width=True, hide_index=True)
    
    elif research_mode == "African Markets":
        st.write("### African Stock Exchanges")
        
        # African markets selector
        african_markets = simulator.get_african_markets()
        selected_african_market = st.selectbox(
            "Select African Market",
            list(african_markets.keys()),
            key="selected_african_market"
        )
        
        if selected_african_market:
            st.markdown(f"""
            <div class="chart-container">
                <h3>{selected_african_market}</h3>
            </div>
            """, unsafe_allow_html=True)
            
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
                st.dataframe(df_market, use_container_width=True, hide_index=True)
                
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

def show_trade_page(simulator, current_user):
    """Show trading page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Trade Stocks & Crypto</h2>
        <p>Execute trades with real-time market data</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick trade setup if coming from research
    if hasattr(st.session_state, 'quick_trade_asset') and st.session_state.quick_trade_asset:
        st.info(f"Quick Trade: {st.session_state.quick_trade_action} {st.session_state.quick_trade_asset}")
    
    # Trading interface
    trade_col1, trade_col2 = st.columns([2, 1])
    
    with trade_col1:
        st.markdown("""
        <div class="chart-container">
            <h3>Place Order</h3>
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
                    asset_type_label = "Cryptocurrency"
                elif asset_data.get('is_african'):
                    display_name = selected_asset
                    asset_type_label = "African Stock"
                else:
                    display_name = selected_asset
                    asset_type_label = "Stock"
                
                st.markdown(f"""
                <div class="metric-card">
                    <h3>{asset_data['name']} ({display_name})</h3>
                    <p><strong>Type:</strong> {asset_type_label}</p>
                    <p><strong>Current Price:</strong> {simulator.format_currency_display(asset_data['price'], asset_data['currency'])}</p>
                    <p><strong>24h Change:</strong> <span class="{'positive' if asset_data['change'] >= 0 else 'negative'}">{simulator.format_currency_display(asset_data['change'], asset_data['currency'])} ({asset_data['change_percent']:+.2f}%)</span></p>
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
                        # For African stocks, convert local currency price to USD for actual cost
                        if asset_data['currency'] != 'USD':
                            actual_cost_usd = simulator.convert_to_usd(asset_data['price'], asset_data['currency']) * shares
                            total_cost_local = asset_data['price'] * shares
                            cost_display = simulator.format_currency_display(total_cost_local, asset_data['currency'])
                            st.write(f"**Total Cost:** {cost_display} (commission-free trading)")
                            st.write(f"**Equivalent to:** ${actual_cost_usd:,.2f} USD")
                        else:
                            actual_cost_usd = asset_data['price'] * shares
                            st.write(f"**Total Cost:** ${actual_cost_usd:,.2f} (commission-free trading)")
                        
                        # Check if user has enough cash (in USD)
                        if actual_cost_usd > current_user['cash']:
                            st.error(f"Insufficient funds! You need ${actual_cost_usd:,.2f} USD but only have ${current_user['cash']:,.2f} USD")
                            can_trade = False
                        else:
                            can_trade = True
                    
                    else:  # SELL
                        portfolio = simulator.db.get_user_portfolio(current_user['id'])
                        owned_position = next((p for p in portfolio if p['symbol'] == selected_asset), None)
                        
                        if owned_position and owned_position['shares'] >= shares:
                            # For African stocks, convert local currency price to USD for actual proceeds
                            if asset_data['currency'] != 'USD':
                                actual_proceeds_usd = simulator.convert_to_usd(asset_data['price'], asset_data['currency']) * shares
                                total_proceeds_local = asset_data['price'] * shares
                                proceeds_display = simulator.format_currency_display(total_proceeds_local, asset_data['currency'])
                                
                                # Convert average price back to local currency for display
                                avg_price_local = simulator.convert_from_usd(owned_position['avg_price'], asset_data['currency'])
                                avg_price_display = simulator.format_currency_display(avg_price_local, asset_data['currency'])
                                
                                profit_loss_usd = actual_proceeds_usd - (owned_position['avg_price'] * shares)
                                
                                st.write(f"**Owned Shares:** {owned_position['shares']}")
                                st.write(f"**Average Price:** {avg_price_display}")
                                st.write(f"**Total Proceeds:** {proceeds_display} (commission-free trading)")
                                st.write(f"**Equivalent to:** ${actual_proceeds_usd:,.2f} USD")
                            else:
                                actual_proceeds_usd = asset_data['price'] * shares
                                profit_loss_usd = (asset_data['price'] - owned_position['avg_price']) * shares
                                
                                st.write(f"**Owned Shares:** {owned_position['shares']}")
                                st.write(f"**Average Price:** ${owned_position['avg_price']:.2f}")
                                st.write(f"**Total Proceeds:** ${actual_proceeds_usd:,.2f} (commission-free trading)")
                            
                            profit_color = "positive" if profit_loss_usd >= 0 else "negative"
                            st.markdown(f"**Estimated P&L:** <span class='{profit_color}'>${profit_loss_usd:+,.2f} USD</span>", unsafe_allow_html=True)
                            
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
                                # Pass the USD price for internal storage
                                simulator.convert_to_usd(asset_data['price'], asset_data['currency']) if asset_data['currency'] != 'USD' else asset_data['price'],
                                asset_data['name'],
                                asset_data['currency'],
                                # Pass the original local currency price for display purposes
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
        st.markdown("""
        <div class="chart-container">
            <h3>Market Movers</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Show some trending assets
        trending_assets = ['AAPL', 'TSLA', 'BTC-USD', 'ETH-USD', 'MTNGH.AC', 'SAFCOM.NR']
        
        for asset in trending_assets:
            data = simulator.get_stock_price(asset)
            if data:
                if data.get('is_crypto'):
                    display_name = asset.replace('-USD', '')
                    asset_type_label = "CRYPTO"
                elif data.get('is_african'):
                    display_name = asset
                    asset_type_label = "AFRICAN"
                else:
                    display_name = asset
                    asset_type_label = "STOCK"
                
                change_class = "positive" if data['change'] >= 0 else "negative"
                
                st.markdown(f"""
                <div class="metric-card">
                    <p><strong>{asset_type_label} {display_name}</strong></p>
                    <p>{simulator.format_currency_display(data['price'], data['currency'])} <span class="{change_class}">({data['change_percent']:+.2f}%)</span></p>
                </div>
                """, unsafe_allow_html=True)

def show_portfolio_page(simulator, current_user):
    """Show portfolio management page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Portfolio Management</h2>
        <p>Track your investments and portfolio performance</p>
    </div>
    """, unsafe_allow_html=True)
    
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
        st.markdown("""
        <div class="chart-container">
            <h3>Portfolio Allocation</h3>
        </div>
        """, unsafe_allow_html=True)
        
        pie_chart = simulator.create_portfolio_pie_chart(current_user['id'])
        if pie_chart:
            st.plotly_chart(pie_chart, use_container_width=True)
        else:
            st.info("No portfolio positions to display")
    
    # Holdings table
    st.markdown("""
    <div class="chart-container">
        <h3>Current Holdings</h3>
    </div>
    """, unsafe_allow_html=True)
    
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
                
                # Asset type label
                if current_data.get('is_crypto'):
                    asset_type_label = "CRYPTO"
                elif current_data.get('is_african'):
                    asset_type_label = "AFRICAN"
                else:
                    asset_type_label = "STOCK"
                
                # For African stocks, convert USD stored prices back to local currency for display
                if current_data.get('is_african') and current_data['currency'] != 'USD':
                    # Convert average price from USD to local currency
                    avg_price_local = simulator.convert_from_usd(position['avg_price'], current_data['currency'])
                    avg_price_display = simulator.format_currency_display(avg_price_local, current_data['currency'])
                    
                    # Current price is already in local currency
                    current_price_display = simulator.format_currency_display(current_data['price'], current_data['currency'])
                    
                    # Calculate market value: current USD value for accurate P&L, local currency for display
                    current_value_usd = simulator.convert_to_usd(current_data['price'], current_data['currency']) * position['shares']
                    current_value_local = current_data['price'] * position['shares']
                    market_value_display = f"{simulator.format_currency_display(current_value_local, current_data['currency'])} (${current_value_usd:,.2f})"
                    
                    # Calculate P&L in USD for accuracy
                    unrealized_pl_usd = current_value_usd - (position['avg_price'] * position['shares'])
                    unrealized_pl_percent_usd = (unrealized_pl_usd / (position['avg_price'] * position['shares'])) * 100 if position['avg_price'] > 0 else 0
                    
                    # Calculate P&L in local currency for display
                    invested_value_local = avg_price_local * position['shares']
                    unrealized_pl_local = current_value_local - invested_value_local
                    
                    holdings_data.append({
                        'Asset': f"{asset_type_label} {position['symbol']}",
                        'Company': position['name'][:25],
                        'Shares': position['shares'],
                        'Avg Price': avg_price_display,
                        'Current Price': current_price_display,
                        'Market Value': market_value_display,
                        'Unrealized P&L': f"{simulator.format_currency_display(unrealized_pl_local, current_data['currency'])} (${unrealized_pl_usd:+,.2f})",
                        'P&L %': f"{unrealized_pl_percent_usd:+.2f}%"
                    })
                else:
                    # For USD assets (US stocks, crypto)
                    holdings_data.append({
                        'Asset': f"{asset_type_label} {position['symbol']}",
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
        st.info("Your portfolio is empty. Start trading to build your portfolio!")

def show_history_page(simulator, current_user):
    """Show trade history page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Trade History</h2>
        <p>Review your trading activity and performance</p>
    </div>
    """, unsafe_allow_html=True)
    
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
        st.markdown("""
        <div class="chart-container">
            <h3>Trade History</h3>
        </div>
        """, unsafe_allow_html=True)
        
        trades_data = []
        for trade in trades[:100]:  # Show last 100 trades
            # Asset type label
            if trade['symbol'].endswith('-USD'):
                asset_type_label = "CRYPTO"
                is_african = False
                currency = 'USD'
            elif simulator.is_african_stock(trade['symbol']):
                asset_type_label = "AFRICAN"
                is_african = True
                currency = simulator.get_currency_symbol(trade['symbol'])
            else:
                asset_type_label = "STOCK"
                is_african = False
                currency = 'USD'
            
            # Use the original_price if available, otherwise convert from USD stored price
            if trade.get('original_price') and trade['original_currency'] != 'USD':
                # Use the original local currency price that was stored
                price_display = simulator.format_currency_display(trade['original_price'], trade['original_currency'])
                total_display = simulator.format_currency_display(trade['original_price'] * trade['shares'], trade['original_currency'])
            elif is_african and currency != 'USD':
                # Convert USD stored prices back to local currency for display
                trade_price_local = simulator.convert_from_usd(trade['price'], currency)
                price_display = simulator.format_currency_display(trade_price_local, currency)
                
                total_cost_local = simulator.convert_from_usd(trade['total_cost'], currency)
                total_display = simulator.format_currency_display(total_cost_local, currency)
            else:
                # For USD assets
                price_display = f"${trade['price']:.2f}"
                total_display = f"${trade['total_cost']:,.2f}"
            
            trades_data.append({
                'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'Type': 'BUY' if trade['type'] == 'BUY' else 'SELL',
                'Asset': f"{asset_type_label} {trade['symbol']}",
                'Company': trade['name'][:20],
                'Shares': trade['shares'],
                'Price': price_display,
                'Total': total_display,
                'Commission': "$0.00",
                'P&L': f"${trade['profit_loss']:+,.2f} USD" if trade['profit_loss'] != 0 else "-"
            })
        
        if trades_data:
            df_trades = pd.DataFrame(trades_data)
            st.dataframe(df_trades, use_container_width=True, hide_index=True)
    else:
        st.info("No trades yet. Start trading to see your history!")

def show_leaderboard_page(simulator, current_user):
    """Show leaderboard page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Leaderboard</h2>
        <p>Compete with other traders and track your ranking</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get leaderboard data
    leaderboard = simulator.db.get_leaderboard()
    
    if leaderboard:
        st.markdown("""
        <div class="chart-container">
            <h3>Top Traders</h3>
        </div>
        """, unsafe_allow_html=True)
        
        leaderboard_data = []
        for i, player in enumerate(leaderboard[:20]):  # Top 20 players
            # Determine rank display
            if player['rank'] == 1:
                rank_display = "1st"
            elif player['rank'] == 2:
                rank_display = "2nd"
            elif player['rank'] == 3:
                rank_display = "3rd"
            else:
                rank_display = f"{player['rank']}th"
            
            # Highlight current user
            username_display = player['username']
            if player['user_id'] == current_user['id']:
                username_display = f"YOU - {username_display}"
            
            leaderboard_data.append({
                'Rank': rank_display,
                'Trader': username_display,
                'Portfolio Value': f"${player['portfolio_value']:,.2f}",
                'Cash': f"${player['cash']:,.2f}",
                'Total Trades': player['total_trades'],
                'P&L': f"${player['total_profit_loss']:+,.2f}"
            })
        
        df_leaderboard = pd.DataFrame(leaderboard_data)
        st.dataframe(df_leaderboard, use_container_width=True, hide_index=True)
        
        # Current user stats
        current_user_rank = next((p['rank'] for p in leaderboard if p['user_id'] == current_user['id']), None)
        if current_user_rank:
            st.info(f"Your current rank: #{current_user_rank} out of {len(leaderboard)} traders")
    else:
        st.info("No leaderboard data available")

def show_account_page(simulator, current_user):
    """Show account information page"""
    st.markdown("""
    <div class="page-header page-content">
        <h2>Account Information</h2>
        <p>Manage your account settings and view trading statistics</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Account overview
    col_acc1, col_acc2 = st.columns(2)
    
    with col_acc1:
        st.markdown("""
        <div class="chart-container">
            <h3>Account Overview</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Username:** {current_user['username']}")
        st.write(f"**Email:** {current_user['email']}")
        st.write(f"**Member Since:** {current_user['created_at']}")
        st.write(f"**Last Login:** {current_user['last_login'] or 'Never'}")
    
    with col_acc2:
        st.markdown("""
        <div class="chart-container">
            <h3>Trading Statistics</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"**Total Trades:** {current_user['total_trades']}")
        st.write(f"**Total P&L:** ${current_user['total_profit_loss']:+,.2f}")
        st.write(f"**Best Trade:** ${current_user['best_trade']:+,.2f}")
        st.write(f"**Worst Trade:** ${current_user['worst_trade']:+,.2f}")
    
    # Exchange rates status
    st.markdown("""
    <div class="chart-container">
        <h3>Exchange Rates Information</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Update exchange rates and show current info
    simulator.update_exchange_rates()
    
    col_fx1, col_fx2 = st.columns(2)
    
    with col_fx1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Rate Source</h4>
            <p>{st.session_state.get('exchange_rates_source', 'Not loaded')}</p>
            <small>Last updated: {st.session_state.get('exchange_rates_last_update', 'Never')}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col_fx2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Update Frequency</h4>
            <p>Every 30 minutes</p>
            <small>Multiple API fallbacks</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Current exchange rates
    st.write("#### Current Exchange Rates (1 USD =)")
    rates_data = []
    for currency, rate in st.session_state.exchange_rates.items():
        if currency != 'USD':
            rates_data.append({
                'Currency': currency,
                'Rate': f"{rate:.2f}",
                'Example': f"$100 = {simulator.format_currency_display(rate * 100, currency)}"
            })
    
    if rates_data:
        df_rates = pd.DataFrame(rates_data)
        st.dataframe(df_rates, use_container_width=True, hide_index=True)
    
    # Game settings
    st.markdown("""
    <div class="chart-container">
        <h3>Game Settings</h3>
    </div>
    """, unsafe_allow_html=True)
    
    settings = st.session_state.game_settings
    
    col_set1, col_set2, col_set3 = st.columns(3)
    
    with col_set1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Starting Cash</h4>
            <p>${settings['starting_cash']:,.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_set2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Commission</h4>
            <p>$0.00 per trade (Commission-Free!)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_set3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>Game Duration</h4>
            <p>{settings['game_duration_days']} days</p>
        </div>
        """, unsafe_allow_html=True)
    
    # About section
    st.markdown("""
    <div class="chart-container">
        <h3>About Leo's Trader</h3>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    **Leo's Trader** is a comprehensive trading simulation platform that allows you to:
    
    - **Trade Real Stocks**: Practice with live market data from major US exchanges
    - **Cryptocurrency Trading**: Trade major cryptocurrencies with real-time prices
    - **African Markets**: Explore opportunities in Ghana, Kenya, Nigeria, South Africa, and Egypt
    - **Technical Analysis**: Use advanced charting tools and indicators
    - **Compete**: Join the leaderboard and compete with other traders
    - **Learn**: Risk-free environment to learn trading strategies
    
    **Features:**
    - Real-time market data for stocks and crypto
    - Live mock data for African stock exchanges
    - Portfolio management and tracking
    - Comprehensive trade history
    - Technical analysis charts
    - Multi-currency support
    
    **Proudly developed in Ghana** to promote financial literacy and trading education across Africa and beyond.
    """)

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
        
        # Calculate portfolio metrics for sidebar
        portfolio_value = simulator.get_portfolio_value(current_user['id'])
        total_return = portfolio_value - st.session_state.game_settings['starting_cash']
        return_percentage = (total_return / st.session_state.game_settings['starting_cash']) * 100
        
        # Sidebar Navigation
        with st.sidebar:
            # Modern Sidebar Header with Company Info
            st.markdown(f"""
            <div class="sidebar-header">
                <div class="company-avatar">LT</div>
                <div class="company-info">
                    <h4>Leo's Trader</h4>
                    <p>Trading Simulator</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Enhanced User Info Card with Portfolio Data
            st.markdown(f"""
            <div class="sidebar-user-info">
                <h4>Welcome, {current_user['username']}</h4>
                <p>Cash: ${current_user['cash']:,.2f}</p>
                <p>Total Trades: {current_user['total_trades']}</p>
                <div class="portfolio-summary">
                    <div class="portfolio-item">
                        <span>Portfolio Value:</span>
                        <span class="portfolio-value">${portfolio_value:,.2f}</span>
                    </div>
                    <div class="portfolio-item">
                        <span>Total Return:</span>
                        <span class="portfolio-value {'positive' if total_return >= 0 else 'negative'}">${total_return:+,.2f}</span>
                    </div>
                    <div class="portfolio-item">
                        <span>Return %:</span>
                        <span class="portfolio-value {'positive' if return_percentage >= 0 else 'negative'}">{return_percentage:+.2f}%</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Modern Navigation Menu
            st.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)
            
            # Navigation buttons with icons
            pages = {
                "🏠 Dashboard": "Dashboard",
                "📊 Research": "Research", 
                "💼 Trade": "Trade",
                "📈 Portfolio": "Portfolio",
                "📋 History": "History",
                "🏆 Leaderboard": "Leaderboard",
                "⚙️ Account": "Account"
            }
            
            # Create navigation buttons
            for page_name, page_key in pages.items():
                if st.button(page_name, key=f"nav_{page_key}", use_container_width=True):
                    st.session_state.current_page = page_key
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # User Profile Section
            user_initial = current_user['username'][0].upper() if current_user['username'] else 'U'
            st.markdown(f"""
            <div class="user-profile">
                <div class="user-avatar">{user_initial}</div>
                <div class="user-info">
                    <h5>{current_user['username']}</h5>
                    <p>{current_user['email']}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Logout button
            st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
            if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Ghana Pride Section - Modernized
            st.markdown("""
            <div class="ghana-pride-sidebar">
                <h4>🇬🇭 Proudly Made in Ghana</h4>
                <p>Gateway to Africa</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Main Content Area
        # Header with title only (no navigation)
        st.markdown("""
        <div class="trading-header">
            <h1>Leo's Trader</h1>
            <p>Professional Trading Simulator - Master the Markets</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show selected page
        current_page = st.session_state.get('current_page', 'Dashboard')
        
        if current_page == 'Dashboard':
            show_dashboard(simulator, current_user)
        elif current_page == 'Research':
            show_research_page(simulator, current_user)
        elif current_page == 'Trade':
            show_trade_page(simulator, current_user)
        elif current_page == 'Portfolio':
            show_portfolio_page(simulator, current_user)
        elif current_page == 'History':
            show_history_page(simulator, current_user)
        elif current_page == 'Leaderboard':
            show_leaderboard_page(simulator, current_user)
        elif current_page == 'Account':
            show_account_page(simulator, current_user)
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please refresh the page and try again.")

if __name__ == "__main__":
    main()
