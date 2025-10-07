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
        '온도': [np.nan] * len(points),
        '분': [np.nan] * len(points),
        '초': [np.nan] * len(points),
        '구간 시간 (초)': [np.nan] * len(points),
        '누적 시간 (초)': [np.nan] * len(points),
        'ROR (℃/sec)': [np.nan] * len(points),
    }
    df = pd.DataFrame(data)
    df.loc[0, ['분', '초', '구간 시간 (초)', '누적 시간 (초)']] = 0
    return df

# --- 앱 실행 로직 및 3단계: Frontend 구현 ---

st.set_page_config(layout="wide")
st.title('☕ Ikawa Profile Analysis Tool')

if not st.session_state.profiles:
    st.session_state.profiles['프로파일 1'] = create_new_profile()
    st.session_state.profiles['프로파일 2'] = create_new_profile()
    st.session_state.profiles['프로파일 3'] = create_new_profile()

profile_names = list(st.session_state.profiles.keys())
profile_tabs = st.tabs(profile_names)

for i, tab in enumerate(profile_tabs):
    current_name = profile_names[i]
    with tab:
        # --- 프로파일 이름 변경 UI ---
        st.subheader("프로파일 이름")
        new_name = st.text_input("프로파일 이름 입력", value=current_name, key=f"name_input_{current_name}")
        if new_name != current_name:
            if new_name in st.session_state.profiles:
                st.error("오류: 동일한 프로파일 이름이 이미 존재합니다.")
            elif not new_name:
                st.error("오류: 프로파일 이름은 비워둘 수 없습니다.")
            else:
                new_profiles = {new_name if name == current_name else name: df for name, df in st.session_state.profiles.items()}
                st.session_state.profiles = new_profiles
                st.rerun()

        st.divider() # 구분선 추가

        # --- 데이터 입력 UI ---
        st.subheader("데이터 입력")
        
        main_input_method = st.radio(
            "입력 방식 선택", 
            ("시간 입력", "구간 입력"), 
            key=f"main_input_{current_name}",
            horizontal=True
        )

        sub_input_method = st.radio(
            "입력 방법",
            ("기본", "엑셀 데이터 붙여넣기"),
            key=f"sub_input_{current_name}",
            horizontal=True
        )

        st.write("") 

        if main_input_method == "시간 입력":
            if sub_input_method == "기본":
                st.data_editor(
                    st.session_state.profiles[current_name],
                    column_config={
                        "Point": st.column_config.NumberColumn("번호", disabled=True),
                        "온도": st.column_config.NumberColumn("온도℃", format="%.1f"),
                        "분": st.column_config.NumberColumn("분"),
                        "초": st.column_config.NumberColumn("초"),
                        "구간 시간 (초)": None,
                        "누적 시간 (초)": None,
                        "ROR (℃/sec)": None,
                    },
                    key=f"editor_time_{current_name}",
                    hide_index=True,
                    num_rows="dynamic"
                )
            else:
                st.text_area(
                    "엑셀 데이터를 여기에 붙여넣으세요 (온도 분 초)",
                    height=250,
                    placeholder="120 0 0\n140 0 40\n160 1 23",
                    key=f"textarea_time_{current_name}"
                )

        elif main_input_method == "구간 입력":
            if sub_input_method == "기본":
                st.data_editor(
                    st.session_state.profiles[current_name],
                    column_config={
                        "Point": st.column_config.NumberColumn("번호", disabled=True),
                        "온도": st.column_config.NumberColumn("온도℃", format="%.1f"),
                        "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"),
                        "분": None,
                        "초": None,
                        "누적 시간 (초)": None,
                        "ROR (℃/sec)": None,
                    },
                    key=f"editor_interval_{current_name}",
                    hide_index=True,
                    num_rows="dynamic"
                )
            else:
                st.text_area(
                    "엑셀 데이터를 여기에 붙여넣으세요 (온도 구간)",
                    height=250,
                    placeholder="120\n140 40\n160 43",
                    key=f"textarea_interval_{current_name}"
                )
