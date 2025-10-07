# Ikawa Profile Analysis Tool (v10.0 Major Performance Rework)
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

def display_hover_info(hovered_time, selected_profiles, profiles_data, colors):
    """그래프 호버 시 분석 패널에 정보를 표시합니다."""
    st.markdown("#### 분석 정보")
    if hovered_time is None or not profiles_data or not selected_profiles:
        st.info("그래프 위에 마우스를 올리면 상세 정보가 표시됩니다.")
        return
        
    hover_sec = int(hovered_time)
    st.markdown(f"**{hover_sec // 60}분 {hover_sec % 60:02d}초 ({hover_sec}초)**")
    st.divider()

    for i, name in enumerate(selected_profiles):
        if name in profiles_data:
            df_calc = profiles_data.get(name)
            if df_calc is None or df_calc.empty: continue
            
            color = colors[i % len(colors)]
            valid_calc = df_calc.dropna(subset=['누적(초)'])
            segment_search = valid_calc[valid_calc['누적(초)'] <= hover_sec]
            if segment_search.empty: continue
            
            segment = segment_search.iloc[-1]
            st.markdown(
                f"<span style='color:{color};'>●</span> **{name}**: 포인트 {int(segment['번호'])} ({segment['온도℃']:.1f}℃) 구간 | "
                f"**ROR:** {segment['ROR(초당)']:.3f}℃/s", 
                unsafe_allow_html=True
            )

# ==============================================================================
# 상태(Session State) 초기화
# ==============================================================================
if 'profiles' not in st.session_state:
    st.session_state.profiles = { f"프로파일 {i+1}": create_profile_template() for i in range(3) }
if 'next_profile_num' not in st.session_state:
    st.session_state.next_profile_num = 4
if 'mode' not in st.session_state:
    st.session_state.mode = 'view' # 'view' 또는 'edit'
if 'active_profile_in_editor' not in st.session_state:
    st.session_state.active_profile_in_editor = None
if 'input_method' not in st.session_state:
    st.session_state.input_method = '시간 입력'

# ==============================================================================
# "수정 모드" UI 함수
# ==============================================================================
def edit_mode_ui():
    st.set_page_config(layout="centered", page_title="프로파일 수정 - 이카와 툴")
    st.title("✍️ 프로파일 데이터 수정")
    
    st.info("데이터 수정을 마친 후, '수정 완료' 버튼을 눌러 그래프를 확인하세요.")
    
    st.radio("입력 방식", ['시간 입력', '구간 입력'], key="input_method", horizontal=True)

    profile_keys = list(st.session_state.profiles.keys())
    if not profile_keys:
        st.warning("프로파일이 없습니다. 먼저 프로파일을 추가해주세요.")
    else:
        if st.session_state.active_profile_in_editor not in profile_keys:
            st.session_state.active_profile_in_editor = profile_keys[0]

        st.selectbox("수정할 프로파일 선택", options=profile_keys, key='active_profile_in_editor')
        active_name = st.session_state.active_profile_in_editor
        
        st.divider()
        
        sub_cols = st.columns([4, 1])
        with sub_cols[0]:
            new_name = st.text_input("프로파일 이름", value=active_name, key=f"rename_{active_name}")
        with sub_cols[1]:
            st.write(" ") # 공백으로 높이 맞춤
            if st.button("🗑️ 삭제", key=f"delete_{active_name}", use_container_width=True):
                del st.session_state.profiles[active_name]
                st.session_state.active_profile_in_editor = None
                st.rerun()

        if new_name != active_name:
            if new_name in st.session_state.profiles:
                st.error("프로파일 이름이 중복될 수 없습니다.")
            else:
                st.session_state.profiles[new_name] = st.session_state.profiles.pop(active_name)
                st.session_state.active_profile_in_editor = new_name
                st.rerun()

        column_config = { "번호": st.column_config.NumberColumn(disabled=True) }
        hidden_cols = ['누적(초)', 'ROR(초당)']
        if st.session_state.input_method == '시간 입력': hidden_cols.append("구간(초)")
        else: hidden_cols.extend(["분", "초"])
        for col in hidden_cols: column_config[col] = None
        
        edited_df = st.data_editor(
            st.session_state.profiles[active_name], 
            key=f"editor_{active_name}_{st.session_state.input_method}", 
            num_rows="dynamic", height=500, column_config=column_config
        )
        st.session_state.profiles[active_name] = edited_df

    st.divider()
    col1, col2 = st.columns(2)
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
        if st.button("✅ 수정 완료 및 그래프 보기", use_container_width=True, type="primary"):
            with st.spinner("데이터 처리 중..."):
                calculated_profiles = {}
                for name, df in st.session_state.profiles.items():
                    calculated_profiles[name] = process_profile_data(df, st.session_state.input_method)
                st.session_state.profiles = calculated_profiles
            st.session_state.mode = 'view'
            st.rerun()

# ==============================================================================
# "보기 모드" UI 함수
# ==============================================================================
def view_mode_ui():
    st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v10.0")
    st.title("☕ 이카와 로스팅 프로파일 계산 툴 v10.0 (대규모 성능 최적화)")

    st.info("그래프를 확인하고, 데이터를 수정하려면 아래 '프로파일 수정하기' 버튼을 누르세요.")
    if st.button("📝 프로파일 수정하기", use_container_width=True, type="primary"):
        st.session_state.mode = 'edit'
        if not st.session_state.active_profile_in_editor and st.session_state.profiles:
            st.session_state.active_profile_in_editor = list(st.session_state.profiles.keys())[0]
        st.rerun()

    with st.sidebar:
        st.header("그래프 보기 옵션")
        profile_keys = list(st.session_state.profiles.keys())
        selected_profiles = [name for name in profile_keys if st.checkbox(name, value=True, key=f"view_select_{name}")]
        st.divider()
        show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)

    st.header("📊 그래프 및 분석")
    col_graph, col_info = st.columns([3, 1])

    with col_graph:
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        if not st.session_state.profiles or not selected_profiles:
            st.info("표시할 프로파일이 없거나 선택되지 않았습니다. 사이드바에서 프로파일을 선택해주세요.")
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
        
        fig.update_layout(height=600, xaxis=dict(title='시간 합계 (초)'), yaxis=dict(title='온도 (°C)'), yaxis2=dict(title='ROR(초당)', overlaying='y', side='right', range=[0, 0.75]), legend=dict(x=0, y=1.1, orientation='h'), hovermode='x unified')
        selected_points = plotly_events(fig, hover_event=True, key="graph_hover_events")

    with col_info:
        last_hovered_time = selected_points[0]['x'] if selected_points else None
        display_hover_info(last_hovered_time, selected_profiles, st.session_state.profiles, colors)


# ==============================================================================
# 메인 실행 로직: 모드에 따라 다른 UI 함수를 호출
# ==============================================================================
if st.session_state.mode == 'view':
    view_mode_ui()
else:
    edit_mode_ui()
