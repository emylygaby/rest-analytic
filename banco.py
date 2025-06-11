import pandas as pd 
import sqlite3
from datetime import datetime

conn = sqlite3.connect("restaurantes.db", check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

cursor.execute(''' 
CREATE TABLE IF NOT EXISTS restaurantes ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    online_order TEXT,
    rate FLOAT, 
    votes INTEGER,
    location TEXT,
    rest_type TEXT, 
    dish_liked TEXT,
    cuisines TEXT,
    approx_cost INTEGER,
    listed_type TEXT,
    listed_city TEXT
    ) ''')

try:
    df = pd.read_csv("zomato.csv", sep=";", encoding="utf-8-sig")
    df.to_sql("restaurantes", conn, if_exists="append", index=False)
    print("Banco populado com sucesso!")
except Exception as e:
    print("Erro ao popular o banco:", e)