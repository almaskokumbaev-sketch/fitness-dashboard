import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import time

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Total Audit", layout="centered", page_icon="🦖")
st.title("🦖 AI-Аудит: Полный Разнос")
st.markdown("### Загрузи данные и расскажи, что болит.")

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

# --- 🔥 НОВЫЙ БЛОК ВВОДА ---
sheet_url = st.text_input("🔗 Ссылка на Google Таблицу:", placeholder="https://docs.google.com/...")
user_context = st.text_area("📝 О чем эта таблица? (Контекст)", 
                            placeholder="Например: Это CRM фитнес-клуба. Мы хотим понять, почему люди не продлевают абонементы. Найди худшего менеджера.",
                            height=100)

# --- ЗАГРУЗКА ВСЕХ ЛИСТОВ ---
@st.cache_data(ttl=60)
def load_all_sheets(url):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        if "gcp_service_account" in st.secrets:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(url)
        worksheets = spreadsheet.worksheets()
        all_data = {}
        
        for ws in worksheets:
            try:
                data = ws.get_all_values()
                if not data: continue
                
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
                if not df.empty:
                    all_data[ws.title] = df
            except: pass
                
        return all_data, None
    except Exception as e:
        return None, str(e)

# --- АНАЛИЗАТОР ---
def analyze_structure(all_dfs):
    report = []
    report.append(f"📂 ВСЕГО ЛИСТОВ: {len(all_dfs)}")
    report.append(f"📑 СПИСОК ВКЛАДОК: {', '.join(all_dfs.keys())}")
    
    global_revenue = 0
    
    for sheet_name, df in all_dfs.items():
        report.append(f"\n--- ЛИСТ: '{sheet_name}' ---")
        report.append(f"   Колонки: {', '.join(df.columns)}")
        
        local_max_sum = 0
        money_col = None
        
        for col in df.columns:
            try:
                numeric = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
                if not numeric.empty and len(numeric) > len(df) * 0.1:
                    total = numeric.sum()
                    if total > local_max_sum:
                        local_max_sum = total
                        money_col = col
            except: pass
            
        if money_col:
            report.append(f"   💰 Деньги в колонке '{money_col}': {local_max_sum:,.0f}")
            global_revenue += local_max_sum
            
            # Топ продаж
            for col in df.columns:
                if df[col].nunique() < 50 and df[col].nunique() > 1 and col != money_col:
                    try:
                        df[money_col] = pd.to_numeric(df[money_col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)
                        top = df.groupby(col)[money_col].sum().sort_values(ascending=False).head(1)
                        if not top.empty:
                            leader = top.index[0]
                            val = top.iloc[0]
                            share = (val / local_max_sum) * 100
                            report.append(f"   🔥 Лидер по '{col}': {leader} ({share:.1f}% от листа)")
                    except: pass
        else:
            report.append("   (Денег не найдено)")

    report.append(f"\n💎 ИТОГО ПО ВСЕМУ ФАЙЛУ: {global_revenue:,.0f}")
    return "\n".join(report)

# --- ИНТЕРФЕЙС ---
if sheet_url:
    all_dfs, error = load_all_sheets(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success(f"✅ Загружено вкладок: {len(all_dfs)}")
        
        # Визуализация вкладок
        tabs = st.tabs(list(all_dfs.keys()))
        for i, (name, df) in enumerate(all_dfs.items()):
            with tabs[i]:
                st.dataframe(df.head(5))
        
        # Кнопка запуска
        if st.button("🚀 РАЗНЕСТИ ПО ФАКТАМ (AI)", type="primary"):
            if "OPENAI_API_KEY" in st.secrets:
                
                with st.status("🧠 Сопоставляю ваши слова с цифрами...", expanded=True) as status:
                    full_stats = analyze_structure(all_dfs)
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    
                    # --- ПРОМПТ С КОНТЕКСТОМ КЛИЕНТА ---
                    prompt = f"""
                    Ты — Жесткий Бизнес-Аудитор (Волк с Уолл-стрит).
                    
                    1. ЧТО ГОВОРИТ КЛИЕНТ (Контекст):
                    "{user_context}"
                    
                    2. ЧТО ГОВОРЯТ ЦИФРЫ (Факты из Python):
                    {full_stats}
                    
                    ТВОЯ ЗАДАЧА:
                    Сопоставь слова клиента с реальностью. 
                    
                    БЛОК 1: 🔮 ПРОВЕРКА НА ВШИВОСТЬ (Ванга)
                    Клиент утверждает одно, а цифры могут говорить другое.
                    - Если клиент пишет "Мы растем", а цифры падают — УНИЧТОЖЬ его фактами.
                    - Если он не дал контекст, сам определи, что это за бизнес по названиям листов.
                    
                    БЛОК 2: 💸 ГДЕ ДЕНЬГИ? (Pareto)
                    - Найди 20% усилий, которые дают 80% денег.
                    - Назови конкретные Имена/Города/Товары, которые тащят этот бизнес.
                    - Назови балласт (кто жрет ресурсы).
                    
                    БЛОК 3: 🚀 ПЛАН ДЕЙСТВИЙ
                    Дай 3 конкретных шага. Не "улучшить маркетинг", а "Уволить менеджера Х" или "Закрыть филиал Y".
                    
                    Стиль: Дерзкий, честный. Используй эмодзи.
                    """
                    
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    status.update(label="Готово!", state="complete", expanded=False)
                
                st.markdown("---")
                st.markdown(response.choices[0].message.content)
            else:
                st.error("Нет ключа API")
else:
    st.info("👈 Вставьте ссылку и опишите проблему.")