import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Business Analyst", layout="wide", page_icon="🦄")
st.title("🦄 Ваш Личный AI-Бизнес Аналитик")

# --- ПОЛУЧАЕМ EMAIL БОТА (ЧТОБЫ ПОКАЗАТЬ ПОЛЬЗОВАТЕЛЮ) ---
# Пытаемся достать email из секретов, чтобы пользователь знал, кому давать доступ
try:
    if "gcp_service_account" in st.secrets:
        bot_email = st.secrets["gcp_service_account"]["client_email"]
    else:
        # Если вдруг секретов нет (локальный запуск), берем из файла (если есть) или пишем заглушку
        bot_email = "python-bot@fitness-dashboard-482106.iam.gserviceaccount.com" # Твой бот
except:
    bot_email = "(email не найден, проверьте ключи)"

# --- ИНСТРУКЦИЯ ДЛЯ КЛИЕНТА (САМОЕ ВАЖНОЕ) ---
with st.expander("🚀 КАК ПОДКЛЮЧИТЬ СВОЮ ТАБЛИЦУ (Инструкция)", expanded=True):
    st.write("Чтобы ИИ мог проанализировать ваши данные, нужно дать ему доступ:")
    st.write(f"1. Скопируйте этот Email робота: code **{bot_email}**")
    st.write("2. Откройте вашу Google Таблицу -> Нажмите кнопку **Настройки доступа (Share)**.")
    st.write("3. Вставьте email робота и сделайте его **Редактором**.")
    st.write("4. Скопируйте ссылку на таблицу и вставьте ниже 👇")

# --- ПОЛЕ ВВОДА ССЫЛКИ ---
sheet_url = st.text_input("🔗 Вставьте ссылку на Google Таблицу:", placeholder="https://docs.google.com/spreadsheets/d/...")

# --- ФУНКЦИЯ ЗАГРУЗКИ ---
@st.cache_data(ttl=60)
def load_data(url):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        
        # Авторизация (Облако или Локально)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        
        # ОТКРЫВАЕМ ПО ССЫЛКЕ (Универсально!)
        sheet = client.open_by_url(url).sheet1
        return pd.DataFrame(sheet.get_all_records())
        
    except Exception as e:
        return None, e

# --- ЛОГИКА ПРИЛОЖЕНИЯ ---
if sheet_url:
    # Если ссылка есть - пробуем грузить
    data_load_result = load_data(sheet_url)
    
    # Проверка на ошибки
    if isinstance(data_load_result, tuple):
        # Если вернулась ошибка (None, error)
        st.error("🚫 Робот не может открыть таблицу!")
        st.warning("Вы точно добавили email бота в 'Настройки доступа' таблицы?")
        st.error(f"Детали ошибки: {data_load_result[1]}")
    else:
        df = data_load_result
        st.success("✅ Таблица успешно подключена!")
        
        # ==========================================
        # ДАЛЬШЕ ИДЕТ НАШ УНИВЕРСАЛЬНЫЙ КОНСТРУКТОР
        # ==========================================
        
        st.sidebar.header("⚙️ Настройка данных")
        st.sidebar.info("Сопоставьте колонки ваших данных:")

        all_columns = df.columns.tolist()
        
        if len(all_columns) > 0:
            # 1. Выбор колонок
            # Пытаемся угадать, но не падаем, если не нашли
            def find_col(keywords):
                match = next((x for x in all_columns if any(k in x.lower() for k in keywords)), all_columns[0])
                return all_columns.index(match)

            col_record = st.sidebar.selectbox("📅 Дата Записи", all_columns, index=find_col(["запис", "дата", "date"]))
            col_visit = st.sidebar.selectbox("🏃 Дата Визита", all_columns, index=find_col(["придет", "визит", "visit"]))
            col_mgr = st.sidebar.selectbox("👤 Менеджер", all_columns, index=find_col(["менеджер", "manager", "сотрудник"]))
            col_status = st.sidebar.selectbox("❓ Статус", all_columns, index=find_col(["статус", "приш", "status", "result"]))
            
            # 2. Настройка Успеха
            st.sidebar.divider()
            unique_statuses = df[col_status].astype(str).unique().tolist()
            st.sidebar.write("Что считать продажей/визитом?")
            
            # Авто-выбор позитивных слов
            default_success = [x for x in unique_statuses if any(sw in x.lower() for sw in ["приш", "куп", "да", "ok", "done"])]
            
            success_values = st.sidebar.multiselect(
                "Выберите успешные статусы:",
                options=unique_statuses,
                default=default_success
            )

            # 3. Аналитика
            if success_values:
                # Фильтрация и расчет
                df_clean = df.copy()
                # Превращаем в даты
                df_clean['Record_DT'] = pd.to_datetime(df_clean[col_record], dayfirst=True, errors='coerce')
                df_clean['Visit_DT'] = pd.to_datetime(df_clean[col_visit], dayfirst=True, errors='coerce')
                df_clean = df_clean.dropna(subset=['Record_DT', 'Visit_DT']) # Убираем кривые даты

                # Флаг успеха
                df_clean['Is_Success'] = df_clean[col_status].astype(str).isin(success_values)
                
                # Фильтр будущего (через сайдбар)
                limit_date = st.sidebar.date_input("Анализ до даты:", pd.to_datetime("2025-12-31"))
                df_valid = df_clean[df_clean['Visit_DT'] <= pd.to_datetime(limit_date)]

                # Считаем цикл сделки
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

                # ВЫВОД НА ЭКРАН
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("Обработано строк", len(df_valid))
                    st.metric("Успешных сделок", df_valid['Is_Success'].sum())
                    
                    st.divider()
                    user_q = st.text_area("Задайте вопрос ИИ:", "Где мы теряем клиентов? Кто худший менеджер?")
                    
                    if st.button("🚀 СПРОСИТЬ ИИ"):
                        if "OPENAI_API_KEY" in st.secrets:
                            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                            with st.spinner("Анализирую..."):
                                prompt = f"Таблица: {stats_df.to_string()}\nВопрос: {user_q}\nОтветь как профи."
                                res = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                                st.success("Инсайт:")
                                st.markdown(res.choices[0].message.content)
                        else:
                            st.error("Нет ключа OpenAI!")

                with col2:
                    st.write("📊 **Сводная статистика:**")
                    st.dataframe(stats_df.style.background_gradient(cmap="RdYlGn", subset=['Конверсия %']))

            else:
                st.warning("👈 Выберите успешные статусы слева, чтобы начать!")
        else:
            st.error("В таблице нет данных!")

else:
    # ЭКРАН ПРИВЕТСТВИЯ (ЕСЛИ ССЫЛКИ НЕТ)
    st.info("👈 Вставьте ссылку на таблицу, чтобы начать магию!")