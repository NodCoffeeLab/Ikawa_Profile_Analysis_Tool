# Ikawa Profile Analysis Tool (v9.2 Refactored)
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
            # 숫자로 변환할 수 없는 값은 NaN(빈 값)으로 처리합니다.
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
        # FIX: '시간 입력' 시 누적 시간은 total_seconds를 직접 사용해야 합니다.
        valid_rows['누적(초)'] = total_seconds
    else: # 구간 입력
        valid_rows['구간(초)'] = valid_rows['구간(초)'].fillna(0)
        total_seconds = valid_rows['구간(초)'].cumsum()
        valid_rows['분'] = (total_seconds // 60).astype('Int64')
        valid_rows['초'] = (total_seconds % 60).astype('Int64')
        valid_rows['누적(초)'] = total_seconds

    temp_diff = valid_rows['온도℃'].diff()
    time_diff = valid_rows['구간(초)']
    
    # ROR 계산 (0으로 나누기 방지)
    ror_per_sec = np.divide(temp_diff, time_diff, out=np.zeros_like(temp_diff, dtype=float), where=time_diff.fillna(0) != 0)
    valid_rows['ROR(초당)'] = pd.Series(ror_per_sec).fillna(0)
    
    # 최종 DataFrame을 템플릿에 합치기
    final_df = create_profile_template()
    # FIX: 더 안정적인 데이터 업데이트 방식 적용
    # set_index를 사용해 '번호'를 기준으로 데이터를 업데이트합니다.
    final_df = final_df.set_index('번호')
    final_df.update(valid_rows.set_index('번호'))
    return final_df.reset_index() # '번호'를 다시 일반 컬럼으로 되돌립니다.


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
            # 호버된 시간 이전의 가장 마지막 데이터 포인트를 찾습니다.
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
if 'main_input_method' not in st.session_state:
    st.session_state.main_input_method = '시간 입력'
if 'show_hidden_cols' not in st.session_state:
    st.session_state.show_hidden_cols = False
if 'next_profile_num' not in st.session_state:
    st.session_state.next_profile_num = 4

# ==============================================================================
# UI 렌더링
# ==============================================================================
st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v9.2")
st.title("☕ 이카와 로스팅 프로파일 계산 툴 v9.2 (성능 및 편의성 개선)")

# --- 사이드바 ---
with st.sidebar:
    st.header("보기 옵션")
    # st.session_state.profiles가 비어있지 않을 때만 체크박스를 표시합니다.
    profile_keys = list(st.session_state.profiles.keys())
    selected_profiles = [name for name in profile_keys if st.checkbox(name, value=True, key=f"select_{name}")]
    st.divider()
    show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)
    st.checkbox("계산된 열 모두 보기", key="show_hidden_cols")
    st.divider()
    st.header("프로파일 관리")
    if st.button("＋ 프로파일 추가", use_container_width=True):
        if len(st.session_state.profiles) < 10:
            new_name = f"프로파일 {st.session_state.next_profile_num}"
            st.session_state.profiles[new_name] = create_profile_template()
            st.session_state.next_profile_num += 1
            st.rerun()
        else:
            st.warning("최대 10개의 프로파일만 추가할 수 있습니다.")

# --- 메인 화면 ---
st.header("① 데이터 입력 및 수정")
st.radio("입력 방식", ['시간 입력', '구간 입력'], horizontal=True, key="main_input_method", label_visibility="collapsed")

profile_cols = st.columns(len(st.session_state.profiles))
edited_data = {}

for i, name in enumerate(profile_keys):
    with profile_cols[i]:
        edited_data[name] = {}
        
        # 이름 변경 및 삭제 UI
        sub_cols = st.columns([4, 1])
        with sub_cols[0]:
            edited_data[name]['new_name'] = st.text_input("프로파일 이름", value=name, key=f"rename_{name}", label_visibility="collapsed")
        with sub_cols[1]:
            if st.button("🗑️", key=f"delete_{name}", help=f"{name} 프로파일 삭제"):
                del st.session_state.profiles[name]
                st.rerun()

        # 데이터 에디터 설정
        column_config = { "번호": st.column_config.NumberColumn(disabled=True) }
        if not st.session_state.show_hidden_cols:
            hidden_cols = ['누적(초)', 'ROR(초당)']
            if st.session_state.main_input_method == '시간 입력':
                hidden_cols.append("구간(초)")
            else:
                hidden_cols.extend(["분", "초"])
            for col in hidden_cols:
                column_config[col] = None
        
        # FIX: data_editor의 key를 입력 방식에 따라 다르게 설정하여 상태 문제를 해결합니다.
        edited_data[name]['table'] = st.data_editor(
            st.session_state.profiles[name], 
            key=f"editor_{name}_{st.session_state.main_input_method}", 
            num_rows="dynamic", 
            column_config=column_config
        )

st.header("② 계산 및 그래프 업데이트")
if st.button("🔄 계산 및 그래프 업데이트", use_container_width=True, type="primary"):
    with st.spinner("데이터 처리 및 그래프 생성 중..."):
        new_names = {name: data['new_name'] for name, data in edited_data.items()}
        if len(set(new_names.values())) != len(new_names):
            st.error("프로파일 이름이 중복될 수 없습니다.")
        else:
            updated_profiles = {}
            for old_name, data in edited_data.items():
                new_name = data['new_name']
                processed_table = process_profile_data(data['table'], st.session_state.main_input_method)
                updated_profiles[new_name] = processed_table
            
            st.session_state.profiles = updated_profiles
            st.success("업데이트 완료!")
            st.rerun()

# --- 그래프 및 분석 패널 ---
st.markdown("---")
st.header("③ 그래프 및 분석")
col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    if not st.session_state.profiles or not selected_profiles:
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
