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
warnings.filterwarnings('ignore')

# Configure Streamlit page
st.set_page_config(
    page_title="Stock Trading Simulator",
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
    
    .trade-success {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    
    .trade-error {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    
    .leaderboard-gold {
        background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
        color: #333;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 5px 15px rgba(255,215,0,0.4);
    }
    
    .leaderboard-silver {
        background: linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%);
        color: #333;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 5px 15px rgba(192,192,192,0.4);
    }
    
    .leaderboard-bronze {
        background: linear-gradient(135deg, #cd7f32 0%, #daa520 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 5px 15px rgba(205,127,50,0.4);
    }
    
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
    
    .achievement-badge {
        background: #17a2b8;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 0.8em;
        margin: 2px;
        display: inline-block;
    }
    
    .trade-button {
        background: linear-gradient(45deg, #28a745, #20c997);
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 25px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .sell-button {
        background: linear-gradient(45deg, #dc3545, #fd7e14);
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 25px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
    }
</style>
""", unsafe_allow_html=True)

class TradingSimulator:
    def __init__(self):
        self.initialize_session_state()
        self.available_stocks = self.get_available_stocks()
        
    def initialize_session_state(self):
        """Initialize session state for the trading game"""
        if 'players' not in st.session_state:
            st.session_state.players = {}
        
        if 'current_player' not in st.session_state:
            st.session_state.current_player = None
            
        if 'game_settings' not in st.session_state:
            st.session_state.game_settings = {
                'starting_cash': 100000,
                'commission': 9.99,
                'game_duration_days': 30,
                'created_date': datetime.now()
            }
            
        if 'market_data_cache' not in st.session_state:
            st.session_state.market_data_cache = {}
            
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
    
    def get_available_stocks(self) -> List[str]:
        """Get list of available stocks for trading"""
        # Popular stocks for the simulation
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK-B',
            'UNH', 'JNJ', 'JPM', 'V', 'PG', 'HD', 'CVX', 'MA', 'PFE', 'ABBV',
            'BAC', 'KO', 'AVGO', 'PEP', 'TMO', 'COST', 'DIS', 'ABT', 'DHR',
            'VZ', 'ADBE', 'NFLX', 'CRM', 'ACN', 'TXN', 'NKE', 'QCOM', 'WMT',
            'NEE', 'RTX', 'HON', 'LOW', 'UPS', 'PM', 'ORCL', 'IBM', 'AMGN',
            'CVS', 'MDT', 'SPGI', 'C', 'GS', 'CAT', 'AXP', 'BLK', 'DE', 'BA',
            'NOW', 'INTU', 'ISRG', 'BKNG', 'GILD', 'AMT', 'MRK', 'LRCX',
            'SBUX', 'AMD', 'TGT', 'REGN', 'VRTX', 'INTC', 'AMAT', 'SYK',
            'MU', 'PANW', 'BSX', 'TJX', 'SCHW', 'CB', 'MCD', 'SO', 'LIN',
            'PYPL', 'UBER', 'SNAP', 'COIN', 'SNOW', 'PLTR', 'CRWD', 'ZM',
            'SPY', 'QQQ', 'IWM', 'VTI', 'VOO'
        ]
    
    @st.cache_data(ttl=300)
    def get_stock_price(_self, symbol: str) -> Dict:
        """Get current stock price and info"""
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="5d")
            info = stock.info
            
            if len(hist) >= 1:
                current_price = hist['Close'].iloc[-1]
                prev_close = info.get('previousClose', current_price)
                change = current_price - prev_close
                change_percent = (change / prev_close) * 100
                
                return {
                    'symbol': symbol,
                    'name': info.get('longName', symbol),
                    'price': current_price,
                    'change': change,
                    'change_percent': change_percent,
                    'volume': hist['Volume'].iloc[-1] if len(hist) > 0 else 0,
                    'market_cap': info.get('marketCap', 0),
                    'pe_ratio': info.get('trailingPE', 0),
                    'day_high': hist['High'].iloc[-1] if len(hist) > 0 else current_price,
                    'day_low': hist['Low'].iloc[-1] if len(hist) > 0 else current_price,
                    'last_updated': datetime.now()
                }
            return None
        except Exception as e:
            return None
    
    def create_player(self, name: str, email: str = "") -> str:
        """Create a new player"""
        player_id = str(uuid.uuid4())[:8]
        
        st.session_state.players[player_id] = {
            'name': name,
            'email': email,
            'cash': st.session_state.game_settings['starting_cash'],
            'portfolio': {},
            'trade_history': [],
            'created_date': datetime.now(),
            'total_trades': 0,
            'total_profit_loss': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'achievements': [],
            'portfolio_value_history': []
        }
        
        return player_id
    
    def buy_stock(self, player_id: str, symbol: str, shares: int) -> Dict:
        """Execute a buy order"""
        if player_id not in st.session_state.players:
            return {'success': False, 'message': 'Player not found'}
        
        stock_data = self.get_stock_price(symbol)
        if not stock_data:
            return {'success': False, 'message': 'Unable to get stock price'}
        
        player = st.session_state.players[player_id]
        total_cost = (stock_data['price'] * shares) + st.session_state.game_settings['commission']
        
        if player['cash'] < total_cost:
            return {'success': False, 'message': 'Insufficient funds'}
        
        # Execute trade
        player['cash'] -= total_cost
        
        if symbol in player['portfolio']:
            # Update existing position
            existing_shares = player['portfolio'][symbol]['shares']
            existing_avg_price = player['portfolio'][symbol]['avg_price']
            new_avg_price = ((existing_shares * existing_avg_price) + (shares * stock_data['price'])) / (existing_shares + shares)
            
            player['portfolio'][symbol]['shares'] += shares
            player['portfolio'][symbol]['avg_price'] = new_avg_price
        else:
            # New position
            player['portfolio'][symbol] = {
                'shares': shares,
                'avg_price': stock_data['price'],
                'name': stock_data['name']
            }
        
        # Record trade
        trade = {
            'id': str(uuid.uuid4())[:8],
            'type': 'BUY',
            'symbol': symbol,
            'shares': shares,
            'price': stock_data['price'],
            'commission': st.session_state.game_settings['commission'],
            'total_cost': total_cost,
            'timestamp': datetime.now(),
            'name': stock_data['name']
        }
        
        player['trade_history'].append(trade)
        player['total_trades'] += 1
        
        # Update session state
        st.session_state.players[player_id] = player
        
        # Check for achievements
        self.check_achievements(player_id)
        
        return {
            'success': True, 
            'message': f'Successfully bought {shares} shares of {symbol} at ${stock_data["price"]:.2f}',
            'trade': trade
        }
    
    def sell_stock(self, player_id: str, symbol: str, shares: int) -> Dict:
        """Execute a sell order"""
        if player_id not in st.session_state.players:
            return {'success': False, 'message': 'Player not found'}
        
        player = st.session_state.players[player_id]
        
        if symbol not in player['portfolio']:
            return {'success': False, 'message': 'You do not own this stock'}
        
        if player['portfolio'][symbol]['shares'] < shares:
            return {'success': False, 'message': 'Insufficient shares'}
        
        stock_data = self.get_stock_price(symbol)
        if not stock_data:
            return {'success': False, 'message': 'Unable to get stock price'}
        
        # Execute trade
        total_proceeds = (stock_data['price'] * shares) - st.session_state.game_settings['commission']
        player['cash'] += total_proceeds
        
        # Calculate profit/loss
        avg_price = player['portfolio'][symbol]['avg_price']
        profit_loss = (stock_data['price'] - avg_price) * shares - st.session_state.game_settings['commission']
        
        # Update portfolio
        player['portfolio'][symbol]['shares'] -= shares
        if player['portfolio'][symbol]['shares'] == 0:
            del player['portfolio'][symbol]
        
        # Record trade
        trade = {
            'id': str(uuid.uuid4())[:8],
            'type': 'SELL',
            'symbol': symbol,
            'shares': shares,
            'price': stock_data['price'],
            'commission': st.session_state.game_settings['commission'],
            'total_proceeds': total_proceeds,
            'profit_loss': profit_loss,
            'timestamp': datetime.now(),
            'name': stock_data['name']
        }
        
        player['trade_history'].append(trade)
        player['total_trades'] += 1
        player['total_profit_loss'] += profit_loss
        
        # Update best/worst trades
        if profit_loss > player['best_trade']:
            player['best_trade'] = profit_loss
        if profit_loss < player['worst_trade']:
            player['worst_trade'] = profit_loss
        
        # Update session state
        st.session_state.players[player_id] = player
        
        # Check for achievements
        self.check_achievements(player_id)
        
        return {
            'success': True, 
            'message': f'Successfully sold {shares} shares of {symbol} at ${stock_data["price"]:.2f}',
            'trade': trade,
            'profit_loss': profit_loss
        }
    
    def get_portfolio_value(self, player_id: str) -> float:
        """Calculate total portfolio value"""
        if player_id not in st.session_state.players:
            return 0
        
        player = st.session_state.players[player_id]
        total_value = player['cash']
        
        for symbol, position in player['portfolio'].items():
            stock_data = self.get_stock_price(symbol)
            if stock_data:
                total_value += stock_data['price'] * position['shares']
        
        return total_value
    
    def check_achievements(self, player_id: str):
        """Check and award achievements"""
        if player_id not in st.session_state.players:
            return
        
        player = st.session_state.players[player_id]
        achievements = set(player['achievements'])
        
        # First Trade
        if player['total_trades'] >= 1 and 'First Trade' not in achievements:
            achievements.add('First Trade')
        
        # Day Trader
        if player['total_trades'] >= 10 and 'Day Trader' not in achievements:
            achievements.add('Day Trader')
        
        # High Roller
        if player['total_trades'] >= 50 and 'High Roller' not in achievements:
            achievements.add('High Roller')
        
        # Profit Maker
        if player['total_profit_loss'] > 1000 and 'Profit Maker' not in achievements:
            achievements.add('Profit Maker')
        
        # Big Winner
        if player['best_trade'] > 5000 and 'Big Winner' not in achievements:
            achievements.add('Big Winner')
        
        # Diversified
        if len(player['portfolio']) >= 5 and 'Diversified' not in achievements:
            achievements.add('Diversified')
        
        # Portfolio value achievements
        portfolio_value = self.get_portfolio_value(player_id)
        if portfolio_value >= 150000 and 'Growing' not in achievements:
            achievements.add('Growing')
        
        if portfolio_value >= 200000 and 'Millionaire Track' not in achievements:
            achievements.add('Millionaire Track')
        
        player['achievements'] = list(achievements)
        st.session_state.players[player_id] = player
    
    def get_leaderboard(self) -> pd.DataFrame:
        """Get leaderboard of all players"""
        leaderboard_data = []
        
        for player_id, player in st.session_state.players.items():
            portfolio_value = self.get_portfolio_value(player_id)
            total_return = portfolio_value - st.session_state.game_settings['starting_cash']
            return_percentage = (total_return / st.session_state.game_settings['starting_cash']) * 100
            
            leaderboard_data.append({
                'Rank': 0,  # Will be set after sorting
                'Player': player['name'],
                'Portfolio Value': portfolio_value,
                'Total Return': total_return,
                'Return %': return_percentage,
                'Total Trades': player['total_trades'],
                'Achievements': len(player['achievements']),
                'Player ID': player_id
            })
        
        df = pd.DataFrame(leaderboard_data)
        if not df.empty:
            df = df.sort_values('Portfolio Value', ascending=False).reset_index(drop=True)
            df['Rank'] = range(1, len(df) + 1)
        
        return df
    
    def create_portfolio_chart(self, player_id: str):
        """Create portfolio allocation pie chart"""
        if player_id not in st.session_state.players:
            return None
        
        player = st.session_state.players[player_id]
        
        if not player['portfolio']:
            return None
        
        portfolio_data = []
        for symbol, position in player['portfolio'].items():
            stock_data = self.get_stock_price(symbol)
            if stock_data:
                value = stock_data['price'] * position['shares']
                portfolio_data.append({
                    'Symbol': symbol,
                    'Value': value,
                    'Shares': position['shares'],
                    'Current Price': stock_data['price'],
                    'Avg Price': position['avg_price']
                })
        
        if not portfolio_data:
            return None
        
        df = pd.DataFrame(portfolio_data)
        
        fig = px.pie(
            df, 
            values='Value', 
            names='Symbol',
            title='Portfolio Allocation',
            hover_data=['Shares', 'Current Price']
        )
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=400)
        
        return fig
    
    def create_performance_chart(self, player_id: str):
        """Create portfolio performance chart over time"""
        if player_id not in st.session_state.players:
            return None
        
        player = st.session_state.players[player_id]
        
        # For now, create a simple chart based on trade history
        if not player['trade_history']:
            return None
        
        # Calculate portfolio value over time based on trades
        portfolio_values = []
        dates = []
        running_cash = st.session_state.game_settings['starting_cash']
        holdings = {}
        
        for trade in player['trade_history']:
            dates.append(trade['timestamp'])
            
            if trade['type'] == 'BUY':
                running_cash -= trade['total_cost']
                if trade['symbol'] in holdings:
                    holdings[trade['symbol']]['shares'] += trade['shares']
                else:
                    holdings[trade['symbol']] = {'shares': trade['shares']}
            else:  # SELL
                running_cash += trade['total_proceeds']
                holdings[trade['symbol']]['shares'] -= trade['shares']
                if holdings[trade['symbol']]['shares'] == 0:
                    del holdings[trade['symbol']]
            
            # Calculate total portfolio value at this point
            total_value = running_cash
            for symbol, position in holdings.items():
                stock_data = self.get_stock_price(symbol)
                if stock_data:
                    total_value += stock_data['price'] * position['shares']
            
            portfolio_values.append(total_value)
        
        if len(dates) < 2:
            return None
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=portfolio_values,
            mode='lines+markers',
            name='Portfolio Value',
            line=dict(color='#28a745', width=3)
        ))
        
        # Add starting value line
        fig.add_hline(
            y=st.session_state.game_settings['starting_cash'],
            line_dash="dash",
            line_color="gray",
            annotation_text="Starting Value"
        )
        
        fig.update_layout(
            title='Portfolio Performance Over Time',
            xaxis_title='Date',
            yaxis_title='Portfolio Value ($)',
            template='plotly_white',
            height=400
        )
        
        return fig

def main():
    simulator = TradingSimulator()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>💰 Stock Trading Simulator</h1>
        <p>🎮 Learn trading with virtual money • 📈 Build your portfolio • 🏆 Compete with friends</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Player Management
    with st.sidebar:
        st.header("🎮 Player Management")
        
        # Create or select player
        if not st.session_state.players:
            st.write("**Create your first player to start trading!**")
            with st.form("create_player"):
                player_name = st.text_input("Player Name", placeholder="Enter your name")
                player_email = st.text_input("Email (optional)", placeholder="your@email.com")
                
                if st.form_submit_button("🚀 Start Trading!"):
                    if player_name:
                        player_id = simulator.create_player(player_name, player_email)
                        st.session_state.current_player = player_id
                        st.success(f"Welcome {player_name}! Your Player ID: {player_id}")
                        st.rerun()
                    else:
                        st.error("Please enter a player name")
        
        else:
            # Player selection
            player_options = {pid: player['name'] for pid, player in st.session_state.players.items()}
            
            selected_player = st.selectbox(
                "Select Player",
                options=list(player_options.keys()),
                format_func=lambda x: player_options[x],
                index=0 if st.session_state.current_player is None else list(player_options.keys()).index(st.session_state.current_player) if st.session_state.current_player in player_options else 0
            )
            
            st.session_state.current_player = selected_player
            
            # Add new player option
            with st.expander("➕ Add New Player"):
                with st.form("add_player"):
                    new_player_name = st.text_input("New Player Name")
                    new_player_email = st.text_input("Email (optional)")
                    
                    if st.form_submit_button("Add Player"):
                        if new_player_name:
                            new_player_id = simulator.create_player(new_player_name, new_player_email)
                            st.session_state.current_player = new_player_id
                            st.success(f"Added {new_player_name}!")
                            st.rerun()
        
        # Game settings
        with st.expander("⚙️ Game Settings"):
            st.write(f"**Starting Cash:** ${st.session_state.game_settings['starting_cash']:,.2f}")
            st.write(f"**Commission:** ${st.session_state.game_settings['commission']:.2f}")
            st.write(f"**Game Duration:** {st.session_state.game_settings['game_duration_days']} days")
            
            if st.button("Reset All Data"):
                st.session_state.players = {}
                st.session_state.current_player = None
                st.success("All data reset!")
                st.rerun()
    
    # Main content
    if st.session_state.current_player and st.session_state.current_player in st.session_state.players:
        current_player = st.session_state.players[st.session_state.current_player]
        
        # Player dashboard
        st.subheader(f"👨‍💼 {current_player['name']}'s Dashboard")
        
        # Portfolio overview
        portfolio_value = simulator.get_portfolio_value(st.session_state.current_player)
        total_return = portfolio_value - st.session_state.game_settings['starting_cash']
        return_percentage = (total_return / st.session_state.game_settings['starting_cash']) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if total_return >= 0:
                st.markdown(f"""
                <div class="profit-card">
                    <h3>💰 Portfolio Value</h3>
                    <h2>${portfolio_value:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="loss-card">
                    <h3>💰 Portfolio Value</h3>
                    <h2>${portfolio_value:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="portfolio-card">
                <h3>💵 Cash Available</h3>
                <h2>${current_player['cash']:,.2f}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if total_return >= 0:
                st.markdown(f"""
                <div class="profit-card">
                    <h3>📈 Total Return</h3>
                    <h2>${total_return:,.2f}</h2>
                    <p>({return_percentage:+.2f}%)</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="loss-card">
                    <h3>📉 Total Return</h3>
                    <h2>${total_return:,.2f}</h2>
                    <p>({return_percentage:+.2f}%)</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="portfolio-card">
                <h3>🔄 Total Trades</h3>
                <h2>{current_player['total_trades']}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Achievements
        if current_player['achievements']:
            st.subheader("🏆 Achievements")
            achievement_html = ""
            for achievement in current_player['achievements']:
                achievement_html += f'<span class="achievement-badge">{achievement}</span>'
            st.markdown(achievement_html, unsafe_allow_html=True)
        
        # Main tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Trade", "📈 Portfolio", "📋 History", "🏆 Leaderboard", "📊 Market"])
        
        with tab1:
            st.subheader("🛒 Buy & Sell Stocks")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### 📈 Buy Stocks")
                
                selected_stock = st.selectbox(
                    "Select Stock",
                    simulator.available_stocks,
                    key="buy_stock"
                )
                
                if selected_stock:
                    stock_data = simulator.get_stock_price(selected_stock)
                    if stock_data:
                        st.write(f"**{stock_data['name']}**")
                        st.write(f"**Current Price:** ${stock_data['price']:.2f}")
                        
                        change_class = "positive" if stock_data['change'] >= 0 else "negative"
                        st.markdown(f"**Change:** <span class='{change_class}'>${stock_data['change']:+.2f} ({stock_data['change_percent']:+.2f}%)</span>", unsafe_allow_html=True)
                        
                        buy_shares = st.number_input("Number of Shares", min_value=1, value=1, key="buy_shares")
                        total_cost = (stock_data['price'] * buy_shares) + st.session_state.game_settings['commission']
                        
                        st.write(f"**Total Cost:** ${total_cost:.2f} (including ${st.session_state.game_settings['commission']:.2f} commission)")
                        
                        if st.button("🛒 Buy Stock", key="buy_button"):
                            result = simulator.buy_stock(st.session_state.current_player, selected_stock, buy_shares)
                            if result['success']:
                                st.markdown(f"""
                                <div class="trade-success">
                                    <h4>✅ Trade Successful!</h4>
                                    <p>{result['message']}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                st.rerun()
                            else:
                                st.markdown(f"""
                                <div class="trade-error">
                                    <h4>❌ Trade Failed</h4>
                                    <p>{result['message']}</p>
                                </div>
                                """, unsafe_allow_html=True)
            
            with col2:
                st.write("### 📉 Sell Stocks")
                
                if current_player['portfolio']:
                    owned_stocks = list(current_player['portfolio'].keys())
                    selected_sell_stock = st.selectbox(
                        "Select Stock to Sell",
                        owned_stocks,
                        key="sell_stock"
                    )
                    
                    if selected_sell_stock:
                        position = current_player['portfolio'][selected_sell_stock]
                        stock_data = simulator.get_stock_price(selected_sell_stock)
                        
                        if stock_data:
                            st.write(f"**{stock_data['name']}**")
                            st.write(f"**Shares Owned:** {position['shares']}")
                            st.write(f"**Average Price:** ${position['avg_price']:.2f}")
                            st.write(f"**Current Price:** ${stock_data['price']:.2f}")
                            
                            unrealized_pl = (stock_data['price'] - position['avg_price']) * position['shares']
                            pl_class = "positive" if unrealized_pl >= 0 else "negative"
                            st.markdown(f"**Unrealized P&L:** <span class='{pl_class}'>${unrealized_pl:+.2f}</span>", unsafe_allow_html=True)
                            
                            sell_shares = st.number_input(
                                "Number of Shares to Sell", 
                                min_value=1, 
                                max_value=position['shares'], 
                                value=min(1, position['shares']),
                                key="sell_shares"
                            )
                            
                            total_proceeds = (stock_data['price'] * sell_shares) - st.session_state.game_settings['commission']
                            st.write(f"**Total Proceeds:** ${total_proceeds:.2f} (after ${st.session_state.game_settings['commission']:.2f} commission)")
                            
                            if st.button("💰 Sell Stock", key="sell_button"):
                                result = simulator.sell_stock(st.session_state.current_player, selected_sell_stock, sell_shares)
                                if result['success']:
                                    pl_message = ""
                                    if 'profit_loss' in result:
                                        pl = result['profit_loss']
                                        pl_class = "profit" if pl >= 0 else "loss"
                                        pl_message = f"<br>Profit/Loss: <strong>${pl:+.2f}</strong>"
                                    
                                    st.markdown(f"""
                                    <div class="trade-success">
                                        <h4>✅ Trade Successful!</h4>
                                        <p>{result['message']}{pl_message}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    st.rerun()
                                else:
                                    st.markdown(f"""
                                    <div class="trade-error">
                                        <h4>❌ Trade Failed</h4>
                                        <p>{result['message']}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                else:
                    st.info("You don't own any stocks yet. Buy some stocks first!")
        
        with tab2:
            st.subheader("📊 Your Portfolio")
            
            if current_player['portfolio']:
                # Portfolio chart
                portfolio_chart = simulator.create_portfolio_chart(st.session_state.current_player)
                if portfolio_chart:
                    st.plotly_chart(portfolio_chart, use_container_width=True)
                
                # Performance chart
                performance_chart = simulator.create_performance_chart(st.session_state.current_player)
                if performance_chart:
                    st.plotly_chart(performance_chart, use_container_width=True)
                
                # Portfolio table
                portfolio_data = []
                total_portfolio_value = 0
                
                for symbol, position in current_player['portfolio'].items():
                    stock_data = simulator.get_stock_price(symbol)
                    if stock_data:
                        current_value = stock_data['price'] * position['shares']
                        cost_basis = position['avg_price'] * position['shares']
                        unrealized_pl = current_value - cost_basis
                        unrealized_pl_percent = (unrealized_pl / cost_basis) * 100
                        
                        portfolio_data.append({
                            'Symbol': symbol,
                            'Name': stock_data['name'],
                            'Shares': position['shares'],
                            'Avg Price': f"${position['avg_price']:.2f}",
                            'Current Price': f"${stock_data['price']:.2f}",
                            'Current Value': f"${current_value:.2f}",
                            'Cost Basis': f"${cost_basis:.2f}",
                            'Unrealized P&L': f"${unrealized_pl:+.2f}",
                            'P&L %': f"{unrealized_pl_percent:+.2f}%"
                        })
                        
                        total_portfolio_value += current_value
                
                if portfolio_data:
                    df = pd.DataFrame(portfolio_data)
                    st.dataframe(df, use_container_width=True)
                    
                    st.write(f"**Total Portfolio Value:** ${total_portfolio_value:,.2f}")
                    st.write(f"**Cash:** ${current_player['cash']:,.2f}")
                    st.write(f"**Total Account Value:** ${total_portfolio_value + current_player['cash']:,.2f}")
            else:
                st.info("Your portfolio is empty. Start trading to build your portfolio!")
        
        with tab3:
            st.subheader("📋 Trade History")
            
            if current_player['trade_history']:
                trade_data = []
                
                for trade in reversed(current_player['trade_history']):  # Most recent first
                    trade_data.append({
                        'Date': trade['timestamp'].strftime('%Y-%m-%d %H:%M'),
                        'Type': trade['type'],
                        'Symbol': trade['symbol'],
                        'Name': trade.get('name', trade['symbol']),
                        'Shares': trade['shares'],
                        'Price': f"${trade['price']:.2f}",
                        'Total': f"${trade.get('total_cost', trade.get('total_proceeds', 0)):.2f}",
                        'P&L': f"${trade.get('profit_loss', 0):+.2f}" if 'profit_loss' in trade else 'N/A'
                    })
                
                df = pd.DataFrame(trade_data)
                st.dataframe(df, use_container_width=True)
                
                # Trade statistics
                st.subheader("📊 Trading Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Trades", current_player['total_trades'])
                
                with col2:
                    st.metric("Best Trade", f"${current_player['best_trade']:+.2f}")
                
                with col3:
                    st.metric("Worst Trade", f"${current_player['worst_trade']:+.2f}")
            else:
                st.info("No trades yet. Start trading to see your history!")
        
        with tab4:
            st.subheader("🏆 Leaderboard")
            
            leaderboard_df = simulator.get_leaderboard()
            
            if not leaderboard_df.empty:
                # Top 3 special display
                if len(leaderboard_df) >= 1:
                    top_player = leaderboard_df.iloc[0]
                    st.markdown(f"""
                    <div class="leaderboard-gold">
                        <h3>🥇 1st Place: {top_player['Player']}</h3>
                        <p><strong>Portfolio Value:</strong> ${top_player['Portfolio Value']:,.2f}</p>
                        <p><strong>Return:</strong> {top_player['Return %']:+.2f}% (${top_player['Total Return']:+,.2f})</p>
                        <p><strong>Trades:</strong> {top_player['Total Trades']} | <strong>Achievements:</strong> {top_player['Achievements']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                if len(leaderboard_df) >= 2:
                    second_player = leaderboard_df.iloc[1]
                    st.markdown(f"""
                    <div class="leaderboard-silver">
                        <h3>🥈 2nd Place: {second_player['Player']}</h3>
                        <p><strong>Portfolio Value:</strong> ${second_player['Portfolio Value']:,.2f}</p>
                        <p><strong>Return:</strong> {second_player['Return %']:+.2f}% (${second_player['Total Return']:+,.2f})</p>
                        <p><strong>Trades:</strong> {second_player['Total Trades']} | <strong>Achievements:</strong> {second_player['Achievements']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                if len(leaderboard_df) >= 3:
                    third_player = leaderboard_df.iloc[2]
                    st.markdown(f"""
                    <div class="leaderboard-bronze">
                        <h3>🥉 3rd Place: {third_player['Player']}</h3>
                        <p><strong>Portfolio Value:</strong> ${third_player['Portfolio Value']:,.2f}</p>
                        <p><strong>Return:</strong> {third_player['Return %']:+.2f}% (${third_player['Total Return']:+,.2f})</p>
                        <p><strong>Trades:</strong> {third_player['Total Trades']} | <strong>Achievements:</strong> {third_player['Achievements']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Full leaderboard table
                st.subheader("📊 Full Rankings")
                display_df = leaderboard_df.drop(['Player ID'], axis=1).copy()
                display_df['Portfolio Value'] = display_df['Portfolio Value'].apply(lambda x: f"${x:,.2f}")
                display_df['Total Return'] = display_df['Total Return'].apply(lambda x: f"${x:+,.2f}")
                display_df['Return %'] = display_df['Return %'].apply(lambda x: f"{x:+.2f}%")
                
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("No players yet. Create players to see the leaderboard!")
        
        with tab5:
            st.subheader("📊 Market Overview")
            
            # Market data for popular stocks
            st.write("### 🔥 Popular Stocks")
            
            popular_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX']
            market_data = []
            
            for symbol in popular_stocks:
                stock_data = simulator.get_stock_price(symbol)
                if stock_data:
                    market_data.append({
                        'Symbol': symbol,
                        'Name': stock_data['name'],
                        'Price': f"${stock_data['price']:.2f}",
                        'Change': f"${stock_data['change']:+.2f}",
                        'Change %': f"{stock_data['change_percent']:+.2f}%",
                        'Volume': f"{stock_data['volume']/1e6:.1f}M" if stock_data['volume'] > 0 else 'N/A'
                    })
            
            if market_data:
                market_df = pd.DataFrame(market_data)
                st.dataframe(market_df, use_container_width=True)
            
            # Market indices (if available)
            st.write("### 📈 Market Indices")
            indices = ['SPY', 'QQQ', 'IWM']
            indices_data = []
            
            for symbol in indices:
                stock_data = simulator.get_stock_price(symbol)
                if stock_data:
                    indices_data.append({
                        'Index': symbol,
                        'Name': stock_data['name'],
                        'Price': f"${stock_data['price']:.2f}",
                        'Change': f"${stock_data['change']:+.2f}",
                        'Change %': f"{stock_data['change_percent']:+.2f}%"
                    })
            
            if indices_data:
                indices_df = pd.DataFrame(indices_data)
                st.dataframe(indices_df, use_container_width=True)
        
    else:
        # Welcome screen
        st.markdown("""
        ## 🎮 Welcome to the Stock Trading Simulator!
        
        **Learn to trade stocks with virtual money:**
        
        ### 🌟 Features:
        - 💰 Start with $100,000 virtual cash
        - 📈 Trade real stocks with live prices
        - 🏆 Compete with friends on the leaderboard
        - 🎯 Unlock achievements as you trade
        - 📊 Track your portfolio performance
        - 📋 View detailed trade history
        
        ### 🚀 How to Start:
        1. Create a player account in the sidebar
        2. Browse and buy stocks you're interested in
        3. Watch your portfolio grow (or shrink!)
        4. Compete with friends and climb the leaderboard
        5. Unlock achievements and become a trading master
        
        ### 💡 Trading Tips:
        - Diversify your portfolio across different sectors
        - Don't put all your money in one stock
        - Keep some cash for opportunities
        - Learn from your wins and losses
        - Have fun and don't risk real money!
        
        **Ready to start your trading journey? Create a player in the sidebar!**
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🎮 Stock Trading Simulator | 📈 Educational Tool | ⚠️ Virtual Money Only</p>
        <p><small>This is for educational purposes only. Not real trading or investment advice.</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
