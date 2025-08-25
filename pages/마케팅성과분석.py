import streamlit as st
import pandas as pd
import altair as alt
import gspread
from datetime import datetime, timedelta
import numpy as np

def authenticate():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return
    
    pw = st.sidebar.text_input("대시보드 비밀번호", type="password")
    
    if not pw:
        st.sidebar.warning("비밀번호를 입력해주세요.")
        st.stop()
    
    if pw == st.secrets["general"]["APP_PASSWORD"]:
        st.session_state.authenticated = True
        return
    
    st.sidebar.error("❌ 비밀번호가 틀렸습니다.")
    st.stop()

st.set_page_config(page_title="마케팅 성과 분석", layout="wide")
authenticate()

st.title("📈 마케팅 성과 분석")
st.markdown("마케팅 캠페인의 효과를 분석하고 ROI를 측정합니다.")

# 데이터 로드
@st.cache_data
def load_data():
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    worksheet_name = st.secrets["google_sheets"]["worksheet_name"]
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = sheet.get_all_records()
    return pd.DataFrame(records)

@st.cache_data
def load_population_data():
    creds_dict = st.secrets["gcp_service_account"]
    client = gspread.service_account_from_dict(creds_dict)
    sheet_id = st.secrets["google_sheets"]["sheet_id"]
    worksheet_name = "연령별인구현황"
    sheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = sheet.get_all_records()
    return pd.DataFrame(records)

df = load_data()
pop_df = load_population_data()

# 데이터 전처리
df['진료일자'] = pd.to_datetime(df['진료일자'], format='%Y%m%d')

# 나이대 카테고리
bins = list(range(0, 101, 10)) + [999]
labels = ["9세이하"] + [f"{i}대" for i in range(10, 100, 10)] + ["100세이상"]
df['연령대'] = pd.cut(df['나이'], bins=bins, labels=labels, right=False, include_lowest=True)

# 사이드바 - 캠페인 설정
st.sidebar.header("🎯 캠페인 설정")

# 캠페인 기간 설정
st.sidebar.subheader("캠페인 기간")
campaign_start = st.sidebar.date_input(
    "시작일", 
    value=datetime.now() - timedelta(days=30),
    max_value=datetime.now()
)
campaign_end = st.sidebar.date_input(
    "종료일", 
    value=datetime.now() - timedelta(days=1),
    max_value=datetime.now()
)

if campaign_start >= campaign_end:
    st.sidebar.error("종료일은 시작일보다 이후여야 합니다.")
    st.stop()

campaign_days = (campaign_end - campaign_start).days + 1

# 비교 기간 설정
st.sidebar.subheader("비교 기간")
comparison_option = st.sidebar.radio(
    "비교 기준",
    ["이전 동일 기간", "전년 동기", "사용자 지정"]
)

if comparison_option == "이전 동일 기간":
    before_end = campaign_start - timedelta(days=1)
    before_start = before_end - timedelta(days=campaign_days-1)
elif comparison_option == "전년 동기":
    before_start = campaign_start - timedelta(days=365)
    before_end = campaign_end - timedelta(days=365)
else:
    before_start = st.sidebar.date_input("비교 시작일")
    before_end = st.sidebar.date_input("비교 종료일")

# 타겟 지역 선택
st.sidebar.subheader("타겟 지역")
all_regions = df['행정동'].dropna().unique().tolist()
target_regions = st.sidebar.multiselect(
    "타겟 지역 선택",
    options=all_regions,
    default=[]
)

# 마케팅 비용 입력 (선택사항)
st.sidebar.subheader("💰 마케팅 비용")
marketing_cost = st.sidebar.number_input(
    "마케팅 비용 (원)",
    min_value=0,
    value=0,
    step=100000,
    help="ROI 계산을 위한 마케팅 비용을 입력하세요"
)

# 데이터 필터링
campaign_data = df[
    (df['진료일자'] >= pd.to_datetime(campaign_start)) & 
    (df['진료일자'] <= pd.to_datetime(campaign_end))
]

