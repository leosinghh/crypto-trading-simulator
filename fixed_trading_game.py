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
warnings.filterwarnings('ignore')

# Database Manager Class
class TradingGameDatabase:
    def __init__(self, db_path: str = "trading_game.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_settings (
                id INTEGER PRIMARY KEY,
                starting_cash REAL DEFAULT 100000.00,
                commission REAL DEFAULT 9.99,
                game_duration_days INTEGER DEFAULT 30,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('SELECT COUNT(*) FROM game_settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO game_settings (starting_cash, commission, game_duration_days)
                VALUES (100000.00, 9.99, 30)
            ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, password: str, email: str) -> Dict:
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
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT commission FROM game_settings ORDER BY id DESC LIMIT 1')
            commission = cursor.fetchone()[0]
            
            cursor.execute('SELECT cash FROM users WHERE id = ?', (user_id,))
            current_cash = cursor.fetchone()[0]
            
            total_cost = (price * shares) + commission
            
            if action.upper() == 'BUY':
                if current_cash < total_cost:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient funds'}
                
                new_cash = current_cash - total_cost
                cursor.execute('UPDATE users SET cash = ? WHERE id = ?', (new_cash, user_id))
                
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
                
                trade_id = str(uuid.uuid4())[:8]
                cursor.execute('''
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price, total_cost, commission, stock_name))
                
                profit_loss = 0
                
            elif action.upper() == 'SELL':
                cursor.execute('''
                    SELECT shares, avg_price FROM portfolio WHERE user_id = ? AND symbol = ?
                ''', (user_id, symbol))
                
                existing = cursor.fetchone()
                if not existing or existing[0] < shares:
                    conn.close()
                    return {'success': False, 'message': 'Insufficient shares'}
                
                owned_shares, avg_price = existing
                
                profit_loss = (price - avg_price) * shares - commission
                
                total_proceeds = (price * shares) - commission
                new_cash = current_cash + total_proceeds
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
                    INSERT INTO trades (id, user_id, trade_type, symbol, shares, price, total_cost, commission, profit_loss, stock_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_id, user_id, action, symbol, shares, price, total_proceeds, commission, profit_loss, stock_name))
                
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

# Custom CSS
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
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
</style>
""", unsafe_allow_html=True)

class TradingSimulator:
    def __init__(self):
        self.db = TradingGameDatabase()
        self.initialize_session_state()
        self.available_stocks = self.get_available_stocks()
        
    def initialize_session_state(self):
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
        return [
            # US Tech stocks
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            # US Finance
            'JPM', 'BAC', 'WFC', 'V', 'MA', 'BRK-B', 'GS', 'MS',
            # US ETFs
            'SPY', 'QQQ', 'VTI', 'VOO', 'IWM',
            # Crypto
            'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'DOGE-USD'
        ]
    
    def get_african_stocks(self) -> List[str]:
        return [
            # South African stocks (JSE) - Real data
            'NPN.JO', 'MTN.JO', 'SHP.JO', 'VOD.JO', 'NED.JO', 'SBK.JO', 
            'FSR.JO', 'INL.JO', 'AGL.JO', 'SOL.JO', 'BVT.JO', 'WHL.JO',
            # Ghana stocks (GSE) - Mock data
            'GSE:EGL', 'GSE:CAL', 'GSE:GCB', 'GSE:MTN', 'GSE:GOIL', 'GSE:TOTAL',
            'GSE:SIC', 'GSE:SCB', 'GSE:TLW', 'GSE:BOPP', 'GSE:ACI', 'GSE:FML',
            # African ETFs
            'AFK', 'EZA', 'GAF', 'FLZA'
        ]
    
    def get_african_categories(self) -> Dict[str, List[str]]:
        return {
            "South African Stocks (JSE)": [
                'NPN.JO', 'MTN.JO', 'SHP.JO', 'VOD.JO', 'NED.JO', 'SBK.JO', 
                'FSR.JO', 'INL.JO', 'AGL.JO', 'SOL.JO', 'BVT.JO', 'WHL.JO'
            ],
            "Ghana Stock Exchange (GSE)": [
                'GSE:EGL', 'GSE:CAL', 'GSE:GCB', 'GSE:MTN', 'GSE:GOIL', 'GSE:TOTAL',
                'GSE:SIC', 'GSE:SCB', 'GSE:TLW', 'GSE:BOPP', 'GSE:ACI', 'GSE:FML'
            ],
            "African ETFs": [
                'AFK', 'EZA', 'GAF', 'FLZA'
            ]
        }
    
    def get_stock_display_name(self, symbol: str) -> str:
        """Get friendly display name for stocks"""
        names = {
            # South African stocks
            'NPN.JO': 'Naspers Limited',
            'MTN.JO': 'MTN Group',
            'SHP.JO': 'Shoprite Holdings',
            'VOD.JO': 'Vodacom Group',
            'NED.JO': 'Nedbank Group',
            'SBK.JO': 'Standard Bank Group',
            'FSR.JO': 'FirstRand Limited',
            'INL.JO': 'Investec Limited',
            'AGL.JO': 'Anglo American Platinum',
            'SOL.JO': 'Sasol Limited',
            'BVT.JO': 'Bidvest Group',
            'WHL.JO': 'Woolworths Holdings',
            
            # Ghana stocks
            'GSE:EGL': 'Enterprise Group Limited',
            'GSE:CAL': 'CAL Bank Limited',
            'GSE:GCB': 'GCB Bank Limited',
            'GSE:MTN': 'MTN Ghana',
            'GSE:GOIL': 'Ghana Oil Company',
            'GSE:TOTAL': 'Total Petroleum Ghana',
            'GSE:SIC': 'SIC Insurance Company',
            'GSE:SCB': 'Standard Chartered Bank Ghana',
            'GSE:TLW': 'Tullow Oil Ghana',
            'GSE:BOPP': 'Benso Oil Palm Plantation',
            'GSE:ACI': 'Ayrton Drug Manufacturing',
            'GSE:FML': 'Fan Milk Limited',
            
            # African ETFs
            'AFK': 'VanEck Africa Index ETF',
            'EZA': 'iShares MSCI South Africa ETF',
            'GAF': 'SPDR S&P Emerging Middle East & Africa ETF',
            'FLZA': 'Franklin FTSE South Africa ETF'
        }
        return names.get(symbol, symbol)
    
    def is_african_stock(self, symbol: str) -> bool:
        return (symbol.endswith('.JO') or 
                symbol.startswith('GSE:') or 
                symbol in ['AFK', 'EZA'])
    
    def get_gse_mock_data(self, symbol: str) -> Dict:
        base_prices = {
            'GSE:EGL': 1.5, 'GSE:CAL': 0.8, 'GSE:GCB': 2.3, 'GSE:MTN': 0.9,
            'GSE:GOIL': 1.2, 'GSE:TOTAL': 3.1, 'GSE:SIC': 0.6, 'GSE:SCB': 2.8,
            'GSE:TLW': 4.2, 'GSE:BOPP': 1.8, 'GSE:ACI': 2.5, 'GSE:FML': 1.4
        }
        
        current_time = time.time()
        update_interval = 300  # 5 minutes
        time_seed = int(current_time / update_interval)
        
        symbol_hash = hash(symbol) % 10000
        combined_seed = time_seed + symbol_hash
        
        random.seed(combined_seed)
        
        base_price = base_prices.get(symbol, 1.0)
        variation = random.uniform(-0.15, 0.15)
        current_price = max(0.10, base_price + variation)
        
        prev_seed = time_seed - 1
        random.seed(prev_seed + symbol_hash)
        prev_variation = random.uniform(-0.15, 0.15)
        prev_price = max(0.10, base_price + prev_variation)
        
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price > 0 else 0
        
        ghana_time = datetime.utcnow()
        is_market_open = 9 <= ghana_time.hour <= 15
        
        return {
            'symbol': symbol,
            'name': self.get_stock_display_name(symbol),
            'price': float(current_price),
            'change': float(change),
            'change_percent': float(change_percent),
            'volume': random.randint(1000, 10000),
            'market_cap': random.randint(10000000, 100000000),
            'pe_ratio': random.uniform(10, 20),
            'day_high': current_price + 0.1,
            'day_low': current_price - 0.1,
            'sector': 'African Markets - Ghana',
            'industry': 'Ghana Stock Exchange',
            'is_crypto': False,
            'is_african': True,
            'currency': 'GHS',
            'market_status': 'Open' if is_market_open else 'Closed',
            'last_updated': datetime.now()
        }
    
    @st.cache_data(ttl=300)
    def get_stock_price(_self, symbol: str) -> Dict:
        try:
            if symbol.startswith('GSE:'):
                return _self.get_gse_mock_data(symbol)
            
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
            
            is_crypto = symbol.endswith('-USD')
            is_african = _self.is_african_stock(symbol)
            
            if is_crypto:
                long_name = symbol.replace('-USD', '')
                sector = 'Cryptocurrency'
            elif is_african:
                long_name = info.get('longName', symbol)
                sector = 'African Markets'
            else:
                long_name = info.get('longName', symbol)
                sector = info.get('sector', 'Unknown')
            
            return {
                'symbol': symbol,
                'name': long_name[:50],
                'price': float(current_price),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': int(hist['Volume'].iloc[-1]) if len(hist) > 0 and not pd.isna(hist['Volume'].iloc[-1]) else 0,
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'day_high': float(hist['High'].iloc[-1]) if len(hist) > 0 else current_price,
                'day_low': float(hist['Low'].iloc[-1]) if len(hist) > 0 else current_price,
                'sector': sector,
                'industry': info.get('industry', 'Unknown'),
                'is_crypto': is_crypto,
                'is_african': is_african,
                'last_updated': datetime.now()
            }
        except Exception as e:
            st.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_portfolio_value(self, user_id: str) -> float:
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
    
    def create_portfolio_pie_chart(self, user_id: str):
        try:
            portfolio = self.db.get_user_portfolio(user_id)
            
            if not portfolio:
                return None
            
            portfolio_data = []
            total_value = 0
            
            for position in portfolio:
                stock_data = self.get_stock_price(position['symbol'])
                if stock_data:
                    current_value = stock_data['price'] * position['shares']
                    total_value += current_value
                    portfolio_data.append({
                        'Symbol': position['symbol'],
                        'Name': position['name'][:20],
                        'Value': current_value,
                        'Shares': position['shares'],
                        'Price': stock_data['price']
                    })
            
            if not portfolio_data:
                return None
            
            df = pd.DataFrame(portfolio_data)
            
            fig = px.pie(
                df,
                values='Value',
                names='Symbol',
                title=f'Portfolio Allocation - Total: ${total_value:,.2f}',
                hover_data=['Name', 'Shares', 'Price']
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating portfolio pie chart: {str(e)}")
            return None

def main():
    try:
        simulator = TradingSimulator()
        
        # Header
        st.markdown("""
        <div class="main-header">
            <h1>Leo's Trader</h1>
            <p>🎮 Learn trading with virtual money • 📈 Build your portfolio • 🏆 Compete with friends</p>
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
            current_user = st.session_state.current_user
            
            # Sidebar
            with st.sidebar:
                st.header(f"👨‍💼 {current_user['username']}")
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
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Research", "💰 Trade", "📈 Portfolio", "📋 History"])
            
            with tab1:
                st.subheader("📊 Research")
                
                # Asset type selector
                asset_type = st.selectbox(
                    "Select Asset Type",
                    ["US Stocks & ETFs", "African Markets", "Cryptocurrencies"]
                )
                
                # Get appropriate stock list
                if asset_type == "US Stocks & ETFs":
                    available_assets = simulator.available_stocks
                    selected_stock = st.selectbox("Select Asset", [''] + available_assets)
                elif asset_type == "African Markets":
                    st.write("### 🌍 African Markets")
                    
                    # Show African categories
                    african_categories = simulator.get_african_categories()
                    selected_category = st.selectbox(
                        "Select Market",
                        ["All African Markets"] + list(african_categories.keys())
                    )
                    
                    if selected_category == "All African Markets":
                        available_assets = simulator.get_african_stocks()
                    else:
                        available_assets = african_categories[selected_category]
                    
                    selected_stock = st.selectbox("Select African Asset", [''] + available_assets)
                    
                    # Show helpful info about African markets
                    if selected_category != "All African Markets":
                        if selected_category == "South African Stocks (JSE)":
                            st.info("🇿🇦 Real-time data from Johannesburg Stock Exchange via Yahoo Finance")
                        elif selected_category == "Ghana Stock Exchange (GSE)":
                            st.info("🇬🇭 Mock data that updates every 5-10 minutes • Market hours: 9 AM - 3 PM GMT")
                        elif selected_category == "African ETFs":
                            st.info("🌍 Real-time data for Africa-focused ETFs")
                
                else:  # Cryptocurrencies
                    crypto_stocks = [s for s in simulator.available_stocks if s.endswith('-USD')]
                    selected_stock = st.selectbox("Select Cryptocurrency", [''] + crypto_stocks)
                
                # Display stock information
                if selected_stock:
                    stock_data = simulator.get_stock_price(selected_stock)
                    if stock_data:
                        # Show stock info with African-specific details
                        st.write(f"**{stock_data['name']}** ({selected_stock})")
                        
                        # Show market-specific info
                        if selected_stock.startswith('GSE:'):
                            market_status = stock_data.get('market_status', 'Unknown')
                            status_color = "🟢" if market_status == 'Open' else "🔴"
                            st.write(f"**Market Status:** {status_color} {market_status}")
                            st.write(f"**Exchange:** Ghana Stock Exchange")
                            st.write(f"**Currency:** Ghana Cedi (₵)")
                        elif selected_stock.endswith('.JO'):
                            st.write(f"**Exchange:** Johannesburg Stock Exchange")
                            st.write(f"**Currency:** South African Rand (ZAR)")
                        elif selected_stock in ['AFK', 'EZA', 'GAF', 'FLZA']:
                            st.write(f"**Type:** African ETF")
                            st.write(f"**Exchange:** US Markets")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # Format price for African currencies
                            if selected_stock.startswith('GSE:'):
                                price_display = f"₵{stock_data['price']:.2f}"
                            else:
                                price_display = f"${stock_data['price']:.2f}"
                            st.metric("Price", price_display)
                        with col2:
                            st.metric("Change", f"{stock_data['change']:+.2f}", f"{stock_data['change_percent']:+.2f}%")
                        
                        # Additional info for GSE stocks
                        if selected_stock.startswith('GSE:'):
                            st.write("---")
                            st.write("**📊 GSE Mock Data Info:**")
                            st.write(f"• Updates every 5-10 minutes")
                            st.write(f"• Market hours: 9:00 AM - 3:00 PM GMT")
                            st.write(f"• Last updated: {stock_data['last_updated'].strftime('%H:%M:%S')}")
                        
                        # Quick trade buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Buy {selected_stock}"):
                                st.session_state.quick_trade = selected_stock
                                st.info("Go to Trade tab to complete purchase")
                        with col2:
                            if st.button(f"Sell {selected_stock}"):
                                st.session_state.quick_trade = selected_stock
                                st.info("Go to Trade tab to complete sale")
            
            with tab2:
                st.subheader("💰 Trade")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### Buy")
                    
                    # Asset type selector for buying
                    buy_asset_type = st.selectbox(
                        "Asset Type",
                        ["US Stocks & ETFs", "African Markets", "Cryptocurrencies"],
                        key="buy_asset_type"
                    )
                    
                    # Get appropriate stock list
                    if buy_asset_type == "US Stocks & ETFs":
                        buy_options = simulator.available_stocks
                    elif buy_asset_type == "African Markets":
                        buy_options = simulator.get_african_stocks()
                    else:  # Cryptocurrencies
                        buy_options = [s for s in simulator.available_stocks if s.endswith('-USD')]
                    
                    buy_stock = st.selectbox("Select Asset to Buy", [''] + buy_options, key="buy_stock")
                    
                    if buy_stock:
                        stock_data = simulator.get_stock_price(buy_stock)
                        if stock_data:
                            st.write(f"**{stock_data['name']}**")
                            
                            # Format price display
                            if buy_stock.startswith('GSE:'):
                                price_display = f"₵{stock_data['price']:.2f}"
                                st.write(f"**Price:** {price_display}")
                            else:
                                price_display = f"${stock_data['price']:.2f}"
                                st.write(f"**Price:** {price_display}")
                            
                            # Show market info for African stocks
                            if buy_stock.startswith('GSE:'):
                                market_status = stock_data.get('market_status', 'Unknown')
                                status_color = "🟢" if market_status == 'Open' else "🔴"
                                st.write(f"**Market:** {status_color} {market_status}")
                            elif buy_stock.endswith('.JO'):
                                st.write(f"**Exchange:** JSE (South Africa)")
                            
                            buy_shares = st.number_input("Shares", min_value=1, value=1, key="buy_shares")
                            total_cost = (stock_data['price'] * buy_shares) + 9.99
                            
                            st.write(f"**Total Cost:** ${total_cost:.2f}")
                            st.write(f"**Available:** ${current_user['cash']:,.2f}")
                            
                            if st.button("Buy Stock"):
                                result = simulator.db.execute_trade(
                                    current_user['id'], buy_stock, 'BUY', 
                                    buy_shares, stock_data['price'], stock_data['name']
                                )
                                if result['success']:
                                    st.success(result['message'])
                                    st.rerun()
                                else:
                                    st.error(result['message'])
                
                with col2:
                    st.write("### Sell")
                    portfolio = simulator.db.get_user_portfolio(current_user['id'])
                    
                    if portfolio:
                        # Group portfolio by asset type
                        us_stocks = []
                        african_stocks = []
                        crypto_stocks = []
                        
                        for p in portfolio:
                            if p['symbol'].endswith('-USD'):
                                crypto_stocks.append(p)
                            elif simulator.is_african_stock(p['symbol']):
                                african_stocks.append(p)
                            else:
                                us_stocks.append(p)
                        
                        # Show portfolio breakdown
                        if us_stocks:
                            st.write("**🇺🇸 US Stocks:**")
                            for stock in us_stocks:
                                st.write(f"• {stock['symbol']} ({stock['shares']} shares)")
                        
                        if african_stocks:
                            st.write("**🌍 African Markets:**")
                            for stock in african_stocks:
                                if stock['symbol'].startswith('GSE:'):
                                    st.write(f"• {stock['symbol']} - Ghana ({stock['shares']} shares)")
                                elif stock['symbol'].endswith('.JO'):
                                    st.write(f"• {stock['symbol']} - South Africa ({stock['shares']} shares)")
                                else:
                                    st.write(f"• {stock['symbol']} ({stock['shares']} shares)")
                        
                        if crypto_stocks:
                            st.write("**🪙 Cryptocurrencies:**")
                            for stock in crypto_stocks:
                                st.write(f"• {stock['symbol']} ({stock['shares']} shares)")
                        
                        # Sell interface
                        owned_stocks = [p['symbol'] for p in portfolio]
                        sell_stock = st.selectbox("Select Asset to Sell", [''] + owned_stocks, key="sell_stock")
                        
                        if sell_stock:
                            position = next((p for p in portfolio if p['symbol'] == sell_stock), None)
                            stock_data = simulator.get_stock_price(sell_stock)
                            
                            if position and stock_data:
                                st.write(f"**{stock_data['name']}**")
                                st.write(f"**Owned:** {position['shares']} shares")
                                
                                # Format price display
                                if sell_stock.startswith('GSE:'):
                                    current_price_display = f"₵{stock_data['price']:.2f}"
                                    avg_price_display = f"₵{position['avg_price']:.2f}"
                                else:
                                    current_price_display = f"${stock_data['price']:.2f}"
                                    avg_price_display = f"${position['avg_price']:.2f}"
                                
                                st.write(f"**Average Price:** {avg_price_display}")
                                st.write(f"**Current Price:** {current_price_display}")
                                
                                sell_shares = st.number_input("Shares to Sell", min_value=1, max_value=position['shares'], value=1, key="sell_shares")
                                total_proceeds = (stock_data['price'] * sell_shares) - 9.99
                                
                                st.write(f"**Total Proceeds:** ${total_proceeds:.2f}")
                                
                                if st.button("Sell Stock"):
                                    result = simulator.db.execute_trade(
                                        current_user['id'], sell_stock, 'SELL', 
                                        sell_shares, stock_data['price'], stock_data['name']
                                    )
                                    if result['success']:
                                        st.success(result['message'])
                                        if result['profit_loss'] > 0:
                                            st.success(f"Profit: ${result['profit_loss']:+.2f}")
                                        else:
                                            st.error(f"Loss: ${result['profit_loss']:+.2f}")
                                        st.rerun()
                                    else:
                                        st.error(result['message'])
                    else:
                        st.info("No stocks owned. Buy some stocks first!")
                        
                        # Show available African stocks to buy
                        st.write("### 🌍 Try These African Stocks:")
                        st.write("**🇿🇦 South African (Real Data):**")
                        st.write("• NPN.JO (Naspers), MTN.JO (MTN Group)")
                        st.write("• SHP.JO (Shoprite), VOD.JO (Vodacom)")
                        
                        st.write("**🇬🇭 Ghana (Mock Data):**")
                        st.write("• GSE:EGL (Enterprise Group)")
                        st.write("• GSE:CAL (CAL Bank)")
                        st.write("• GSE:GCB (GCB Bank)")
                        
                        st.write("**🌍 African ETFs:**")
                        st.write("• AFK (VanEck Africa ETF)")
                        st.write("• EZA (iShares South Africa ETF)")
            
            with tab3:
                st.subheader("📈 Portfolio")
                
                portfolio = simulator.db.get_user_portfolio(current_user['id'])
                
                if portfolio:
                    # Portfolio pie chart
                    pie_chart = simulator.create_portfolio_pie_chart(current_user['id'])
                    if pie_chart:
                        st.plotly_chart(pie_chart, use_container_width=True)
                    
                    # Holdings table
                    st.write("### Holdings")
                    portfolio_data = []
                    
                    for position in portfolio:
                        stock_data = simulator.get_stock_price(position['symbol'])
                        if stock_data:
                            current_value = stock_data['price'] * position['shares']
                            cost_basis = position['avg_price'] * position['shares']
                            unrealized_pl = current_value - cost_basis
                            
                            portfolio_data.append({
                                'Symbol': position['symbol'],
                                'Name': position['name'][:30],
                                'Shares': position['shares'],
                                'Avg Price': f"${position['avg_price']:.2f}",
                                'Current Price': f"${stock_data['price']:.2f}",
                                'Value': f"${current_value:.2f}",
                                'P&L': f"${unrealized_pl:+.2f}"
                            })
                    
                    if portfolio_data:
                        df = pd.DataFrame(portfolio_data)
                        st.dataframe(df, use_container_width=True)
                
                else:
                    st.info("No holdings. Start trading to build your portfolio!")
            
            with tab4:
                st.subheader("📋 Trade History")
                
                trades = simulator.db.get_user_trades(current_user['id'])
                
                if trades:
                    trade_data = []
                    for trade in trades:
                        trade_data.append({
                            'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                            'Type': trade['type'],
                            'Symbol': trade['symbol'],
                            'Shares': trade['shares'],
                            'Price': f"${trade['price']:.2f}",
                            'Total': f"${trade['total_cost']:.2f}",
                            'P&L': f"${trade['profit_loss']:+.2f}" if trade['profit_loss'] != 0 else 'N/A'
                        })
                    
                    df = pd.DataFrame(trade_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No trades yet!")
    
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.write("Please refresh the page and try again.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🎮 Leo's Trader | 📈 Educational Tool | ⚠️ Virtual Money Only</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
