import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 1. 환경 설정 및 비밀키 관리 (Secret Management)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Farminfo Analytics",
    page_icon="🍊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 비밀키 로드 함수 (Local vs Cloud Hybrid)
def get_naver_api_secrets():
    """
    Naver API 키를 로드합니다.
    1순위: Streamlit Cloud Secrets (st.secrets)
    2순위: 로컬 .env 파일
    """
    # 1. Streamlit Cloud Secrets 확인
    if "naver_api" in st.secrets:
        return st.secrets["naver_api"]["client_id"], st.secrets["naver_api"]["client_secret"]
    
    # 2. 로컬 .env 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # .env 후보 경로
    env_candidates = [
        os.path.join(project_root, ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    
    for env_path in env_candidates:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            break
            
    c_id = os.getenv('NAVER_CLIENT_ID')
    c_secret = os.getenv('NAVER_CLIENT_SECRET')
    
    if c_id and c_secret:
        return c_id, c_secret
    
    return None, None

client_id, client_secret = get_naver_api_secrets()

# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리 (Data Loading)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """데이터를 로드하고 캐싱합니다."""
    # 파일 경로 (절대 경로 또는 상대 경로)
    # ---------------------------
    # [Path Debugging Strategy]
    # ---------------------------
    # Streamlit Cloud와 로컬 환경의 경로 차이를 해결하기 위한 후보군 탐색
    current_dir = os.path.dirname(os.path.abspath(__file__)) # .../output
    project_root = os.path.dirname(current_dir)             # .../farminfo
    
    candidate_paths = [
        # 1. 스크립트 기준 상대 경로 (로컬/Cloud 일반적)
        os.path.join(project_root, "input", "preprocessed_data.csv"),
        # 2. 현재 작업 디렉토리(CWD) 기준 입수 (Streamlit Cloud Root 실행 시)
        os.path.join(os.getcwd(), "input", "preprocessed_data.csv"),
        # 3. Mount 경로 하드코딩 (최후의 수단, 리포지토리명에 따라 다를 수 있음)
        "/mount/src/farminfo/input/preprocessed_data.csv", 
        "input/preprocessed_data.csv"
    ]
    
    filepath = None
    for path in candidate_paths:
        if os.path.exists(path):
            filepath = path
            break
            
    if filepath is None:
        st.error("🚨 데이터 파일을 찾을 수 없습니다.")
        st.write("### Debug Info")
        st.write(f"- Current Working Dir: `{os.getcwd()}`")
        st.write(f"- Script Loc: `{current_dir}`")
        st.write("#### Checked Paths:")
        for p in candidate_paths:
            st.write(f"- `{p}`")
            
        # 디렉토리 구조 힌트 제공
        st.write("#### Directory Structure (Root):")
        try:
            st.write(os.listdir(os.getcwd()))
            if os.path.exists("input"):
                 st.write(f"input dir contents: {os.listdir('input')}")
        except Exception as e:
            st.write(f"Error listing dir: {e}")
            
        return pd.DataFrame()

    df = pd.read_csv(filepath)
    
    # 날짜 변환
    if '주문일' in df.columns:
        df['주문일'] = pd.to_datetime(df['주문일'])
        df['주문월'] = df['주문일'].dt.to_period('M').astype(str)
        df['주문시간'] = df['주문일'].dt.hour
        df['요일'] = df['주문일'].dt.day_name()
    
    # [Simulation] 연령대 데이터 생성 (데모용)
    if '연령대' not in df.columns:
        import numpy as np
        # 재현성을 위해 시드 고정
        np.random.seed(42)
        age_groups = ['20대', '30대', '40대', '50대', '60대 이상']
        # 가중치: 3040 주축
        probs = [0.15, 0.30, 0.35, 0.15, 0.05] 
        df['연령대'] = np.random.choice(age_groups, size=len(df), p=probs)
    
    # 숫자형 컬럼 변환 (콤마 제거)
    numeric_cols = ['결제금액', '판매단가', '공급단가', '주문취소 금액', '실결제 금액', '주문수량']
    for col in numeric_cols:
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(',', '').astype(float)
    
    # 마진 계산
    if '판매단가' in df.columns and '공급단가' in df.columns:
        df['마진'] = (df['판매단가'] - df['공급단가']) * df.get('주문수량', 1)
        
    return df

raw_df = load_data()

if raw_df.empty:
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 및 프롬프트 (Sidebar & Prompt UI)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🎛️ 컨트롤 패널")
    
    # 기간 설정
    min_date = raw_df['주문일'].min().date()
    max_date = raw_df['주문일'].max().date()
    
    date_range = st.date_input(
        "기간 선택",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # 빠른 필터
    st.divider()
    all_channels = raw_df['주문경로'].unique().tolist()
    selected_channels = st.multiselect("주문 경로 필터", all_channels, default=all_channels)
    
    if '이벤트 여부' in raw_df.columns:
        show_event_only = st.checkbox("이벤트 주문만 보기")
    else:
        show_event_only = False
        
    st.info(f"Updated: {pd.Timestamp.now().strftime('%Y-%m-%d')}")
    
    # API 상태 표시 (보안상 키 자체는 노출 X)
    if client_id:
        st.success("Naver API Key Loaded ✅")
    else:
        st.warning("Naver API Key Not Found ⚠️")

# 메인 프롬프트 영역
st.markdown("## 🍊 Farminfo Prompt Analytics")
prompt = st.text_input(
    "분석하고 싶은 키워드를 입력하세요 (예: 서울, 감귤, 선물, 카카오톡)", 
    placeholder="키워드를 입력하면 관련 데이터만 필터링하여 깊이 있게 분석합니다.",
    help="상품명, 옵션, 주소, 주문경로 등에서 키워드를 검색합니다."
)

# -----------------------------------------------------------------------------
# 4. 데이터 필터링 로직 (Filtering Logic)
# -----------------------------------------------------------------------------
df_filtered = raw_df.copy()

# 1. 기간 필터
if len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_filtered[
        (df_filtered['주문일'].dt.date >= start_date) & 
        (df_filtered['주문일'].dt.date <= end_date)
    ]

# 2. 채널 필터
if selected_channels:
    df_filtered = df_filtered[df_filtered['주문경로'].isin(selected_channels)]

# 3. 이벤트 필터
if show_event_only and '이벤트 여부' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['이벤트 여부'] == 'Y']

# 4. 프롬프트(검색어) 필터 - 핵심 로직
if prompt:
    with st.spinner(f"'{prompt}' 관련 데이터 분석 중..."):
        # 검색 대상 컬럼
        search_cols = ['상품명', '옵션코드', '주소', '주문경로', '목적', '고객선택옵션']
        valid_cols = [c for c in search_cols if c in df_filtered.columns]
        
        # 키워드 포함 여부 마스크 생성 (OR 조건)
        mask = pd.Series(False, index=df_filtered.index)
        for col in valid_cols:
            mask |= df_filtered[col].astype(str).str.contains(prompt, case=False)
        
        df_filtered = df_filtered[mask]
        
        if df_filtered.empty:
            st.warning(f"'{prompt}'에 대한 검색 결과가 없습니다.")
            st.stop()
        else:
            st.success(f"'{prompt}' 키워드로 {len(df_filtered):,}건의 데이터를 찾았습니다.")

# -----------------------------------------------------------------------------
# 5. KPI 메트릭 (Metrics) [Table Like 1]
# -----------------------------------------------------------------------------
total_sales = df_filtered['실결제 금액'].sum()
total_orders = len(df_filtered)
avg_order_value = total_sales / total_orders if total_orders > 0 else 0
avg_margin = df_filtered['마진'].mean() if '마진' in df_filtered.columns else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("총 매출액", f"{total_sales:,.0f}원")
col2.metric("총 주문수", f"{total_orders:,}건")
col3.metric("평균 객단가 (AOV)", f"{avg_order_value:,.0f}원")
col4.metric("평균 마진", f"{avg_margin:,.0f}원")

st.divider()

# -----------------------------------------------------------------------------
# 5. 메인 대시보드 구조 (Sidebar Navigation)
# -----------------------------------------------------------------------------

# 사이드바 메뉴 구성
st.sidebar.header("Navigation")
menu = st.sidebar.radio(
    "분석 메뉴 선택",
    [
        "📊 매출 및 성과 (Sales)",
        "🍊 상품 분석 (Product)",
        "📢 채널 및 지역 (Ch & Reg)",
        "👥 고객 분석 (Customer)",
        "📈 셀러 분석 (Seller)"
    ]
)

st.title(f"{menu}")
st.markdown("---")

# -----------------------------------------------------------
# View 1: 📊 매출 및 성과 Analysis
# -----------------------------------------------------------
if "매출" in menu:
    # [View 1] 📊 매출 및 성과 Analysis
    
    # [Row 1] KPI 지표
    total_sales = df_filtered['실결제 금액'].sum()
    total_orders = df_filtered['주문수량'].sum()
    unique_customers = df_filtered['주문자명'].nunique()
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    col_kpi1.metric("총 매출액", f"{total_sales:,.0f} 원")
    col_kpi2.metric("총 주문수량", f"{total_orders:,.0f} 개")
    col_kpi3.metric("순수 구매자 수", f"{unique_customers:,.0f} 명")
    
    st.divider()
    
    # [Graph 1] 일별 매출 추이
    st.subheader("📈 일별 매출 및 주문 추이")
    daily_sales = df_filtered.groupby('주문일').agg({'실결제 금액':'sum', '주문수량':'sum'}).reset_index()
    
    fig_daily = px.line(daily_sales, x='주문일', y='실결제 금액', title='일별 매출 추이')
    fig_daily.update_traces(line_color='#FF9F40', line_width=3)
    st.plotly_chart(fig_daily, use_container_width=True)

elif "상품" in menu:
    # [View 2] 🍊 상품 분석 Analysis
    st.header("🍊 상품 분석 (Product Analysis)")
    
    col_prod1, col_prod2 = st.columns([1, 1])
    
    with col_prod1:
        st.subheader("🍩 카테고리별 판매 비중")
        if '품종' in df_filtered.columns and '무게 구분' in df_filtered.columns:
            fig_sun = px.sunburst(
                df_filtered, 
                path=['품종', '무게 구분'], 
                values='실결제 금액',
                color='실결제 금액',
                color_continuous_scale='Oranges'
            )
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.warning("품종/무게 데이터가 없습니다.")
            
    with col_prod2:
        st.subheader("🏆 상품 판매 순위 (Top 10)")
        top_products = df_filtered.groupby('상품명')['실결제 금액'].sum().sort_values(ascending=False).head(10).reset_index()
        fig_bar = px.bar(top_products, x='실결제 금액', y='상품명', orientation='h', text_auto='.2s')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        fig_bar.update_traces(marker_color='#FF8C00')
        st.plotly_chart(fig_bar, use_container_width=True)

elif "채널" in menu:
    # [View 3] 📢 채널 및 지역 Analysis
    st.header("📢 채널 및 지역 분석 (Channel & Region)")
    
    col_ch1, col_ch2 = st.columns(2)
    
    with col_ch1:
        st.subheader("📢 주문 경로(채널) 효율")
        channel_perf = df_filtered.groupby('주문경로')[['실결제 금액', '주문수량']].sum().reset_index()
        fig_ch = px.bar(channel_perf, x='주문경로', y='실결제 금액', color='주문경로', title="채널별 매출액")
        st.plotly_chart(fig_ch, use_container_width=True)
        
    with col_ch2:
        st.subheader("📍 지역별 매출 규모")
        if '광역지역' in df_filtered.columns:
            region_stats = df_filtered.groupby('광역지역')['실결제 금액'].sum().reset_index().sort_values('실결제 금액', ascending=True)
            fig_bar_region = px.bar(
                region_stats,
                x='실결제 금액',
                y='광역지역',
                orientation='h',
                text_auto='.2s',
                title="지역별 매출액"
            )
            fig_bar_region.update_traces(marker_color='#FF8C00')
            st.plotly_chart(fig_bar_region, use_container_width=True)

    st.subheader("🕰️ 주문 패턴 분석 (시간대/요일)")
    df_filtered['시간대'] = df_filtered['주문시간']
    fig_scatter = px.scatter(
        df_filtered, 
        x='주문시간', 
        y='실결제 금액', 
        color='요일',
        size='주문수량', 
        hover_data=['상품명'],
        title="시간대별 주문 분포"
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

elif "고객" in menu:
    # [View 4] 👥 고객 분석 Analysis
    st.header("👥 고객 데이터 분석 (Customer Data)")
    
    # 1. 재구매 분석
    st.subheader("🔄 재구매율 분석 (Repurchase Analysis)")
    
    if '재구매 횟수' in df_filtered.columns and 'UID' in df_filtered.columns:
        cust_stats = df_filtered.groupby('UID')['재구매 횟수'].max().reset_index()
        total_customers = len(cust_stats)
        returning_customers = len(cust_stats[cust_stats['재구매 횟수'] > 0])
        repurchase_rate = (returning_customers / total_customers * 100) if total_customers > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 고객", f"{total_customers:,}명")
        c2.metric("재구매 고객", f"{returning_customers:,}명")
        c3.metric("재구매율", f"{repurchase_rate:.1f}%")
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            # Pie Chart logic
            vals = [total_customers - returning_customers, returning_customers]
            fig_pie = px.pie(values=vals, names=['신규', '재구매'], hole=0.4, title="신규 vs 재구매 비율")
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_chart2:
            st.info("💡 재구매율이 높은 상위 상품")
            # Loyalty logic simplified for brevity
            df_filtered['is_returning'] = df_filtered['재구매 횟수'] > 0
            loyalty = df_filtered.groupby('상품명').agg(Cnt=('UID','count'), Ret=('is_returning','sum')).reset_index()
            loyalty = loyalty[loyalty['Cnt'] >= 5]
            loyalty['Rate'] = loyalty['Ret']/loyalty['Cnt']*100
            st.dataframe(loyalty.sort_values('Rate', ascending=False).head(5)[['상품명','Rate']], use_container_width=True)

    st.divider()

    # 2. 연령대 분석
    st.subheader("👥 연령대별 분석 (Simulated)")
    col_age1, col_age2 = st.columns(2)
    with col_age1:
        age_sales = df_filtered.groupby('연령대')['실결제 금액'].sum().reset_index()
        fig_age = px.pie(age_sales, values='실결제 금액', names='연령대', title="연령별 매출 비중", hole=0.4)
        st.plotly_chart(fig_age, use_container_width=True)
    with col_age2:
        age_aov = df_filtered.groupby('연령대')['실결제 금액'].mean().reset_index()
        fig_aov = px.bar(age_aov, x='연령대', y='실결제 금액', title="연령별 객단가", color='실결제 금액')
        st.plotly_chart(fig_aov, use_container_width=True)

    st.subheader("📄 고객 상세 데이터")
    st.dataframe(df_filtered.head(100), use_container_width=True)

elif "셀러" in menu:
    # [View 5] 📈 셀러 분석 Analysis
    st.header("📈 셀러 성과 및 유입 분석")
    
    col_sel1, col_sel2 = st.columns(2)
    
    # 셀러별 매출 Top 10
    with col_sel1:
        top_sellers = df_filtered.groupby('셀러명')['실결제 금액'].sum().nlargest(10).reset_index()
        fig_seller = px.bar(top_sellers, x='셀러명', y='실결제 금액', title="Top 10 셀러 매출", color='실결제 금액')
        st.plotly_chart(fig_seller, use_container_width=True)
    
    # 셀러 유입/이탈 (월별)
    with col_sel2:
        # Simple logic for acquisition based on first order
        first_dates = df_filtered.groupby('셀러명')['주문일'].min().reset_index()
        first_dates['Month'] = first_dates['주문일'].dt.to_period('M').astype(str)
        new_counts = first_dates.groupby('Month')['셀러명'].count().reset_index()
        fig_inflow = px.bar(new_counts, x='Month', y='셀러명', title="월별 신규 셀러 유입", color_discrete_sequence=['#2ECC71'])
        st.plotly_chart(fig_inflow, use_container_width=True)

    # 셀러 상세 검색
    st.divider()
    sellers = df_filtered['셀러명'].unique()
    choice = st.selectbox("셀러 상세 분석", options=sellers)
    if choice:
        seller_df = df_filtered[df_filtered['셀러명'] == choice]
        st.write(f"**{choice}** 님의 총 매출: {seller_df['실결제 금액'].sum():,.0f}원 (총 {len(seller_df)}건 주문)")
        daily_trend = seller_df.groupby('주문일')['실결제 금액'].sum().reset_index()
        st.line_chart(daily_trend.set_index('주문일'))
