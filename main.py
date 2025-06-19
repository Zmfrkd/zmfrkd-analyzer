
import streamlit as st
import pandas as pd
import pdfplumber
from io import BytesIO
from datetime import datetime
import requests 
from bs4 import BeautifulSoup

st.set_page_config(page_title="ZMFRKD: Анализ банковских выписок", layout="wide")
st.info("Загрузите хотя бы один файл для начала анализа.")

# --- Подключение кастомного CSS ---
with open("custom_ui.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # Вставка SVG-фонов
st.markdown("""
<div class="background-icons">
<svg width="200" height="200" viewBox="0 0 24 24" fill="#ddf62b">
  <path d="M3 3h18v2H3zm0 4h10v2H3zm0 4h18v2H3zm0 4h10v2H3zm0 4h18v2H3z"/>
</svg>
<svg width="200" height="200" viewBox="0 0 24 24" fill="#ddf62b">
  <path d="M5 8h14v2H5zm0 4h10v2H5zm0 4h14v2H5z"/>
</svg>
</div>
""", unsafe_allow_html=True)

# --- Очистка денежных значений ---
def clean_money(val):
    try:
        if pd.isna(val): return 0.0
        return float(str(val).replace(" ", "").replace(",", "."))
    except:
        return 0.0

# --- Получение данных из ФНС ---
def get_fns_data(inn):
    try:
        API_KEY = "16705715af79b9eccb75157e077a059452f8fbb5"
        url = f"https://api-fns.ru/api/search?q={inn}&key={API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()

        if response.status_code != 200 or "items" not in data or not data["items"]:
            return {"error": "Контрагент не найден в ФНС"}

        item = data["items"][0]
        org = item.get("ЮЛ", {})  # 👈 ОБЯЗАТЕЛЬНО!

        return {
            "ИНН": org.get("ИНН", ""),
            "ОГРН": org.get("ОГРН", ""),
            "Наименование": org.get("НаимСокрЮЛ", ""),
            "Полное наименование": org.get("НаимПолнЮЛ", ""),
            "Адрес": org.get("АдресПолн", ""),
            "Дата регистрации": org.get("ДатаОГРН", ""),
            "Статус": org.get("Статус", ""),
            "Вид деятельности": org.get("ОснВидДеят", "")
        }

    except Exception as e:
        return {"error": f"Ошибка при обращении к API: {str(e)}"}

# --- Парсинг PDF-файлов ---
def parse_pdf(file):
    text_rows = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split("\n") if text else []
            for line in lines:
                if len(line.strip().split()) >= 4:
                    text_rows.append(line.strip().split())
    df = pd.DataFrame(text_rows)
    return df

# --- Загрузка интерфейса ---
st.title("ZMFRKD: Объединённый анализатор выписок")
st.markdown("Загрузите один или несколько файлов выписок (.xlsx, .xls, .csv, .pdf)")

uploaded_files = st.file_uploader("Выберите файлы", type=["xlsx", "xls", "csv", "pdf"], accept_multiple_files=True)
FIELDS = ["Дата", "ИНН контрагента", "Контрагент", "Назначение", "Дебет", "Кредит"]
all_normalized = []

# --- Загрузка и нормализация каждого файла ---
for uploaded_file in uploaded_files:
    try:
        st.markdown(f"### 📄 Обработка файла: {uploaded_file.name}")
        manual = st.checkbox("🔧 Ручная настройка колонок", key=f"manual_{uploaded_file.name}")
        filetype = uploaded_file.name.lower().split(".")[-1]

        if filetype == "pdf":
            df = parse_pdf(uploaded_file)
            df.columns = df.iloc[0]
            df = df.drop(index=0).reset_index(drop=True)
        else:
            preview_df = pd.read_excel(uploaded_file, header=None)
            header_row = preview_df[preview_df.apply(
                lambda row: row.astype(str).str.contains("дата|назначение|инн|контрагент", case=False).sum() >= 2,
                axis=1
            )].index.min()

            df = pd.read_excel(uploaded_file, header=header_row)
            df = df.dropna(how="all").loc[:, ~df.columns.duplicated()]
            df.columns = df.columns.map(str).str.strip()

        if manual:
            st.markdown("#### ⚙️ Настройка колонок вручную:")
            mapping = {}
            for key in FIELDS:
                options = [""] + list(df.columns)
                mapping[key] = st.selectbox(
                    f"{key} ({uploaded_file.name})",
                    options=options,
                    index=options.index(key) if key in options else 0,
                    key=f"{key}_{uploaded_file.name}"
                )
        else:
            mapping = {
                "Дата": "Дата операции",
                "ИНН контрагента": "ИНН/КИО.1",
                "Контрагент": "Наименование",
                "Назначение": "Назначение платежа",
                "Дебет": "По дебету (руб)",
                "Кредит": "По кредиту (руб)"
            }

        normalized_data = []
        for _, row in df.iterrows():
            try:
                normalized_row = {
                    "Дата": str(pd.to_datetime(row.get(mapping["Дата"], ""), errors="coerce").date()) if pd.notna(row.get(mapping["Дата"], "")) else "",
                    "ИНН контрагента": str(row.get(mapping["ИНН контрагента"], "")).strip(),
                    "Контрагент": str(row.get(mapping["Контрагент"], "")).strip(),
                    "Назначение": str(row.get(mapping["Назначение"], "")).strip(),
                    "Дебет": clean_money(row.get(mapping["Дебет"], "")),
                    "Кредит": clean_money(row.get(mapping["Кредит"], ""))
                }
                if all(normalized_row[f] not in ["", "None", "nan"] for f in ["Дата", "Контрагент", "ИНН контрагента"]):
                    normalized_data.append(normalized_row)
            except:
                continue

        normalized_df = pd.DataFrame(normalized_data)
        all_normalized.append(normalized_df)

    except Exception as e:
        st.error(f"❌ Ошибка при обработке файла {uploaded_file.name}: {str(e)}")
# --- Вывод объединённых данных ---
if all_normalized:
    combined_df = pd.concat(all_normalized, ignore_index=True)
    st.markdown("## 📊 Объединённые отнормированные данные:")
    st.dataframe(combined_df, use_container_width=True)

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        combined_df.to_excel(writer, index=False, sheet_name='Combined')
    excel_buffer.seek(0)
    st.download_button(
        label="📥 Скачать объединённые данные (.xlsx)",
        data=excel_buffer,
        file_name="объединенные_данные.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Фильтрация и аналитика ---
    st.markdown("## 📈 Фильтрация и аналитика:")
    col1, col2, col3 = st.columns(3)
    with col1:
        date_range = st.date_input("Выберите диапазон дат", [])
    with col2:
        inn_filter = st.text_input("Фильтр по ИНН")
    with col3:
        name_filter = st.text_input("Фильтр по названию контрагента")

    filtered_df = combined_df.copy()
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df["Дата"], errors="coerce") >= pd.to_datetime(start_date)) &
            (pd.to_datetime(filtered_df["Дата"], errors="coerce") <= pd.to_datetime(end_date))
        ]
    if inn_filter:
        filtered_df = filtered_df[filtered_df["ИНН контрагента"].astype(str).str.contains(inn_filter)]
    if name_filter:
        filtered_df = filtered_df[filtered_df["Контрагент"].astype(str).str.lower().str.contains(name_filter.lower())]

    st.metric("🧾 Количество операций", len(filtered_df))
    st.metric("💸 Сумма по дебету", f"{filtered_df['Дебет'].sum():,.2f}".replace(",", " "))
    st.metric("💰 Сумма по кредиту", f"{filtered_df['Кредит'].sum():,.2f}".replace(",", " "))

    filtered_excel = BytesIO()
    with pd.ExcelWriter(filtered_excel, engine='xlsxwriter') as writer:
        filtered_df.to_excel(writer, index=False, sheet_name='Filtered')
    filtered_excel.seek(0)
    st.download_button(
        label="📥 Скачать фильтрованные данные (.xlsx)",
        data=filtered_excel,
        file_name="фильтрованные_данные.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Краткая аналитика по контрагентам ---
    st.markdown("## 👥 Краткая аналитика по контрагентам:")
    group_df = filtered_df.groupby("ИНН контрагента").agg({
        "Контрагент": lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0],
        "Дата": "count",
        "Дебет": "sum",
        "Кредит": "sum"
    }).reset_index().rename(columns={"Дата": "Количество операций"})

    st.dataframe(group_df, use_container_width=True)

    group_excel = BytesIO()
    with pd.ExcelWriter(group_excel, engine='xlsxwriter') as writer:
        group_df.to_excel(writer, index=False, sheet_name='Контрагенты')
    group_excel.seek(0)
    st.download_button(
        label="📥 Скачать аналитику по контрагентам (.xlsx)",
        data=group_excel,
        file_name="аналитика_контрагенты.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Подробная аналитика по выбранному контрагенту ---
    st.markdown("## 🔍 Подробная информация по контрагенту:")
    selected_inn = st.selectbox("Выберите ИНН контрагента", group_df["ИНН контрагента"].unique())
    selected_df = filtered_df[filtered_df["ИНН контрагента"] == selected_inn]
    st.dataframe(selected_df, use_container_width=True)

    detail_excel = BytesIO()
    with pd.ExcelWriter(detail_excel, engine='xlsxwriter') as writer:
        selected_df.to_excel(writer, index=False, sheet_name='Операции по контрагенту')
    detail_excel.seek(0)
    st.download_button(
        label="📥 Скачать подробные операции (.xlsx)",
        data=detail_excel,
        file_name="операции_по_контрагенту.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- 🔍 Проверка контрагента по ИНН (ФНС + ссылки) ---
st.markdown("## 🔍 Проверка контрагента по ИНН")
input_inn = st.text_input("Введите ИНН контрагента")

if input_inn:
    data = get_fns_data(input_inn.strip())
    if "error" in data:
        st.error(f"❌ {data['error']}")
    else:
        st.success("✅ Найдено в ФНС")
        for key, value in data.items():
            st.markdown(f"**{key}:** {value}")

        # получаем ОГРН из ответа ФНС
        ogrn = data.get("ogrn", "").strip()

        st.markdown("### 🔗 Внешние источники")
        st.markdown(f"""
- 🟩 [Rusprofile](https://www.rusprofile.ru/search?query={input_inn})
- 📗 [Kontur.Focus](https://focus.kontur.ru/search?query={input_inn})
- 📕 [СПАРК](https://spark-interfax.ru/search?query={input_inn})
- 📘 [Casebook](https://casebook.ru/card/company/review/{ogrn})
- ⚖️ [КАД Арбитр](https://kad.arbitr.ru/Search/?q={input_inn})
""")


