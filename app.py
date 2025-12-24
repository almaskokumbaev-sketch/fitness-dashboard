import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Rescue Mode", layout="centered", page_icon="🚑")
st.title("🚑 Сайт восстановлен")
st.success("Если ты видишь этот текст — сервер живой!")

# --- КЛЮЧИ ---
try:
    if "gcp_service_account" in st.secrets:
        bot_email = st.secrets["gcp_service_account"]["client_email"]
    else:
        bot_email = "python-bot@..."
except:
    bot_email = "Ошибка ключей"

# --- ИНСТРУКЦИЯ ---
with st.expander("Как подключить таблицу?", expanded=False):
    st.write(f"1. Добавьте бота **{bot_email}** редактором.")
    st.write("2. Вставьте ссылку ниже.")

sheet_url = st.text_input("🔗 Ссылка на Google Таблицу:", placeholder="https://docs.google.com/...")

# --- ЗАГРУЗКА ---
@st.cache_data(ttl=60)
def load_data(url):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_url(url).sheet1
        data = sheet.get_all_values()
        
        if not data: return None, "Пустая таблица"
        
        headers = data.pop(0)
        unique_headers = []
        seen_headers = {}
        for i, h in enumerate(headers):
            clean_h = str(h).strip()
            if not clean_h: clean_h = f"Col_{i}"
            if clean_h in seen_headers:
                seen_headers[clean_h] += 1
                unique_headers.append(f"{clean_h}_{seen_headers[clean_h]}")
            else:
                seen_headers[clean_h] = 1
                unique_headers.append(clean_h)
        
        df = pd.DataFrame(data, columns=unique_headers)
        df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
        return df, None
    except Exception as e:
        return None, str(e)

if sheet_url:
    df, error = load_data(sheet_url)
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success(f"Данные загружены! Строк: {len(df)}")
        st.dataframe(df.head())