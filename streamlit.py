import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import json
import time
from geopy.geocoders import Nominatim

# --- CONFIG ---
st.set_page_config(
    page_title="Painel de Restaurantes - Versão Aprimorada",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THEME SELECTION ---
template = st.sidebar.selectbox(
    "Tema dos Gráficos", ['plotly_dark', 'plotly_white'], index=0
)

# --- LOAD DATA ---
@st.cache_data(show_spinner=False)
def load_data():
    engine = create_engine("sqlite:///restaurantes.db")
    df = pd.read_sql("SELECT * FROM restaurantes", con=engine)
    df = df.assign(
        rate=pd.to_numeric(df['rate'], errors='coerce'),
        approx_cost=pd.to_numeric(df['approx_cost'], errors='coerce'),
        online_order=df['online_order'].str.lower().map({'yes':'Sim','no':'Não'})
    )
    return df  # preserva todos os registros para total

# --- BUILD COORDS OFFLINE OR ON DEMAND ---
def build_coords(df, cache_path="bairro_coords.json"):
    st.info("Gerando coordenadas dos bairros. Isto pode levar alguns minutos...")
    geolocator = Nominatim(user_agent="painel_restaurantes")
    bairros = df['location'].dropna().unique().tolist()
    coords = {}
    progress = st.progress(0)
    for i, bairro in enumerate(bairros, 1):
        try:
            place = geolocator.geocode(f"{bairro}, Bengaluru, India")
            coords[bairro] = {"lat": place.latitude, "lon": place.longitude}
        except:
            coords[bairro] = {}
        time.sleep(1)
        progress.progress(i/len(bairros))
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(coords, f, ensure_ascii=False, indent=2)
    st.success(f"Arquivo '{cache_path}' gerado com sucesso.")
    return coords

# --- COORDS LOADING ---
def load_coords(df, cache_path="bairro_coords.json"):
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        if st.sidebar.button("🗺️ Gerar Coordenadas dos Bairros"):
            return build_coords(df, cache_path)
        st.sidebar.warning("Coordenadas não encontradas. Clique no botão para gerar JSON.")
        return {}

# --- DATA QUALITY INFO ---
def show_data_quality(df):
    st.sidebar.markdown("### Qualidade dos Dados")
    missing = df[['rate','votes','approx_cost']].isna().sum()
    st.sidebar.write("Valores ausentes:", missing.to_dict())
    q1, q3 = df['approx_cost'].quantile([0.25, 0.75])
    outliers = (df['approx_cost'] > q3 + 1.5 * (q3 - q1)).sum()
    st.sidebar.write(f"Outliers de custo (>Q3+1.5*IQR): {outliers}")
    if st.sidebar.checkbox("Remover outliers de custo", value=False):
        mask = df['approx_cost'] <= q3 + 1.5 * (q3 - q1)
        return df[mask]
    return df

# --- FILTERS ---
def build_filters(df):
    st.sidebar.header("🔍 Filtros")
    df = show_data_quality(df)
    for key in ['loc','r_type','cuisine']:
        if key not in st.session_state:
            st.session_state[key] = []
    if st.sidebar.button("🔄 Resetar Filtros"):
        st.session_state.loc = []
        st.session_state.r_type = []
        st.session_state.cuisine = []

    locs = sorted(df['location'].dropna().unique())
    types = sorted(df['rest_type'].dropna().unique())
    cuisines = sorted({c.strip() for row in df['cuisines'].dropna().str.split(',') for c in row})

    sel_loc = st.sidebar.multiselect("Bairro", locs, key='loc')
    sel_type = st.sidebar.multiselect("Tipo de Restaurante", types, key='r_type')
    sel_cuis = st.sidebar.multiselect("Culinária", cuisines, key='cuisine')

    filtered = df.copy()
    if sel_loc:
        filtered = filtered[filtered['location'].isin(sel_loc)]
    if sel_type:
        filtered = filtered[filtered['rest_type'].isin(sel_type)]
    if sel_cuis:
        filtered = filtered.assign(cuisine_list=filtered['cuisines'].str.split(','))
        filtered = filtered.explode('cuisine_list')
        filtered = filtered[filtered['cuisine_list'].str.strip().isin(sel_cuis)]
    return filtered

# --- VISUAL FUNCTIONS ---
def show_overview(df):
    # Mantém o df completo e um df_valid só para quem tem rate/cost
    df_all = df
    df_valid = df.dropna(subset=['rate','approx_cost'])

    # Métricas usando df_all
    total_rest = len(df_all)
    total_votes_all = int(df_all['votes'].sum())

    # Métricas variáveis no painel
    st.markdown(
        f"**Visão Geral (após filtros):**\n\n"
        f"- Total de Restaurantes: **{total_rest}**\n"
        f"- Total de Votos: **{total_votes_all:,}**\n\n"
        "*Obs:* para as análises de avaliação e custo, excluímos temporariamente os registros sem nota ou custo.\n"
        "*CTA:* reveja outliers antes de expandir para novas regiões."
    )

    # Exibe as métricas principais
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Restaurantes", total_rest)
    c2.metric("Nota Média (s/ nulos)", f"{df_valid['rate'].mean():.2f}")
    c3.metric("Total Votos (todos)", f"{total_votes_all:,}")
    c4.metric("Custo Médio (s/ nulos)", f"₹ {df_valid['approx_cost'].mean():.2f}")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Distribuição de Avaliações (Rate)")
        fig = px.histogram(df_valid, x='rate', nbins=20, marginal='box', template=template,
                           hover_data=['votes'], labels={'rate':'Avaliação'})
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Distribuição de Custo Aproximado")
        fig = px.histogram(df_valid, x='approx_cost', nbins=20, marginal='box', template=template,
                           hover_data=['votes'], labels={'approx_cost':'Custo (INR)'})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Custo vs Nota Média por Restaurante")
    fig = px.scatter(df_valid, x='approx_cost', y='rate', size='votes', template=template,
                     hover_data=['name','rest_type'], labels={'approx_cost':'Custo (INR)','rate':'Nota'})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🚚 Delivery vs Não-Delivery: Engajamento")
    pivot = df_valid.groupby('online_order').agg(
        num_restaurantes=('name','count'),
        total_votos=('votes','sum')
    ).reset_index()
    pivot['votos_por_restaurante'] = pivot['total_votos'] / pivot['num_restaurantes']
    fig = go.Figure()
    fig.add_trace(go.Bar(x=pivot['online_order'], y=pivot['num_restaurantes'], name='# Restaurantes'))
    fig.add_trace(go.Bar(x=pivot['online_order'], y=pivot['votos_por_restaurante'], name='Votos por Restaurante', yaxis='y2'))
    fig.update_layout(template=template,
                      yaxis=dict(title='Quantidade Restaurantes'),
                      yaxis2=dict(title='Votos por Restaurante', overlaying='y', side='right'))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("*CTA*: considerar foco em delivery se votos/restaurant forem maiores.")

# --- MAIN ---

df = load_data()
coords = load_coords(df)
filtered = build_filters(df)

# Paletas mantidas
PALETTE = ['#4B0082','#800080','#DA70D6','#1E90FF','#00BFFF','#87CEFA','#FFC0CB']
PALETTE_CONT = px.colors.sequential.Plasma
PALETTE_HEAT = px.colors.sequential.Purples

tab1,tab2,tab3,tab4,tab5 = st.tabs(["📊 Visão Geral","📍 Oferta/Mix","🌟 Qualidade","📈 Expansão","🧠 Inteligência"])

with tab1:
    st.header("📊 Visão Geral")
    if filtered.empty:
        st.info("Nenhum dado encontrado nos filtros.")
    else:
        show_overview(filtered)

with tab2:
    st.header("📍 Oferta e Mix")
    st.markdown("**Insights:** rever categorias de restaurante para identificar lacunas de oferta.")
    # lógica original...

with tab3:
    st.header("🌟 Qualidade")
    if filtered.empty:
        st.info("Nenhum dado disponível para avaliação de qualidade.")
    else:
        # Seleciona restaurantes com dados válidos
        df_q = filtered.dropna(subset=['votes','rate'])

        # Texto de contexto
        st.markdown(
            "Este gráfico mostra a **relação** entre o número de votos recebidos e a nota média de cada restaurante. "
            "Cada bolha representa um restaurante, o tamanho da bolha corresponde à quantidade de votos. "
            "A cor indica a avaliação média."
        )
        st.markdown("---")

        # Scatter plot com customização de layout
        fig = px.scatter(
            df_q.nlargest(20, 'votes'),
            x='votes', y='rate',
            size='votes',
            hover_name='name',
            hover_data={
                'votes':True,
                'rate':True,
                'rest_type':True
            },
            color='rate',
            color_continuous_scale=PALETTE_CONT,
            labels={'votes':'Número de Votos', 'rate':'Avaliação Média'},
            title='Top 20 Restaurantes por Votos vs Avaliação Média',
            template=template
        )
        # Ajuste de eixos e legenda
        fig.update_layout(
            xaxis_title='Total de Votos',
            yaxis_title='Avaliação Média',
            coloraxis_colorbar=dict(title='Avaliação'),
            legend=dict(title=''),
            margin=dict(l=40, r=40, t=80, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Conclusões
        st.markdown("**Principais Conclusões:**")
        st.markdown(
            "- Restaurantes com mais de 16.000 votos mantêm avaliações muito altas (>4.9), o que indica forte engajamento.  "
            "- A maioria dos restaurantes (menos votados) se concentra em avaliações ao redor de 4.7, sugerindo oportunidades de melhorar a qualidade para subir a nota.  "
            "- Considere investir em estratégias de fidelização nos restaurantes de média votação para elevar a avaliação geral."
        )

with tab4:
    st.header("📈 Expansão")
    if filtered.empty:
        st.info("Nenhum dado para análise de expansão.")
    else:
        # Prepara dados válidos
        df_exp = filtered.dropna(subset=['rate','approx_cost'])
        st.markdown(
            "Este gráfico compara a nota média dos restaurantes em diferentes faixas de custo. "
            "As cores representam a avaliação média, facilitando a identificação das faixas com melhor desempenho."
        )
        # Segmentação de custo
        bins = [0,50,100,200,400, df_exp['approx_cost'].max()]
        labels = ['0-50','51-100','101-200','201-400','>400']
        df_exp = df_exp.assign(cost_range=pd.cut(df_exp['approx_cost'], bins=bins, labels=labels))
        avg = df_exp.groupby('cost_range')['rate'].mean().reset_index()

        # Barra colorida por avaliação
        fig = px.bar(
            avg,
            x='cost_range',
            y='rate',
            color='rate',
            color_continuous_scale=PALETTE_CONT,
            labels={'cost_range':'Faixa de Custo (INR)','rate':'Avaliação Média'},
            title='Avaliação Média por Faixa de Custo',
            template=template
        )
        fig.update_layout(
            xaxis_title='Faixa de Custo (INR)',
            yaxis_title='Avaliação Média',
            margin=dict(l=40, r=40, t=80, b=40),
            coloraxis_colorbar=dict(title='Nota Média')
        )
        st.plotly_chart(fig, use_container_width=True)

        # Conclusões
        st.markdown("**Principais Conclusões:**")
        st.markdown(
            "- Restaurantes na faixa '>400' apresentam a maior avaliação média, sugerindo alto valor percebido.  "
            "- Faixa '0-50' tem nota média levemente superior à faixa '51-100', indicando vantagem competitiva em preço baixo.  "
            "- Considere focar em investimento nas faixas com avaliação menor para elevar o desempenho geral."
        )


with tab5:
    st.header("🧠 Inteligência")
    if not filtered.empty:
        st.markdown("**Insights:** pratos mais citados podem sinalizar tendências de menu.")
        dishes = Counter([p.strip().lower() for row in filtered['dish_liked'].dropna().str.split(',') for p in row])
        dish_df = pd.DataFrame(dishes.most_common(10), columns=['dish','count'])
        fig = px.pie(dish_df, names='dish', values='count', hole=0.4, template=template)
        st.plotly_chart(fig, use_container_width=True)
        # Mapa de pontos e heatmap
        agg = filtered.groupby('location')['rate'].mean().reset_index()
        agg['lat'] = agg['location'].map(lambda x: coords.get(x, {}).get('lat'))
        agg['lon'] = agg['location'].map(lambda x: coords.get(x, {}).get('lon'))
        agg = agg.dropna(subset=['lat','lon','rate'])
        st.subheader("Mapa de Notas por Bairro")
        fig_map = px.scatter_mapbox(agg, lat='lat', lon='lon', size='rate', color='rate',
                                    mapbox_style='open-street-map', zoom=10,
                                    color_continuous_scale=PALETTE_CONT, template=template)
        st.plotly_chart(fig_map, use_container_width=True)
        st.subheader("Mapa de Densidade de Restaurantes")
        density = px.density_mapbox(
            filtered, lat=filtered['location'].map(lambda x: coords.get(x,{}).get('lat')),
            lon=filtered['location'].map(lambda x: coords.get(x,{}).get('lon')),
            radius=10, mapbox_style='open-street-map', zoom=10, template=template
        )
        st.plotly_chart(density, use_container_width=True)

# --- EXPORT ---
st.sidebar.download_button(
    "📥 Exportar Filtrado",
    filtered.to_csv(index=False).encode(),
    "restaurantes_filtrados.csv",
    "text/csv"
)

