# Ikawa Profile Analysis Tool (v8.0 - Final Stable Version)
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_plotly_events import plotly_events

# ==============================================================================
# 핵심 함수 (보간 기능 제거, 안정화)
# ==============================================================================

def create_profile_template():
    """프로파일의 기본 뼈대가 되는 DataFrame을 생성합니다."""
    df = pd.DataFrame({
        '번호': range(21), '온도℃': [np.nan] * 21, '분': [np.nan] * 21,
        '초': [np.nan] * 21, '구간(초)': [np.nan] * 21, '누적(초)': [np.nan] * 21,
        'ROR(초당)': [np.nan] * 21, '이벤트': [''] * 21
    })
    df.loc[0, ['분', '초']] = 0
    return df

def process_profile_data(df: pd.DataFrame, main_input_method: str) -> pd.DataFrame:
    """단일 프로파일 DF를 받아 모든 시간/ROR 계산을 수행합니다."""
    processed_df = df.copy()
    cols_to_numeric = ['온도℃', '분', '초', '구간(초)']
    for col in cols_to_numeric:
        if col in processed_df.columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')

    processed_df.dropna(subset=['온도℃'], inplace=True)
    if processed_df.empty: return create_profile_template()
    processed_df.reset_index(drop=True, inplace=True)
    processed_df.insert(0, '번호', processed_df.index)

    if main_input_method == '시간 입력':
        processed_df['분'].fillna(0, inplace=True)
        processed_df['초'].fillna(0, inplace=True)
        total_seconds = processed_df['분'] * 60 + processed_df['초']
        processed_df['구간(초)'] = total_seconds.diff()
    else: # 구간 입력
        processed_df['구간(초)'].fillna(0, inplace=True)
        total_seconds = processed_df['구간(초)'].cumsum()
        processed_df['분'] = (total_seconds // 60).astype('Int64')
        processed_df['초'] = (total_seconds % 60).astype('Int64')

    processed_df['구간(초)'].fillna(0, inplace=True)
    processed_df['누적(초)'] = processed_df['구간(초)'].cumsum()
    
    temp_diff = processed_df['온도℃'].diff()
    time_diff = processed_df['구간(초)']
    where_condition = time_diff.fillna(0) != 0
    ror_per_sec = np.divide(temp_diff, time_diff, out=np.zeros_like(temp_diff, dtype=float), where=where_condition)
    processed_df['ROR(초당)'] = pd.Series(ror_per_sec).fillna(0)
    
    # 원본 템플릿과 합쳐 최종 형태 유지
    final_df = create_profile_template()
    final_df.update(processed_df)
    return final_df

def display_hover_info(hovered_time, selected_profiles, graph_data, colors):
    """그래프 호버 시 분석 패널에 정보를 표시합니다."""
    st.markdown("#### 분석 정보")
    if hovered_time is None or not graph_data:
        st.info("그래프 위에 마우스를 올리면 상세 정보가 표시됩니다.")
        return
    hover_sec = int(hovered_time)
    
    try:
        first_profile_name = next(name for name in selected_profiles if name in graph_data and graph_data[name] is not None)
        df_calc_first = graph_data[first_profile_name]
        
        valid_data = df_calc_first.dropna(subset=['누적(초)', '온도℃'])
        if len(valid_data) > 1:
            temp_at_hover = np.interp(hover_sec, valid_data['누적(초)'], valid_data['온도℃'])
        elif len(valid_data) == 1:
            temp_at_hover = valid_data['온도℃'].iloc[0]
        else:
            return

        st.markdown(f"**{hover_sec // 60}분 {hover_sec % 60:02d}초 ({hover_sec}초) / {temp_at_hover:.1f}℃**")
    except (StopIteration, KeyError, IndexError):
         return
    st.divider()
    for i, name in enumerate(selected_profiles):
        if name in graph_data:
            df_calc = graph_data.get(name)
            if df_calc is None: continue
            
            color = colors[i % len(colors)]
            
            valid_calc = df_calc.dropna(subset=['누적(초)'])
            if valid_calc.empty: continue

            current_segment_search = valid_calc[valid_calc['누적(초)'] <= hover_sec]
            if current_segment_search.empty: continue
            current_segment = current_segment_search.iloc[-1]

            current_time = current_segment['누적(초)']
            current_ror = current_segment['ROR(초당)']
            current_temp = current_segment['온도℃']
            
            is_on_point = abs(current_time - hover_sec) <= 0.5
            
            if is_on_point:
                display_temp = current_temp
                point_num = current_segment['번호']
                st.markdown(f"<span style='color:{color};'>●</span> **{name}**: 포인트 {int(point_num)}: {display_temp:.1f}℃ (초당 {current_ror:.3f}℃ 상승)", unsafe_allow_html=True)
            else:
                time_in_segment = hover_sec - current_time
                interp_temp = current_temp + current_ror * time_in_segment
                next_point_num = int(current_segment['번호']) + 1
                st.markdown(f"<span style='color:{color};'>●</span> **{name}**: 포인트 {int(current_segment['번호'])}-{next_point_num} 구간: {interp_temp:.1f}℃ (초당 {current_ror:.3f}℃ 상승)", unsafe_allow_html=True)

# ==============================================================================
# 상태(Session State) 초기화
# ==============================================================================
if 'profiles' not in st.session_state:
    st.session_state.profiles = { f"프로파일 {i+1}": create_profile_template() for i in range(3) }
if 'main_input_method' not in st.session_state: st.session_state.main_input_method = '시간 입력'
if 'show_hidden_cols' not in st.session_state: st.session_state.show_hidden_cols = False
if 'next_profile_num' not in st.session_state: st.session_state.next_profile_num = 4
if 'graph_data' not in st.session_state: st.session_state.graph_data = {}
if 'data_synced' not in st.session_state: st.session_state.data_synced = False

# ==============================================================================
# UI 렌더링
# ==============================================================================
st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v8.0")
st.title("☕ 이카와 로스팅 프로파일 계산 툴 v8.0 (Final)")

with st.sidebar:
    st.header("④ 보기 옵션")
    selected_profiles_sidebar = [name for name in st.session_state.profiles.keys() if st.checkbox(name, value=True, key=f"select_{name}")]
    st.divider()
    show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)
    st.checkbox("계산된 열 모두 보기", key="show_hidden_cols")
    st.divider()
    with st.expander("🛠️ 개발자 모드"):
        st.write("`profiles`의 프로파일 개수: " + str(len(st.session_state.profiles)))
        st.write("`graph_data`의 프로파일 개수: " + str(len(st.session_state.graph_data)))

