import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import time
import requests
from typing import Dict, List, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Configure Streamlit page
st.set_page_config(
    page_title="Complete US Stock Market Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        padding: 1rem 0;
        border-bottom: 2px solid #e6f3ff;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .stock-card {
        border: 1px solid #e6f3ff;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
    
    .exchange-badge {
        background: #007bff;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 5px;
    }
    
    .sector-tag {
        background: #28a745;
        color: white;
        padding: 2px 6px;
        border-radius: 8px;
        font-size: 0.7em;
        margin-right: 5px;
    }
</style>
""", unsafe_allow_html=True)

class ComprehensiveStockTracker:
    def __init__(self):
        self.all_tickers = []
        self.stock_data = pd.DataFrame()
        self.cache_duration = 300  # 5 minutes
        
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_all_us_stocks(_self) -> pd.DataFrame:
        """Fetch all US publicly traded companies from multiple sources"""
        try:
            all_stocks = []
            
            # Method 1: Get from NASDAQ, NYSE, AMEX
            exchanges = ['nasdaq', 'nyse', 'amex']
            
            for exchange in exchanges:
                try:
                    # Using FMP API (free tier available)
                    url = f"https://financialmodelingprep.com/api/v3/stock/list?apikey=demo"
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for stock in data:
                            if stock.get('exchange') and stock.get('symbol'):
                                all_stocks.append({
                                    'symbol': stock['symbol'],
                                    'name': stock.get('name', 'N/A'),
                                    'exchange': stock.get('exchange', 'N/A'),
                                    'type': stock.get('type', 'Common Stock'),
                                    'sector': 'Unknown',
                                    'industry': 'Unknown',
                                    'market_cap': 0
                                })
                except Exception as e:
                    st.warning(f"Error fetching from {exchange}: {str(e)}")
                    continue
            
            # Method 2: Add major indices and ETFs
            major_tickers = [
                # S&P 500 components (sample)
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK-B',
                'UNH', 'JNJ', 'JPM', 'V', 'PG', 'HD', 'CVX', 'MA', 'PFE', 'ABBV',
                'BAC', 'KO', 'AVGO', 'PEP', 'TMO', 'COST', 'DIS', 'ABT', 'DHR',
                'VZ', 'ADBE', 'NFLX', 'CRM', 'ACN', 'TXN', 'NKE', 'QCOM', 'WMT',
                'NEE', 'RTX', 'HON', 'LOW', 'UPS', 'PM', 'ORCL', 'IBM', 'AMGN',
                'CVS', 'MDT', 'SPGI', 'C', 'GS', 'CAT', 'AXP', 'BLK', 'DE', 'BA',
                
                # Technology
                'INTC', 'AMD', 'CRM', 'PYPL', 'UBER', 'SHOP', 'ZOOM', 'DOCU',
                'TWTR', 'SNAP', 'PINS', 'ROKU', 'SQ', 'PLTR', 'CRWD', 'SNOW',
                
                # Healthcare & Biotech
                'MRNA', 'BNTX', 'GILD', 'BIIB', 'REGN', 'VRTX', 'ILMN', 'ISRG',
                
                # Finance
                'WFC', 'MS', 'SCHW', 'USB', 'PNC', 'TFC', 'COF', 'AIG',
                
                # Energy
                'XOM', 'COP', 'EOG', 'SLB', 'MPC', 'VLO', 'PSX', 'OXY',
                
                # Consumer
                'AMZN', 'TSLA', 'NKE', 'SBUX', 'MCD', 'CMG', 'LULU', 'TJX',
                
                # REITs
                'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'WELL', 'DLR', 'SPG',
                
                # ETFs
                'SPY', 'QQQ', 'IWM', 'VTI', 'VOO', 'VEA', 'VWO', 'BND',
                
                # Crypto-related
                'COIN', 'RIOT', 'MARA', 'MSTR', 'SQ', 'PYPL'
            ]
            
            # Add major tickers if not already present
            existing_symbols = {stock['symbol'] for stock in all_stocks}
            for ticker in major_tickers:
                if ticker not in existing_symbols:
                    all_stocks.append({
                        'symbol': ticker,
                        'name': 'Major US Stock',
                        'exchange': 'NASDAQ/NYSE',
                        'type': 'Common Stock',
                        'sector': 'Unknown',
                        'industry': 'Unknown',
                        'market_cap': 0
                    })
            
            # Method 3: Add popular stocks from different sectors
            sector_stocks = {
                'Technology': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'ADBE', 'CRM', 'ORCL', 'IBM', 'INTC', 'AMD', 'QCOM', 'AVGO', 'TXN', 'AMAT', 'LRCX', 'KLAC'],
                'Healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN', 'GILD', 'BIIB', 'REGN', 'VRTX', 'ILMN', 'ISRG', 'DXCM', 'ZTS', 'MRNA', 'BNTX', 'CVS'],
                'Finance': ['BRK-B', 'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'USB', 'PNC', 'TFC', 'COF', 'AXP', 'SCHW', 'BLK', 'SPGI', 'ICE', 'CME', 'CB', 'AIG', 'PGR'],
                'Consumer': ['AMZN', 'TSLA', 'HD', 'WMT', 'PG', 'KO', 'PEP', 'COST', 'NKE', 'SBUX', 'MCD', 'DIS', 'NFLX', 'LOW', 'TJX', 'TGT', 'LULU', 'CMG', 'YUM', 'ULTA'],
                'Energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'MPC', 'VLO', 'PSX', 'OXY', 'KMI', 'WMB', 'EPD', 'ET', 'MPLX', 'MRO', 'APA', 'DVN', 'FANG', 'PXD', 'HAL'],
                'Industrial': ['BA', 'HON', 'UPS', 'RTX', 'CAT', 'DE', 'MMM', 'LMT', 'GD', 'NOC', 'FDX', 'CSX', 'NSC', 'UNP', 'ITW', 'EMR', 'ETN', 'PH', 'CMI', 'GWW']
            }
            
            for sector, tickers in sector_stocks.items():
                for ticker in tickers:
                    if ticker not in existing_symbols:
                        all_stocks.append({
                            'symbol': ticker,
                            'name': f'{sector} Stock',
                            'exchange': 'NASDAQ/NYSE',
                            'type': 'Common Stock',
                            'sector': sector,
                            'industry': sector,
                            'market_cap': 0
                        })
            
            # Convert to DataFrame and clean up
            df = pd.DataFrame(all_stocks)
            if not df.empty:
                # Remove duplicates
                df = df.drop_duplicates(subset=['symbol'], keep='first')
                
                # Filter out invalid symbols
                df = df[df['symbol'].str.len() <= 5]  # Most US stocks have 1-5 character symbols
                df = df[~df['symbol'].str.contains('[^A-Z.-]', regex=True)]  # Only letters, dots, and dashes
                
                # Sort by symbol
                df = df.sort_values('symbol').reset_index(drop=True)
                
                st.success(f"Successfully loaded {len(df)} US stocks from multiple sources!")
                return df
            else:
                # Fallback to major stocks only
                st.warning("Using fallback stock list due to API limitations")
                return _self.get_fallback_stocks()
                
        except Exception as e:
            st.error(f"Error fetching stock list: {str(e)}")
            return _self.get_fallback_stocks()
    
    def get_fallback_stocks(self) -> pd.DataFrame:
        """Fallback list of major US stocks"""
        fallback_stocks = [
            # Top 100 by market cap
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'BRK-B', 'name': 'Berkshire Hathaway Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'UNH', 'name': 'UnitedHealth Group Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'V', 'name': 'Visa Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'PG', 'name': 'Procter & Gamble Co.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'HD', 'name': 'Home Depot Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'CVX', 'name': 'Chevron Corporation', 'exchange': 'NYSE', 'sector': 'Energy'},
            {'symbol': 'MA', 'name': 'Mastercard Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'PFE', 'name': 'Pfizer Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'ABBV', 'name': 'AbbVie Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'BAC', 'name': 'Bank of America Corp.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'KO', 'name': 'Coca-Cola Company', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'AVGO', 'name': 'Broadcom Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'PEP', 'name': 'PepsiCo Inc.', 'exchange': 'NASDAQ', 'sector': 'Consumer Goods'},
            {'symbol': 'TMO', 'name': 'Thermo Fisher Scientific Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'COST', 'name': 'Costco Wholesale Corp.', 'exchange': 'NASDAQ', 'sector': 'Consumer Goods'},
            {'symbol': 'DIS', 'name': 'Walt Disney Company', 'exchange': 'NYSE', 'sector': 'Entertainment'},
            {'symbol': 'ABT', 'name': 'Abbott Laboratories', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'DHR', 'name': 'Danaher Corporation', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'VZ', 'name': 'Verizon Communications Inc.', 'exchange': 'NYSE', 'sector': 'Telecommunications'},
            {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'exchange': 'NASDAQ', 'sector': 'Entertainment'},
            {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'ACN', 'name': 'Accenture plc', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'TXN', 'name': 'Texas Instruments Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'NKE', 'name': 'Nike Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'QCOM', 'name': 'Qualcomm Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'WMT', 'name': 'Walmart Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'NEE', 'name': 'NextEra Energy Inc.', 'exchange': 'NYSE', 'sector': 'Utilities'},
            {'symbol': 'RTX', 'name': 'Raytheon Technologies Corp.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'HON', 'name': 'Honeywell International Inc.', 'exchange': 'NASDAQ', 'sector': 'Industrial'},
            {'symbol': 'LOW', 'name': 'Lowes Companies Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'UPS', 'name': 'United Parcel Service Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'PM', 'name': 'Philip Morris International Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'ORCL', 'name': 'Oracle Corporation', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'IBM', 'name': 'International Business Machines Corp.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'AMGN', 'name': 'Amgen Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'CVS', 'name': 'CVS Health Corporation', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'MDT', 'name': 'Medtronic plc', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'SPGI', 'name': 'S&P Global Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'C', 'name': 'Citigroup Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'GS', 'name': 'Goldman Sachs Group Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'CAT', 'name': 'Caterpillar Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'AXP', 'name': 'American Express Company', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'BLK', 'name': 'BlackRock Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'DE', 'name': 'Deere & Company', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'BA', 'name': 'Boeing Company', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'NOW', 'name': 'ServiceNow Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'INTU', 'name': 'Intuit Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'ISRG', 'name': 'Intuitive Surgical Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'BKNG', 'name': 'Booking Holdings Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'GILD', 'name': 'Gilead Sciences Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'AMT', 'name': 'American Tower Corporation', 'exchange': 'NYSE', 'sector': 'Real Estate'},
            {'symbol': 'MRK', 'name': 'Merck & Co. Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'LRCX', 'name': 'Lam Research Corporation', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'SBUX', 'name': 'Starbucks Corporation', 'exchange': 'NASDAQ', 'sector': 'Consumer Goods'},
            {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'TGT', 'name': 'Target Corporation', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'REGN', 'name': 'Regeneron Pharmaceuticals Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'VRTX', 'name': 'Vertex Pharmaceuticals Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'INTC', 'name': 'Intel Corporation', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'AMAT', 'name': 'Applied Materials Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'SYK', 'name': 'Stryker Corporation', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'MU', 'name': 'Micron Technology Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'PANW', 'name': 'Palo Alto Networks Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'BSX', 'name': 'Boston Scientific Corporation', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'TJX', 'name': 'TJX Companies Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'SCHW', 'name': 'Charles Schwab Corporation', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'CB', 'name': 'Chubb Limited', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'MCD', 'name': 'McDonalds Corporation', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'SO', 'name': 'Southern Company', 'exchange': 'NYSE', 'sector': 'Utilities'},
            {'symbol': 'LIN', 'name': 'Linde plc', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'ETN', 'name': 'Eaton Corporation plc', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'ZTS', 'name': 'Zoetis Inc.', 'exchange': 'NYSE', 'sector': 'Healthcare'},
            {'symbol': 'MMM', 'name': '3M Company', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'ICE', 'name': 'Intercontinental Exchange Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'PLD', 'name': 'Prologis Inc.', 'exchange': 'NYSE', 'sector': 'Real Estate'},
            {'symbol': 'FCX', 'name': 'Freeport-McMoRan Inc.', 'exchange': 'NYSE', 'sector': 'Materials'},
            {'symbol': 'APD', 'name': 'Air Products and Chemicals Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'EQIX', 'name': 'Equinix Inc.', 'exchange': 'NASDAQ', 'sector': 'Real Estate'},
            {'symbol': 'CSX', 'name': 'CSX Corporation', 'exchange': 'NASDAQ', 'sector': 'Industrial'},
            {'symbol': 'NSC', 'name': 'Norfolk Southern Corporation', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'DUK', 'name': 'Duke Energy Corporation', 'exchange': 'NYSE', 'sector': 'Utilities'},
            {'symbol': 'WFC', 'name': 'Wells Fargo & Company', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'USB', 'name': 'U.S. Bancorp', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'PNC', 'name': 'PNC Financial Services Group Inc.', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'AON', 'name': 'Aon plc', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'CME', 'name': 'CME Group Inc.', 'exchange': 'NASDAQ', 'sector': 'Finance'},
            {'symbol': 'CCI', 'name': 'Crown Castle International Corp.', 'exchange': 'NYSE', 'sector': 'Real Estate'},
            {'symbol': 'BIIB', 'name': 'Biogen Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'FDX', 'name': 'FedEx Corporation', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'SHW', 'name': 'Sherwin-Williams Company', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'ECL', 'name': 'Ecolab Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'GD', 'name': 'General Dynamics Corporation', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'PYPL', 'name': 'PayPal Holdings Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'ATVI', 'name': 'Activision Blizzard Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'ILMN', 'name': 'Illumina Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'EL', 'name': 'Estee Lauder Companies Inc.', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'KLAC', 'name': 'KLA Corporation', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'WM', 'name': 'Waste Management Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'DG', 'name': 'Dollar General Corporation', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'EMR', 'name': 'Emerson Electric Co.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'ITW', 'name': 'Illinois Tool Works Inc.', 'exchange': 'NYSE', 'sector': 'Industrial'},
            {'symbol': 'COF', 'name': 'Capital One Financial Corporation', 'exchange': 'NYSE', 'sector': 'Finance'},
            {'symbol': 'GM', 'name': 'General Motors Company', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'F', 'name': 'Ford Motor Company', 'exchange': 'NYSE', 'sector': 'Consumer Goods'},
            {'symbol': 'UBER', 'name': 'Uber Technologies Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'SNAP', 'name': 'Snap Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'COIN', 'name': 'Coinbase Global Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'SNOW', 'name': 'Snowflake Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'PLTR', 'name': 'Palantir Technologies Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'CRWD', 'name': 'CrowdStrike Holdings Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'ZM', 'name': 'Zoom Video Communications Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'DOCU', 'name': 'DocuSign Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'ROKU', 'name': 'Roku Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'PINS', 'name': 'Pinterest Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'TWLO', 'name': 'Twilio Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'OKTA', 'name': 'Okta Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'DDOG', 'name': 'Datadog Inc.', 'exchange': 'NASDAQ', 'sector': 'Technology'},
            {'symbol': 'MRNA', 'name': 'Moderna Inc.', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'BNTX', 'name': 'BioNTech SE', 'exchange': 'NASDAQ', 'sector': 'Healthcare'},
            {'symbol': 'SHOP', 'name': 'Shopify Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'SQ', 'name': 'Block Inc.', 'exchange': 'NYSE', 'sector': 'Technology'},
            {'symbol': 'ARKK', 'name': 'ARK Innovation ETF', 'exchange': 'NYSE', 'sector': 'ETF'},
            {'symbol': 'SPY', 'name': 'SPDR S&P 500 ETF Trust', 'exchange': 'NYSE', 'sector': 'ETF'},
            {'symbol': 'QQQ', 'name': 'Invesco QQQ Trust', 'exchange': 'NASDAQ', 'sector': 'ETF'},
            {'symbol': 'IWM', 'name': 'iShares Russell 2000 ETF', 'exchange': 'NYSE', 'sector': 'ETF'},
            {'symbol': 'VTI', 'name': 'Vanguard Total Stock Market ETF', 'exchange': 'NYSE', 'sector': 'ETF'},
            {'symbol': 'VOO', 'name': 'Vanguard S&P 500 ETF', 'exchange': 'NYSE', 'sector': 'ETF'},
        ]
        
        return pd.DataFrame(fallback_stocks)
    
    def fetch_batch_stock_data(self, tickers: List[str], max_workers: int = 10) -> pd.DataFrame:
        """Fetch stock data for multiple tickers in parallel"""
        data = []
        
        def fetch_single_stock(ticker):
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="2d")
                info = stock.info
                
                if len(hist) >= 1:
                    current_price = hist['Close'].iloc[-1]
                    prev_close = info.get('previousClose', current_price)
                    change = current_price - prev_close
                    change_percent = (change / prev_close) * 100
                    
                    return {
                        'Ticker': ticker,
                        'Name': info.get('longName', ticker),
                        'Sector': info.get('sector', 'Unknown'),
                        'Industry': info.get('industry', 'Unknown'),
                        'Exchange': info.get('exchange', 'Unknown'),
                        'Price': current_price,
                        'Change': change,
                        'Change%': change_percent,
                        'Market Cap': info.get('marketCap', 0),
                        'P/E Ratio': info.get('trailingPE', 0),
                        'Forward P/E': info.get('forwardPE', 0),
                        'PEG Ratio': info.get('pegRatio', 0),
                        'Dividend Yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
                        'Volume': hist['Volume'].iloc[-1] if len(hist) > 0 else 0,
                        'Avg Volume': info.get('averageVolume', 0),
                        '52W High': info.get('fiftyTwoWeekHigh', 0),
                        '52W Low': info.get('fiftyTwoWeekLow', 0),
                        'Beta': info.get('beta', 0),
                        'EPS': info.get('trailingEps', 0),
                        'Revenue': info.get('totalRevenue', 0),
                        'Employees': info.get('fullTimeEmployees', 0),
                        'Float': info.get('floatShares', 0),
                        'Shares Outstanding': info.get('sharesOutstanding', 0),
                        'Book Value': info.get('bookValue', 0),
                        'Price to Book': info.get('priceToBook', 0),
                        'Debt to Equity': info.get('debtToEquity', 0),
                        'ROE': info.get('returnOnEquity', 0),
                        'ROA': info.get('returnOnAssets', 0),
                        'Profit Margin': info.get('profitMargins', 0),
                        'Operating Margin': info.get('operatingMargins', 0),
                        'Gross Margin': info.get('grossMargins', 0),
                        'Revenue Growth': info.get('revenueGrowth', 0),
                        'Earnings Growth': info.get('earningsGrowth', 0),
                        'Current Ratio': info.get('currentRatio', 0),
                        'Quick Ratio': info.get('quickRatio', 0),
                        'Cash Per Share': info.get('totalCashPerShare', 0),
                        'Enterprise Value': info.get('enterpriseValue', 0),
                        'EV/Revenue': info.get('enterpriseToRevenue', 0),
                        'EV/EBITDA': info.get('enterpriseToEbitda', 0),
                        'Price/Sales': info.get('priceToSalesTrailing12Months', 0),
                        'Price/Cash Flow': info.get('priceToCashFlow', 0),
                        'Day High': hist['High'].iloc[-1] if len(hist) > 0 else current_price,
                        'Day Low': hist['Low'].iloc[-1] if len(hist) > 0 else current_price,
                        'Open': hist['Open'].iloc[-1] if len(hist) > 0 else current_price,
                        'Previous Close': prev_close,
                        'Country': info.get('country', 'Unknown'),
                        'Website': info.get('website', ''),
                        'Business Summary': info.get('longBusinessSummary', '')[:200] + '...' if info.get('longBusinessSummary') else '',
                        'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                return None
            except Exception as e:
                return None
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(fetch_single_stock, ticker): ticker for ticker in tickers}
            
            for future in as_completed(future_to_ticker):
                result = future.result()
                if result:
                    data.append(result)
        
        return pd.DataFrame(data)
    
    def format_large_number(self, value):
        """Format large numbers for display"""
        if pd.isna(value) or value == 0:
            return 'N/A'
        
        if abs(value) >= 1e12:
            return f"${value/1e12:.2f}T"
        elif abs(value) >= 1e9:
            return f"${value/1e9:.2f}B"
        elif abs(value) >= 1e6:
            return f"${value/1e6:.2f}M"
        elif abs(value) >= 1e3:
            return f"${value/1e3:.2f}K"
        else:
            return f"${value:.2f}"
    
    def create_market_overview_charts(self, df: pd.DataFrame):
        """Create comprehensive market overview charts"""
        if df.empty:
            return None, None, None
        
        # Sector Performance
        sector_perf = df.groupby('Sector')['Change%'].agg(['mean', 'count']).reset_index()
        sector_perf = sector_perf[sector_perf['count'] >= 3]  # Only sectors with 3+ stocks
        sector_perf = sector_perf.sort_values('mean', ascending=False)
        
        fig_sector = px.bar(
            sector_perf, 
            x='Sector', 
            y='mean',
            title='Average Sector Performance Today',
            labels={'mean': 'Average Change %', 'Sector': 'Sector'},
            color='mean',
            color_continuous_scale='RdYlGn'
        )
        fig_sector.update_layout(height=400)
        
        # Market Cap Distribution
        df_with_mcap = df[df['Market Cap'] > 0].copy()
        df_with_mcap['Market Cap Bucket'] = pd.cut(
            df_with_mcap['Market Cap'],
            bins=[0, 1e9, 10e9, 100e9, 1e12, float('inf')],
            labels=['<$1B', '$1B-$10B', '$10B-$100B', '$100B-$1T', '>$1T']
        )
        
        mcap_dist = df_with_mcap['Market Cap Bucket'].value_counts().reset_index()
        fig_mcap = px.pie(
            mcap_dist,
            values='count',
            names='Market Cap Bucket',
            title='Market Cap Distribution'
        )
        fig_mcap.update_layout(height=400)
        
        # Top Gainers vs Losers
        gainers_losers = pd.DataFrame({
            'Category': ['Gainers', 'Losers', 'Unchanged'],
            'Count': [
                len(df[df['Change%'] > 0]),
                len(df[df['Change%'] < 0]),
                len(df[df['Change%'] == 0])
            ]
        })
        
        fig_gainers = px.bar(
            gainers_losers,
            x='Category',
            y='Count',
            title='Market Breadth: Gainers vs Losers',
            color='Category',
            color_discrete_map={'Gainers': 'green', 'Losers': 'red', 'Unchanged': 'gray'}
        )
        fig_gainers.update_layout(height=400)
        
        return fig_sector, fig_mcap, fig_gainers
    
    def create_individual_stock_chart(self, ticker: str, period: str = "1mo"):
        """Create detailed chart for individual stock"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                return None
            
            fig = go.Figure()
            
            # Add candlestick chart
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name=ticker
            ))
            
            # Add volume
            fig.add_trace(go.Bar(
                x=hist.index,
                y=hist['Volume'],
                name='Volume',
                yaxis='y2',
                opacity=0.3
            ))
            
            # Add moving averages
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['MA50'] = hist['Close'].rolling(window=50).mean()
            
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['MA20'],
                mode='lines',
                name='MA20',
                line=dict(color='orange', width=1)
            ))
            
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['MA50'],
                mode='lines',
                name='MA50',
                line=dict(color='blue', width=1)
            ))
            
            fig.update_layout(
                title=f"{ticker} Stock Price and Volume",
                yaxis_title="Price ($)",
                yaxis2=dict(
                    title="Volume",
                    overlaying="y",
                    side="right",
                    showgrid=False
                ),
                xaxis_title="Date",
                template="plotly_white",
                height=600,
                showlegend=True
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating chart for {ticker}: {str(e)}")
            return None

def main():
    st.markdown("""
    <div class="main-header">
        <h1>🏛️ Complete US Stock Market Tracker</h1>
        <p>Comprehensive real-time monitoring of ALL publicly traded US companies</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize tracker
    tracker = ComprehensiveStockTracker()
    
    # Sidebar
    st.sidebar.header("🎛️ Market Controls")
    
    # Load stock universe
    with st.sidebar:
        if st.button("🔄 Refresh Stock Universe"):
            st.cache_data.clear()
        
        st.info("💡 **Tip:** This tracker includes thousands of US stocks. Use filters to narrow down results.")
    
    # Load all stocks
    with st.spinner("Loading comprehensive US stock database..."):
        all_stocks_df = tracker.get_all_us_stocks()
    
    if all_stocks_df.empty:
        st.error("Unable to load stock data. Please check your internet connection.")
        return
    
    # Display stock universe info
    st.subheader("📊 Stock Universe Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Stocks", f"{len(all_stocks_df):,}")
    
    with col2:
        exchanges = all_stocks_df['exchange'].value_counts()
        st.metric("Exchanges", len(exchanges))
    
    with col3:
        sectors = all_stocks_df['sector'].value_counts()
        st.metric("Sectors", len(sectors))
    
    with col4:
        st.metric("Last Updated", datetime.now().strftime("%H:%M"))
    
    # Filters
    st.subheader("🔍 Search and Filter")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_term = st.text_input("🔍 Search by Symbol or Name", "")
        
    with col2:
        available_sectors = ['All'] + sorted(all_stocks_df['sector'].unique().tolist())
        selected_sector = st.selectbox("📈 Sector", available_sectors)
        
    with col3:
        available_exchanges = ['All'] + sorted(all_stocks_df['exchange'].unique().tolist())
        selected_exchange = st.selectbox("🏛️ Exchange", available_exchanges)
    
    # Advanced filters
    with st.expander("🎯 Advanced Filters"):
        col1, col2 = st.columns(2)
        
        with col1:
            min_price = st.number_input("Min Price ($)", 0.01, 10000.0, 0.01)
            max_price = st.number_input("Max Price ($)", 0.01, 10000.0, 10000.0)
            
        with col2:
            stock_type = st.selectbox("Stock Type", ['All', 'Common Stock', 'ETF', 'Preferred Stock'])
            sort_by = st.selectbox("Sort By", ['Symbol', 'Name', 'Price', 'Change%', 'Volume', 'Market Cap'])
    
    # Apply filters
    filtered_df = all_stocks_df.copy()
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['symbol'].str.contains(search_term.upper(), na=False) |
            filtered_df['name'].str.contains(search_term, case=False, na=False)
        ]
    
    if selected_sector != 'All':
        filtered_df = filtered_df[filtered_df['sector'] == selected_sector]
    
    if selected_exchange != 'All':
        filtered_df = filtered_df[filtered_df['exchange'] == selected_exchange]
    
    # Limit results for performance
    max_results = st.sidebar.slider("Max Results to Load", 10, 500, 100)
    display_tickers = filtered_df['symbol'].head(max_results).tolist()
    
    st.info(f"Found {len(filtered_df)} stocks matching your criteria. Loading data for top {len(display_tickers)} stocks...")
    
    # Fetch detailed data
    if display_tickers:
        with st.spinner(f"Fetching detailed data for {len(display_tickers)} stocks..."):
            detailed_df = tracker.fetch_batch_stock_data(display_tickers, max_workers=20)
        
        if not detailed_df.empty:
            # Market Overview
            st.subheader("📈 Market Overview")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_change = detailed_df['Change%'].mean()
                st.metric("Average Change", f"{avg_change:.2f}%")
            
            with col2:
                gainers = len(detailed_df[detailed_df['Change%'] > 0])
                st.metric("Gainers", gainers)
            
            with col3:
                losers = len(detailed_df[detailed_df['Change%'] < 0])
                st.metric("Losers", losers)
            
            with col4:
                total_volume = detailed_df['Volume'].sum()
                st.metric("Total Volume", f"{total_volume/1e6:.1f}M")
            
            # Charts
            st.subheader("📊 Market Analysis")
            
            sector_chart, mcap_chart, gainers_chart = tracker.create_market_overview_charts(detailed_df)
            
            if sector_chart:
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(sector_chart, use_container_width=True)
                with col2:
                    st.plotly_chart(gainers_chart, use_container_width=True)
            
            if mcap_chart:
                st.plotly_chart(mcap_chart, use_container_width=True)
            
            # Top Movers
            st.subheader("🏆 Top Movers")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**📈 Top Gainers**")
                top_gainers = detailed_df.nlargest(10, 'Change%')[['Ticker', 'Name', 'Price', 'Change%']]
                st.dataframe(top_gainers, use_container_width=True)
            
            with col2:
                st.write("**📉 Top Losers**")
                top_losers = detailed_df.nsmallest(10, 'Change%')[['Ticker', 'Name', 'Price', 'Change%']]
                st.dataframe(top_losers, use_container_width=True)
            
            # Detailed Stock Table
            st.subheader("📋 Detailed Stock Data")
            
            # Format the dataframe for better display
            display_df = detailed_df.copy()
            
            # Format numeric columns
            numeric_columns = ['Price', 'Change', 'Market Cap', 'Volume', 'Avg Volume', '52W High', '52W Low']
            for col in numeric_columns:
                if col in display_df.columns:
                    if col == 'Price':
                        display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}" if pd.notna(x) else 'N/A')
                    elif col == 'Change':
                        display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}" if pd.notna(x) else 'N/A')
                    elif col in ['Market Cap']:
                        display_df[col] = display_df[col].apply(tracker.format_large_number)
                    elif col in ['Volume', 'Avg Volume']:
                        display_df[col] = display_df[col].apply(lambda x: f"{x/1e6:.1f}M" if pd.notna(x) and x > 0 else 'N/A')
                    elif col in ['52W High', '52W Low']:
                        display_df[col] = display_df[col].apply(lambda x: f"${x:.2f}" if pd.notna(x) and x > 0 else 'N/A')
            
            # Format percentage columns
            percentage_columns = ['Change%', 'Dividend Yield', 'ROE', 'ROA', 'Profit Margin']
            for col in percentage_columns:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else 'N/A')
            
            # Format ratio columns
            ratio_columns = ['P/E Ratio', 'Forward P/E', 'PEG Ratio', 'Beta', 'Price to Book']
            for col in ratio_columns:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) and x > 0 else 'N/A')
            
            # Select columns to display
            display_columns = ['Ticker', 'Name', 'Sector', 'Exchange', 'Price', 'Change', 'Change%', 
                             'Market Cap', 'P/E Ratio', 'Dividend Yield', 'Volume', 'Beta']
            
            available_columns = [col for col in display_columns if col in display_df.columns]
            
            # Add column selector
            with st.expander("📊 Customize Table Columns"):
                all_columns = display_df.columns.tolist()
                selected_columns = st.multiselect(
                    "Select columns to display:",
                    all_columns,
                    default=available_columns
                )
                
                if selected_columns:
                    available_columns = selected_columns
            
            # Display the table
            st.dataframe(
                display_df[available_columns],
                use_container_width=True,
                height=600
            )
            
            # Individual Stock Analysis
            st.subheader("🔍 Individual Stock Analysis")
            
            selected_ticker = st.selectbox(
                "Select a stock for detailed analysis:",
                detailed_df['Ticker'].tolist()
            )
            
            if selected_ticker:
                stock_data = detailed_df[detailed_df['Ticker'] == selected_ticker].iloc[0]
                
                # Stock details
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**📊 {stock_data['Name']} ({selected_ticker})**")
                    st.write(f"**Sector:** {stock_data['Sector']}")
                    st.write(f"**Industry:** {stock_data['Industry']}")
                    st.write(f"**Exchange:** {stock_data['Exchange']}")
                    st.write(f"**Price:** ${stock_data['Price']:.2f}")
                    st.write(f"**Change:** ${stock_data['Change']:.2f} ({stock_data['Change%']:.2f}%)")
                    st.write(f"**Market Cap:** {tracker.format_large_number(stock_data['Market Cap'])}")
                    
                with col2:
                    st.write(f"**P/E Ratio:** {stock_data['P/E Ratio']:.2f}" if stock_data['P/E Ratio'] > 0 else "**P/E Ratio:** N/A")
                    st.write(f"**Beta:** {stock_data['Beta']:.2f}" if stock_data['Beta'] > 0 else "**Beta:** N/A")
                    st.write(f"**Dividend Yield:** {stock_data['Dividend Yield']:.2f}%" if stock_data['Dividend Yield'] > 0 else "**Dividend Yield:** N/A")
                    st.write(f"**52W High:** ${stock_data['52W High']:.2f}" if stock_data['52W High'] > 0 else "**52W High:** N/A")
                    st.write(f"**52W Low:** ${stock_data['52W Low']:.2f}" if stock_data['52W Low'] > 0 else "**52W Low:** N/A")
                    st.write(f"**Volume:** {stock_data['Volume']/1e6:.1f}M" if stock_data['Volume'] > 0 else "**Volume:** N/A")
                
                # Chart
                period = st.selectbox("Chart Period", ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y'])
                
                chart = tracker.create_individual_stock_chart(selected_ticker, period)
                if chart:
                    st.plotly_chart(chart, use_container_width=True)
                
                # Business summary
                if stock_data['Business Summary']:
                    st.write("**Business Summary:**")
                    st.write(stock_data['Business Summary'])
        
        else:
            st.warning("No detailed data available for the selected stocks. This may be due to API limits or network issues.")
    
    else:
        st.info("No stocks found matching your criteria. Please adjust your filters.")
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; color: #666;'>
        <p>📊 Comprehensive US Stock Market Data | 
        🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        📈 Data from Yahoo Finance</p>
        <p><small>⚠️ This tool is for educational purposes only. Not investment advice.</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()