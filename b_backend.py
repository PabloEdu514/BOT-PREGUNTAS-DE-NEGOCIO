# app_segura_con_tabla_y_export.py

import os
import re
import time
import sqlite3
import requests
import streamlit as st
import pandas as pd
import gdown

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain
from langchain_core.prompts import PromptTemplate

# Descargar base de datos
@st.cache_data(ttl=3600)
def download_database():
    db_path = "ecommerce.db"
    if os.path.exists(db_path) and os.path.getsize(db_path) > 1000:
        return db_path
    file_id = "1YDmVjf5Nrz9Llgtka3KQMBUKwsnSF5vk"
    url = f"https://drive.google.com/uc?id={file_id}"
    try:
        output = gdown.download(url, db_path, quiet=True)
        if output:
            return db_path
    except:
        pass
    st.error("❌ Error al descargar la base de datos.")
    return None

@st.cache_resource
def init_database():
    try:
        db_path = download_database()
        if db_path and os.path.exists(db_path):
            return SQLDatabase.from_uri(f"sqlite:///{db_path}")
    except Exception as e:
        st.error(f"Error al inicializar la base de datos: {e}")
    return None

db = init_database()

if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
else:
    try:
        import a_env_vars
        os.environ["OPENAI_API_KEY"] = a_env_vars.OPENAI_API_KEY
    except ImportError:
        st.warning("No se encontró la API Key de OpenAI.")

@st.cache_resource
def init_chain():
    global db
    if db is None:
        db = init_database()
        if db is None:
            return None, None, None, None

    try:
        llm = ChatOpenAI(model_name='gpt-4', temperature=0)
        query_chain = create_sql_query_chain(llm, db)
        answer_prompt = PromptTemplate.from_template(
            """Dada la siguiente pregunta del usuario, la consulta SQL correspondiente y el resultado SQL, 
            formula una respuesta clara y amigable en español.

            Pregunta: {question}
            Consulta SQL: {query}
            Resultado SQL: {result}
            Respuesta:"""
        )
        return query_chain, db, answer_prompt, llm
    except Exception as e:
        st.error(f"Error al inicializar la cadena: {str(e)}")
        return None, None, None, None

def es_consulta_segura(sql):
    sql = sql.strip().lower()
    sql = re.sub(r'--.*?(\n|$)', '', sql)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    if not sql.startswith("select"):
        return False
    peligrosas = ["insert", "update", "delete", "drop", "alter",
                  "create", "truncate", "replace", "attach", "detach",
                  "pragma", "exec", "execute"]
    return not any(p in sql for p in peligrosas)

def consulta(pregunta_usuario):
    try:
        if "OPENAI_API_KEY" not in os.environ:
            return "❌ No se configuró la API Key."

        query_chain, db_sql, prompt, llm = init_chain()
        if not query_chain or not db_sql:
            return "⚠️ No se pudo inicializar el sistema."

        with st.spinner("🔍 Generando consulta SQL..."):
            consulta_sql = query_chain.invoke({"question": pregunta_usuario})

        if not es_consulta_segura(consulta_sql):
            return "❌ Consulta bloqueada por seguridad. Solo se permiten operaciones SELECT."

        # Agregar LIMIT 1000 si no existe en la consulta
        if "limit" not in consulta_sql.lower():
            consulta_sql += " LIMIT 1000"

        with st.spinner("⚙️ Ejecutando consulta segura..."):
            conn = sqlite3.connect("ecommerce.db")
            cursor = conn.cursor()
            cursor.execute(consulta_sql)
            columnas = [desc[0] for desc in cursor.description]
            filas = cursor.fetchall()
            conn.close()

        if not filas:
            resultado = "[]"
        else:
            resultado = str(filas[:3]) + (" ..." if len(filas) > 3 else "")

        with st.spinner("💬 Generando respuesta..."):
            respuesta = llm.invoke(prompt.format_prompt(
                question=pregunta_usuario,
                query=consulta_sql,
                result=resultado
            ).to_string())

        df = pd.DataFrame(filas, columns=columnas)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Exportar resultados a CSV", data=csv, file_name="resultado.csv", mime="text/csv")

        return respuesta.content

    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# Interfaz
st.title("🛡️ Chat SQL Seguro (solo SELECT)")
user_input = st.text_input("Haz una pregunta:")
if st.button("Consultar") and user_input:
    resultado = consulta(user_input)
    st.write(resultado)
