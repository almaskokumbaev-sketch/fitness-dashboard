import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import toml

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Business Killer", layout="centered", page_icon="🦁")
st.title("🦁 AI-Разнос Бизнеса (Hardcore Mode)")
st.markdown("### Кидай ссылку. Будет больно, но полезно.")

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

# --- 🧠 MATH ENGINE (Считаем то, что скрыто) ---
def deep_analyze_data(df):
    report = []
    money_col = None
    max_sum = 0
    cat_cols = []
    
    report.append(f"INFO: Строк {len(df)}, Колонок {len(df.columns)}")
    report.append(f"COLUMNS: {', '.join(df.columns)}") # Для Ванги

    # 1. ИЩЕМ ДЕНЬГИ И КАТЕГОРИИ
    for col in df.columns:
        # Числа
        try:
            numeric = pd.to_numeric(df[col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').dropna()
            if not numeric.empty and len(numeric) > len(df) * 0.1:
                total = numeric.sum()
                avg = numeric.mean()
                if total > max_sum:
                    max_sum = total
                    money_col = col
                report.append(f"NUM '{col}': Total={total:,.0f}, Avg={avg:,.0f}")
        except: pass

        # Категории
        if df[col].nunique() < 100 and df[col].nunique() > 1:
            cat_cols.append(col)

    # 2. КРОСС-АНАЛИЗ (PARETO)
    if money_col and cat_cols:
        report.append(f"\n--- АНАЛИЗ ДЕНЕГ (База: {money_col}) ---")
        
        df[money_col] = pd.to_numeric(df[money_col].astype(str).str.replace(r'[^\d.-]', '', regex=True), errors='coerce').fillna(0)
        total_revenue = df[money_col].sum()
        
        for cat in cat_cols:
            if df[cat].nunique() > 20: continue # Пропускаем имена клиентов
            
            grouped = df.groupby(cat)[money_col].agg(['sum', 'count', 'mean'])
            grouped = grouped.sort_values(by='sum', ascending=False)
            
            # Топ-1 Лидер
            top_name = grouped.index[0]
            top_val = grouped.iloc[0]['sum']
            top_share = (top_val / total_revenue) * 100
            
            # Средний чек лидера vs Средний чек остальных
            avg_check_leader = grouped.iloc[0]['mean']
            avg_check_rest = grouped.iloc[1:]['mean'].mean() if len(grouped) > 1 else 0
            
            report.append(f"CATEGORY '{cat}':")
            report.append(f"   - Лидер: {top_name} (держит {top_share:.1f}% всей кассы)")
            
            if avg_check_rest > 0:
                multiplier = avg_check_leader / avg_check_rest
                if multiplier > 1.2:
                    report.append(f"   - ИНСАЙТ: У {top_name} средний чек в {multiplier:.1f}x выше, чем у остальных! ({avg_check_leader:,.0f} vs {avg_check_rest:,.0f})")
                elif multiplier < 0.8:
                    report.append(f"   - АНОМАЛИЯ: {top_name} делает кассу объемом, но продает дешево (чек ниже рынка).")

    return "\n".join(report)

# --- ИНТЕРФЕЙС ---
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error(f"Ошибка: {error}")
    else:
        st.success("✅ Данные захвачены.")
        
        if st.button("🔥 РАЗНЕСТИ ПО ФАКТАМ (AI)", type="primary"):
            if "OPENAI_API_KEY" in st.secrets:
                
                with st.status("💀 Вскрываю подноготную...", expanded=True) as status:
                    stats = deep_analyze_data(df)
                    st.code(stats) # Показываем математику (для доверия)
                    
                    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
                    
                    # --- ПРОМПТ: ВОЛК С УОЛЛ-СТРИТ ---
                    prompt = f"""
                    Роль: Ты — Дерзкий, Циничный и Гениальный Бизнес-Аудитор (как Гордон Рамзи или Волк с Уолл-стрит).
                    Ты ненавидишь воду. Ты любишь деньги и эффективность.
                    Твоя цель — дать клиенту пощечину правдой, чтобы он начал зарабатывать.
                    
                    ВХОДНЫЕ ДАННЫЕ (Python посчитал математику):
                    {stats}
                    
                    ТВОЯ ЗАДАЧА (СТРОГО ПО ПУНКТАМ):

                    1. 🔮 ЭФФЕКТ ВАНГИ (Профайлинг)
                    Посмотри на названия колонок и структуру.
                    Напиши: "Я просканировал таблицу. Судя по колонкам [Названия], вы занимаетесь [Вид бизнеса]. Похоже на [Детали]."
                    (Удиви его точностью).

                    2. 💥 РАЗНОС (Инсайты 10/10)
                    Ищи перекосы в цифрах.
                    - Если кто-то делает 50%+ кассы: "У вас бизнес одного актера. Если [Имя] уйдет, вы закроетесь."
                    - Если есть высокий средний чек: "Посмотрите на [Имя/Город]. Они продают ДОРОГО. Почему остальные продают дешевку? Клонируйте лидера!"
                    - Если много записей, но мало денег: "Много суеты, мало выхлопа. Вы работаете в холостую."
                    
                    Пиши жестко: "Хватит сливать бюджет", "Увольте лентяев", "Поднимите цены".
                    Используй жирный шрифт и эмодзи.

                    3. 💸 ГДЕ ДЕНЬГИ (Opportunity)
                    Скажи, чего не хватает для полного счастья.
                    "Ты показал мне Доходы, но скрыл Расходы. Боишься увидеть убытки? Добавь колонку 'Маржа', и я найду, где ты теряешь миллионы."
                    """
                    
                    response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user", "content":prompt}])
                    status.update(label="Готово!", state="complete", expanded=False)
                
                st.markdown("---")
                st.markdown(response.choices[0].message.content)
                
            else:
                st.error("Нет ключа API")
else:
    st.info("👈 Вставь ссылку. Не бойся правды.")