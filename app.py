import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Business Analyst", layout="wide", page_icon="🦄")
st.title("🦄 Ваш Личный AI-Бизнес Аналитик")

# --- ПОЛУЧАЕМ EMAIL БОТА ---
try:
    if "gcp_service_account" in st.secrets:
        bot_email = st.secrets["gcp_service_account"]["client_email"]
    else:
        bot_email = "python-bot@..." 
except:
    bot_email = "(email не найден)"

# --- ИНСТРУКЦИЯ ---
with st.expander("🚀 ИНСТРУКЦИЯ ПОДКЛЮЧЕНИЯ", expanded=True):
    st.write("1. Скопируйте Email робота: code **" + bot_email + "**")
    st.write("2. В Google Таблице нажмите **Настройки доступа (Share)** -> Добавьте этот email как **Редактора**.")
    st.write("3. Вставьте ссылку на таблицу ниже.")

sheet_url = st.text_input("🔗 Ссылка на таблицу:", placeholder="https://docs.google.com/...")

# --- 🔥 ОБНОВЛЕННАЯ ФУНКЦИЯ ЗАГРУЗКИ (FIX) ---
@st.cache_data(ttl=60)
def load_data(url):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Авторизация
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_url(url).sheet1
        
        # ВМЕСТО get_all_records() ИСПОЛЬЗУЕМ БОЛЕЕ НАДЕЖНЫЙ МЕТОД
        # Он не падает, если есть пустые колонки
        data = sheet.get_all_values()
        
        if not data:
            return None, "Таблица пуста"

        # Превращаем в Pandas DataFrame вручную
        headers = data.pop(0) # Первая строка - заголовки
        df = pd.DataFrame(data, columns=headers)
        
        # Чистим пустые колонки (если заголовка нет - удаляем колонку)
        df = df.loc[:, df.columns != '']
        
        return df
        
    except Exception as e:
        return None, e

# --- ЛОГИКА ---
if sheet_url:
    data_result = load_data(sheet_url)
    
    # Проверка: Если вернулся кортеж (None, ошибка)
    if isinstance(data_result, tuple):
        st.error("🚫 Ошибка подключения!")
        st.write(f"Детали: {data_result[1]}")
    else:
        df = data_result
        st.success(f"✅ Успешно! Загружено строк: {len(df)}")
        
        # ==========================================
        # УНИВЕРСАЛЬНЫЙ КОНСТРУКТОР
        # ==========================================
        
        st.sidebar.header("⚙️ Настройка")
        all_columns = df.columns.tolist()
        
        if len(all_columns) > 0:
            # 1. Выбор колонок (С защитой от дурака)
            def find_col(keywords):
                # Ищем совпадение, если нет - берем первую колонку
                found = next((x for x in all_columns if any(k in x.lower() for k in keywords)), None)
                return all_columns.index(found) if found else 0

            col_record = st.sidebar.selectbox("📅 Дата Записи", all_columns, index=find_col(["запис", "дата", "date"]))
            col_visit = st.sidebar.selectbox("🏃 Дата Визита", all_columns, index=find_col(["придет", "визит", "visit"]))
            col_mgr = st.sidebar.selectbox("👤 Менеджер", all_columns, index=find_col(["менеджер", "manager"]))
            col_status = st.sidebar.selectbox("❓ Статус", all_columns, index=find_col(["статус", "result", "приш"]))
            
            # 2. Успех
            unique_statuses = df[col_status].unique().tolist()
            default_success = [x for x in unique_statuses if any(s in str(x).lower() for s in ["приш", "куп", "да", "ok"])]
            
            success_values = st.sidebar.multiselect("Что считать успехом?", unique_statuses, default=default_success)

            if success_values:
                # Расчеты
                df_clean = df.copy()
                df_clean['Record_DT'] = pd.to_datetime(df_clean[col_record], dayfirst=True, errors='coerce')
                df_clean['Visit_DT'] = pd.to_datetime(df_clean[col_visit], dayfirst=True, errors='coerce')
                df_clean = df_clean.dropna(subset=['Record_DT', 'Visit_DT'])
                df_clean['Is_Success'] = df_clean[col_status].isin(success_values)

                # Фильтр будущего
                limit_date = st.sidebar.date_input("Не считать после:", pd.to_datetime("2025-12-31"))
                df_valid = df_clean[df_clean['Visit_DT'] <= pd.to_datetime(limit_date)]

                # Цикл сделки
                df_valid['Lag'] = (df_valid['Visit_DT'] - df_valid['Record_DT']).dt.days
                def group_lag(d):
                    if d == 0: return "День в день"
                    if 1 <= d <= 7: return "1-7 дней"
                    return "> Недели"
                df_valid['Time_Group'] = df_valid['Lag'].apply(group_lag)

                # Агрегация
                stats = df_valid.groupby(['Time_Group', col_mgr]).agg(
                    Всего=('Is_Success', 'count'),
                    Успех=('Is_Success', 'sum')
                )
                stats['Конверсия %'] = (stats['Успех'] / stats['Всего'] * 100).round(1)

                # Вывод
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric("Лидов", len(df_valid))
                    st.metric("Продаж", df_valid['Is_Success'].sum())
                    
                    q = st.text_area("Вопрос ИИ:", "Где теряем деньги?")
                    if st.button("🚀 СПРОСИТЬ"):
                        if "OPENAI_API_KEY" in st.secrets:
                            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                            with st.spinner("Думаю..."):
                                prompt = f"Данные:\n{stats.to_string()}\nВопрос: {q}"
                                res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                                st.success("Инсайт:")
                                st.markdown(res.choices[0].message.content)

                with c2:
                    st.dataframe(stats.style.background_gradient(cmap="RdYlGn", subset=['Конверсия %']))
            else:
                st.warning("👈 Выберите статусы успеха слева!")
else:
    st.info("👈 Вставьте ссылку, чтобы начать.")