import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="AI Business Audit", layout="centered", page_icon="🦄")
st.title("🦄 Авто-Аудит Бизнеса")
st.markdown("### Вставьте ссылку — получите правду.")

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
    st.write(f"1. Добавьте бота **{bot_email}** редактором в таблицу.")
    st.write("2. Вставьте ссылку ниже.")

sheet_url = st.text_input("🔗 Ссылка на Google Таблицу:", placeholder="https://docs.google.com/...")

# --- ЗАГРУЗКА (С ЗАЩИТОЙ ОТ ДУБЛЕЙ) ---
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
        
        # 🔥 ЛЕЧЕНИЕ ДУБЛИКАТОВ В ЗАГОЛОВКАХ 🔥
        headers = data.pop(0)
        unique_headers = []
        seen_headers = {}
        
        for h in headers:
            clean_h = str(h).strip() # Убираем лишние пробелы
            if clean_h in seen_headers:
                seen_headers[clean_h] += 1
                unique_headers.append(f"{clean_h}_{seen_headers[clean_h]}") # Делаем "Колонка_2"
            else:
                seen_headers[clean_h] = 1
                unique_headers.append(clean_h)
        
        # Создаем таблицу с уникальными именами
        df = pd.DataFrame(data, columns=unique_headers)
        
        # Убираем полностью пустые строки и столбцы (где header пустой)
        df = df.loc[:, df.columns != ''] 
        df = df.dropna(how='all', axis=0)
        
        return df, None
    except Exception as e:
        return None, str(e)

# --- АВТО-ПРОФАЙЛИНГ ---
def profile_data(df):
    summary = []
    summary.append(f"Всего строк: {len(df)}")
    summary.append(f"Всего колонок: {len(df.columns)}")
    summary.append(f"Список колонок: {', '.join(df.columns)}")
    
    # Анализ каждой колонки
    for col in df.columns:
        # Пропускаем пустые названия колонок
        if not col.strip(): continue

        # 1. Пробуем найти ЧИСЛА
        try:
            # Чистим от валют и пробелов
            numeric_series = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
            if not numeric_series.empty and len(numeric_series) > len(df) * 0.5:
                total = numeric_series.sum()
                avg = numeric_series.mean()
                summary.append(f"📊 '{col}' (Число): Сумма={total:,.0f}, Среднее={avg:,.0f}")
                continue
        except: pass
        
        # 2. Пробуем найти ДАТЫ
        try:
            date_series = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dropna()
            if not date_series.empty and len(date_series) > len(df) * 0.3:
                min_date = date_series.min().date()
                max_date = date_series.max().date()
                summary.append(f"📅 '{col}' (Дата): {min_date} — {max_date}")
                continue
        except: pass
        
        # 3. Иначе это КАТЕГОРИЯ
        # Берем только если уникальных значений немного (чтобы не перегрузить ИИ именами всех клиентов)
        unique_count = df[col].nunique()
        if unique_count < 50: 
            top_vals = df[col].value_counts().head(5).to_dict()
            summary.append(f"🔤 '{col}' (Текст): Топ значения -> {top_vals}")
    
    return "\n".join(summary)

# --- ИНТЕРФЕЙС ---
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success("✅ Данные получены.")
        
        if st.button("🚀 ЗАПУСТИТЬ АНАЛИЗ (AI)", type="primary"):
            if "OPENAI_API_KEY" in st.secrets:
                
                with st.status("🤖 ИИ изучает ваш бизнес...", expanded=True) as status:
                    st.write("🔍 Сканирую структуру и исправляю дубликаты...")
                    data_profile = profile_data(df)
                    st.write("🧠 Пишу отчет...")
                    
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    
                    prompt = f"""
                    Ты — Элитный Бизнес-Аудитор. Тебе прислали "слепок" данных.
                    
                    СТАТИСТИКА (Python посчитал цифры):
                    {data_profile}
                    
                    НАПИШИ ОТЧЕТ:
                    1. 🧐 ЧТО ЭТО ЗА БИЗНЕС? (Вывод по колонкам)
                    
                    2. 💎 ЖЕЛЕЗНЫЕ ФАКТЫ
                    - Кто лидер?
                    - Какой оборот?
                    - Тренды?
                    
                    3. 🚀 СОВЕТ ПО ДАННЫМ
                    - Чего не хватает? (Например: "Вижу Продажи, но нет Себестоимости").
                    
                    Пиши профессионально, используй Markdown.
                    """
                    
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    
                    status.update(label="Готово!", state="complete", expanded=False)
                
                st.markdown("---")
                st.markdown(response.choices[0].message.content)
                
            else:
                st.error("Нет ключа API")
else:
    st.info("👈 Вставьте ссылку, чтобы начать.")