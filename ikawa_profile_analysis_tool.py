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
    """
    입력된 데이터를 기반으로 DataFrame의 모든 시간 관련 값을 동기화합니다.
    df: 동기화할 프로파일 DataFrame
    primary_input_mode: '시간 입력' 또는 '구간 입력'
    """
    # 마지막으로 유효한 데이터가 있는 행까지만 계산 대상으로 삼습니다.
    # 온도가 비어있지 않은 마지막 행의 인덱스를 찾습니다.
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None:
        return df # 데이터가 없으면 그대로 반환

    # 계산할 범위의 DataFrame을 슬라이싱합니다.
    calc_df = df.loc[0:last_valid_index].copy()

    if primary_input_mode == '시간 입력':
        # '분', '초' -> '누적 시간 (초)' 계산
        calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
        # '누적 시간 (초)' -> '구간 시간 (초)' 계산
        # .diff()는 행 간의 차이를 계산하는 함수입니다.
        calc_df['구간 시간 (초)'] = calc_df['누적 시간 (초)'].diff().fillna(0)

    elif primary_input_mode == '구간 입력':
        # '구간 시간 (초)' -> '누적 시간 (초)' 계산
        # .cumsum()은 누적 합계를 계산하는 함수입니다.
        calc_df['누적 시간 (초)'] = calc_df['구간 시간 (초)'].fillna(0).cumsum()
        # '누적 시간 (초)' -> '분', '초' 계산
        calc_df['분'] = (calc_df['누적 시간 (초)'] // 60).astype(int)
        calc_df['초'] = (calc_df['누적 시간 (초)'] % 60).astype(int)

    # 원본 DataFrame에 계산된 값을 다시 합칩니다.
    df.update(calc_df)
    return df

def parse_excel_data(text_data, mode):
    """
    텍스트 영역의 데이터를 파싱하여 DataFrame의 '온도' 및 시간 열을 업데이트합니다.
    """
    new_data = []
    lines = text_data.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip(): continue # 빈 줄은 건너뜀
        parts = line.split()
        
        row = {'Point': i}
        if mode == '시간 입력':
            if len(parts) >= 3: # 온도 분 초
                row['온도'] = float(parts[0])
                row['분'] = int(parts[1])
                row['초'] = int(parts[2])
            elif len(parts) == 1: # 첫 줄 온도만 있는 경우
                 row['온도'] = float(parts[0])
                 row['분'], row['초'] = 0, 0
        elif mode == '구간 입력':
            if len(parts) >= 2: # 온도 구간
                row['온도'] = float(parts[0])
                row['구간 시간 (초)'] = int(parts[1])
            elif len(parts) == 1: # 첫 줄 온도만 있는 경우
                row['온도'] = float(parts[0])
                row['구간 시간 (초)'] = 0
        new_data.append(row)

    if not new_data:
        return pd.DataFrame()

    return pd.DataFrame(new_data).set_index('Point')


# --- 앱 실행 로직 및 UI 구현 ---

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
        st.subheader("프로파일 이름")
        new_name = st.text_input("프로파일 이름 입력", value=current_name, key=f"name_input_{current_name}")
        # (이름 변경 로직은 생략)

        st.divider()

        st.subheader("데이터 입력")
        main_input_method = st.radio("입력 방식 선택", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        sub_input_method = st.radio("입력 방법", ("기본", "엑셀 데이터 붙여넣기"), key=f"sub_input_{current_name}", horizontal=True, label_visibility="collapsed")
        
        # '엑셀 데이터 붙여넣기' 모드일 때 사용할 텍스트 영역을 미리 정의합니다.
        text_area_content = ""
        if sub_input_method == "엑셀 데이터 붙여넣기":
            placeholder = "120 0 0\n140 0 40" if main_input_method == "시간 입력" else "120\n140 40"
            text_area_content = st.text_area("엑셀 데이터를 여기에 붙여넣으세요", height=250, placeholder=placeholder, key=f"textarea_{current_name}")
        else:
            # '기본' 입력 모드일 때 보여줄 데이터 에디터
            df_editor_key = f"editor_{main_input_method}_{current_name}"
            column_config = {}
            if main_input_method == "시간 입력":
                column_config = {
                    "Point": st.column_config.NumberColumn("번호", disabled=True),
                    "온도": st.column_config.NumberColumn("온도℃", format="%.1f"),
                    "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"),
                    "구간 시간 (초)": None, "누적 시간 (초)": None, "ROR (℃/sec)": None,
                }
            else: # 구간 입력
                column_config = {
                    "Point": st.column_config.NumberColumn("번호", disabled=True),
                    "온도": st.column_config.NumberColumn("온도℃", format="%.1f"),
                    "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"),
                    "분": None, "초": None, "누적 시간 (초)": None, "ROR (℃/sec)": None,
                }
            st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=df_editor_key, hide_index=True, num_rows="fixed")
        
        st.write("") # 간격
        
        # --- 액션 버튼 ---
        if st.button("🔄 데이터 입력/동기화", key=f"sync_button_{current_name}"):
            profile_df = st.session_state.profiles[current_name]
            
            # 1. '엑셀 붙여넣기' 모드인 경우, 텍스트를 파싱하여 DataFrame 업데이트
            if sub_input_method == "엑셀 데이터 붙여넣기" and text_area_content:
                parsed_df = parse_excel_data(text_area_content, main_input_method)
                # 기존 DataFrame을 클리어하고 파싱된 데이터로 채웁니다.
                empty_df = create_new_profile()
                empty_df.update(parsed_df)
                profile_df = empty_df

            # 2. 메인 동기화 함수 호출
            synced_df = sync_profile_data(profile_df, main_input_method)
            
            # 3. session_state에 최종 결과 저장
            st.session_state.profiles[current_name] = synced_df
            st.rerun()
