import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
from collections import Counter
import json
from geopy.geocoders import Nominatim

# --- CONFIGURAÇÃO DO APP ---
st.set_page_config(
    page_title="Painel de Restaurantes - Versão Aprimorada",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNÇÕES AUXILIARES ---
@st.cache_data(show_spinner=False)
def load_data():
    engine = create_engine("sqlite:///restaurantes.db")
    df = pd.read_sql("SELECT * FROM restaurantes", con=engine)
    df = df.assign(
        rate=pd.to_numeric(df['rate'], errors='coerce'),
        approx_cost=pd.to_numeric(df['approx_cost'], errors='coerce'),
        online_order=df['online_order'].str.lower().map({'yes': 'Sim', 'no': 'Não'})
    )
    return df

def load_coords(df, cache_path="bairro_coords.json"):
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.sidebar.warning("Coordenadas não encontradas. Clique no botão para gerar JSON.")
        if st.sidebar.button("🗺️ Gerar Coordenadas dos Bairros"):
            geolocator = Nominatim(user_agent="geoapiExercises")
            coords = {}
            for location in df['location'].dropna().unique():
                try:
                    loc = geolocator.geocode(location)
                    if loc:
                        coords[location] = {'lat': loc.latitude, 'lon': loc.longitude}
                except Exception as e:
                    st.warning(f"Erro ao buscar coordenadas para {location}: {e}")
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(coords, f, ensure_ascii=False, indent=4)
            return coords
        return {}

# --- SIDEBAR - FILTROS ---
st.sidebar.header("🔍 Filtros")
if st.sidebar.button("🔄 Resetar Filtros"):
    st.session_state.loc = []
    st.session_state.r_type = []
    st.session_state.cuisine = []

for key in ['loc', 'r_type', 'cuisine']:
    if key not in st.session_state:
        st.session_state[key] = []

df = load_data()
coords = load_coords(df)

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

df_valid = filtered.dropna(subset=['rate', 'approx_cost'])

COLOR_SCALE = ['#4B0082', '#6A0DAD', '#8A2BE2', '#7B68EE', '#4169E1', '#1E90FF', '#00BFFF']

# --- ABAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Visão Geral",
    "📍 Oferta/Mix",
    "🌟 Qualidade",
    "📈 Expansão",
    "🧠 Inteligência"
])

