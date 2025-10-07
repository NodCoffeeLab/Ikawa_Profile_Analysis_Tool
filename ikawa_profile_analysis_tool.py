# Ikawa Profile Analysis Tool (v9.1 Refactored)
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

    # '온도' 열에 유효한 값이 있는 행만 남깁니다.
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
    else: # 구간 입력
        valid_rows['구간(초)'] = valid_rows['구간(초)'].fillna(0)
        total_seconds = valid_rows['구간(초)'].cumsum()
        valid_rows['분'] = (total_seconds // 60).astype('Int64')
        valid_rows['초'] = (total_seconds % 60).astype('Int64')

    valid_rows['누적(초)'] = valid_rows['구간(초)'].cumsum()
    temp_diff = valid_rows['온도℃'].diff()
    time_diff = valid_rows['구간(초)']
    
    # ROR 계산 (0으로 나누기 방지)
    ror_per_sec = np.divide(temp_diff, time_diff, out=np.zeros_like(temp_diff, dtype=float), where=time_diff.fillna(0) != 0)
    valid_rows['ROR(초당)'] = pd.Series(ror_per_sec).fillna(0)
    
    # 최종 DataFrame을 템플릿에 합치기
    final_df = create_profile_template()
    # update()는 인덱스 기준으로 동작하므로, 번호(인덱스)가 맞는 위치에 데이터가 들어감
    final_df.update(valid_rows.set_index('번호')) 
    # 번호 열을 다시 리셋하여 일반 컬럼으로 만듦
    return final_df.reset_index().rename(columns={'index': '번호'})


def display_hover_info(hovered_time, selected_profiles, profiles_data, colors):
    """그래프 호버 시 분석 패널에 정보를 표시합니다."""
    st.markdown("#### 분석 정보")
    if hovered_time is None or not profiles_data:
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
            
            # 호버된 시간 바로 이전의 데이터 포인트를 찾습니다.
            valid_calc = df_calc.dropna(subset=['누적(초)'])
            current_segment_search = valid_calc[valid_calc['누적(초)'] <= hover_sec]
            if current_segment_search.empty: continue
            
            current_segment = current_segment_search.iloc[-1]
            
            current_ror = current_segment['ROR(초당)']
            current_temp = current_segment['온도℃']
            point_num = current_segment['번호']

            st.markdown(f"<span style='color:{color};'>●</span> **{name}**: 포인트 {int(point_num)} ({current_temp:.1f}℃) 구간의 ROR은 초당 {current_ror:.3f}℃ 입니다.", unsafe_allow_html=True)

# ==============================================================================
# 상태(Session State) 초기화
# ==============================================================================
if 'profiles' not in st.session_state:
    st.session_state.profiles = { f"프로파일 {i+1}": create_profile_template() for i in range(3) }
if 'main_input_method' not in st.session_state:
    st.session_state.main_input_method = '시간 입력'
if 'show_hidden_cols' not in st.session_state:
    st.session_state.show_hidden_cols = False
if 'next_profile_num' not in st.session_state:
    st.session_state.next_profile_num = 4

# ==============================================================================
# UI 렌더링
# ==============================================================================
st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v9.1")
st.title("☕ 이카와 로스팅 프로파일 계산 툴 v9.1 (성능 개선)")

with st.sidebar:
    st.header("③ 보기 옵션")
    selected_profiles = [name for name in st.session_state.profiles.keys() if st.checkbox(name, value=True, key=f"select_{name}")]
    st.divider()
    show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)
    st.checkbox("계산된 열 모두 보기", key="show_hidden_cols")
    st.divider()
    if st.button("＋ 프로파일 추가"):
        if len(st.session_state.profiles) < 10:
            new_name = f"프로파일 {st.session_state.next_profile_num}"
            st.session_state.profiles[new_name] = create_profile_template()
            st.session_state.next_profile_num += 1
            st.rerun()
        else:
            st.warning("최대 10개의 프로파일만 추가할 수 있습니다.")

st.header("① 데이터 입력")
st.radio("입력 방식", ['시간 입력', '구간 입력'], horizontal=True, key="main_input_method", label_visibility="collapsed")

# --- REFACTORED: `st.form` 제거 및 단일 버튼으로 통합 ---
st.header("② 계산 및 그래프 업데이트")
update_button = st.button("🔄 계산 및 그래프 업데이트", use_container_width=True, type="primary")

profile_cols = st.columns(len(st.session_state.profiles))
edited_data = {}

for i, name in enumerate(st.session_state.profiles.keys()):
    with profile_cols[i]:
        edited_data[name] = {}
        edited_data[name]['new_name'] = st.text_input("프로파일 이름", value=name, key=f"rename_{name}")
        
        column_config = { "번호": st.column_config.NumberColumn(disabled=True) }
        if not st.session_state.show_hidden_cols:
            hidden_cols = ['누적(초)', 'ROR(초당)']
            if st.session_state.main_input_method == '시간 입력': hidden_cols.append("구간(초)")
            else: hidden_cols.extend(["분", "초"])
            for col in hidden_cols: column_config[col] = None
        
        edited_data[name]['table'] = st.data_editor(
            st.session_state.profiles[name], 
            key=f"editor_{name}", 
            num_rows="dynamic", 
            column_config=column_config
        )

# --- REFACTORED: 버튼 클릭 시에만 데이터 처리 ---
if update_button:
    with st.spinner("데이터 처리 및 그래프 생성 중..."):
        # 이름 변경 처리
        new_names = {name: data['new_name'] for name, data in edited_data.items()}
        if len(set(new_names.values())) < len(new_names):
            st.error("프로파일 이름이 중복될 수 없습니다.")
        else:
            current_profiles = {}
            for old_name, data in edited_data.items():
                new_name = data['new_name']
                # 계산된 결과를 바로 저장
                current_profiles[new_name] = process_profile_data(data['table'], st.session_state.main_input_method)
            
            st.session_state.profiles = current_profiles
            st.success("업데이트 완료!")
            st.rerun()

# --- 그래프 및 분석 패널 ---
st.markdown("---")
st.header("④ 그래프 및 분석")
col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    # --- REFACTORED: `graph_data` 대신 `profiles`를 직접 사용 ---
    if not st.session_state.profiles:
        st.info("데이터를 입력하고 '계산 및 그래프 업데이트' 버튼을 눌러주세요.")
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
