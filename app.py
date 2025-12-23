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

# --- ИНСТРУКЦИЯ (СКРЫТАЯ) ---
with st.expander("Как подключить таблицу? (Нажмите, если не знаете)", expanded=False):
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

# --- АВТО-ПРОФАЙЛИНГ (PYTHON ДЕЛАЕТ ВСЮ ГРЯЗНУЮ РАБОТУ) ---
def profile_data(df):
    summary = []
    summary.append(f"Всего строк: {len(df)}")
    summary.append(f"Всего колонок: {len(df.columns)}")
    summary.append(f"Список колонок: {', '.join(df.columns)}")
    
    # Анализ каждой колонки
    for col in df.columns:
        # 1. Пробуем найти ЧИСЛА
        try:
            numeric_series = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
            if not numeric_series.empty and len(numeric_series) > len(df) * 0.5: # Если чисел больше половины
                total = numeric_series.sum()
                avg = numeric_series.mean()
                summary.append(f"📊 Колонка '{col}' (Числа): Сумма = {total:,.0f}, Среднее = {avg:,.0f}")
                continue
        except: pass
        
        # 2. Пробуем найти ДАТЫ
        try:
            date_series = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dropna()
            if not date_series.empty:
                min_date = date_series.min().date()
                max_date = date_series.max().date()
                summary.append(f"📅 Колонка '{col}' (Даты): c {min_date} по {max_date}")
                continue
        except: pass
        
        # 3. Иначе это КАТЕГОРИЯ (Текст)
        # Считаем топ-5 значений
        top_vals = df[col].value_counts().head(5).to_dict()
        if len(df[col].unique()) < 50: # Если уникальных значений мало - это категория
            summary.append(f"🔤 Колонка '{col}' (Категория): Топ значения -> {top_vals}")
    
    return "\n".join(summary)

# --- ИНТЕРФЕЙС ---
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        # ПОКАЗЫВАЕМ ТОЛЬКО ГЛАВНУЮ КНОПКУ
        st.success("✅ Данные получены.")
        
        if st.button("🚀 ЗАПУСТИТЬ АНАЛИЗ (AI)", type="primary"):
            if "OPENAI_API_KEY" in st.secrets:
                
                with st.status("🤖 ИИ изучает ваш бизнес...", expanded=True) as status:
                    st.write("🔍 Сканирую структуру таблицы...")
                    data_profile = profile_data(df)
                    st.write("🧮 Считаю статистику...")
                    st.write("🧠 Пишу отчет...")
                    
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    
                    # --- ПРОМПТ (ТВОЁ ТЗ) ---
                    prompt = f"""
                    Ты — Элитный Бизнес-Аудитор. Тебе прислали "слепок" данных компании.
                    
                    ВОТ СТАТИСТИКА ДАННЫХ (Python уже посчитал цифры):
                    {data_profile}
                    
                    ТВОЯ ЗАДАЧА - НАПИСАТЬ ОТЧЕТ ИЗ 3 ПУНКТОВ:

                    1. 🧐 ЧЕМ ОНИ ЗАНИМАЮТСЯ?
                    Посмотри на названия колонок и данные. Сделай вывод, какой это бизнес.
                    (Пример: "Судя по колонкам 'Тренер' и 'Абонемент', вы — Фитнес-клуб").
                    
                    2. 💎 ЖЕЛЕЗНЫЕ ФАКТЫ (Только правда)
                    Используй цифры из статистики выше. Напиши 3 ключевых факта.
                    - Кто лидер продаж/активности? (Смотри Топ значения категорий)
                    - Какой оборот или объем? (Смотри суммы чисел)
                    - Какая динамика? (Смотри даты)
                    Пиши кратко и жестко.
                    
                    3. 🚀 ЧТО МОЖНО УЛУЧШИТЬ (Допродажа)
                    Посмотри на список колонок. Чего критически не хватает для глубокого анализа?
                    Напиши: "Я посчитал то, что есть. Но если вы добавите колонку [Название], я смогу показать [Выгода]".
                    
                    Пиши профессионально, используй Markdown и эмодзи.
                    """
                    
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    
                    status.update(label="Готово!", state="complete", expanded=False)
                
                # ВЫВОД РЕЗУЛЬТАТА
                st.markdown("---")
                st.markdown(response.choices[0].message.content)
                
            else:
                st.error("Нет ключа API")
else:
    st.info("👈 Вставьте ссылку, чтобы начать.")