def show_overview(filtered, df_valid):
    # Se nenhum registro passar pelo filtro:
    if filtered.empty:
        st.warning("😕 Nenhum restaurante encontrado para os filtros aplicados. Tente outro conjunto de filtros.")
        return

    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        # Total de restaurantes: sempre sobre o 'filtered' completo
        c1.metric("Total Restaurantes", filtered.shape[0])
        # Nota média: apenas onde há avaliação
        c2.metric("Nota Média", f"{df_valid['rate'].mean():.2f}")
        # Total de votos: sobre tudo que passou no filtro (mesmo sem nota/custo)
        c3.metric("Total Votos", f"{filtered['votes'].sum():,}")
        # Custo médio: apenas onde há custo informado
        c4.metric("Custo Médio (para 2 pessoas)", f"₹ {df_valid['approx_cost'].mean():.2f}")

    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Distribuição de Avaliações")
            fig1 = px.histogram(df_valid, x='rate', nbins=20,
                               color_discrete_sequence=[COLOR_SCALE[0]],
                               labels={'rate':'Avaliação'})
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown("**Conclusão:** A maioria dos restaurantes concentra-se entre nota 3.5 e 4.5, com poucos extremos.")

        with col2:
            st.subheader("Distribuição de Custo (ECDF)")
            # Gráfico ECDF para distribuição de custo
            fig2 = px.ecdf(
            df_valid,
            x='approx_cost',
            labels={
                'approx_cost':'Custo Aproximado (INR)',
                'ecdf':'Proporção de Restaurantes'
            },
            title="ECDF: Distribuição de Custo dos Restaurantes"
            )
            # usa a segunda cor da paleta
            fig2.update_traces(line_color=COLOR_SCALE[1])

            # formata o eixo Y pra mostrar percentuais inteiros
            fig2.update_layout(
                yaxis=dict(
                    tickformat=".0%",   # formata 0.8 como 80%
                    dtick=0.25          # coloca ticks a cada 25% (0.00, 0.25, 0.50, …)
                )
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("**Conclusão:** O gráfico ECDF mostra a proporção acumulada de restaurantes até cada valor de custo, facilitando a leitura de percentis.")

        with st.container():
            st.subheader("Matriz Custo x Nota (Distribuição)")
            df_valid['faixa_custo'] = pd.cut(df_valid['approx_cost'], bins=[0,100,200,400,600,1000,2000,5000],
                                            labels=['<100','101-200','201-400','401-600','601-1k','1k-2k','2k+'])
            heat = df_valid.groupby(['faixa_custo', 'rate']).size().reset_index(name='count')

            # Novo gráfico de barras empilhadas
            fig3 = px.bar(
                heat,
                x='faixa_custo',
                y='count',
                color='rate',
                color_continuous_scale=COLOR_SCALE,
                labels={'rate': 'Nota', 'faixa_custo': 'Faixa de Custo', 'count': 'Qtde Restaurantes'},
                title="Distribuição de Restaurantes por Faixa de Custo e Nota"
            )
            fig3.update_layout(
                xaxis_title='Faixa de Custo',
                yaxis_title='Quantidade de Restaurantes',
                coloraxis_colorbar=dict(title='Nota Média'),
                margin=dict(l=40, r=40, t=80, b=40)
            )
            st.plotly_chart(fig3, use_container_width=True)
            st.markdown("**Conclusão:** O gráfico de barras empilhadas facilita a visualização da relação entre faixas de custo e notas, destacando as faixas mais relevantes.")

    with st.container():
        st.subheader("Delivery vs Não: Votos e Restaurantes")
        pivot = df_valid.groupby('online_order').agg(num=('name','count'), votos=('votes','sum')).reset_index()
        pivot['média_votos'] = pivot['votos'] / pivot['num']

        fig4 = px.bar(pivot, x='online_order', y='num',
                     color='online_order',
                     color_discrete_sequence=COLOR_SCALE[:2],
                     labels={'num':'# Restaurantes'})
        st.plotly_chart(fig4, use_container_width=True)
        st.markdown("**Conclusão:** Restaurantes com delivery têm maior presença e engajamento do que os sem.")

# Visão Geral
with tab1:
    st.header("📊 Visão Geral")
    # Usa filtered
    df_valid = filtered.dropna(subset=['rate','approx_cost'])
    show_overview(filtered, df_valid)

    # Aplica faixa de preço apenas em filtered
    def faixa_preco(custo):
        if pd.isna(custo):
            return None
        elif custo <= 200:
            return "Econômico"
        elif custo <= 400:
            return "Intermediário"
        else:
            return "Premium"

    filtered['faixa_preco'] = filtered['approx_cost'].apply(faixa_preco)
    df_valid['faixa_preco'] = df_valid['approx_cost'].apply(faixa_preco)

    # Big Numbers para faixas de custo
    col1, col2, col3 = st.columns(3)
    col1.metric("🍽️ Econômicos",  filtered[filtered['faixa_preco']=='Econômico'].shape[0])
    col2.metric("💼 Intermediários", filtered[filtered['faixa_preco']=='Intermediário'].shape[0])
    col3.metric("🍷 Premium",       filtered[filtered['faixa_preco']=='Premium'].shape[0])

    # Tabela de distribuição por faixa de preço
    faixa_preco_table = filtered[["name","approx_cost","rate","faixa_preco"]].dropna()
    faixa_preco_table = faixa_preco_table.rename(columns={
        "name": "Nome do Restaurante",
        "approx_cost": "Custo Aproximado (₹)",
        "rate": "Nota",
        "faixa_preco": "Faixa de Preço"
    })
    st.subheader("Distribuição de Restaurantes por Faixa de Preço")
    faixa_sel = st.selectbox("Selecione a faixa de preço:", ["Todos","Econômico","Intermediário","Premium"], key='faixa_tab1')
    if faixa_sel != "Todos":
        faixa_preco_table = faixa_preco_table[faixa_preco_table['Faixa de Preço']==faixa_sel]
    st.dataframe(faixa_preco_table)



# Oferta e Mix
with tab2:
    st.header("📍 Oferta e Mix")
    st.markdown("""
    Esta aba detalha a **distribuição de restaurantes por bairros e tipos de serviço**, além do **mix de culinárias disponíveis** em cada região. A análise ajuda a entender a variedade e a saturação em diferentes áreas.
    """)

    col1, col2 = st.columns(2)
    col1.metric("Bairros Analisados", filtered["location"].nunique())
    col2.metric("Tipos de Cozinha", filtered["rest_type"].nunique())

    with st.container():
        st.subheader("📊 Densidade de Restaurantes por Bairro e Tipo")
        densidade = (
            filtered.groupby(["location", "rest_type"])
            .size()
            .reset_index(name="quantidade")
            .sort_values(by="quantidade", ascending=False)
            .head(50)
        )
        fig_densidade = px.bar(
            densidade,
            x="location",
            y="quantidade",
            color="rest_type",
            barmode="group",
            title="Top 50 Bairros com Maior Densidade de Tipos de Restaurante",
            color_discrete_sequence=COLOR_SCALE
        )
        st.plotly_chart(fig_densidade, use_container_width=True)
        st.markdown("**Conclusão:** Alguns bairros concentram grande variedade de tipos de restaurantes, indicando áreas de alta competitividade e oferta diversificada.")

    with st.container():
        st.subheader("🍽️ Top 50 Nichos de Cozinhas Mais Atendidos")
        # Contagem de cozinhas
        cozinhas_geral = filtered["cuisines"].value_counts().reset_index()
        cozinhas_geral.columns = ["Tipo de Cozinha", "Quantidade de Restaurantes"]

        # Ordena pelos mais atendidos e seleciona os 50 primeiros
        cozinhas_geral = cozinhas_geral.sort_values(by="Quantidade de Restaurantes", ascending=False).head(50)

        # Gráfico de barras horizontais
        fig = px.bar(
            cozinhas_geral,
            x="Quantidade de Restaurantes",
            y="Tipo de Cozinha",
            orientation="h",
            title="Top 50 Nichos de Cozinhas Mais Atendidos",
            height=800,
            color_discrete_sequence=COLOR_SCALE
        )
        st.plotly_chart(fig, use_container_width=True)


# Qualidade
with tab3:
    st.header("🌟 Qualidade")
    st.markdown("""
    Esta aba explora a **relação entre a nota média e o volume de votos** de cada restaurante.
    Restaurantes bem avaliados com muitos votos tendem a ter maior reputação e reconhecimento.
    """)

    if filtered.empty:
        st.info("Nenhum dado disponível para avaliação de qualidade.")
    else:
        df_q = filtered.dropna(subset=['votes', 'rate'])

        st.markdown("""
        O gráfico a seguir mostra os **20 restaurantes mais votados**, com destaque para avaliação média.
        """)

        top20 = df_q.nlargest(20, 'votes')
        fig = px.bar(
            top20,
            x='name',
            y='votes',
            color='rate',
            color_continuous_scale=COLOR_SCALE,
            labels={'name': 'Restaurante', 'votes': 'Número de Votos', 'rate': 'Nota'},
        
        )
        fig.update_layout(
            xaxis_title='Restaurante',
            yaxis_title='Total de Votos',
            coloraxis_colorbar=dict(title='Nota Média'),
            margin=dict(l=40, r=40, t=80, b=40)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Principais Conclusões:**")
        st.markdown("""
        - Os restaurantes mais votados também são altamente avaliados.
        - Isso indica correlação entre visibilidade e qualidade percebida.
        - Estratégias de marketing podem amplificar esse efeito.
        """)

# Expansão
with tab4:
    st.header("📈 Expansão")
    st.markdown("""
    Esta aba avalia o potencial de expansão com base na relação entre **faixa de custo** e **avaliação média**.
    O objetivo é identificar segmentos com alto desempenho e bairros com boa percepção de valor.
    """)

    if filtered.empty:
        st.info("Nenhum dado para análise de expansão.")
    else:
        df_exp = filtered.dropna(subset=['rate','approx_cost'])

        st.markdown("""
        O gráfico abaixo mostra a **avaliação média** por **faixa de custo**.
        Cores mais escuras indicam melhor desempenho, sugerindo onde investir.
        """)

        bins = [0,100,200,400,600,1000,2000,5000]
        labels = ['<100','101-200','201-400','401-600','601-1k','1k-2k','2k+']
        df_exp['cost_range'] = pd.cut(df_exp['approx_cost'], bins=bins, labels=labels)

        avg = df_exp.groupby('cost_range')['rate'].mean().reset_index()

        fig = px.bar(
            avg,
            x='cost_range',
            y='rate',
            color='rate',
            color_continuous_scale=COLOR_SCALE,
            labels={'cost_range':'Faixa de Custo (INR)','rate':'Avaliação Média'},
            title='Avaliação Média por Faixa de Custo',
        
        )
        fig.update_layout(
            xaxis_title='Faixa de Custo (INR)',
            yaxis_title='Avaliação Média',
            margin=dict(l=40, r=40, t=80, b=40),
            coloraxis_colorbar=dict(title='Nota Média')
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Principais Conclusões:**")
        st.markdown("""
        - Restaurantes nas faixas mais altas (>1k) tendem a ter avaliações superiores.
        - Faixas econômicas até ₹200 também mostram boa percepção.
        - Faixas intermediárias (<600) são oportunidades para diferenciação.
        """)

        st.subheader("📍 Distribuição de Restaurantes por Faixa de Preço")
        faixa_dist = df_exp['cost_range'].value_counts().sort_index().reset_index()
        faixa_dist.columns = ['Faixa de Custo', 'Quantidade']
        fig2 = px.bar(
            faixa_dist,
            x='Faixa de Custo',
            y='Quantidade',
            text='Quantidade',
            color='Faixa de Custo',
            color_discrete_sequence=COLOR_SCALE,
            title="Distribuição de Restaurantes por Faixa de Custo"
        )
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("**Conclusão:** A maioria dos restaurantes está concentrada nas faixas intermediárias, indicando potencial saturação e oportunidades em extremos (baixo ou alto custo).")
    if filtered.empty:
        st.info("Nenhum dado para análise de expansão.")
    else:
        df_exp = filtered.dropna(subset=['rate', 'approx_cost'])


with tab5:
    st.header("🧠 Inteligência")
    st.markdown("""
    Esta aba apresenta uma visão analítica sobre os **pratos mais apreciados** e a **distribuição geográfica das avaliações**,
    ajudando na identificação de tendências e regiões de destaque.
    """)

    if not filtered.empty:
        st.markdown("**🍽️ Pratos Mais Citados:**")
        dishes = Counter([p.strip().lower() for row in filtered['dish_liked'].dropna().str.split(',') for p in row])
        dish_df = pd.DataFrame(dishes.most_common(10), columns=['dish','count'])
        fig = px.pie(dish_df, names='dish', values='count', hole=0.4, color_discrete_sequence=COLOR_SCALE,)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("**Conclusão:** Os pratos mais citados indicam preferências populares. Estas escolhas podem variar conforme a região e o perfil dos restaurantes filtrados.")

        st.markdown("**🗺️ Mapa de Avaliações por Bairro:**")
        agg = filtered.groupby('location')['rate'].mean().reset_index()
        agg['lat'] = agg['location'].map(lambda x: coords.get(x, {}).get('lat'))
        agg['lon'] = agg['location'].map(lambda x: coords.get(x, {}).get('lon'))
        agg = agg.dropna(subset=['lat','lon','rate'])

        fig_map = px.scatter_mapbox(
            agg,
            lat='lat',
            lon='lon',
            size='rate',
            color='rate',
            mapbox_style='open-street-map',
            zoom=10,
            color_continuous_scale=COLOR_SCALE,
        
        )
        fig_map.update_layout(height=600)
        st.plotly_chart(fig_map, use_container_width=True)
        st.markdown("**Conclusão:** As regiões com maiores avaliações tendem a se concentrar em áreas centrais ou com maior diversidade de oferta culinária. Isso pode orientar decisões de expansão ou foco de marketing.")

