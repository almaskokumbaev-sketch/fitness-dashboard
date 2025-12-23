import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Business Audit Pro", layout="centered", page_icon="🦄")
st.title("🦄 Глубокий Аудит Бизнеса (Pro)")
st.markdown("### Загрузите ссылку — получите Стратегию.")

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

# --- ЗАГРУЗКА (FIX ПУСТЫХ ЗАГОЛОВКОВ) ---
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
        
        # Улучшенная обработка заголовков
        headers = data.pop(0)
        unique_headers = []
        seen_headers = {}
        
        for i, h in enumerate(headers):
            clean_h = str(h).strip()
            if not clean_h:
                clean_h = f"Колонка_{i+1}" # Если пусто - даем имя "Колонка_N"
            
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

# --- 🕵️‍♂️ ШЕРЛОК ХОЛМС (УМНЫЙ АНАЛИЗАТОР) ---
def deep_analyze_data(df):
    report = []
    
    # 1. Поиск Денег (Самая важная колонка)
    money_col = None
    max_sum = 0
    
    # 2. Поиск Категорий
    cat_cols = []
    
    report.append(f"📊 ОБЪЕМ ДАННЫХ: {len(df)} строк")
    
    for col in df.columns:
        # --- АНАЛИЗ ЧИСЕЛ ---
        try:
            # Чистим от валют и пробелов
            numeric = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
            if not numeric.empty and len(numeric) > len(df) * 0.1: # Если чисел хотя бы 10%
                total = numeric.sum()
                if total > max_sum: # Ищем колонку с самой большой суммой (Скорее всего Выручка)
                    max_sum = total
                    money_col = col
                
                report.append(f"💰 '{col}': Сумма = {total:,.0f} | Среднее = {numeric.mean():,.0f}")
        except: pass

        # --- АНАЛИЗ ТЕКСТА (КАТЕГОРИИ) ---
        if df[col].nunique() < 100 and df[col].nunique() > 1: # Категория (не уникальные ID)
            cat_cols.append(col)
            
            # Считаем Топ и ПРОЦЕНТЫ
            counts = df[col].value_counts().head(5)
            total_rows = len(df)
            
            top_str = []
            for name, count in counts.items():
                percent = (count / total_rows) * 100
                top_str.append(f"{name}: {count} шт ({percent:.1f}%)")
            
            # Проверяем: Это Менеджер или Клиент?
            # Если топ-1 значение встречается чаще 5% случаев - скорее всего это Сотрудник/Статус/Город
            role_hint = "(Возможно, Менеджер или Категория)" if (counts.iloc[0] / total_rows > 0.05) else "(Возможно, Имена клиентов)"
            
            report.append(f"🔤 '{col}' {role_hint}: {', '.join(top_str)}")

    # --- 3. CROSS-ANALYSIS (ЗОЛОТАЯ ЖИЛА) ---
    # Если нашли Деньги и Категории - скрещиваем их!
    if money_col and cat_cols:
        report.append("\n🏆 РЕЙТИНГ ЭФФЕКТИВНОСТИ (Кто приносит деньги?):")
        for cat in cat_cols:
            # Пропускаем, если слишком много уникальных (это клиенты)
            if df[cat].nunique() > 20: continue 
            
            # Группируем Деньги по Категории
            df[money_col] = pd.to_numeric(df[money_col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)
            grouped = df.groupby(cat)[money_col].sum().sort_values(ascending=False).head(3)
            
            total_money = df[money_col].sum()
            if total_money > 0:
                best_performer = []
                for name, val in grouped.items():
                    share = (val / total_money) * 100
                    best_performer.append(f"{name} = {val:,.0f} ({share:.1f}% от всей кассы)")
                
                report.append(f"📌 Лидеры по '{cat}':\n   " + "\n   ".join(best_performer))

    return "\n".join(report)

# --- ИНТЕРФЕЙС ---
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success("✅ Данные загружены.")
        
        if st.button("🚀 НАЙТИ ТОЧКИ РОСТА (AI)", type="primary"):
            if "OPENAI_API_KEY" in st.secrets:
                
                with st.status("🧠 Анализирую каждый байт...", expanded=True) as status:
                    st.write("🔍 Провожу перекрестный анализ...")
                    deep_stats = deep_analyze_data(df)
                    st.code(deep_stats) # Покажем юзеру сухие цифры для прозрачности
                    
                    st.write("💡 Генерирую стратегию...")
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    
                    # --- ЕБЕЙШИЙ ПРОМПТ ---
                    prompt = f"""
                    Ты — Топовый Стратегический Консультант (уровень McKinsey).
                    Твоя цель — найти "Аномалию" или "Рычаг роста".
                    
                    СУХИЕ ФАКТЫ (Python уже посчитал проценты и деньги):
                    {deep_stats}
                    
                    ЗАДАЧА:
                    Напиши 3 блока. Без воды.

                    1. 🎯 ГЛАВНЫЙ ИНСАЙТ (The One Thing)
                    Найди самую мощную цифру. 
                    Например: "Ваш менеджер Асель делает 40% всей выручки. Она кормит весь отдел. Если она уйдет — бизнес рухнет."
                    Или: "Астана приносит 80% денег, но там всего 30% клиентов. Значит, там платят в 2 раза больше (высокий чек). Масштабируйте Астану!"
                    (Используй посчитанные проценты из Фактов).

                    2. 🕵️‍♂️ РАЗБОР ПОЛЕТОВ (Ошибки)
                    Посмотри, кто "ест ресурсы", но не приносит результата.
                    (Например: "Услуга Х популярна (50% записей), но денег дает мало. Поднимите на неё цену").
                    
                    3. 🔮 ЧЕГО НЕ ХВАТАЕТ (Upsell)
                    Посмотри на колонки. Скажи: "Я посчитал выручку, но не вижу РАСХОДЫ. Добавьте колонку 'Себестоимость', и я найду скрытые убытки".
                    
                    Важно:
                    - Если видишь имя, которое повторяется часто — это СОТРУДНИК, а не клиент.
                    - Используй Эмодзи.
                    - Делай выводы на основе % (доли).
                    """
                    
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    status.update(label="Готово!", state="complete", expanded=False)
                
                st.markdown("---")
                st.markdown(response.choices[0].message.content)
                
            else:
                st.error("Нет ключа API")
else:
    st.info("👈 Вставьте ссылку, чтобы начать.")