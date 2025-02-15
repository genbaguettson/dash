import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import numpy as np

# -----------------------------------------------------------------------------
# Configuration de la page
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Bot de Trading EUR/USD - Temps réel",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Auto-refresh toutes les 5 secondes
st_autorefresh(interval=5000, key="datarefresh")

# -----------------------------------------------------------------------------
# Initialisation des données dans st.session_state
# -----------------------------------------------------------------------------
if "prices" not in st.session_state:
    st.session_state.prices = pd.DataFrame(columns=["Timestamp", "EUR/USD Price"])
if "invested_amount" not in st.session_state:
    st.session_state.invested_amount = 0
if "balance" not in st.session_state:
    st.session_state.balance = 0
if "last_action" not in st.session_state:
    st.session_state.last_action = "Aucune"
if "last_price" not in st.session_state:
    st.session_state.last_price = None
if "transactions" not in st.session_state:
    st.session_state.transactions = []
if "profit" not in st.session_state:
    st.session_state.profit = 0
if "last_buy_price" not in st.session_state:
    st.session_state.last_buy_price = None

# -----------------------------------------------------------------------------
# Fonction pour scraper le prix depuis Investing.com
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
        
        # Trouver la balise contenant le prix (avec la classe et l'attribut data-test)
        price_tag = soup.find("div", class_="text-5xl/9 font-bold text-[#232526] md:text-[42px] md:leading-[60px]", 
                              attrs={"data-test": "instrument-price-last"})
        
        if price_tag:
            # Récupère le texte, nettoie et remplace la virgule par un point
            price_text = price_tag.get_text(strip=True)
            price_value = price_text.replace(",", ".")
            return float(price_value)
        else:
            st.error("Impossible de trouver le prix EUR/USD sur la page.")
            return None
    except Exception as e:
        st.error(f"Erreur lors de la récupération du prix : {e}")
        return None

# -----------------------------------------------------------------------------
# Fonction pour mettre à jour les données de prix
# -----------------------------------------------------------------------------
def update_prices(price):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_data = pd.DataFrame([{"Timestamp": current_time, "EUR/USD Price": price}])
    st.session_state.prices = pd.concat([new_data, st.session_state.prices]).head(20)  # Garder les 20 derniers enregistrements

