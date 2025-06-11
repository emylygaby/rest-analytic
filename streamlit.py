import pandas as pd 
import streamlit as st 
import seaborn as sns
import matplotlib.pyplot as plt
import sqlite3
from datetime import datetime

conn = sqlite3.connect("restaurantes.db", check_same_thread=False)

# Menu lateral para navegação entre páginas
pagina = st.sidebar.radio(
    "Selecione a página",
    ("Principal", "Sessão A", "Sessão B", "Sessão C")
)

def pagina_principal():
    st.title("Página Principal")
    st.write("Conteúdo da página principal aqui.")

def sessao_a():
    st.title("Sessão A")
    st.write("Conteúdo da Sessão A aqui.")

def sessao_b():
    st.title("Sessão B")
    st.write("Conteúdo da Sessão B aqui.")

def sessao_c():
    st.title("Sessão C")
    st.write("Conteúdo da Sessão C aqui.")

# Exibe a página selecionada
if pagina == "Principal":
    pagina_principal()
elif pagina == "Sessão A":
    sessao_a()
elif pagina == "Sessão B":
    sessao_b()
elif pagina == "Sessão C":
    sessao_c()