st.header("① 데이터 입력")

# --- 프로파일 선택 탭 (Single-View Architecture) ---
profile_tabs = st.tabs(list(st.session_state.profiles.keys()))

for i, tab in enumerate(profile_tabs):
    with tab:
        active_profile_name = list(st.session_state.profiles.keys())[i]
        
        # --- 이름 변경 ---
        new_name = st.text_input("프로파일 이름", value=active_profile_name, key=f"rename_{active_profile_name}")
        if new_name != active_profile_name and new_name:
            if new_name in st.session_state.profiles: st.error("이름 중복")
            else:
                items = list(st.session_state.profiles.items())
                items[i] = (new_name, st.session_state.profiles[active_profile_name])
                st.session_state.profiles = dict(items)
                st.rerun()

        # --- 입력 방식 선택 ---
        st.radio("입력 방식", ['시간 입력', '구간 입력'], horizontal=True, key="main_input_method")
        
        # --- 데이터 테이블 ---
        column_config = { "번호": st.column_config.NumberColumn(disabled=True) }
        if not st.session_state.show_hidden_cols:
            hidden_cols = ['누적(초)', 'ROR(초당)']
            if st.session_state.main_input_method == '시간 입력': hidden_cols.append("구간(초)")
            else: hidden_cols.extend(["분", "초"])
            for col in hidden_cols: column_config[col] = None
        
        edited_df = st.data_editor(st.session_state.profiles[active_profile_name], key=f"editor_{active_profile_name}", num_rows="dynamic", column_config=column_config)

        # --- 데이터 동기화 버튼 ---
        if st.button("🔄 이 프로파일 동기화", key=f"sync_{active_profile_name}"):
            with st.spinner(f"'{active_profile_name}' 동기화 중..."):
                st.session_state.profiles[active_profile_name] = process_profile_data(edited_df, st.session_state.main_input_method)
                st.session_state.data_synced = True
            st.success(f"'{active_profile_name}' 동기화 완료!")
            st.rerun()

st.markdown("---")
st.header("③ 액션 버튼")

# --- 그래프 업데이트 및 프로파일 추가 버튼 ---
btn_cols = st.columns([4, 1])
with btn_cols[0]:
    if st.button("📈 모든 프로파일 그래프 업데이트", use_container_width=True, disabled=not st.session_state.data_synced):
        with st.spinner("그래프 생성 중..."):
            st.session_state.graph_data = st.session_state.profiles
        st.session_state.data_synced = False
        st.success("그래프 업데이트 완료!")
        st.rerun()
with btn_cols[1]:
    if st.button("＋ 프로파일 추가"):
        if len(st.session_state.profiles) < 10:
            new_name = f"프로파일 {st.session_state.next_profile_num}"
            st.session_state.profiles[new_name] = create_profile_template()
            st.session_state.next_profile_num += 1
            st.rerun()
        else:
            st.warning("최대 10개의 프로파일만 추가할 수 있습니다.")

# --- 그래프 및 분석 패널 ---
st.markdown("---")
st.header("④ 그래프 및 분석")
col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    graph_data_to_display = st.session_state.graph_data
    
    if not graph_data_to_display:
        st.info("데이터를 동기화하고 '그래프 업데이트' 버튼을 눌러주세요.")
    else:
        for i, name in enumerate(selected_profiles_sidebar):
            if name in graph_data_to_display:
                df_calc = graph_data_to_display.get(name)
                color = colors[i % len(colors)]
                if df_calc is not None:
                    valid_points = df_calc.dropna(subset=['온도℃', '누적(초)'])
                    if not valid_points.empty:
                        fig.add_trace(go.Scatter(x=valid_points['누적(초)'], y=valid_points['온도℃'], name=f'{name} - 온도', mode='lines+markers', line=dict(color=color), marker=dict(size=8), hoverinfo='none'))
                        if show_ror_graph:
                            fig.add_trace(go.Scatter(x=valid_points['누적(초)'], y=valid_points['ROR(초당)'], name=f'{name} - ROR', mode='lines+markers', line=dict(color=color, dash='dot'), yaxis='y2', marker=dict(size=8), hoverinfo='none'))
    
    fig.update_layout(height=600, xaxis=dict(title='시간 합계 (초)', range=[0, 360]), yaxis=dict(title='온도 (°C)', range=[85, 235]), yaxis2=dict(title='ROR(초당)', overlaying='y', side='right', range=[0, 0.75]), legend=dict(x=0, y=1.1, orientation='h'), hovermode='x unified')
    selected_points = plotly_events(fig, hover_event=True, key="graph_hover_events")

with col_info:
    last_hovered_time = selected_points[0]['x'] if selected_points else None
    display_hover_info(last_hovered_time, selected_profiles_sidebar, st.session_state.graph_data, px.colors.qualitative.Plotly)

