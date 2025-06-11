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


cursor.execute('''
CREATE VIEW IF NOT EXISTS resumo_bairro AS
SELECT
    location AS bairro,
    listed_city AS cidade,
    COUNT(*) AS total_restaurantes,
    ROUND(AVG(rate), 2) AS media_avaliacao,
    SUM(votes) AS total_votos,
    ROUND(AVG(approx_cost), 2) AS custo_medio_para_dois
FROM
    restaurantes
GROUP BY
    location, listed_city
ORDER BY
    total_restaurantes DESC
''')

conn.commit()
conn.close()