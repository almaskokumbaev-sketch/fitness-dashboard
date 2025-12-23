import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Debug Mode", layout="wide")
st.title("🛠 Режим Диагностики")

# --- 1. ПРОВЕРКА КЛЮЧЕЙ ---
st.subheader("1. Проверка ключей в Сейфе")

# Проверяем Google Cloud
if "gcp_service_account" in st.secrets:
    st.success("✅ Секция [gcp_service_account] найдена!")
    # Проверяем, что внутри есть данные
    creds_dict = st.secrets["gcp_service_account"]
    if "private_key" in creds_dict:
        st.info(f"🔑 Private Key найден (длина: {len(creds_dict['private_key'])})")
    else:
        st.error("❌ Внутри нет private_key!")
else:
    st.error("❌ Секция [gcp_service_account] НЕ найдена. Проверь название в Secrets.")

# Проверяем OpenAI
if "OPENAI_API_KEY" in st.secrets:
    st.success("✅ OpenAI Key найден!")
else:
    st.warning("⚠️ OpenAI Key не найден (но для запуска таблицы это не критично)")

# --- 2. ПОПЫТКА ПОДКЛЮЧЕНИЯ ---
st.subheader("2. Попытка подключения к Google")

SHEET_NAME = 'мой первый дэшборд'

try:
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Пытаемся создать учетные данные
    if "gcp_service_account" in st.secrets:
        # Важно: превращаем объект Streamlit в обычный словарь Python
        creds_json = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        st.write("... Учетные данные созданы")
        
        client = gspread.authorize(creds)
        st.write("... Клиент авторизован")
        
        sheet = client.open(SHEET_NAME).sheet1
        st.write(f"... Таблица '{SHEET_NAME}' найдена")
        
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        st.success(f"🎉 УСПЕХ! Скачано {len(df)} строк.")
        st.dataframe(df.head())
        
    else:
        st.error("Нет ключей — нет подключения.")

except Exception as e:
    # ВОТ ОНО! Самое важное: выводим полный текст ошибки
    st.error("🔥 ОШИБКА ПОДКЛЮЧЕНИЯ ПОДРОБНО:")
    st.code(str(e))
    st.warning("👇 Что это значит:")
    
    err_text = str(e)
    if "Sprite" in err_text or "SpreadsheetNotFound" in err_text:
        st.write("Робот не видит таблицу. Проверь: 1) Название таблицы точное? 2) Дал ли ты доступ боту (python-bot@...) в настройках доступа таблицы?")
    elif "Invalid RSA" in err_text:
        st.write("Ошибка в самом ключе (private_key). Возможно, при копировании потерялись переносы строк.")
    elif "project_id" in err_text:
        st.write("Ошибка в структуре JSON/TOML файла.")