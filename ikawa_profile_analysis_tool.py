# Ikawa Profile Analysis Tool (v9.0 - Final Version)
# -*- coding: utf-8 -*-

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from streamlit_plotly_events import plotly_events
import io

# ==============================================================================
# 핵심 함수
# ==============================================================================

def process_profile_data(df: pd.DataFrame, input_method: str) -> pd.DataFrame | None:
    """단일 프로파일 DF를 받아 모든 시간/ROR 계산을 수행합니다."""
    processed_df = df.copy()
    cols_to_numeric = ['온도℃']
    if input_method == '시간 입력':
        cols_to_numeric.extend(['분', '초'])
    else:
        cols_to_numeric.append('구간(초)')

    for col in cols_to_numeric:
        if col in processed_df.columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')

    processed_df.dropna(subset=['온도℃'], inplace=True)
    if processed_df.empty: return None
    
    processed_df.reset_index(drop=True, inplace=True)
    processed_df.insert(0, '번호', processed_df.index)

    if input_method == '시간 입력':
        processed_df['분'].fillna(0, inplace=True)
        processed_df['초'].fillna(0, inplace=True)
        total_seconds = processed_df['분'] * 60 + processed_df['초']
        processed_df['구간(초)'] = total_seconds.diff().fillna(total_seconds.iloc[0])
    else: # 구간 입력
        processed_df['구간(초)'].fillna(0, inplace=True)
        total_seconds = processed_df['구간(초)'].cumsum()
        processed_df['분'] = (total_seconds // 60).astype('Int64')
        processed_df['초'] = (total_seconds % 60).astype('Int64')

    processed_df['누적(초)'] = total_seconds
    temp_diff = processed_df['온도℃'].diff()
    time_diff = processed_df['구간(초)']
    where_condition = time_diff.fillna(0) != 0
    ror_per_sec = np.divide(temp_diff, time_diff, out=np.zeros_like(temp_diff, dtype=float), where=where_condition)
    processed_df['ROR(초당)'] = pd.Series(ror_per_sec).fillna(0)
    
    return processed_df

def display_hover_info(hovered_time, selected_profiles, graph_data, colors):
    """그래프 호버 시 분석 패널에 정보를 표시합니다. (보간 기능 완전 제거)"""
    st.markdown("#### 분석 정보")
    if hovered_time is None or not graph_data:
        st.info("그래프 위에 마우스를 올리면 상세 정보가 표시됩니다.")
        return
        
    hover_sec = int(hovered_time)
    
    # --- [수정] 시간 헤더 표시 로직 변경 ---
    # 이제 보간 없이, 단순히 호버된 시간만 표시합니다.
    st.markdown(f"**{hover_sec // 60}분 {hover_sec % 60:02d}초 ({hover_sec}초)**")
    st.divider()

    for i, name in enumerate(selected_profiles):
        if name in graph_data:
            df_calc = graph_data.get(name)
            if df_calc is None or df_calc.empty: continue
            
            color = colors[i % len(colors)]
            
            # 호버된 시간 바로 이전의 데이터 포인트를 찾습니다.
            current_segment = df_calc[df_calc['누적(초)'] <= hover_sec]
            if current_segment.empty: continue
            current_segment = current_segment.iloc[-1]
            
            current_time = current_segment['누적(초)']
            current_ror = current_segment['ROR(초당)']
            current_temp = current_segment['온도℃']
            
            # [수정] 이제 포인트 위인지, 사이인지 구분할 필요 없이
            # 항상 이전 포인트의 정보를 기준으로 표시합니다.
            point_num = current_segment['번호']
            st.markdown(f"<span style='color:{color};'>●</span> **{name}**: 포인트 {int(point_num)} ({current_temp:.1f}℃) 구간의 ROR은 초당 {current_ror:.3f}℃ 입니다.", unsafe_allow_html=True)


@st.cache_data
def create_template_excel(format_type):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if format_type == '시간 입력':
            df_template = pd.DataFrame({'온도℃': [120, 140, 160], '분': [0, 0, 1], '초': [0, 40, 23]})
        else: # 구간 입력
            df_template = pd.DataFrame({'온도℃': [120, 140, 160], '구간(초)': [np.nan, 40, 43]})
        
        # 템플릿 구조를 더 단순하고 명확하게 변경
        df_final = pd.DataFrame()
        
        # 프로파일 A 예시
        df_final['A'] = pd.Series(['프로파일 A', df_template.columns[0]] + list(df_template.iloc[:, 0]))
        if format_type == '시간 입력':
            df_final['B'] = pd.Series(['', df_template.columns[1]] + list(df_template.iloc[:, 1]))
            df_final['C'] = pd.Series(['', df_template.columns[2]] + list(df_template.iloc[:, 2]))
        else:
            df_final['B'] = pd.Series(['', df_template.columns[1]] + list(df_template.iloc[:, 1]))

        df_final.to_excel(writer, sheet_name='profiles', index=False, header=False)
    return output.getvalue()

# ==============================================================================
# UI 렌더링
# ==============================================================================
st.set_page_config(layout="wide", page_title="이카와 로스팅 프로파일 계산 툴 v9.0")
st.title("☕ 이카와 로스팅 프로파일 계산 툴 v9.0 (최종 안정화 버전)")

st.markdown("### 1. 분석할 파일의 형식을 선택하세요.")
input_method = st.radio("파일 형식 선택", ["시간 입력", "구간 입력"], horizontal=True, label_visibility="collapsed")

col1, col2 = st.columns(2)
with col1:
    st.download_button(label="📥 엑셀 템플릿 다운로드", data=create_template_excel(input_method), file_name=f"template.xlsx")
with col2:
    uploaded_file = st.file_uploader("**2. 프로파일 엑셀 파일을 업로드하세요.**", type=['xlsx'], label_visibility="collapsed")

st.markdown("---")

graph_data = {}
if uploaded_file is not None:
    try:
        with st.spinner("파일을 분석 중입니다..."):
            raw_df = pd.read_excel(uploaded_file, header=None)
            
            # --- 파싱 로직 ---
            profile_names_row = raw_df.iloc[0]
            cols_per_profile = 3 if input_method == '시간 입력' else 2
            
            for col_idx, name in profile_names_row.dropna().items():
                try:
                    profile_chunk = raw_df.iloc[2:, col_idx:col_idx + cols_per_profile]
                    profile_chunk.columns = raw_df.iloc[1, col_idx:col_idx + cols_per_profile].values
                    calculated = process_profile_data(profile_chunk, input_method)
                    if calculated is not None:
                        graph_data[name] = calculated
                except Exception:
                    continue
    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {e}")

# --- 사이드바 ---
with st.sidebar:
    st.header("보기 옵션")
    if graph_data:
        selected_profiles = [name for name in graph_data.keys() if st.checkbox(name, value=True, key=f"select_{name}")]
        st.divider()
        show_ror_graph = st.checkbox("ROR 그래프 표시", value=True)
    else:
        selected_profiles = []
        show_ror_graph = True

# --- 그래프 및 분석 패널 ---
st.header("📊 프로파일 비교 그래프 및 분석")
col_graph, col_info = st.columns([3, 1])

with col_graph:
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    if not graph_data:
        st.info("엑셀 파일을 업로드하여 분석을 시작하세요.")
    else:
        for i, name in enumerate(selected_profiles):
            if name in graph_data:
                df_calc = graph_data.get(name)
                color = colors[i % len(colors)]
                if df_calc is not None:
                    fig.add_trace(go.Scatter(x=df_calc['누적(초)'], y=df_calc['온도℃'], name=f'{name} - 온도', mode='lines+markers', line=dict(color=color), marker=dict(size=8), showlegend=True, hoverinfo='none'))
                    if show_ror_graph:
                        fig.add_trace(go.Scatter(x=df_calc['누적(초)'], y=df_calc['ROR(초당)'], name=f'{name} - ROR', mode='lines+markers', line=dict(color=color, dash='dot'), yaxis='y2', marker=dict(size=8), showlegend=True, hoverinfo='none'))
    
    fig.update_layout(height=600, xaxis=dict(title='시간 합계 (초)', range=[0, 360]), yaxis=dict(title='온도 (°C)', range=[85, 235]), yaxis2=dict(title='ROR(초당)', overlaying='y', side='right', range=[0, 0.75]), legend=dict(x=0, y=1.1, orientation='h'), hovermode='x unified')
    selected_points = plotly_events(fig, hover_event=True, key="graph_hover_events")

with col_info:
    last_hovered_time = selected_points[0]['x'] if selected_points else None
    display_hover_info(last_hovered_time, selected_profiles, graph_data, colors)

