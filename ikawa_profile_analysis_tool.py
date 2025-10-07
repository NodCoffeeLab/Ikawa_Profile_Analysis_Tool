import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 백엔드 함수 ---

def create_new_profile():
    points = list(range(21))
    data = {'Point': points, '온도': [np.nan]*len(points), '분': [np.nan]*len(points), '초': [np.nan]*len(points), '구간 시간 (초)': [np.nan]*len(points), '누적 시간 (초)': [np.nan]*len(points), 'ROR (℃/sec)': [np.nan]*len(points)}
    df = pd.DataFrame(data)
    df.loc[0, ['분', '초', '누적 시간 (초)']] = 0
    # 0번 행의 구간 시간은 다음 포인트를 위한 것이므로 비워두지 않습니다.
    return df

# --- 여기가 수정된 부분: 새로운 '구간' 계산 로직 ---
def sync_profile_data(df, primary_input_mode):
    if df['온도'].isnull().all(): return df
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()

    if primary_input_mode == '시간 입력':
        calc_df['누적 시간 (초)'] = calc_df['분'].fillna(0) * 60 + calc_df['초'].fillna(0)
        # 구간 시간 계산: 다음 포인트의 누적시간 - 현재 포인트의 누적시간
        calc_df['구간 시간 (초)'] = calc_df['누적 시간 (초)'].diff().shift(-1)

    elif primary_input_mode == '구간 입력':
        # 누적 시간 계산: 0번 행부터 입력된 구간 시간들의 누적 합
        calc_df['누적 시간 (초)'] = calc_df['구간 시간 (초)'].fillna(0).cumsum()
        # 0번 포인트의 누적 시간은 항상 0이므로, 계산된 값을 한 칸씩 아래로 내립니다.
        calc_df['누적 시간 (초)'] = calc_df['누적 시간 (초)'].shift(1).fillna(0)

        calc_df['분'] = (calc_df['누적 시간 (초)'] // 60).astype(int)
        calc_df['초'] = (calc_df['누적 시간 (초)'] % 60).astype(int)

    df.update(calc_df)
    return df

# --- parse_excel_data 및 calculate_ror 함수 (변경 없음) ---
def parse_excel_data(text_data, mode):
    new_data = []; lines = text_data.strip().split('\n')
    for i, line in enumerate(lines):
        if not line.strip(): continue
        parts = line.strip().split(); row = {'Point': i}
        try:
            if mode == '시간 입력':
                if len(parts) >= 3: row['온도'], row['분'], row['초'] = float(parts[0]), int(parts[1]), int(parts[2])
                elif len(parts) >= 1: row['온도'], row['분'], row['초'] = float(parts[0]), 0, 0
                else: continue
            elif mode == '구간 입력':
                if len(parts) >= 2: row['온도'], row['구간 시간 (초)'] = float(parts[0]), int(parts[1])
                elif len(parts) >= 1: row['온도'], row['구간 시간 (초)'] = float(parts[0]), 0
                else: continue
            new_data.append(row)
        except (ValueError, IndexError): continue
    if not new_data: return pd.DataFrame()
    return pd.DataFrame(new_data).set_index('Point')

def calculate_ror(df):
    if df['온도'].isnull().all(): return df
    last_valid_index = df['온도'].last_valid_index()
    if last_valid_index is None: return df
    calc_df = df.loc[0:last_valid_index].copy()
    delta_temp = calc_df['온도'].diff()
    delta_time = calc_df['누적 시간 (초)'].diff()
    ror = (delta_temp / delta_time).replace([np.inf, -np.inf], 0).fillna(0)
    calc_df['ROR (℃/sec)'] = ror
    df.update(calc_df)
    return df

# --- UI 및 앱 실행 로직 ---
st.set_page_config(layout="wide")
st.title('☕ Ikawa Profile Analysis Tool')

if 'profiles' not in st.session_state or not st.session_state.profiles:
    st.session_state.profiles = {'프로파일 1': create_new_profile(), '프로파일 2': create_new_profile(), '프로파일 3': create_new_profile()}
if 'processed_profiles' not in st.session_state: st.session_state.processed_profiles = None
if 'graph_button_enabled' not in st.session_state: st.session_state.graph_button_enabled = False

st.subheader("프로파일 관리");
if len(st.session_state.profiles) < 10:
    if st.button("＋ 새 프로파일 추가"):
        existing_nums = [int(name.split(' ')[1]) for name in st.session_state.profiles.keys() if name.startswith("프로파일 ") and name.split(' ')[1].isdigit()]
        new_profile_num = max(existing_nums) + 1 if existing_nums else 1
        st.session_state.profiles[f"프로파일 {new_profile_num}"] = create_new_profile()
        st.rerun()
else: st.warning("최대 10개의 프로파일까지 추가할 수 있습니다.")
st.divider()

profile_names = list(st.session_state.profiles.keys())
cols = st.columns(len(profile_names))
for i, col in enumerate(cols):
    # (데이터 입력 UI 로직: 이전과 거의 동일)
    current_name = profile_names[i]
    with col:
        col1, col2 = st.columns([0.8, 0.2]);
        with col1: new_name = st.text_input("프로파일 이름", value=current_name, key=f"name_input_{current_name}", label_visibility="collapsed")
        with col2:
            if st.button("삭제", key=f"delete_button_{current_name}"): del st.session_state.profiles[current_name]; st.rerun()
        if new_name != current_name:
            if new_name in st.session_state.profiles: st.error("이름 중복!")
            elif not new_name: st.error("이름은 비워둘 수 없습니다.")
            else:
                new_profiles = {new_name if name == current_name else name: df for name, df in st.session_state.profiles.items()}; st.session_state.profiles = new_profiles; st.rerun()
        st.divider()
        st.subheader("데이터 입력")
        main_input_method = st.radio("입력 방식", ("시간 입력", "구간 입력"), key=f"main_input_{current_name}", horizontal=True)
        sub_input_method = st.radio("입력 방법", ("기본", "엑셀 데이터 붙여넣기"), key=f"sub_input_{current_name}", horizontal=True)
        if main_input_method == "구간 입력" and sub_input_method == "기본":
             st.info("구간(초): 현재 포인트에서 다음 포인트까지 걸릴 시간") # 안내 문구 수정
        edited_df = st.session_state.profiles[current_name]
        text_area_content = ""
        if sub_input_method == "엑셀 데이터 붙여넣기":
            placeholder = "120 0 0\n..." if main_input_method == "시간 입력" else "120 40\n140 43\n..." # 구간 입력 예시 수정
            text_area_content = st.text_area("엑셀 데이터 붙여넣기", height=250, placeholder=placeholder, key=f"textarea_{current_name}", label_visibility="collapsed")
        else:
            df_editor_key = f"editor_{main_input_method}_{current_name}"; column_config = {}
            if main_input_method == "시간 입력": column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "분": st.column_config.NumberColumn("분"), "초": st.column_config.NumberColumn("초"), "구간 시간 (초)": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            else: column_config = { "Point": st.column_config.NumberColumn("번호", disabled=True), "온도": st.column_config.NumberColumn("온도℃", format="%.1f"), "구간 시간 (초)": st.column_config.NumberColumn("구간(초)"), "분": None, "초": None, "누적 시간 (초)": None, "ROR (℃/sec)": None, }
            edited_df = st.data_editor(st.session_state.profiles[current_name], column_config=column_config, key=df_editor_key, hide_index=True, num_rows="fixed")
        st.write("")
        if st.button("🔄 데이터 입력/동기화", key=f"sync_button_{current_name}"):
            profile_df_to_sync = None
            if sub_input_method == "기본": profile_df_to_sync = edited_df
            elif sub_input_method == "엑셀 데이터 붙여넣기" and text_area_content:
                parsed_df = parse_excel_data(text_area_content, main_input_method); profile_df_to_sync = create_new_profile(); profile_df_to_sync.update(parsed_df)
            if profile_df_to_sync is not None:
                synced_df = sync_profile_data(profile_df_to_sync, main_input_method); st.session_state.profiles[current_name] = synced_df; st.session_state.graph_button_enabled = True; st.rerun()
st.divider()

# --- 그래프 및 분석 패널 UI (슬라이더 적용) ---
st.header("📈 그래프 및 분석")
if st.button("📊 그래프 업데이트", disabled=not st.session_state.graph_button_enabled):
    st.session_state.processed_profiles = {name: calculate_ror(df.copy()) for name, df in st.session_state.profiles.items()}
    st.session_state.selected_time = 0.0 # 그래프 업데이트 시 슬라이더 초기화

if st.session_state.processed_profiles:
    graph_col, analysis_col = st.columns([0.7, 0.3])
    max_time = max(df['누적 시간 (초)'].max() for df in st.session_state.processed_profiles.values() if not df.empty) if st.session_state.processed_profiles else 1

    with graph_col:
        fig = go.Figure()
        for name, df in st.session_state.processed_profiles.items():
            valid_df = df.dropna(subset=['누적 시간 (초)', '온도'])
            if not valid_df.empty:
                fig.add_trace(go.Scatter(x=valid_df['누적 시간 (초)'], y=valid_df['온도'], mode='lines+markers', name=name, yaxis='y1'))
                fig.add_trace(go.Scatter(x=valid_df['ROR (℃/sec)'], y=valid_df['온도'], mode='lines', name=f'{name} ROR', yaxis='y2', line=dict(dash='dot')))
        fig.update_layout(xaxis_title='시간 (초)', yaxis_title='온도 (°C)', yaxis=dict(range=[85, 235]), yaxis2=dict(title='ROR (℃/sec)', overlaying='y', side='right', range=[0, 0.75]), xaxis=dict(range=[0, 360]), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        
        # 슬라이더에서 선택된 시간에 맞춰 세로선을 추가
        if 'selected_time' in st.session_state:
            fig.add_vline(x=st.session_state.selected_time, line_width=1, line_dash="dash", line_color="grey")
        st.plotly_chart(fig, use_container_width=True)

    with analysis_col:
        st.subheader("🔍 분석 정보"); st.markdown("---")
        st.write("**총 로스팅 시간**")
        for name, df in st.session_state.processed_profiles.items():
            valid_df = df.dropna(subset=['누적 시간 (초)'])
            if not valid_df.empty:
                total_time = valid_df['누적 시간 (초)'].max()
                time_str = f"{int(total_time // 60)}분 {int(total_time % 60)}초"
                # Markdown을 사용해 폰트 크기 키우기
                st.markdown(f"**{name}**: <span style='font-size: 1.2em;'>{time_str}</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        # --- 타임라인 슬라이더 ---
        st.session_state.selected_time = st.slider("시간 선택 (초)", 0.0, max_time, st.session_state.get('selected_time', 0.0), 0.1)
        
        st.write("**실시간 상세 정보**")
        selected_time = st.session_state.selected_time
        st.metric(label="선택된 시간", value=f"{int(selected_time // 60)}분 {int(selected_time % 60):02d}초 ({selected_time:.1f}초)")
        for name, df in st.session_state.processed_profiles.items():
            valid_df = df.dropna(subset=['누적 시간 (초)', '온도', 'ROR (℃/sec)'])
            if not valid_df.empty and len(valid_df) > 1:
                hover_temp = np.interp(selected_time, valid_df['누적 시간 (초)'], valid_df['온도']); hover_ror = np.interp(selected_time, valid_df['누적 시간 (초)'], valid_df['ROR (℃/sec)'])
                st.write(f"**{name}**"); st.text(f"  - 온도: {hover_temp:.1f}℃"); st.text(f"  - ROR: {hover_ror:.3f}℃/sec")
