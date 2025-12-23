import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Business Analyst", layout="wide", page_icon="💼")
st.title("💼 Универсальный AI-Аналитик")

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
st.sidebar.header("⚙️ Настройка данных")

# --- ЗАГРУЗКА ---
SHEET_NAME = 'мой первый дэшборд'

@st.cache_data(ttl=60)
def load_data():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return None

df = load_data()

# --- ЛОГИКА ИИ ---
def ask_ai(stats, context):
    if "OPENAI_API_KEY" not in st.secrets:
        return "⚠️ Нет ключа API"
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        prompt = f"""
        Ты — Бизнес-аналитик. 
        Контекст: {context}
        
        ВОТ СТАТИСТИКА (МЫ УЧЛИ ТОЛЬКО РЕАЛЬНЫЕ ПРОДАЖИ/ВИЗИТЫ):
        {stats}
        
        ЗАДАЧА:
        Дай 3 жестких инсайта по этим цифрам. Где мы теряем деньги?
        """
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка: {e}"

# --- ИНТЕРФЕЙС ---
if st.button('🔄 Обновить данные'):
    st.cache_data.clear()

if df is not None and not df.empty:
    # ---------------------------------------------------------
    # 🎛️ УНИВЕРСАЛЬНЫЙ КОНФИГУРАТОР (SaaS MAGIC)
    # ---------------------------------------------------------
    st.sidebar.info("1. Сопоставьте колонки:")
    
    # 1. Выбираем, где какая колонка (Код читает заголовки сам!)
    all_columns = df.columns.tolist()
    
    # Пытаемся угадать (чтобы клиенту было проще), но даем изменить
    default_rec = next((x for x in all_columns if "запис" in x.lower()), all_columns[0])
    default_vis = next((x for x in all_columns if "придет" in x.lower() or "дата" in x.lower()), all_columns[0])
    default_mgr = next((x for x in all_columns if "менеджер" in x.lower()), all_columns[0])
    default_sts = next((x for x in all_columns if "приш" in x.lower() or "статус" in x.lower()), all_columns[0])

    col_record = st.sidebar.selectbox("📅 Дата Записи", all_columns, index=all_columns.index(default_rec))
    col_visit = st.sidebar.selectbox("🏃 Дата Визита", all_columns, index=all_columns.index(default_vis))
    col_mgr = st.sidebar.selectbox("👤 Менеджер", all_columns, index=all_columns.index(default_mgr))
    col_status = st.sidebar.selectbox("❓ Статус (Пришел/Нет)", all_columns, index=all_columns.index(default_sts))
    
    st.sidebar.divider()
    st.sidebar.info("2. Что считать УСПЕХОМ?")
    
    # 2. Самое важное: Пользователь сам выбирает, что такое "Пришел"
    unique_statuses = df[col_status].dropna().unique().tolist()
    
    # По умолчанию ищем позитивные слова, чтобы проставить галочки
    default_success = [x for x in unique_statuses if "приш" in str(x).lower() or "куп" in str(x).lower() or "да" in str(x).lower()]
    
    success_values = st.sidebar.multiselect(
        "Выберите статусы, которые означают 'Деньги/Визит':",
        options=unique_statuses,
        default=default_success
    )
    
    if not success_values:
        st.sidebar.warning("⚠️ Выберите хотя бы один успешный статус!")

    # ---------------------------------------------------------
    # 📐 МАТЕМАТИКА (НА ОСНОВЕ ВЫБОРА ПОЛЬЗОВАТЕЛЯ)
    # ---------------------------------------------------------
    
    # Очистка и конвертация
    df_clean = df.copy()
    df_clean = df_clean[df_clean[col_record] != '']
    df_clean['Record_DT'] = pd.to_datetime(df_clean[col_record], dayfirst=True, errors='coerce')
    df_clean['Visit_DT'] = pd.to_datetime(df_clean[col_visit], dayfirst=True, errors='coerce')
    
    # Флаг Успеха (теперь зависит от галочек в меню!)
    df_clean['Is_Success'] = df_clean[col_status].isin(success_values)
    
    # Фильтр дат (будущее не считаем)
    limit_date = st.sidebar.date_input("Не считать статистику после:", pd.to_datetime("2025-12-21"))
    df_valid = df_clean[df_clean['Visit_DT'] <= pd.to_datetime(limit_date)]
    
    # Расчет метрик
    df_valid['Lag'] = (df_valid['Visit_DT'] - df_valid['Record_DT']).dt.days
    
    def group_lag(d):
        if d == 0: return "День в день"
        if 1 <= d <= 7: return "1-7 дней"
        return "> Недели"
        
    df_valid['Time_Group'] = df_valid['Lag'].apply(group_lag)
    
    # Таблица для ИИ
    stats_df = df_valid.groupby(['Time_Group', col_mgr]).agg(
        Всего=('Is_Success', 'count'),
        Успех=('Is_Success', 'sum')
    )
    stats_df['Конверсия %'] = (stats_df['Успех'] / stats_df['Всего'] * 100).round(1)
    
    # ---------------------------------------------------------
    # 📺 ВЫВОД
    # ---------------------------------------------------------
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Настройки Успеха")
        st.write(f"Вы считаете успехом статусы: **{', '.join(map(str, success_values))}**")
        st.write(f"Всего валидных записей: **{len(df_valid)}**")
        st.write(f"Из них успешных: **{df_valid['Is_Success'].sum()}**")
        
        user_q = st.text_area("Вопрос ИИ:", "Найди аномалии в конверсии.")
        if st.button("🚀 Анализ"):
            res = ask_ai(stats_df.to_string(), user_q)
            st.markdown(res)

    with col2:
        st.subheader("📊 Живая Статистика")
        st.dataframe(stats_df.style.background_gradient(cmap="RdYlGn", subset=['Конверсия %']))

else:
    st.warning("Таблица пуста или ошибка загрузки.")