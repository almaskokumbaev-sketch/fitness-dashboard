import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide", page_icon="💪")
st.title("🚀 Smart Analytics: Фитнес Сеть")

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.header("🧠 Центр Управления")
    
    # Проверка ключа OpenAI
    if "OPENAI_API_KEY" in st.secrets:
        st.success("✅ AI-мозг подключен (Облако)")
        openai_api_key = st.secrets["OPENAI_API_KEY"]
    else:
        openai_api_key = st.text_input("Введите OpenAI API Key", type="password")
        if not openai_api_key:
            st.warning("⚠️ Введите ключ, чтобы работал ИИ")

    st.divider()
    
    st.info("📝 Контекст для робота:")
    user_context = st.text_area(
        "Опиши ситуацию:", 
        value="Это CRM фитнес-сети. Задача: найти менеджеров с низкой конверсией и понять, почему падают продажи. Данные за последние 2-3 дня могут быть неполными.",
        height=150
    )

# --- ФУНКЦИЯ ЗАГРУЗКИ (ГИБРИДНАЯ) ---
SHEET_NAME = 'мой первый дэшборд'

@st.cache_data(ttl=60)
def load_data():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # 1. Если мы в Облаке (Streamlit Cloud)
        if "gcp_service_account" in st.secrets:
            # Превращаем секреты в словарь Python
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        # 2. Если мы на Компьютере (Локально)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        st.error(f"Ошибка подключения: {e}")
        return None

df = load_data()

# --- ФУНКЦИЯ ИИ-АНАЛИЗА ---
def ask_ai(prompt):
    if not openai_api_key:
        return "⚠️ Нет ключа API"
    
    try:
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o", # Можно поменять на gpt-3.5-turbo, если 4o дорого
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка OpenAI: {e}"

# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
if st.button('🔄 Обновить данные'):
    st.cache_data.clear()

if df is not None:
    # МЕТРИКИ
    total_leads = len(df)
    st.metric("Всего Лидов", total_leads)
    st.divider()
    
    # РАЗДЕЛЕНИЕ ЭКРАНА
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("🤖 AI-Директор")
        if st.button("🔥 АНАЛИЗИРОВАТЬ СИТУАЦИЮ"):
            with st.spinner("ИИ изучает таблицу..."):
                # Готовим "выжимку" для ИИ
                sample = df.head(5).to_string()
                columns = ", ".join(df.columns)
                
                # Промпт
                final_prompt = f"""
                Роль: Опытный Коммерческий Директор.
                Контекст от владельца: "{user_context}"
                
                Структура таблицы (Колонки): {columns}
                Пример данных: 
                {sample}
                
                ЗАДАЧА:
                На основе структуры данных и контекста, напиши 3 стратегических совета.
                Не лей воду. Пиши жестко и по делу. Используй эмодзи.
                """
                
                result = ask_ai(final_prompt)
                st.success("Готово!")
                st.markdown(result)

    with col_right:
        st.subheader("📊 Данные")
        st.dataframe(df.head(50))
        
        st.write("---")
        # Автоматический график (если есть колонка Менеджер)
        if "Менеджер" in df.columns:
            st.caption("Активность менеджеров:")
            st.bar_chart(df["Менеджер"].value_counts().head(10))

else:
    st.warning("Загрузка...")