import streamlit as st
import pandas as pd
import numpy as np

# --- 2단계: 핵심 로직 및 데이터 구조 개발 (Backend) ---

if 'profiles' not in st.session_state:
    st.session_state.profiles = {}

def create_new_profile():
    points = list(range(21))
    data = {
        'Point': points,
        '온도': [np.nan]*len(points),
        '분': [np.nan]*len(points),
        '초': [np.nan]*len(points),
        '구간 시간 (초)': [np.nan]*len(points),
        '누적 시간 (초)': [np.nan]*len(points),
        'ROR (℃/sec)': [np.nan]*len(points),
    }
    df = pd.DataFrame(data)
    df.loc[0, ['분', '초', '구간 시간 (초)', '누적 시간 (초)']] = 0
    return df

def sync_profile_data(df, primary_input_mode):
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None:
        return df

    calc_df = df.loc[0:last_valid_index].copy()

    if primary_input_mode == '시간 입력':
        calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
        calc_df['구간 시간 (초)'] = calc_df['누적 시간 (초)'].diff().fillna(0)

    elif primary_input_mode == '구간 입력':
        calc_df['누적 시간 (초)'] = calc_df['구간 시간 (초)'].fillna(0).cumsum()
        calc_df['분'] = (calc_df['누적 시간 (초)'] // 60).astype(int)
        calc_df['초'] = (calc_df['누적 시간 (초)'] % 60).astype(int)

    df.update(calc_df)
    return df

def parse_excel_data(text_data, mode):
    new_data = []
    lines = text_data.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip(): continue
        parts = line.split()
        
        row = {'Point': i}
        if mode == '시간 입력':
            if len(parts) >= 3:
                row['온도'] = float(parts[0])
                row['분'] = int(parts[1])
                row['초'] = int(parts[2])
            elif len(parts) == 1:
                 row['온도'] = float(parts[0])
                 row['분'], row['초'] = 0, 0
        elif mode == '구간 입력':
            if len(parts) >= 2:
                row['온도'] = float(parts[0])
                row['구간 시간 (초)'] = int(parts[1])
            elif len(parts) == 1:
                row['온도'] = float(parts[0])
                row['구간 시간 (초)'] = 0
        new_data.append(row)

    if not new_data:
        return pd.DataFrame()

    return pd.DataFrame(new_data).set_index('Point')

# --- 앱 실행 로직 및 UI 구현 ---

st.set_page_config(layout="wide")
st.title('☕ Ikawa Profile Analysis Tool')

if 'profiles' not in st.session_state or not st.session_state.profiles:
    st.session_state.profiles = {
        '프로파일 1': create_new_profile(),
        '프로파일 2': create_new_profile(),
        '프로파일 3': create_new_profile()
    }

profile_names = list(st.session_state.profiles.keys())
# st.tabs 대신 st.columns를 사용하여 각 프로파일을 수직 열에 배치합니다.
cols = st.columns(len(profile_names))

for i, col in enumerate(cols):
    current_name = profile_names[i]
    with col:
        # --- 프로파일 이름 변경 UI ---
        st.subheader(f"📄 {current_name}")
        new_name = st.text_input("프로파일 이름 수정", value=current_name, key=f"name_input_{current_name}")
        if new_name != current_name:
            if new_name in st.session_state.profiles:
                st.error("이름 중복!")
            elif not new_name:
                st.error("이름은 비워둘 수 없습니다.")
            else:
                new_profiles = {new_name if name == current_name else name: df for name, df in st.session_state.profiles.items()}
                st.session_state.profiles = new_profiles
                st.rerun()

        st.divider()

        # --- 데이터 입력 UI ---
        st.subheader("데이터 입력")
        main_input_method = st.radio("입력 방식", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        sub_input_method = st.radio("입력 방법", ("기본", "엑셀 붙여넣기"), key=f"sub_input_{current_name}", horizontal=True, label_visibility="collapsed")
        
        text_area_content = ""
        if sub_input_method == "엑셀 데이터 붙여넣기":
            placeholder = "120 0 0\n140 0 40" if main_input_method == "시간 입력" else "120\n140 40"
            text_area_content = st.text_area("엑셀 데이터 붙여넣기", height=250, placeholder=placeholder, key=f"textarea_{current_name}", label_visibility="collapsed")
        else:
            df_editor_key = f"editor_{main_input_method}_{current_name}"
            column_config = {}
            if main_input_method == "시간 입력":
                column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "구간 시간 (초)": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            else:
                column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"), "분": None, "초": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=df_editor_key, hide_index=True, num_rows="fixed")
        
        st.write("")
        
        if st.button("🔄 데이터 입력/동기화", key=f"sync_button_{current_name}"):
            profile_df = st.session_state.profiles[current_name].copy()
            if sub_input_method == "엑셀 데이터 붙여넣기" and text_area_content:
                parsed_df = parse_excel_data(text_area_content, main_input_method)
                empty_df = create_new_profile()
                empty_df.update(parsed_df)
                profile_df = empty_df
            
            synced_df = sync_profile_data(profile_df, main_input_method)
            st.session_state.profiles[current_name] = synced_df
            st.rerun()
