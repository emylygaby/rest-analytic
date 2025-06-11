import sqlite3 

conn = sqlite3.connect("restaurantes.db", check_same_thread=False)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

cursor.execute("SELECT * FROM resumo_bairro")
resultados = cursor.fetchall()
for row in resultados:
    print(row)
