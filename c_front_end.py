# lanzar con streamlit run c_front_end.py en el terminal

import b_backend
import streamlit as st

st.title("🤖 BOT para contestar PREGUNTAS DE NEGOCIO de la tabla de socios")

st.write("📝 **Te sugiero iniciar preguntándome:**")
st.write("¿CUÁLES SON LOS NOMBRES DE LAS COLUMNAS DE LA TABLA SOCIOS?")

st.write("")  # Línea en blanco

st.write("💡 **Ejemplos de consultas útiles:**")

ejemplos = [
    "💰 MUÉSTRAME LOS 5 NÚMEROS DE SOCIOS CON MAYOR SALDO EN DPFs",
    "💳 ¿CUÁNTOS SOCIOS TIENEN TARJETA DE CRÉDITO EN LA REGIÓN ORIENTE?",
    "📊 DAME LA SUMA DE SALDO DE AHORRO DE SOCIOS QUE ESTÁN EN CARTERA VENCIDA",
    "🌎 AGRÚPAME LAS SUMAS DE RESPONSABILIDAD TOTAL DE LOS CRÉDITOS ACTIVOS POR REGIONES",
    "⭐ ¿QUIÉN ES EL SOCIO QUE TIENE EL MAYOR BC SCORE?",
    "🔍 ENCUENTRA 3 REGISTROS DE SOCIOS QUE PERTENEZCAN A SUCURSAL CENTRO QUE NO TENGAN TARJETA DE CRÉDITO Y QUE TENGAN SCORE MAYOR A 700; MUÉSTRAME EL RESULTADO CON LAS COLUMNAS NÚMERO DE SOCIO Y SCORE"
]

for i, ejemplo in enumerate(ejemplos, 1):
    st.write(f"{i}. {ejemplo}")

st.write("")  # Línea en blanco

st.info("🔎 **Consulta individual:** Si quieres ver los campos de un socio en particular, solicítalo así: MUESTRAME EL REGISTRO CON NÚMERO DE SOCIO ###### CON TODOS SUS CAMPOS TAL CUAL ESTAN EN LA TABLA DE SOCIOS")



# Inicializar el estado de la sesión
if 'mensajes' not in st.session_state:
    st.session_state.mensajes = []

# Contenedor para el historial de chat
chat_container = st.container()

# Mostrar historial de mensajes
with chat_container:
    for mensaje in st.session_state.mensajes:
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])

# Input del usuario
if prompt := st.chat_input("¿En qué te puedo ayudar?"):
    # Agregar mensaje del usuario al historial
    st.session_state.mensajes.append({"role": "user", "content": prompt})
    
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.write(prompt)
    
    # Obtener respuesta del backend
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            respuesta = b_backend.consulta(prompt)
        st.write(respuesta)
    
    # Agregar respuesta al historial
    st.session_state.mensajes.append({"role": "assistant", "content": respuesta})

# Botón para limpiar conversación
if st.button("Nueva conversación"):
    st.session_state.mensajes = []
    st.rerun()


