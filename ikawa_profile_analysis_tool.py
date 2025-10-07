# Ikawa Profile Analysis Tool (v9.5 Refactored for Performance)
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_plotly_events import plotly_events

# ==============================================================================
# 핵심 함수 (Core Functions)
# ==============================================================================

def create_profile_template():
    """프로파일의 기본 뼈대가 되는 DataFrame을 생성합니다."""
    return pd.DataFrame({
        '번호': range(21), '온도℃': [np.nan] * 21, '분': [np.nan] * 21,
        '초': [np.nan] * 21, '구간(초)': [np.nan] * 21, '누적(초)': [np.nan] * 21,
        'ROR(초당)': [np.nan] * 21, '이벤트': [''] * 21
    })

def process_profile_data(df: pd.DataFrame, main_input_method: str) -> pd.DataFrame:
    """단일 프로파일 DF를 받아 모든 시간/ROR 계산을 수행합니다."""
    processed_df = df.copy()
    cols_to_numeric = ['온도℃', '분', '초', '구간(초)']
    for col in cols_to_numeric:
        if col in processed_df.columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')

    valid_rows = processed_df.dropna(subset=['온도℃']).copy()
    if valid_rows.empty:
        return create_profile_template()
        
    valid_rows.reset_index(drop=True, inplace=True)
    valid_rows['번호'] = valid_rows.index

    if main_input_method == '시간 입력':
        valid_rows['분'] = valid_rows['분'].fillna(0)
        valid_rows['초'] = valid_rows['초'].fillna(0)
        total_seconds = valid_rows['분'] * 60 + valid_rows['초']
        valid_rows['구간(초)'] = total_seconds.diff()
        valid_rows['누적(초)'] = total_seconds
    else: # 구간 입력
        valid_rows['구간(초)'] = valid_rows['구간(초)'].fillna(0)
        total_seconds = valid_rows['구간(초)'].cumsum()
        valid_rows['분'] = (total_seconds // 60).astype('Int64')
        valid_rows['초'] = (total_seconds % 60).astype('Int64')
        valid_rows['누적(초)'] = total_seconds

    temp_diff = valid_rows['온도℃'].diff()
    time_diff = valid_rows['구간(초)']
    
    ror_per_sec = np.divide(temp_diff, time_diff, out=np.zeros_like(temp_diff, dtype=float), where=time_diff.fillna(0) != 0)
    valid_rows['ROR(초당)'] = pd.Series(ror_per_sec).fillna(0)
    
    final_df = create_profile_template()
    final_df = final_df.set_index('번호')
    final_df.update(valid_rows.set_index('번호'))
    return final_df.reset_index()

# ==============================================================================
# 상태(Session State) 초기화
# ==============================================================================
if 'profiles' not in st.session_state:
    st.session_state.profiles = { f"프로파일 {i+1}": create_profile_template() for i in range(3) }
if 'next_profile_num' not in st.session_state:
    st.session_state.next_profile_num = 4
if 'show_editor' not in st.session_state:
    st.session_state.show_editor = False
if 'active_profile_in_editor' not in st.session_state:
    st.session_state.active_profile_in_editor = None

# ==============================================================================
# 데이터 수정용 팝업(Dialog) 함수 (성능 개선)
# ==============================================================================
@st.dialog("프로파일 데이터 관리")
def profile_editor_dialog():
    st.markdown("#### 데이터 입력 및 수정")
    input_method = st.radio("입력 방식", ['시간 입력', '구간 입력'], key="dialog_input_method", horizontal=True)

    # --- REFACTOR: 탭 대신 셀렉트박스를 사용하여 한 번에 하나의 프로파일만 편집 ---
    profile_keys = list(st.session_state.profiles.keys())
    
    # 현재 활성화된 프로파일이 유효한지 확인합니다.
    if st.session_state.active_profile_in_editor not in profile_keys:
        st.session_state.active_profile_in_editor = profile_keys[0] if profile_keys else None

    if st.session_state.active_profile_in_editor:
        # 셀렉트박스의 상태를 session_state와 연결하여 제어합니다.
        st.selectbox(
            "수정할 프로파일 선택",
            options=profile_keys,
            key='active_profile_in_editor'
        )
        
        active_profile_name = st.session_state.active_profile_in_editor
        
        st.divider()
        
        sub_cols = st.columns([4, 1])
        with sub_cols[0]:
            new_name = st.text_input("프로파일 이름", value=active_profile_name, key=f"d_rename_{active_profile_name}")
        with sub_cols[1]:
            if st.button("🗑️ 삭제", key=f"d_delete_{active_profile_name}", use_container_width=True):
                del st.session_state.profiles[active_profile_name]
                st.session_state.active_profile_in_editor = None
                st.rerun()

        # 이름 변경을 실시간으로 처리합니다.
        if new_name != active_profile_name:
            if new_name in st.session_state.profiles:
                st.error("프로파일 이름이 중복될 수 없습니다.")
            else:
                st.session_state.profiles[new_name] = st.session_state.profiles.pop(active_profile_name)
                st.session_state.active_profile_in_editor = new_name
                st.rerun()
                
        column_config = { "번호": st.column_config.NumberColumn(disabled=True) }
        hidden_cols = ['누적(초)', 'ROR(초당)']
        if input_method == '시간 입력': hidden_cols.append("구간(초)")
        else: hidden_cols.extend(["분", "초"])
        for col in hidden_cols: column_config[col] = None
        
        # 데이터 에디터의 변경사항을 session_state에 실시간으로 반영합니다.
        edited_df = st.data_editor(
            st.session_state.profiles[active_profile_name], 
            key=f"d_editor_{active_profile_name}_{input_method}", 
            num_rows="dynamic",
            height=500,
            column_config=column_config
        )
        st.session_state.profiles[active_profile_name] = edited_df

    else:
        st.warning("프로파일이 없습니다. 먼저 프로파일을 추가해주세요.")

    st.divider()
    col1, col2, col3 = st.columns([2,2,1])
    with col1:
        if st.button("＋ 프로파일 추가", use_container_width=True):
            if len(st.session_state.profiles) < 10:
                new_name = f"프로파일 {st.session_state.next_profile_num}"
                st.session_state.profiles[new_name] = create_profile_template()
                st.session_state.next_profile_num += 1
                st.session_state.active_profile_in_editor = new_name
                st.rerun()
            else:
                st.warning("최대 10개까지만 추가할 수 있습니다.")

    with col2:
        if st.button("✅ 계산하고 닫기", type="primary", use_container_width=True):
            with st.spinner("데이터 처리 중..."):
                calculated_profiles = {}
                for name, df in st.session_state.profiles.items():
                    calculated_profiles[name] = process_profile_data(df, input_method)
                st.session_state.profiles = calculated_profiles
                
            st.success("데이터 계산 완료!")
            st.session_state.show_editor = False
            st.rerun()
            
    with col3:
        if st.button("❌ 닫기", use_container_width=True):
            st.session_state.show_editor = False
            st.rerun()

# ==============================================================================
# 메인 UI 렌더링
# ==============================================================================
st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v9.5")
st.title("☕ 이카와 로스팅 프로파일 계산 툴 v9.5 (성능 개선)")

st.info("아래 '프로파일 데이터 관리' 버튼을 눌러 데이터를 수정하세요.")

if st.button("📝 프로파일 데이터 관리", use_container_width=True, type="primary"):
    st.session_state.show_editor = True
    st.rerun()

if st.session_state.show_editor:
    profile_editor_dialog()

# --- 사이드바 (그래프 표시 옵션) ---
with st.sidebar:
    st.header("그래프 보기 옵션")
    profile_keys = list(st.session_state.profiles.keys())
    selected_profiles = [name for name in profile_keys if st.checkbox(name, value=True, key=f"select_{name}")]
    st.divider()
    show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)
    st.checkbox("계산된 열 모두 보기 (팝업창에 적용)", key="show_hidden_cols")