before_data = df[
    (df['진료일자'] >= pd.to_datetime(before_start)) & 
    (df['진료일자'] <= pd.to_datetime(before_end))
]

# 캠페인 후 30일 데이터
after_start = campaign_end + timedelta(days=1)
after_end = campaign_end + timedelta(days=30)
after_data = df[
    (df['진료일자'] >= pd.to_datetime(after_start)) & 
    (df['진료일자'] <= pd.to_datetime(after_end))
]

# 메인 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview", 
    "🗺️ 지역별 성과", 
    "👥 신환 분석", 
    "💰 ROI 분석"
])

with tab1:
    st.header("📊 캠페인 성과 Overview")
    
    # 기간 정보 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**캠페인 기간**: {campaign_start} ~ {campaign_end} ({campaign_days}일)")
    with col2:
        st.info(f"**비교 기간**: {before_start} ~ {before_end}")
    with col3:
        if len(target_regions) > 0:
            st.info(f"**타겟 지역**: {', '.join(target_regions[:3])}{'...' if len(target_regions) > 3 else ''}")
        else:
            st.info("**타겟 지역**: 전체")
    
    # 핵심 KPI
    st.subheader("핵심 성과 지표")
    
    # 타겟 지역 필터링
    if target_regions:
        campaign_target = campaign_data[campaign_data['행정동'].isin(target_regions)]
        before_target = before_data[before_data['행정동'].isin(target_regions)]
        campaign_non_target = campaign_data[~campaign_data['행정동'].isin(target_regions)]
        before_non_target = before_data[~before_data['행정동'].isin(target_regions)]
    else:
        campaign_target = campaign_data
        before_target = before_data
        campaign_non_target = pd.DataFrame()
        before_non_target = pd.DataFrame()
    
    # KPI 계산
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        new_patients_campaign = len(campaign_target[campaign_target['초/재진'] == '신환'])
        new_patients_before = len(before_target[before_target['초/재진'] == '신환'])
        new_patient_growth = ((new_patients_campaign - new_patients_before) / new_patients_before * 100) if new_patients_before > 0 else 0
        
        st.metric(
            "신환 수",
            f"{new_patients_campaign:,}명",
            f"{new_patient_growth:+.1f}%",
            delta_color="normal"
        )
    
    with col2:
        total_visits_campaign = len(campaign_target)
        total_visits_before = len(before_target)
        visit_growth = ((total_visits_campaign - total_visits_before) / total_visits_before * 100) if total_visits_before > 0 else 0
        
        st.metric(
            "전체 방문",
            f"{total_visits_campaign:,}건",
            f"{visit_growth:+.1f}%",
            delta_color="normal"
        )
    
    with col3:
        unique_patients_campaign = campaign_target['환자번호'].nunique()
        unique_patients_before = before_target['환자번호'].nunique()
        patient_growth = ((unique_patients_campaign - unique_patients_before) / unique_patients_before * 100) if unique_patients_before > 0 else 0
        
        st.metric(
            "전체 환자 수",
            f"{unique_patients_campaign:,}명",
            f"{patient_growth:+.1f}%",
            delta_color="normal"
        )
    
    with col4:
        new_ratio_campaign = (new_patients_campaign / unique_patients_campaign * 100) if unique_patients_campaign > 0 else 0
        new_ratio_before = (new_patients_before / unique_patients_before * 100) if unique_patients_before > 0 else 0
        new_ratio_change = new_ratio_campaign - new_ratio_before
        
        st.metric(
            "신환 비율",
            f"{new_ratio_campaign:.1f}%",
            f"{new_ratio_change:+.1f}%p",
            delta_color="normal"
        )
    
    # 타겟 vs 비타겟 지역 비교 (타겟 지역이 선택된 경우)
    if target_regions and len(campaign_non_target) > 0:
        st.subheader("타겟 vs 비타겟 지역 성과 비교")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 타겟 지역 성과
            st.write("**🎯 타겟 지역**")
            target_new_growth = ((new_patients_campaign - new_patients_before) / new_patients_before * 100) if new_patients_before > 0 else 0
            
            non_target_new_campaign = len(campaign_non_target[campaign_non_target['초/재진'] == '신환'])
            non_target_new_before = len(before_non_target[before_non_target['초/재진'] == '신환'])
            non_target_new_growth = ((non_target_new_campaign - non_target_new_before) / non_target_new_before * 100) if non_target_new_before > 0 else 0
            
            comparison_df = pd.DataFrame({
                '구분': ['타겟 지역', '비타겟 지역'],
                '신환 증가율': [target_new_growth, non_target_new_growth],
                '방문 증가율': [visit_growth, 
                               ((len(campaign_non_target) - len(before_non_target)) / len(before_non_target) * 100) if len(before_non_target) > 0 else 0]
            })
            
            chart = alt.Chart(comparison_df).mark_bar().encode(
                x=alt.X('구분:N', title='', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('신환 증가율:Q', title='신환 증가율 (%)'),
                color=alt.Color('구분:N', legend=None, scale=alt.Scale(scheme='blues')),
                tooltip=['구분', alt.Tooltip('신환 증가율:Q', format='.1f')]
            ).properties(height=300)
            
            st.altair_chart(chart, use_container_width=True)
        
        with col2:
            st.write("**📈 방문 증가율 비교**")
            
            chart2 = alt.Chart(comparison_df).mark_bar().encode(
                x=alt.X('구분:N', title='', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('방문 증가율:Q', title='방문 증가율 (%)'),
                color=alt.Color('구분:N', legend=None, scale=alt.Scale(scheme='greens')),
                tooltip=['구분', alt.Tooltip('방문 증가율:Q', format='.1f')]
            ).properties(height=300)
            
            st.altair_chart(chart2, use_container_width=True)
    
    # 일별 트렌드
    st.subheader("일별 신환 트렌드")
    
    # 캠페인 전후 60일 데이터
    trend_start = campaign_start - timedelta(days=30)
    trend_end = campaign_end + timedelta(days=30)
    trend_data = df[(df['진료일자'] >= pd.to_datetime(trend_start)) & (df['진료일자'] <= pd.to_datetime(trend_end))]

    if target_regions:
        trend_data = trend_data[trend_data['행정동'].isin(target_regions)]

    daily_new = trend_data[trend_data['초/재진'] == '신환'].groupby('진료일자').size().reset_index(name='신환수')
    daily_new['7일 이동평균'] = daily_new['신환수'].rolling(window=7, min_periods=1).mean()
    
    base = alt.Chart(daily_new).encode(
        x=alt.X('진료일자:T', title='날짜')
    )
    
    line = base.mark_line(color='#0072C3').encode(
        y=alt.Y('신환수:Q', title='신환 수'),
        tooltip=['진료일자:T', '신환수:Q']
    )
    
    avg_line = base.mark_line(color='red', strokeDash=[5, 5]).encode(
        y='7일 이동평균:Q',
        tooltip=['진료일자:T', alt.Tooltip('7일 이동평균:Q', format='.1f')]
    )
    
    # 캠페인 기간 음영
    campaign_rect = alt.Chart(pd.DataFrame({
        'start': [campaign_start],
        'end': [campaign_end]
    })).mark_rect(opacity=0.2, color='green').encode(
        x='start:T',
        x2='end:T'
    )
    
    chart = (campaign_rect + line + avg_line).properties(
        height=400,
        title='캠페인 전후 신환 추이'
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

with tab2:
    st.header("🗺️ 지역별 성과 분석")
    
    if not target_regions:
        st.info("타겟 지역을 선택하면 더 상세한 분석을 볼 수 있습니다.")
    
    # 지역별 성과 계산
    region_campaign = campaign_data.groupby('행정동').agg({
        '환자번호': 'nunique',
        '초/재진': lambda x: (x == '신환').sum()
    }).rename(columns={'환자번호': '환자수_캠페인', '초/재진': '신환수_캠페인'})
    
    region_before = before_data.groupby('행정동').agg({
        '환자번호': 'nunique',
        '초/재진': lambda x: (x == '신환').sum()
    }).rename(columns={'환자번호': '환자수_이전', '초/재진': '신환수_이전'})
    
    region_performance = pd.merge(region_campaign, region_before, 
                                 left_index=True, right_index=True, how='outer').fillna(0)
    
    region_performance['신환_증가'] = region_performance['신환수_캠페인'] - region_performance['신환수_이전']
    region_performance['신환_증가율'] = (region_performance['신환_증가'] / region_performance['신환수_이전'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
    region_performance['환자_증가율'] = ((region_performance['환자수_캠페인'] - region_performance['환자수_이전']) / region_performance['환자수_이전'] * 100).replace([np.inf, -np.inf], 0).fillna(0)
    
    # 타겟 지역 표시
    region_performance['타겟여부'] = region_performance.index.isin(target_regions)
    
    # 상위 성과 지역
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 신환 증가 TOP 10")
        top_regions = region_performance.nlargest(10, '신환_증가')[['신환수_캠페인', '신환수_이전', '신환_증가', '타겟여부']]
        top_regions['지역'] = top_regions.index
        
        # 색상 구분을 위한 차트
        chart = alt.Chart(top_regions.reset_index()).mark_bar().encode(
            x=alt.X('신환_증가:Q', title='신환 증가수'),
            y=alt.Y('행정동:N', sort='-x', title=''),
            color=alt.Color('타겟여부:N', 
                          scale=alt.Scale(domain=[True, False], range=['#FF6B6B', '#4ECDC4']),
                          legend=alt.Legend(title='타겟 지역')),
            tooltip=['행정동', '신환수_이전', '신환수_캠페인', '신환_증가']
        ).properties(height=400)
        
        st.altair_chart(chart, use_container_width=True)
    
    with col2:
        st.subheader("📊 신환 증가율 TOP 10")
        # 최소 기준을 만족하는 지역만 (이전 기간에 최소 5명 이상)
        filtered_regions = region_performance[region_performance['신환수_이전'] >= 5]
        top_growth = filtered_regions.nlargest(10, '신환_증가율')[['신환수_캠페인', '신환수_이전', '신환_증가율', '타겟여부']]
        top_growth['지역'] = top_growth.index
        
        chart2 = alt.Chart(top_growth.reset_index()).mark_bar().encode(
            x=alt.X('신환_증가율:Q', title='신환 증가율 (%)'),
            y=alt.Y('행정동:N', sort='-x', title=''),
            color=alt.Color('타겟여부:N',
                          scale=alt.Scale(domain=[True, False], range=['#FF6B6B', '#4ECDC4']),
                          legend=alt.Legend(title='타겟 지역')),
            tooltip=['행정동', '신환수_이전', '신환수_캠페인', alt.Tooltip('신환_증가율:Q', format='.1f')]
        ).properties(height=400)
        
        st.altair_chart(chart2, use_container_width=True)
    
    # 지역별 침투율 변화 (인구 데이터가 있는 경우)
    if not pop_df.empty:
        st.subheader("🎯 지역별 시장 침투율 변화")
        
        # 인구 데이터 전처리 (지역장악도 페이지와 동일한 방식)
        def split_address(addr: str):
            parts = addr.split()
            special_cities = {"수원시","성남시","안양시","부천시","안산시","고양시","용인시","청주시","천안시","전주시","포항시","창원시"}
            if parts[0]=="세종특별자치시" and len(parts)==2:
                return pd.Series({"시/도":parts[0],"시/군/구":"","행정동":parts[1]})
            elif len(parts)==4 and parts[1] in special_cities:
                return pd.Series({"시/도":parts[0],"시/군/구":f"{parts[1]} {parts[2]}","행정동":parts[3]})
            elif len(parts)==3 and parts[1] not in special_cities:
                return pd.Series({"시/도":parts[0],"시/군/구":parts[1],"행정동":parts[2]})
            else:
                return pd.Series({"시/도":None,"시/군/구":None,"행정동":None})
        
        split_df = pop_df["행정기관"].apply(split_address)
        pop_processed = pd.concat([pop_df, split_df], axis=1).dropna(subset=["시/도"])
        
        # 총 인구수 컬럼명 확인
        if "총 인구수" in pop_processed.columns:
            pop_processed = pop_processed.rename(columns={"총 인구수":"전체인구"})
        
        # 행정동별 인구 합계
        pop_summary = pop_processed.groupby('행정동')['전체인구'].sum().reset_index()
        
        penetration_data = region_performance.reset_index()
        penetration_data = pd.merge(penetration_data, pop_summary, on='행정동', how='left')
        
        penetration_data['침투율_캠페인'] = (penetration_data['환자수_캠페인'] / penetration_data['전체인구'] * 100).fillna(0)
        penetration_data['침투율_이전'] = (penetration_data['환자수_이전'] / penetration_data['전체인구'] * 100).fillna(0)
        penetration_data['침투율_변화'] = penetration_data['침투율_캠페인'] - penetration_data['침투율_이전']
        
        # 침투율 변화 상위 지역
        top_penetration = penetration_data.nlargest(10, '침투율_변화')[['행정동', '침투율_이전', '침투율_캠페인', '침투율_변화', '타겟여부']]
        
        chart3 = alt.Chart(top_penetration).mark_bar().encode(
            x=alt.X('침투율_변화:Q', title='침투율 변화 (%p)'),
            y=alt.Y('행정동:N', sort='-x', title=''),
            color=alt.Color('타겟여부:N',
                          scale=alt.Scale(domain=[True, False], range=['#FF6B6B', '#4ECDC4']),
                          legend=alt.Legend(title='타겟 지역')),
            tooltip=['행정동', 
                    alt.Tooltip('침투율_이전:Q', format='.2f'),
                    alt.Tooltip('침투율_캠페인:Q', format='.2f'),
                    alt.Tooltip('침투율_변화:Q', format='.2f')]
        ).properties(height=400)
        
        st.altair_chart(chart3, use_container_width=True)

with tab3:
    st.header("👥 신환 분석")
    
    # 신환 상세 분석
    new_patients_campaign = campaign_data[campaign_data['초/재진'] == '신환']
    new_patients_before = before_data[before_data['초/재진'] == '신환']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("연령대별 신환 분포")
        
        age_campaign = new_patients_campaign.groupby('연령대', observed=True).size().reset_index(name='캠페인')
        age_before = new_patients_before.groupby('연령대', observed=True).size().reset_index(name='이전')
        
        age_comparison = pd.merge(age_campaign, age_before, on='연령대', how='outer')
        age_comparison['캠페인'] = age_comparison['캠페인'].fillna(0)
        age_comparison['이전'] = age_comparison['이전'].fillna(0)
        age_comparison = age_comparison.melt(id_vars='연령대', var_name='기간', value_name='신환수')
        
        chart = alt.Chart(age_comparison).mark_bar().encode(
            x=alt.X('연령대:N', title='연령대', sort=labels),
            y=alt.Y('신환수:Q', title='신환 수'),
            color=alt.Color('기간:N', scale=alt.Scale(scheme='category10')),
            xOffset='기간:N',
            tooltip=['연령대', '기간', '신환수']
        ).properties(height=350)
        
        st.altair_chart(chart, use_container_width=True)
    
    with col2:
        st.subheader("성별 신환 분포")
        
        gender_campaign = new_patients_campaign.groupby('성별').size().reset_index(name='캠페인')
        gender_before = new_patients_before.groupby('성별').size().reset_index(name='이전')
        
        gender_comparison = pd.merge(gender_campaign, gender_before, on='성별', how='outer')
        gender_comparison['캠페인'] = gender_comparison['캠페인'].fillna(0)
        gender_comparison['이전'] = gender_comparison['이전'].fillna(0)
        gender_comparison = gender_comparison.melt(id_vars='성별', var_name='기간', value_name='신환수')
        
        chart2 = alt.Chart(gender_comparison).mark_bar().encode(
            x=alt.X('성별:N', title='성별'),
            y=alt.Y('신환수:Q', title='신환 수'),
            color=alt.Color('기간:N', scale=alt.Scale(scheme='category10')),
            xOffset='기간:N',
            tooltip=['성별', '기간', '신환수']
        ).properties(height=350)
        
        st.altair_chart(chart2, use_container_width=True)
    
    # 신환 재방문 분석
    st.subheader("📊 신환 재방문 분석")
    
    # 캠페인 기간 신환의 환자번호 추출
    new_patient_ids = new_patients_campaign['환자번호'].unique()
    
    # 이후 30일간 재방문 확인
    if len(after_data) > 0:
        revisits = after_data[after_data['환자번호'].isin(new_patient_ids)]
        
        revisit_count = revisits.groupby('환자번호').size().reset_index(name='재방문횟수')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            revisit_rate = len(revisit_count) / len(new_patient_ids) * 100 if len(new_patient_ids) > 0 else 0
            st.metric("30일 내 재방문율", f"{revisit_rate:.1f}%")
        
        with col2:
            avg_revisits = revisit_count['재방문횟수'].mean() if len(revisit_count) > 0 else 0
            st.metric("평균 재방문 횟수", f"{avg_revisits:.1f}회")
        
        with col3:
            retention_7d = len(after_data[(after_data['환자번호'].isin(new_patient_ids)) & 
                                         (after_data['진료일자'] <= pd.to_datetime(campaign_end + timedelta(days=7)))]['환자번호'].unique())
            retention_7d_rate = retention_7d / len(new_patient_ids) * 100 if len(new_patient_ids) > 0 else 0
            st.metric("7일 내 재방문율", f"{retention_7d_rate:.1f}%")
        
        # 재방문 분포
        st.subheader("재방문 횟수 분포")
        
        revisit_dist = revisit_count['재방문횟수'].value_counts().reset_index()
        revisit_dist.columns = ['재방문횟수', '환자수']
        
        chart3 = alt.Chart(revisit_dist).mark_bar().encode(
            x=alt.X('재방문횟수:O', title='재방문 횟수'),
            y=alt.Y('환자수:Q', title='환자 수'),
            color=alt.value('#0072C3'),
            tooltip=['재방문횟수', '환자수']
        ).properties(height=300)
        
        st.altair_chart(chart3, use_container_width=True)
    else:
        st.info("캠페인 종료 후 데이터가 충분하지 않아 재방문 분석을 수행할 수 없습니다.")

with tab4:
    st.header("💰 ROI 분석")
    
    if marketing_cost > 0:
        # ROI 계산
        st.subheader("투자 수익률 (ROI)")
        
        # 신환 관련 메트릭
        new_patients = len(campaign_data[campaign_data['초/재진'] == '신환'])
        cac = marketing_cost / new_patients if new_patients > 0 else 0
        
        # 신환의 평균 재방문 횟수 계산 (향후 30일)
        new_patient_ids = campaign_data[campaign_data['초/재진'] == '신환']['환자번호'].unique()
        
        if len(after_data) > 0:
            revisits_per_patient = after_data[after_data['환자번호'].isin(new_patient_ids)].groupby('환자번호').size().mean()
        else:
            revisits_per_patient = 1
        
        # 예상 수익 (가정: 방문당 평균 진료비)
        avg_revenue_per_visit = st.number_input(
            "방문당 평균 매출 (원)",
            min_value=0,
            value=50000,
            step=10000,
            help="정확한 ROI 계산을 위해 평균 진료비를 입력하세요"
        )
        
        total_revenue = new_patients * (1 + revisits_per_patient) * avg_revenue_per_visit
        roi = ((total_revenue - marketing_cost) / marketing_cost * 100) if marketing_cost > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "신환 획득 비용 (CAC)",
                f"{cac:,.0f}원",
                help="Customer Acquisition Cost"
            )
        
        with col2:
            st.metric(
                "신환 예상 LTV",
                f"{(1 + revisits_per_patient) * avg_revenue_per_visit:,.0f}원",
                help="30일 기준 Life Time Value"
            )
        
        with col3:
            st.metric(
                "예상 총 수익",
                f"{total_revenue:,.0f}원"
            )
        
        with col4:
            st.metric(
                "ROI",
                f"{roi:.1f}%",
                delta=f"{roi:.1f}%",
                delta_color="normal" if roi > 0 else "inverse"
            )
        
        # 손익분기점 분석
        st.subheader("📊 손익분기점 분석")
        
        breakeven_patients = marketing_cost / ((1 + revisits_per_patient) * avg_revenue_per_visit)
        current_progress = (new_patients / breakeven_patients * 100) if breakeven_patients > 0 else 0
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "손익분기 필요 신환수",
                f"{breakeven_patients:.0f}명"
            )
            st.metric(
                "현재 달성률",
                f"{current_progress:.1f}%"
            )
        
        with col2:
            # 진행률 바 차트
            progress_data = pd.DataFrame({
                '구분': ['달성', '미달성'],
                '값': [min(current_progress, 100), max(0, 100 - current_progress)]
            })
            
            chart = alt.Chart(progress_data).mark_arc().encode(
                theta='값:Q',
                color=alt.Color('구분:N', 
                              scale=alt.Scale(domain=['달성', '미달성'], 
                                            range=['#00D084', '#E0E0E0']),
                              legend=None),
                tooltip=['구분', '값']
            ).properties(
                width=200,
                height=200
            )
            
            st.altair_chart(chart, use_container_width=True)
        
        # 예측 시뮬레이션
        st.subheader("🔮 수익 예측 시뮬레이션")
        
        # 시뮬레이션 파라미터
        col1, col2 = st.columns(2)
        
        with col1:
            ltv_months = st.slider("LTV 계산 기간 (개월)", 1, 12, 6)
            monthly_retention = st.slider("월 평균 재방문율 (%)", 0, 100, 70)
        
        with col2:
            monthly_visits = st.slider("재방문시 월평균 방문 횟수", 1, 10, 2)
            
        # LTV 계산
        projected_ltv = 0
        for month in range(ltv_months):
            retention = (monthly_retention / 100) ** month
            projected_ltv += retention * monthly_visits * avg_revenue_per_visit
        
        projected_total_revenue = new_patients * projected_ltv
        projected_roi = ((projected_total_revenue - marketing_cost) / marketing_cost * 100) if marketing_cost > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                f"{ltv_months}개월 예상 LTV",
                f"{projected_ltv:,.0f}원"
            )
        
        with col2:
            st.metric(
                f"{ltv_months}개월 예상 총 수익",
                f"{projected_total_revenue:,.0f}원"
            )
        
        with col3:
            st.metric(
                f"{ltv_months}개월 예상 ROI",
                f"{projected_roi:.1f}%",
                delta=f"{projected_roi - roi:.1f}%p",
                delta_color="normal" if projected_roi > roi else "inverse"
            )
        
    else:
        st.info("💡 마케팅 비용을 입력하면 ROI 분석을 볼 수 있습니다.")
        
        # 비용 없이도 볼 수 있는 기본 메트릭
        st.subheader("기본 성과 지표")
        
        new_patients = len(campaign_data[campaign_data['초/재진'] == '신환'])
        total_visits = len(campaign_data)
        unique_patients = campaign_data['환자번호'].nunique()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("캠페인 기간 신환", f"{new_patients:,}명")
        
        with col2:
            st.metric("총 방문 건수", f"{total_visits:,}건")
        
        with col3:
            avg_visits = total_visits / unique_patients if unique_patients > 0 else 0
            st.metric("환자당 평균 방문", f"{avg_visits:.1f}회")