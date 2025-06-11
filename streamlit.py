import streamlit as st
import pandas as pd
import sqlite3
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# --- CONFIG ---
st.set_page_config(
    page_title="Painel de Restaurantes",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LOAD DATA ---
@st.cache_data

def load_data():
    engine = create_engine("sqlite:///restaurantes.db")
    df = pd.read_sql("SELECT * FROM restaurantes", con=engine)
    return df

df = load_data()
df['rate'] = pd.to_numeric(df['rate'], errors='coerce')
df['approx_cost'] = pd.to_numeric(df['approx_cost'], errors='coerce') 

# --- FILTER SIDEBAR ---
st.sidebar.header("Filtros")

all_locations = sorted(df['location'].dropna().unique())
all_rest_types = sorted(df['rest_type'].dropna().unique())
all_cuisines = sorted(df['cuisines'].dropna().unique())

selected_location = st.sidebar.multiselect("Bairro", all_locations)
selected_rest_type = st.sidebar.multiselect("Tipo de Restaurante", all_rest_types)
selected_cuisine = st.sidebar.multiselect("Culinária", all_cuisines)

reset_btn = st.sidebar.button("Resetar Filtros")
if reset_btn:
    selected_location = []
    selected_rest_type = []
    selected_cuisine = []

filtered_df = df.copy()

if selected_location:
    filtered_df = filtered_df[filtered_df['location'].isin(selected_location)]
if selected_rest_type:
    filtered_df = filtered_df[filtered_df['rest_type'].isin(selected_rest_type)]
if selected_cuisine:
    filtered_df = filtered_df[filtered_df['cuisines'].isin(selected_cuisine)]

# --- COLOR PALETTE ---
PALETTE_PRIMARY = ["#6366F1", "#7C3AED", "#8B5CF6", "#A78BFA", "#C4B5FD"]  # tons de roxo e azul
PALETTE_ALT = ["#3B82F6", "#6366F1", "#60A5FA", "#818CF8", "#A5B4FC"]

# --- NAVIGATION ---
st.sidebar.title("📚 Menu de Análises")
menu = st.sidebar.radio("Escolha uma seção:", [
    "📊 Visão Geral",
    "📍 Oferta e Mix de Mercado",
    "🌟 Qualidade e Avaliação",
    "📈 Estratégias de Expansão",
    "🧠 Inteligência de Negócios"
])

# --- PAGE: Visão Geral ---
if menu == "📊 Visão Geral":
    st.title("📊 Visão Geral do Marketplace")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Restaurantes", len(filtered_df))
    col2.metric("Nota Média", round(filtered_df['rate'].mean(), 2))
    col3.metric("Total de Votos", f"{int(filtered_df['votes'].sum()):,}".replace(",", "."))

    st.subheader("🏆 Top 10 Tipos de Restaurante por Votos")
    tipo_votos = filtered_df.groupby(['rest_type', 'online_order'])['votes'].sum().reset_index()
    tipo_votos = tipo_votos.sort_values(by='votes', ascending=False).groupby('rest_type').head(1).nlargest(10, 'votes')

    fig = px.bar(tipo_votos, x='rest_type', y='votes', color='online_order', barmode='group',
                 title='Tipos de Restaurante com Mais Votos (Online vs Offline)',
                 labels={'rest_type': 'Tipo', 'votes': 'Votos', 'online_order': 'Pedido Online'},
                 color_discrete_sequence=PALETTE_ALT)
    fig.update_layout(plot_bgcolor="#F8FAFC", xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

# --- PAGE: Oferta e Mix de Mercado ---
if menu == "📍 Oferta e Mix de Mercado":
    st.title("Análises de Oferta e Diversidade")



# --- PAGE: Qualidade e Avaliação ---
if menu == "🌟 Qualidade e Avaliação":
    st.title("Avaliação, Satisfação e Performance")
    st.subheader("Top Restaurantes (Nota ≥ 4.0 e > 200 votos)")
    top_df = filtered_df[(filtered_df['rate'] >= 4.0) & (filtered_df['votes'] > 200)]
    fig = px.bar(top_df.sort_values(by='rate', ascending=False).head(20),
                 x='name', y='rate', color='votes',
                 title="Top Restaurantes Avaliados",
                 color_continuous_scale=PALETTE_PRIMARY)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Alta Demanda sem Pedido Online")
    offline_df = filtered_df[(filtered_df['online_order'] == 'No') & (filtered_df['votes'] > 100)]
    offline_df = offline_df.dropna(subset=['rate']) 
    fig2 = px.scatter(offline_df, x='name', y='votes', size='rate',
                     color='rest_type', title="Restaurantes com Muitos Votos mas sem Online")
    st.plotly_chart(fig2, use_container_width=True)

# --- PAGE: Estratégias de Expansão ---
if menu == "📈 Estratégias de Expansão":
    st.title("Custo, Marketing e Clusters")
    st.subheader("Custo Médio vs Nota")
    fig = px.scatter(filtered_df, x="approx_cost", y="rate", size="votes", color="rest_type",
                     title="Custo Médio x Avaliação",
                     color_discrete_sequence=PALETTE_PRIMARY)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Clusters de Alta Demanda por Bairro")
    cluster_data = (
        filtered_df.groupby('location')
        .agg({'rate': 'mean', 'votes': 'sum', 'approx_cost': 'mean'})
        .reset_index()
        .sort_values(by='votes', ascending=False)
    )
    fig3 = px.bar(cluster_data.head(20), x='location', y='votes',
                  title="Bairros com Alta Demanda",
                  color_discrete_sequence=PALETTE_PRIMARY)
    st.plotly_chart(fig3, use_container_width=True)

# --- PAGE: Inteligência de Negócios ---
if menu == "🧠 Inteligência de Negócios":
    st.title("🧠 Insights Avançados")
    st.subheader("Pratos Mais Citados entre Restaurantes")
    pratos_raw = filtered_df['dish_liked'].dropna().str.split(',')
    flat_list = [prato.strip().lower() for sublist in pratos_raw for prato in sublist]
    top_pratos = Counter(flat_list).most_common(15)
    prato_df = pd.DataFrame(top_pratos, columns=['Prato', 'Frequência'])

    fig = px.bar(prato_df, x='Prato', y='Frequência', title="Top 15 Pratos Mais Citados",
                 color='Frequência', color_continuous_scale=PALETTE_ALT)
    fig.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Correlação entre Variáveis Numéricas")
    num_df = filtered_df[['rate', 'votes', 'approx_cost']].dropna()
    corr = num_df.corr()
    fig2 = go.Figure(data=go.Heatmap(z=corr.values,
                                     x=corr.columns,
                                     y=corr.columns,
                                     colorscale='Purples'))
    st.plotly_chart(fig2, use_container_width=True)

# --- EXPORTAÇÃO ---
st.sidebar.download_button(
    label="📥 Exportar dados filtrados",
    data=filtered_df.to_csv(index=False).encode('utf-8'),
    file_name="restaurantes_filtrados.csv",
    mime='text/csv'
)

# --- FOOTER ---
st.markdown("---")

