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
    
    def execute_trade(self, user_id: str, symbol: str, action: str, shares: int, price: float, stock_name: str) -> Dict:
        """Execute a trade and update database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get commission from settings
            cursor.execute('SELECT commission FROM game_settings ORDER BY id DESC LIMIT 1')
            commission = cursor.fetchone()[0]
            
            # Get current user data
            cursor.execute('SELECT cash FROM users WHERE id = ?', (user_id,))
            current_cash = cursor.fetchone()[0]
            
            total_cost = (price * shares) + commission
            
            if action.upper() == 'BUY':
                if current_cash < total_cost:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient funds'}
                
                # Update cash
                new_cash = current_cash - total_cost
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
                # Update portfolio
                cursor.execute('''
                    SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?
                ''', (user_id, symbol))
                
                existing = cursor.fetchone()
                if existing:
                    old_shares, old_avg_price = existing
                    new_shares = old_shares + shares
                    new_avg_price = ((old_shares * old_avg_price) + (shares * price)) / new_shares
                    
                    cursor.execute('''
                        UPDATE portfolio SET shares = ?, avg_price = ?, stock_name = ?
                        WHERE user_id = ? AND symbol = ?
                    ''', (new_shares, new_avg_price, stock_name, user_id, symbol))
                else:
                    cursor.execute('''
                        INSERT INTO portfolio (user_id, symbol, shares, avg_price, stock_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, symbol, shares, price, stock_name))
                
                # Record trade
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price, total_cost, commission, stock_name))
                
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
                
                owned_shares, avg_price = existing
                
                # Calculate profit/loss
                profit_loss = (price - avg_price) * shares - commission
                
                # Update cash
                total_proceeds = (price * shares) - commission
                new_cash = current_cash + total_proceeds
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
                
                # Record trade
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, profit_loss, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price, total_proceeds, commission, profit_loss, stock_name))
                
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
        """Get current stock/crypto price and info with error handling"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            
            if hist.empty:
                return None
                
            info = ticker.info
            
            current_price = hist['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            if prev_close == 0:
                prev_close = current_price
                
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
            
            # Determine asset type
            is_crypto = symbol.endswith('-USD')
            is_african = _self.is_african_stock(symbol)
            
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
                'country': _self.get_african_country_from_symbol(symbol) if is_african else None,
                'last_updated': datetime.now()
            }
        except Exception as e:
            st.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
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
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                st.warning(f"No data available for {symbol} for the selected period")
                return None
            
            # Create subplots
            fig = go.Figure()
            
            # Determine asset type
            is_crypto = symbol.endswith('-USD')
            is_african = self.is_african_stock(symbol)
            
            if is_crypto:
                display_name = symbol.replace('-USD', '')
                asset_type = "Cryptocurrency"
                asset_icon = "🪙"
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
            
            # Price formatting
            if (is_crypto and hist['Close'].iloc[-1] < 1) or (is_african and hist['Close'].iloc[-1] < 10):
                price_format = ".6f"
            else:
                price_format = ".2f"
            
            # Update layout
            fig.update_layout(
                title=f"{asset_icon} {display_name} - {asset_type} Technical Analysis ({period})",
                yaxis_title="Price ($)",
                xaxis_title="Date",
                template="plotly_white",
                height=600,
                showlegend=True,
                yaxis=dict(
                    tickformat=f"${price_format}",
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
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if not hist.empty:
                    # Normalize prices to percentage change from start
                    normalized_prices = ((hist['Close'] / hist['Close'].iloc[0]) - 1) * 100
                    
                    # Get display name based on asset type
                    if symbol.endswith('-USD'):
                        display_name = symbol.replace('-USD', '')
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
                            
                            # Asset header
                            st.markdown(f"""
                            <div class="metric-card">
                                <h2>{asset_type_icon} {asset_data['name']} ({asset_display_name})</h2>
                                <p><strong>Sector:</strong> {asset_data['sector']}</p>
                                <p><strong>Industry:</strong> {asset_data['industry']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Current price metrics
                            col_price1, col_price2, col_price3, col_price4 = st.columns(4)
                            
                            with col_price1:
                                if asset_data.get('is_crypto') and asset_data['price'] < 1:
                                    price_display = f"${asset_data['price']:.6f}"
                                else:
                                    price_display = f"${asset_data['price']:.2f}"
                                st.metric("Current Price", price_display)
                            
                            with col_price2:
                                change_color = "normal" if asset_data['change'] >= 0 else "inverse"
                                st.metric(
                                    "24h Change", 
                                    f"${asset_data['change']:+.2f}",
                                    f"{asset_data['change_percent']:+.2f}%",
                                    delta_color=change_color
                                )
                            
                            with col_price3:
                                st.metric("Volume", f"{asset_data['volume']:,}")
                            
                            with col_price4:
                                if asset_data['market_cap'] > 0:
                                    if asset_data['market_cap'] > 1_000_000_000:
                                        cap_display = f"${asset_data['market_cap']/1_000_000_000:.1f}B"
                                    else:
                                        cap_display = f"${asset_data['market_cap']/1_000_000:.1f}M"
                                    st.metric("Market Cap", cap_display)
                                else:
                                    st.metric("Market Cap", "N/A")
                            
                            # Additional metrics
                            col_info1, col_info2, col_info3 = st.columns(3)
                            with col_info1:
                                st.metric("Day High", f"${asset_data['day_high']:.2f}")
                            with col_info2:
                                st.metric("Day Low", f"${asset_data['day_low']:.2f}")
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
                                    'Price': f"${asset_data['price']:.2f}",
                                    'Change': f"{asset_data['change']:+.2f}",
                                    'Change %': f"{asset_data['change_percent']:+.2f}%",
                                    'Volume': f"{asset_data['volume']:,}",
                                    'Market Cap': f"${asset_data['market_cap']/1_000_000_000:.1f}B" if asset_data['market_cap'] > 1_000_000_000 else f"${asset_data['market_cap']/1_000_000:.1f}M" if asset_data['market_cap'] > 0 else "N/A"
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
                                'Crypto': display_name,
                                'Name': data['name'],
                                'Price': f"${data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%"
                            })
                    
                    if crypto_data:
                        df_crypto = pd.DataFrame(crypto_data)
                        st.dataframe(df_crypto, use_container_width=True)
                    
                    # African markets overview
                    st.write("#### 🌍 Major African Stocks")
                    african_data = []
                    for african in african_major:
                        data = simulator.get_stock_price(african)
                        if data:
                            country = simulator.get_african_country_from_symbol(african)
                            african_data.append({
                                'Stock': african,
                                'Country': country,
                                'Name': data['name'][:30],
                                'Price': f"${data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%"
                            })
                    
                    if african_data:
                        df_african = pd.DataFrame(african_data)
                        st.dataframe(df_african, use_container_width=True)
                    
                    # Market comparison chart
                    st.write("#### 📊 Market Comparison")
                    market_assets = indices + crypto_major + african_major
                    
                    with st.spinner("Loading market comparison..."):
                        market_chart = simulator.create_comparison_chart(market_assets, "3mo")
                        if market_chart:
                            st.plotly_chart(market_chart, use_container_width=True)
                
                elif research_mode == "🌍 African Markets":
                    st.write("### 🌍 African Markets Research")
                    
                    african_markets = simulator.get_african_markets()
                    
                    # African market selector
                    selected_african_market = st.selectbox(
                        "Select African Market",
                        list(african_markets.keys()),
                        key="african_market_selector"
                    )
                    
                    market_stocks = african_markets[selected_african_market]
                    
                    # Market overview
                    st.markdown(f"""
                    <div class="african-card">
                        <h3>{selected_african_market}</h3>
                        <p>📊 {len(market_stocks)} stocks available for trading</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Top stocks from selected market
                    st.write(f"#### 📈 Top Stocks from {selected_african_market}")
                    
                    market_data = []
                    for stock in market_stocks[:20]:  # Show top 20
                        data = simulator.get_stock_price(stock)
                        if data:
                            market_data.append({
                                'Symbol': stock,
                                'Company': data['name'][:40],
                                'Price': f"${data['price']:.2f}",
                                'Change': f"{data['change']:+.2f}",
                                'Change %': f"{data['change_percent']:+.2f}%",
                                'Volume': f"{data['volume']:,}",
                                'Sector': data['industry'][:20]
                            })
                    
                    if market_data:
                        df_market = pd.DataFrame(market_data)
                        st.dataframe(df_market, use_container_width=True)
                    
                    # African market comparison chart
                    st.write("#### 📊 African Market Performance Comparison")
                    
                    # Select representative stocks from each market
                    african_comparison = []
                    for market_name, stocks in african_markets.items():
                        if stocks:
                            african_comparison.append(stocks[0])  # Take first stock from each market
                    
                    if african_comparison:
                        with st.spinner("Loading African market comparison..."):
                            african_chart = simulator.create_comparison_chart(african_comparison, "3mo")
                            if african_chart:
                                st.plotly_chart(african_chart, use_container_width=True)
                    
                    # African market insights
                    st.write("#### 💡 African Market Insights")
                    st.info("""
                    **🌍 African Markets Overview:**
                    - **Ghana (GSE)**: Emerging market with strong banking and mining sectors
                    - **South Africa (JSE)**: Most developed African market with large cap stocks
                    - **Kenya (NSE)**: Fast-growing market with strong telecom and banking sectors
                    - **Nigeria (NGX)**: Largest economy in Africa with diversified sectors
                    - **Egypt (EGX)**: Strategic location connecting Africa, Middle East, and Europe
                    
                    **💰 Trading Tips:**
                    - African markets may have different trading hours
                    - Consider currency fluctuations when trading
                    - Research local economic conditions and political stability
                    - Diversify across different African countries and sectors
                    """)
            
            with tab2:
                st.subheader("🛒 Trade Stocks, Cryptocurrencies & African Markets")
                
                # Check for quick trade from research tab
                if 'quick_trade_asset' in st.session_state and st.session_state.quick_trade_asset:
                    if st.session_state.quick_trade_asset.endswith('-USD'):
                        asset_display = st.session_state.quick_trade_asset.replace('-USD', '')
                    else:
                        asset_display = st.session_state.quick_trade_asset
                    st.info(f"🎯 Quick Trade: {st.session_state.quick_trade_action} {asset_display}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### 📈 Buy Assets")
                    
                    # Asset type filter for buying
                    buy_asset_type = st.selectbox(
                        "Asset Type",
                        ["All Assets", "Stocks & ETFs", "Cryptocurrencies", "🌍 African Markets"],
                        key="buy_asset_type"
                    )
                    
                    # Filter assets
                    if buy_asset_type == "Stocks & ETFs":
                        buy_options = [s for s in simulator.available_stocks if not s.endswith('-USD') and not simulator.is_african_stock(s)]
                    elif buy_asset_type == "Cryptocurrencies":
                        buy_options = [s for s in simulator.available_stocks if s.endswith('-USD')]
                    elif buy_asset_type == "🌍 African Markets":
                        buy_options = [s for s in simulator.available_stocks if simulator.is_african_stock(s)]
                    else:
                        buy_options = simulator.available_stocks
                    
                    # Pre-select asset from research tab if available
                    buy_asset_options = [''] + buy_options[:100]
                    default_buy_index = 0
                    
                    if 'quick_trade_asset' in st.session_state and st.session_state.quick_trade_asset in buy_asset_options:
                        if st.session_state.get('quick_trade_action') == 'BUY':
                            default_buy_index = buy_asset_options.index(st.session_state.quick_trade_asset)
                    
                    selected_asset = st.selectbox(
                        "Select Asset",
                        buy_asset_options,
                        key="buy_asset",
                        index=default_buy_index
                    )
                    
                    if selected_asset:
                        asset_data = simulator.get_stock_price(selected_asset)
                        if asset_data:
                            # Display asset info
                            if asset_data.get('is_crypto'):
                                asset_display_name = selected_asset.replace('-USD', '')
                                asset_type_icon = "🪙"
                            elif asset_data.get('is_african'):
                                asset_display_name = selected_asset
                                asset_type_icon = "🌍"
                            else:
                                asset_display_name = selected_asset
                                asset_type_icon = "📈"
                            
                            st.write(f"{asset_type_icon} **{asset_data['name']}**")
                            
                            # Show country for African stocks
                            if asset_data.get('is_african'):
                                country = simulator.get_african_country_from_symbol(selected_asset)
                                st.write(f"**Country:** {country}")
                            
                            # Format price display
                            if asset_data.get('is_crypto') and asset_data['price'] < 1:
                                price_display = f"${asset_data['price']:.6f}"
                            else:
                                price_display = f"${asset_data['price']:.2f}"
                            st.write(f"**Current Price:** {price_display}")
                            
                            change_class = "positive" if asset_data['change'] >= 0 else "negative"
                            st.markdown(f"**Change:** <span class='{change_class}'>${asset_data['change']:+.2f} ({asset_data['change_percent']:+.2f}%)</span>", unsafe_allow_html=True)
                            
                            # Shares/Units input
                            unit_label = "Amount" if asset_data.get('is_crypto') else "Shares"
                            if asset_data.get('is_crypto'):
                                buy_amount = st.number_input(f"Number of {asset_display_name}", min_value=0.000001, value=1.0, step=0.1, format="%.6f", key="buy_amount")
                            else:
                                buy_amount = st.number_input("Number of Shares", min_value=1, value=1, key="buy_shares")
                            
                            total_cost = (asset_data['price'] * buy_amount) + st.session_state.game_settings['commission']
                            
                            st.write(f"**Total Cost:** ${total_cost:.2f}")
                            st.write(f"**Available Cash:** ${current_user['cash']:,.2f}")
                            
                            buy_button_text = f"🛒 Buy {asset_display_name}"
                            if st.button(buy_button_text, key="buy_button"):
                                result = simulator.db.execute_trade(
                                    current_user['id'], 
                                    selected_asset, 
                                    'BUY', 
                                    buy_amount, 
                                    asset_data['price'], 
                                    asset_data['name']
                                )
                                if result['success']:
                                    st.success(result['message'])
                                    # Clear quick trade
                                    if 'quick_trade_asset' in st.session_state:
                                        del st.session_state.quick_trade_asset
                                        del st.session_state.quick_trade_action
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                
                with col2:
                    st.write("### 📉 Sell Assets")
                    
                    portfolio = simulator.db.get_user_portfolio(current_user['id'])
                    
                    if portfolio:
                        owned_assets = [''] + [p['symbol'] for p in portfolio]
                        default_sell_index = 0
                        
                        # Pre-select asset from research tab if available
                        if 'quick_trade_asset' in st.session_state and st.session_state.quick_trade_asset in owned_assets:
                            if st.session_state.get('quick_trade_action') == 'SELL':
                                default_sell_index = owned_assets.index(st.session_state.quick_trade_asset)
                        
                        selected_sell_asset = st.selectbox(
                            "Select Asset to Sell",
                            owned_assets,
                            key="sell_asset",
                            index=default_sell_index
                        )
                        
                        if selected_sell_asset:
                            position = next((p for p in portfolio if p['symbol'] == selected_sell_asset), None)
                            asset_data = simulator.get_stock_price(selected_sell_asset)
                            
                            if asset_data and position:
                                # Display asset info
                                if asset_data.get('is_crypto'):
                                    asset_display_name = selected_sell_asset.replace('-USD', '')
                                    asset_type_icon = "🪙"
                                elif asset_data.get('is_african'):
                                    asset_display_name = selected_sell_asset
                                    asset_type_icon = "🌍"
                                else:
                                    asset_display_name = selected_sell_asset
                                    asset_type_icon = "📈"
                                
                                st.write(f"{asset_type_icon} **{asset_data['name']}**")
                                
                                # Show country for African stocks
                                if asset_data.get('is_african'):
                                    country = simulator.get_african_country_from_symbol(selected_sell_asset)
                                    st.write(f"**Country:** {country}")
                                
                                # Units owned
                                unit_label = "Amount" if asset_data.get('is_crypto') else "Shares"
                                if asset_data.get('is_crypto'):
                                    st.write(f"**{unit_label} Owned:** {position['shares']:.6f}")
                                else:
                                    st.write(f"**{unit_label} Owned:** {position['shares']}")
                                
                                # Prices
                                st.write(f"**Average Price:** ${position['avg_price']:.6f}" if asset_data.get('is_crypto') and position['avg_price'] < 1 else f"**Average Price:** ${position['avg_price']:.2f}")
                                st.write(f"**Current Price:** ${asset_data['price']:.6f}" if asset_data.get('is_crypto') and asset_data['price'] < 1 else f"**Current Price:** ${asset_data['price']:.2f}")
                                
                                # Show unrealized P&L
                                unrealized_pl = (asset_data['price'] - position['avg_price']) * position['shares']
                                pl_color = "positive" if unrealized_pl >= 0 else "negative"
                                st.markdown(f"**Unrealized P&L:** <span class='{pl_color}'>${unrealized_pl:+.2f}</span>", unsafe_allow_html=True)
                                
                                # Amount to sell
                                if asset_data.get('is_crypto'):
                                    sell_amount = st.number_input(
                                        f"{unit_label} to Sell", 
                                        min_value=0.000001, 
                                        max_value=float(position['shares']), 
                                        value=min(1.0, float(position['shares'])),
                                        step=0.1,
                                        format="%.6f",
                                        key="sell_amount"
                                    )
                                else:
                                    sell_amount = st.number_input(
                                        f"{unit_label} to Sell", 
                                        min_value=1, 
                                        max_value=position['shares'], 
                                        value=1,
                                        key="sell_shares"
                                    )
                                
                                total_proceeds = (asset_data['price'] * sell_amount) - st.session_state.game_settings['commission']
                                expected_pl = (asset_data['price'] - position['avg_price']) * sell_amount - st.session_state.game_settings['commission']
                                
                                st.write(f"**Total Proceeds:** ${total_proceeds:.2f}")
                                pl_color = "positive" if expected_pl >= 0 else "negative"
                                st.markdown(f"**Expected P&L:** <span class='{pl_color}'>${expected_pl:+.2f}</span>", unsafe_allow_html=True)
                                
                                sell_button_text = f"💰 Sell {asset_display_name}"
                                if st.button(sell_button_text, key="sell_button"):
                                    result = simulator.db.execute_trade(
                                        current_user['id'], 
                                        selected_sell_asset, 
                                        'SELL', 
                                        sell_amount, 
                                        asset_data['price'], 
                                        asset_data['name']
                                    )
                                    if result['success']:
                                        st.success(result['message'])
                                        if result['profit_loss'] != 0:
                                            if result['profit_loss'] > 0:
                                                st.success(f"💰 Profit: ${result['profit_loss']:+.2f}")
                                            else:
                                                st.error(f"📉 Loss: ${result['profit_loss']:+.2f}")
                                        # Clear quick trade
                                        if 'quick_trade_asset' in st.session_state:
                                            del st.session_state.quick_trade_asset
                                            del st.session_state.quick_trade_action
                                        st.rerun()
                                    else:
                                        st.error(result['message'])
                    else:
                        st.info("You don't own any assets yet!")
            
            with tab3:
                st.subheader("📊 Your Portfolio")
                
                portfolio = simulator.db.get_user_portfolio(current_user['id'])
                
                if portfolio:
                    # Portfolio summary
                    summary = simulator.get_portfolio_summary(current_user['id'])
                    
                    if summary:
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("💰 Cash", f"${summary['cash']:,.2f}")
                        with col2:
                            st.metric("📊 Invested", f"${summary['total_invested']:,.2f}")
                        with col3:
                            st.metric("📈 Current Value", f"${summary['total_current_value']:,.2f}")
                        with col4:
                            pl_delta = summary['total_unrealized_pl']
                            st.metric("💸 Unrealized P&L", f"${pl_delta:+,.2f}", delta=f"{pl_delta:+,.2f}")
                    
                    # Portfolio visualization
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown("""
                        <div class="chart-container">
                            <h3>🥧 Portfolio Allocation</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        pie_chart = simulator.create_portfolio_pie_chart(current_user['id'])
                        if pie_chart:
                            st.plotly_chart(pie_chart, use_container_width=True)
                        else:
                            st.info("No portfolio data available for chart")
                    
                    with col2:
                        st.write("### 📋 Holdings Summary")
                        if summary:
                            st.write(f"**Total Holdings:** {summary['holdings_count']}")
                            st.write(f"**Portfolio Value:** ${summary['total_portfolio_value']:,.2f}")
                            
                            # Calculate allocation percentages
                            if summary['total_portfolio_value'] > 0:
                                cash_pct = (summary['cash'] / summary['total_portfolio_value']) * 100
                                invested_pct = (summary['total_current_value'] / summary['total_portfolio_value']) * 100
                                
                                st.write(f"**Cash Allocation:** {cash_pct:.1f}%")
                                st.write(f"**Asset Allocation:** {invested_pct:.1f}%")
                                
                                # Performance indicator
                                if summary['total_invested'] > 0:
                                    performance = (summary['total_unrealized_pl'] / summary['total_invested']) * 100
                                    perf_color = "🟢" if performance >= 0 else "🔴"
                                    st.write(f"**Performance:** {perf_color} {performance:+.2f}%")
                    
                    # Detailed holdings table
                    st.write("### 📈 Detailed Holdings")
                    portfolio_data = []
                    
                    for position in portfolio:
                        asset_data = simulator.get_stock_price(position['symbol'])
                        if asset_data:
                            current_value = asset_data['price'] * position['shares']
                            cost_basis = position['avg_price'] * position['shares']
                            unrealized_pl = current_value - cost_basis
                            unrealized_pl_pct = (unrealized_pl / cost_basis) * 100 if cost_basis > 0 else 0
                            
                            # Format display based on asset type
                            if asset_data.get('is_crypto'):
                                asset_display_name = position['symbol'].replace('-USD', '')
                                asset_type_icon = "🪙"
                            elif asset_data.get('is_african'):
                                asset_display_name = position['symbol']
                                asset_type_icon = "🌍"
                            else:
                                asset_display_name = position['symbol']
                                asset_type_icon = "📈"
                            
                            # Format amounts based on asset type
                            if asset_data.get('is_crypto'):
                                shares_display = f"{position['shares']:.6f}"
                                avg_price_display = f"${position['avg_price']:.6f}" if position['avg_price'] < 1 else f"${position['avg_price']:.2f}"
                                current_price_display = f"${asset_data['price']:.6f}" if asset_data['price'] < 1 else f"${asset_data['price']:.2f}"
                            else:
                                shares_display = str(position['shares'])
                                avg_price_display = f"${position['avg_price']:.2f}"
                                current_price_display = f"${asset_data['price']:.2f}"
                            
                            portfolio_data.append({
                                'Symbol': f"{asset_type_icon} {asset_display_name}",
                                'Name': position['name'][:30],
                                'Amount': shares_display,
                                'Avg Price': avg_price_display,
                                'Current Price': current_price_display,
                                'Cost Basis': f"${cost_basis:.2f}",
                                'Current Value': f"${current_value:.2f}",
                                'Unrealized P&L': f"${unrealized_pl:+.2f}",
                                'P&L %': f"{unrealized_pl_pct:+.2f}%"
                            })
                    
                    if portfolio_data:
                        df = pd.DataFrame(portfolio_data)
                        st.dataframe(df, use_container_width=True)
                    
                else:
                    st.info("Your portfolio is empty. Start trading to see your holdings!")
                    
                    # Show empty state with helpful tips
                    st.write("### 💡 Getting Started Tips:")
                    st.write("1. 🔍 Go to the **Research** tab to analyze stocks, crypto, and African markets")
                    st.write("2. 💰 Use the **Trade** tab to buy your first assets")
                    st.write("3. 📊 Return here to see your portfolio allocation")
                    st.write("4. 🏆 Compete with others on the **Leaderboard**")
                    st.write("5. 🪙 Try trading cryptocurrencies for 24/7 markets!")
                    st.write("6. 🌍 Explore African markets for emerging opportunities!")
            
            with tab4:
                st.subheader("📋 Trade History")
                
                trades = simulator.db.get_user_trades(current_user['id'])
                
                if trades:
                    trade_data = []
                    
                    for trade in trades:
                        # Add asset type icon
                        if trade['symbol'].endswith('-USD'):
                            symbol_display = f"🪙 {trade['symbol']}"
                        elif simulator.is_african_stock(trade['symbol']):
                            symbol_display = f"🌍 {trade['symbol']}"
                        else:
                            symbol_display = f"📈 {trade['symbol']}"
                        
                        trade_data.append({
                            'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                            'Type': trade['type'],
                            'Symbol': symbol_display,
                            'Shares': trade['shares'],
                            'Price': f"${trade['price']:.2f}",
                            'Total': f"${trade['total_cost']:.2f}",
                            'P&L': f"${trade['profit_loss']:+.2f}" if trade['profit_loss'] != 0 else 'N/A'
                        })
                    
                    df = pd.DataFrame(trade_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Trades", current_user['total_trades'])
                    with col2:
                        st.metric("Best Trade", f"${current_user['best_trade']:+.2f}")
                    with col3:
                        st.metric("Worst Trade", f"${current_user['worst_trade']:+.2f}")
                else:
                    st.info("No trades yet! Start by buying some stocks, crypto, or African market assets!")
            
            with tab5:
                st.subheader("🏆 Leaderboard")
                
                leaderboard = simulator.db.get_leaderboard()
                
                if leaderboard:
                    leaderboard_data = []
                    for player in leaderboard:
                        # Get current portfolio value
                        portfolio_value = simulator.get_portfolio_value(player['user_id'])
                        
                        leaderboard_data.append({
                            'Rank': player['rank'],
                            'Player': player['username'],
                            'Portfolio Value': f"${portfolio_value:,.2f}",
                            'Total Return': f"${portfolio_value - st.session_state.game_settings['starting_cash']:+,.2f}",
                            'Total Trades': player['total_trades'],
                            'P&L': f"${player['total_profit_loss']:+,.2f}"
                        })
                    
                    df = pd.DataFrame(leaderboard_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No players yet!")
            
            with tab6:
                st.subheader("⚙️ Settings")
                
                settings = simulator.db.get_game_settings()
                
                st.write("**Game Settings:**")
                st.write(f"Starting Cash: ${settings['starting_cash']:,.2f}")
                st.write(f"Commission: ${settings['commission']:.2f}")
                st.write(f"Game Duration: {settings['game_duration_days']} days")
                
                st.write("**Available Markets:**")
                st.write("📈 US Stocks & ETFs")
                st.write("🪙 Cryptocurrencies")
                st.write("🌍 African Markets:")
                st.write("  - 🇬🇭 Ghana Stock Exchange (GSE)")
                st.write("  - 🇿🇦 Johannesburg Stock Exchange (JSE)")
                st.write("  - 🇰🇪 Nairobi Securities Exchange (NSE)")
                st.write("  - 🇳🇬 Nigerian Exchange (NGX)")
                st.write("  - 🇪🇬 Egyptian Exchange (EGX)")
                
                st.write("**Database Information:**")
                st.write(f"Database file: {simulator.db.db_path}")
                st.write(f"User ID: {current_user['id']}")
                st.write(f"Created: {current_user['created_at']}")
                st.write(f"Last login: {current_user['last_login']}")
    
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.write("Please refresh the page and try again.")
        
        # Debug information
        with st.expander("Debug Information"):
            st.write("**Error Details:**")
            st.code(str(e))
            st.write("**Session State:**")
            st.json(dict(st.session_state))
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🎮 Leo's Trader | 📈 Educational Tool | 🌍 Now with African Markets | ⚠️ Virtual Money Only</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