# -----------------------------------------------------------------------------
# Fonction de Trading (achat / vente)
# -----------------------------------------------------------------------------
def trading_strategy(sensitivity):
    current_price = st.session_state.prices["EUR/USD Price"].iloc[0]
    last_buy_price = st.session_state.last_buy_price

    # Si aucun achat n'a été effectué, initialiser le dernier prix d'achat
    if last_buy_price is None:
        st.session_state.last_buy_price = current_price
        return

    # Calcul de la variation en pourcentage par rapport au dernier prix d'achat
    variation_percent = ((current_price - last_buy_price) / last_buy_price) * 100

    # Stratégie d'achat : si le prix baisse de x% ou plus
    if variation_percent <= -sensitivity:
        st.session_state.invested_amount = st.session_state.balance
        st.session_state.balance = 0
        st.session_state.last_buy_price = current_price
        st.session_state.last_action = "Achat"
        st.session_state.transactions.append({
            "Action": "Achat",
            "Prix": f"{current_price:.6f}",
            "Montant": f"{st.session_state.invested_amount:.2f}",
            "Temps": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    # Stratégie de vente : si le prix augmente de x% ou plus
    elif variation_percent >= sensitivity:
        profit = st.session_state.invested_amount * (1 + variation_percent / 100)
        st.session_state.balance += profit
        st.session_state.profit += profit - st.session_state.invested_amount
        st.session_state.invested_amount = 0
        st.session_state.last_action = "Vente"
        st.session_state.transactions.append({
            "Action": "Vente",
            "Prix": f"{current_price:.6f}",
            "Montant": f"{st.session_state.balance:.2f}",
            "Profit": f"{profit - st.session_state.invested_amount:.2f}",
            "Temps": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# -----------------------------------------------------------------------------
# Fonction pour calculer les KPI du marché
# -----------------------------------------------------------------------------
def calculate_market_kpis(prices):
    if len(prices) < 2:
        return None, None, None

    # Volatilité (écart-type des variations de prix)
    price_changes = prices["EUR/USD Price"].pct_change().dropna()
    volatility = price_changes.std() * 100  # En pourcentage

    # Tendance (moyenne des variations de prix)
    trend = price_changes.mean() * 100  # En pourcentage

    # Volume d'échanges simulé (basé sur les variations de prix)
    volume = np.abs(price_changes).sum() * 100  # En pourcentage

    return volatility, trend, volume

# -----------------------------------------------------------------------------
# Fonction principale pour le dashboard
# -----------------------------------------------------------------------------
def main():
    st.title("💹 Bot de Trading EUR/USD - Temps Réel")
    st.write("Bot de trading automatique sur le taux EUR/USD avec stratégie d'achat/vente en fonction de la variation de x%.")

    # Saisie du capital initial si non défini
    if st.session_state.balance == 0 and st.session_state.invested_amount == 0:
        st.session_state.balance = st.number_input("Capital initial (€):", min_value=100, value=1000, step=100)

    # Slider pour régler la sensibilité
    sensitivity = st.slider("Sensibilité (% de variation pour déclencher un achat/vente):", min_value=0.01, max_value=5.0, value=1.0, step=0.01)

    # Récupération du prix et mise à jour des données
    price = fetch_price()
    if price is not None:
        update_prices(price)
        trading_strategy(sensitivity)
    
    # Calcul des KPI du marché
    volatility, trend, volume = calculate_market_kpis(st.session_state.prices)

    # Affichage des indicateurs clés
    st.header("📊 Indicateurs clés")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Dernier Prix EUR/USD", f"{price:.6f}")
    with col2:
        st.metric("Dernière Action", st.session_state.last_action)
    with col3:
        st.metric("Montant Investi (€)", f"{st.session_state.invested_amount:.2f}")
    with col4:
        st.metric("Profit Total (€)", f"{st.session_state.profit:.2f}")

    # Calcul du solde total
    solde_total = st.session_state.balance + st.session_state.invested_amount
    st.metric("Solde Total (€)", f"{solde_total:.2f}")

    # Affichage des KPI du marché
    st.header("📈 KPI du Marché")
    if volatility is not None and trend is not None and volume is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Volatilité", f"{volatility:.2f}%", help="Variabilité des prix sur les 20 dernières minutes.")
        with col2:
            st.metric("Tendance", f"{trend:.2f}%", help="Tendance moyenne des prix (haussière ou baissière).")
        with col3:
            st.metric("Volume Simulé", f"{volume:.2f}%", help="Volume d'échanges simulé basé sur les variations de prix.")
    else:
        st.write("Pas assez de données pour calculer les KPI du marché.")

    # Tableau des transactions (nombre d'achats et de ventes)
    st.header("📋 Nombre de Transactions")
    if st.session_state.transactions:
        df_transactions = pd.DataFrame(st.session_state.transactions)
        buy_count = df_transactions[df_transactions["Action"] == "Achat"].shape[0]
        sell_count = df_transactions[df_transactions["Action"] == "Vente"].shape[0]
        st.dataframe(pd.DataFrame({
            "Type": ["Achats", "Ventes"],
            "Nombre": [buy_count, sell_count]
        }))
    else:
        st.write("Aucune transaction pour le moment.")

    # Affichage du graphique dynamique
    st.header("📈 Graphique dynamique")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=st.session_state.prices["Timestamp"],
        y=st.session_state.prices["EUR/USD Price"],
        mode="lines+markers",
        line=dict(color="royalblue", width=2),
        marker=dict(size=6, color="red"),
        name="EUR/USD",
    ))
    fig.update_layout(
        title="Évolution détaillée du taux EUR/USD",
        xaxis_title="Temps",
        yaxis_title="Prix",
        template="plotly_dark",
        height=500
    )
    # Affichage de l'axe Y avec 6 chiffres après la virgule
    fig.update_yaxes(tickformat=".6f")
    st.plotly_chart(fig, use_container_width=True)
    
    # Tableau des dernières variations du cours
    st.header("📋 Dernières variations du cours EUR/USD")
    st.dataframe(st.session_state.prices)
    
    # Tableau de l'historique des transactions (10 dernières)
    st.header("📊 Historique des Transactions (10 dernières)")
    if st.session_state.transactions:
        st.dataframe(pd.DataFrame(st.session_state.transactions).head(10))
    else:
        st.write("Aucune transaction pour le moment.")

# -----------------------------------------------------------------------------
# Exécution du dashboard
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()