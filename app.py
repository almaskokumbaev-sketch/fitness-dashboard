import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Universal AI Analyst", layout="wide", page_icon="🦄")
st.title("🦄 Ваш Личный AI-Бизнес Аналитик")

# --- КЛЮЧИ ---
try:
    if "gcp_service_account" in st.secrets:
        bot_email = st.secrets["gcp_service_account"]["client_email"]
    else:
        bot_email = "python-bot@..."
except:
    bot_email = "Ошибка ключей"

# --- ИНСТРУКЦИЯ ---
with st.expander("🔌 Подключение таблицы", expanded=False):
    st.write(f"1. Добавьте бота **{bot_email}** редактором в таблицу.")
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
        df = pd.DataFrame(data, columns=headers)
        df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
        return df, None
    except Exception as e:
        return None, str(e)

def detect_types(df):
    col_types = {}
    for col in df.columns:
        try:
            pd.to_numeric(df[col].str.replace(r'[^\d.-]', '', regex=True))
            col_types[col] = "🔢"
            continue
        except: pass
        try:
            pd.to_datetime(df[col], dayfirst=True)
            col_types[col] = "📅"
            continue
        except: pass
        col_types[col] = "🔤"
    return col_types

# --- ИНТЕРФЕЙС ---
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success(f"✅ Данные загружены. Строк: {len(df)}")
        col_types = detect_types(df)
        
        st.sidebar.header("🛠 Конструктор Анализа")
        
        # 1. ГРУППИРОВКА
        group_selection = st.sidebar.multiselect(
            "1. По каким параметрам группируем?",
            options=df.columns,
            format_func=lambda x: f"{col_types[x]} {x}"
        )
        
        # 2. МЕТРИКИ
        num_cols = [c for c, t in col_types.items() if t == "🔢"]
        metric_selection = st.sidebar.multiselect(
            "2. Что суммируем/считаем?",
            options=num_cols,
            format_func=lambda x: f"🔢 {x}"
        )
        
        # 3. ФИЛЬТР
        date_cols = [c for c, t in col_types.items() if t == "📅"]
        if date_cols:
            filter_date_col = st.sidebar.selectbox("Фильтр по дате (опция):", ["(Нет)"] + date_cols)
            if filter_date_col != "(Нет)":
                df[filter_date_col] = pd.to_datetime(df[filter_date_col], dayfirst=True, errors='coerce')
                max_date = st.sidebar.date_input("Обрезать данные после:", pd.to_datetime("today"))
                df = df[df[filter_date_col] <= pd.to_datetime(max_date)]

        # --- ЯДРО ---
        if group_selection:
            st.subheader("📊 Живой Отчет")
            
            df_grouped = df.copy()
            for col in group_selection:
                if col_types[col] == "📅":
                    df_grouped[col] = pd.to_datetime(df_grouped[col], dayfirst=True, errors='coerce').dt.date.astype(str)

            if metric_selection:
                for col in metric_selection:
                    df_grouped[col] = pd.to_numeric(df_grouped[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)
                result_df = df_grouped.groupby(group_selection)[metric_selection].sum().reset_index()
                count_df = df_grouped.groupby(group_selection).size().reset_index(name='Кол-во операций')
                result_df = pd.merge(result_df, count_df, on=group_selection)
            else:
                result_df = df_grouped.groupby(group_selection).size().reset_index(name='Количество')
            
            sort_col = result_df.columns[-1]
            result_df = result_df.sort_values(by=sort_col, ascending=False)
            
            st.dataframe(result_df, use_container_width=True)
            
            # --- AI ИНСАЙТЫ ---
            col1, col2 = st.columns([1, 1])
            with col1:
                st.info("💡 ИИ готов анализировать то, что есть.")
                user_q = st.text_area("Вопрос к ИИ:", "Дай главные выводы по этим цифрам.")
            
            with col2:
                if st.button("🚀 ПОЛУЧИТЬ РАЗБОР (Честный)"):
                    if "OPENAI_API_KEY" in st.secrets:
                        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                        with st.spinner("Думаю..."):
                            
                            csv_data = result_df.head(50).to_string()
                            
                            # --- ВОТ ОН, НОВЫЙ ПРОМПТ ---
                            prompt = f"""
                            Ты — Опытный, Честный и Амбициозный Бизнес-Аналитик.
                            
                            ТВОЯ ЗАДАЧА - ДАТЬ ОТВЕТ ИЗ ДВУХ ЧАСТЕЙ:

                            ЧАСТЬ 1: ЖЕЛЕЗНЫЕ ФАКТЫ (Только правда)
                            Посмотри на эту сводную таблицу:
                            {csv_data}
                            
                            Дай 3 конкретных инсайта. Кто лидер? Кто аутсайдер? Где аномалия?
                            Опирайся ТОЛЬКО на цифры, которые видишь. Не выдумывай. Если цифры говорят, что продаж 0 - так и пиши: "Продаж 0, у нас проблема".
                            
                            ЧАСТЬ 2: ТВОЙ ПОТЕНЦИАЛ (Opportunity)
                            Посмотри на список доступных колонок в исходной таблице: {list(col_types.keys())}.
                            
                            Скажи клиенту честно, чего тебе не хватает, чтобы стать ЕЩЕ полезнее.
                            Пример: "Ты дал мне продажи, но если добавишь колонку 'Себестоимость', я посчитаю тебе чистую прибыль".
                            Пример: "Если добавишь 'Источник рекламы', я скажу, куда сливается бюджет".
                            
                            Фраза-триггер: "В целом, ты меня недооцениваешь. Дай мне эти данные, и я покажу тебе магию."
                            
                            Контекст пользователя: "{user_q}"
                            """
                            
                            res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                            st.markdown(res.choices[0].message.content)
                    else:
                        st.error("Нет ключа API")

        else:
            st.info("👈 Выберите параметры слева, чтобы построить отчет.")

else:
    st.info("👈 Вставьте ссылку на таблицу.")