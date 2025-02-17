import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import time

# -----------------------------------------------------------------------------
# Globers
# -----------------------------------------------------------------------------
global prices
prices = pd.DataFrame(columns=["Timestamp", "EUR/USD Price"])

global invested_amount
invested_amount=0

global balance
balance=0

global last_action
last_action="Aucune"

global last_price
last_price = None

global transactions
transactions=[]

global profit
profit=0

global last_buy_price
last_buy_price = None

global prompt
prompt="Analyse ces données\n"

# -----------------------------------------------------------------------------
# Scrape from Investing.com
# -----------------------------------------------------------------------------
def fetch_price():
    try:
        url = "https://fr.investing.com/currencies/eur-usd"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find price tag
        price_tag = soup.find("div", class_="text-5xl/9 font-bold text-[#232526] md:text-[42px] md:leading-[60px]", 
            attrs={"data-test": "instrument-price-last"})
        
        if price_tag:
            # Get tag, cleanup, remove comma
            price_text = price_tag.get_text(strip=True)
            price_value = price_text.replace(",", ".")
            return float(price_value)
        else:
            prompt = "ERREUR: Impossible de trouver le prix EUR/USD sur la page."
            return None
    except Exception as e:
        prompt = f"Erreur lors de la récupération du prix : {e}"
        return None

# -----------------------------------------------------------------------------
# Update prices
# -----------------------------------------------------------------------------
def update_prices(price):
    global prices

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = pd.DataFrame([{"Timestamp": current_time, "EUR/USD Price": price}])
    prices = pd.concat([new_data, prices]).head(20)

# -----------------------------------------------------------------------------
# Trade
# -----------------------------------------------------------------------------
def trading_strategy(sensitivity):
    global prices
    global last_buy_price

    current_price = prices["EUR/USD Price"].iloc[0]

    if last_buy_price is None:
        last_buy_price = current_price
        return

    variation_percent = ((current_price - last_buy_price) / last_buy_price) * 100

    if variation_percent <= -sensitivity:
        invested_amount = balance
        balance = 0
        last_buy_price = current_price
        last_action = "Achat"
        transactions.append({
            "Action": "Achat",
            "Prix": f"{current_price:.6f}",
            "Montant": f"{invested_amount:.2f}",
            "Temps": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    elif variation_percent >= sensitivity:
        profit = invested_amount * (1 + variation_percent / 100)
        balance += profit
        profit += profit - invested_amount
        invested_amount = 0
        last_action = "Vente"
        transactions.append({
            "Action": "Vente",
            "Prix": f"{current_price:.6f}",
            "Montant": f"{balance:.2f}",
            "Profit": f"{profit - invested_amount:.2f}",
            "Temps": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# -----------------------------------------------------------------------------
# Calc KPIs
# -----------------------------------------------------------------------------
def calculate_market_kpis(prices):
    if len(prices) < 2:
        return None, None, None
    
    price_changes = prices["EUR/USD Price"].pct_change().dropna()
    volatility = price_changes.std() * 100

    trend = price_changes.mean() * 100

    volume = np.abs(price_changes).sum() * 100

    return volatility, trend, volume

# -----------------------------------------------------------------------------
# Generate prompt
# -----------------------------------------------------------------------------
def generate_prompt():
    global prices
    global prompt
    global last_action
    global balance

    # reset prompt
    prompt="Analyse ces données\n"

    # TODO: set sensivity to something maybe
    sensitivity=1

    # get prices
    price = fetch_price()
    if price is not None:
        update_prices(price)
        trading_strategy(sensitivity)
    
    # calc KPIs
    volatility, trend, volume = calculate_market_kpis(prices)

    # set key indicators
    prompt += "Dernier Prix EUR/USD: " + f"{price:.6f}" + "\n"
    prompt += "Dernière Action: " + last_action + "\n"
    prompt += "Montant Investi (€): " + f"{invested_amount:.2f}" + "\n"
    prompt += "Profit Total (€): " + f"{profit:.2f}" + "\n"

    solde_total = balance + invested_amount
    prompt += "Solde Total (€): " + f"{solde_total:.2f}" + "\n"

    prompt += "KPIs du Marché\n"
    if volatility is not None and trend is not None and volume is not None:
        prompt += "Variabilité des prix sur les 20 dernières minutes: " + f"{volatility:.2f}%" + "\n"
        prompt += "Tendance moyenne des prix (haussière ou baissière): " + f"{trend:.2f}%" + "\n"
        prompt += "Volume d'échanges simulé basé sur les variations de prix: " + f"{volume:.2f}%" + "\n"
    else:
        prompt += "Pas assez de données pour calculer les KPI du marché\n"

    prompt += "Nombre de Transactions\n"
    if transactions:
        df_transactions = pd.DataFrame(transactions)
        buy_count = df_transactions[df_transactions["Action"] == "Achat"].shape[0]
        sell_count = df_transactions[df_transactions["Action"] == "Vente"].shape[0]
        prompt += pd.DataFrame({
            "Type": ["Achats", "Ventes"],
            "Nombre": [buy_count, sell_count]
        })
    else:
        prompt += "Aucune transaction pour le moment\n"

    prompt += "Dernières variations du cours EUR/USD\n"
    prompt += prices.to_string() + "\n"
    
    prompt += "Historique des Transactions (10 dernières)\n"
    if transactions:
        prompt += "Dernières variations du cours EUR/USD\n"
        prompt += pd.DataFrame(transactions).head(10) + "\n"
    else:
        prompt += "Aucune transaction pour le moment.\n"

# -----------------------------------------------------------------------------
# prompt cronjob
# -----------------------------------------------------------------------------
def prompt_cronjob():
    while True:
        generate_prompt()
        print(prompt)
        print("sleeping for 5 seconds")
        time.sleep(5)

# -----------------------------------------------------------------------------
# dothings
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    prompt_cronjob()
