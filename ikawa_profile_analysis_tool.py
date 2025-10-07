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
    # 데이터프레임이 비어있는 경우를 대비
    if df['온도'].isnull().all():
        return df
        
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
            try:
                if len(parts) >= 3:
                    row['온도'], row['분'], row['초'] = float(parts[0]), int(parts[1]), int(parts[2])
                elif len(parts) == 1 and i == 0:
                     row['온도'], row['분'], row['초'] = float(parts[0]), 0, 0
                else: continue
            except (ValueError, IndexError): continue
        elif mode == '구간 입력':
            try:
                if len(parts) >= 2:
                    row['온도'], row['구간 시간 (초)'] = float(parts[0]), int(parts[1])
                elif len(parts) == 1 and i == 0:
                    row['온도'], row['구간 시간 (초)'] = float(parts[0]), 0
                else: continue
            except (ValueError, IndexError): continue
        new_data.append(row)

    if not new_data: return pd.DataFrame()
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
cols = st.columns(len(profile_names))

for i, col in enumerate(cols):
    current_name = profile_names[i]
    with col:
        st.subheader(f"📄 {current_name}")
        # (이름 변경 로직 생략)

        st.divider()

        st.subheader("데이터 입력")
        main_input_method = st.radio("입력 방식", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        sub_input_method = st.radio("입력 방법", ("기본", "엑셀 붙여넣기"), key=f"sub_input_{current_name}", horizontal=True, label_visibility="collapsed")
        
        # 데이터 입력을 받을 변수 초기화
        edited_df = None
        text_area_content = ""

        if sub_input_method == "엑셀 데이터 붙여넣기":
            placeholder = "120 0 0\n140 0 40" if main_input_method == "시간 입력" else "120\n140 40"
            text_area_content = st.text_area("엑셀 데이터 붙여넣기", height=250, placeholder=placeholder, key=f"textarea_{current_name}", label_visibility="collapsed")
        else: # '기본' 입력 모드
            df_editor_key = f"editor_{main_input_method}_{current_name}"
            column_config = {}
            if main_input_method == "시간 입력":
                column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "구간 시간 (초)": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            else: # 구간 입력
                column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"), "분": None, "초": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            
            # st.data_editor에서 반환된 수정본을 edited_df에 저장합니다. 이것이 핵심 수정사항입니다.
            edited_df = st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=df_editor_key, hide_index=True, num_rows="fixed")
        
        st.write("")
        
        if st.button("🔄 데이터 입력/동기화", key=f"sync_button_{current_name}"):
            # '기본' 모드일 경우, 위에서 받은 수정본(edited_df)을 사용합니다.
            if sub_input_method == "기본":
                profile_df_to_sync = edited_df
            # '엑셀' 모드일 경우, 텍스트를 파싱해서 완전히 새로운 df를 만듭니다.
            elif sub_input_method == "엑셀 데이터 붙여넣기" and text_area_content:
                parsed_df = parse_excel_data(text_area_content, main_input_method)
                profile_df_to_sync = create_new_profile()
                profile_df_to_sync.update(parsed_df)
            # 아무 데이터도 없을 경우, 기존 데이터를 그대로 사용
            else:
                profile_df_to_sync = st.session_state.profiles[current_name]

            synced_df = sync_profile_data(profile_df_to_sync, main_input_method)
            st.session_state.profiles[current_name] = synced_df
            st.rerun()