# --- 그래프 및 분석 패널 ---
st.header("📊 그래프 및 분석")
col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    if not st.session_state.profiles or not selected_profiles:
        st.info("데이터를 입력하고 '계산하고 닫기' 버튼을 눌러주세요.")
    else:
        for i, name in enumerate(selected_profiles):
            if name in st.session_state.profiles:
                df_calc = st.session_state.profiles.get(name)
                color = colors[i % len(colors)]
                if df_calc is not None:
                    valid_points = df_calc.dropna(subset=['온도℃', '누적(초)'])
                    if not valid_points.empty:
                        fig.add_trace(go.Scatter(x=valid_points['누적(초)'], y=valid_points['온도℃'], name=f'{name} - 온도', mode='lines+markers', line=dict(color=color), marker=dict(size=8)))
                        if show_ror_graph:
                            fig.add_trace(go.Scatter(x=valid_points['누적(초)'], y=valid_points['ROR(초당)'], name=f'{name} - ROR', mode='lines+markers', line=dict(color=color, dash='dot'), yaxis='y2', marker=dict(size=8)))
    
    fig.update_layout(
        height=600, 
        xaxis=dict(title='시간 합계 (초)', range=[0, 360]), 
        yaxis=dict(title='온도 (°C)', range=[85, 235]), 
        yaxis2=dict(title='ROR(초당)', overlaying='y', side='right', range=[0, 0.75]), 
        legend=dict(x=0, y=1.1, orientation='h'),
        hovermode='x unified'
    )
    selected_points = plotly_events(fig, hover_event=True, key="graph_hover_events")

with col_info:
    last_hovered_time = selected_points[0]['x'] if selected_points else None
    display_hover_info(last_hovered_time, selected_profiles, st.session_state.profiles, colors)
