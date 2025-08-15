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

# Descargar base de datos (versión robusta)
@st.cache_data(ttl=3600)
def download_database():
    db_path = "ecommerce.db"

    if os.path.exists(db_path):
        file_size = os.path.getsize(db_path)
        if file_size > 1000:
            return db_path
        else:
            os.remove(db_path)

    try:
        file_id = "1YDmVjf5Nrz9Llgtka3KQMBUKwsnSF5vk"
        url = f"https://drive.google.com/uc?id={file_id}"

        progress_container = st.container()
        with progress_container:
            st.info("🔄 Descargando base de datos... Esto puede tardar unos segundos.")
            progress_bar = st.progress(10)
            status_text = st.empty()

            try:
                status_text.text("Conectando con Google Drive...")
                output = gdown.download(url, db_path, quiet=True)
                if output:
                    progress_bar.progress(100)
                    status_text.text("✅ Base de datos descargada exitosamente!")
                    time.sleep(1)
                    return db_path
                else:
                    raise Exception("gdown no pudo descargar el archivo")
            except Exception:
                status_text.text("Intentando método alternativo...")
                progress_bar.progress(50)

                session = requests.Session()
                response = session.get(f"https://drive.google.com/uc?export=download&id={file_id}", stream=True)

                token = None
                for key, value in response.cookies.items():
                    if key.startswith('download_warning'):
                        token = value
                        break

                urls = [f"https://drive.google.com/uc?export=download&id={file_id}"]
                if token:
                    urls.insert(0, f"https://drive.google.com/uc?export=download&confirm={token}&id={file_id}")

                for url in urls:
                    try:
                        response = session.get(url, stream=True, timeout=300)
                        if response.status_code == 200 and 'text/html' not in response.headers.get('content-type', ''):
                            total_size = int(response.headers.get('content-length', 0))
                            block_size = 8192
                            downloaded = 0
                            temp_path = db_path + ".tmp"

                            with open(temp_path, 'wb') as f:
                                for chunk in response.iter_content(block_size):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        if total_size > 0:
                                            progress = int(50 + (downloaded / total_size) * 50)
                                            progress_bar.progress(progress)
                                            status_text.text(f"Descargando... {downloaded / 1024 / 1024:.1f} MB")

                            try:
                                conn = sqlite3.connect(temp_path)
                                cursor = conn.cursor()
                                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                                cursor.close()
                                conn.close()

                                os.rename(temp_path, db_path)
                                progress_bar.progress(100)
                                status_text.text("✅ Base de datos descargada y verificada!")
                                time.sleep(1)
                                return db_path

                            except sqlite3.DatabaseError:
                                os.remove(temp_path)
                                status_text.text("❌ Archivo descargado no válido (no es SQLite)")
                                continue
                    except:
                        continue

                raise Exception("No se pudo descargar el archivo.")
    except Exception as e:
        st.error(f"❌ Error al descargar base de datos: {str(e)}")
        st.error("Verifica que el archivo sea público en Drive.")
        return None
    finally:
        if 'progress_container' in locals():
            progress_container.empty()

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

# Interfaz de usuario
st.title("🛡️ Chat SQL Seguro (solo SELECT)")
user_input = st.text_input("Haz una pregunta:")
if st.button("Consultar") and user_input:
    resultado = consulta(user_input)
    st.write(resultado)
