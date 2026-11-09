import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

print("▶ 서버 내 원본 HTML 데이터 스캔 및 결측 분포 분석 중...")

# 1. 서버 원본 데이터 경로 설정
root = Path("/mnt/data/stock")
records = []

# '20'으로 시작하는 날짜별 폴더 순회
date_folders = sorted([f for f in root.iterdir() if f.is_dir() and f.name.startswith("20")])

for folder in date_folders:
    date_str = folder.name
    
    # 실패(.fail.html) 파일을 제외한 순수 유효 종목 코드 집합 추출
    valid_codes = {f.stem for f in folder.glob("*.html") if not f.name.endswith(".fail.html")}
    
    records.append({
        'Date': pd.to_datetime(date_str),
        'Stock_Count': len(valid_codes)
    })

df = pd.DataFrame(records)

if not df.empty:
    df = df.sort_values('Date').reset_index(drop=True)
    
    # 2. 전체 평일/캘린더 캘린더 기준 결측일(데이터가 0인 날) 뼈대 맞추기
    all_days = pd.date_range(start=df['Date'].min(), end=df['Date'].max())
    df = df.set_index('Date').reindex(all_days).fillna({'Stock_Count': 0}).reset_index()
    df.rename(columns={'index': 'Date'}, inplace=True)
    
    # 3. 결측 현황 집계
    total_days = len(df)
    missing_df = df[df['Stock_Count'] == 0]
    missing_days_count = len(missing_df)
    
    print("\n" + "=" * 50)
    print("📊 [전체 데이터 결측 분포 분석 리포트]")
    print(f"  - 분석 기간: {df['Date'].min().strftime('%Y-%m-%d')} ~ {df['Date'].max().strftime('%Y-%m-%d')} (총 {total_days}일)")
    print(f"  - 최대 활성 종목 수: {int(df['Stock_Count'].max()):,}개")
    print(f"  - 데이터 누락/휴장일(Stock_Count = 0): {missing_days_count}일")
    print("=" * 50)

    # 4. 시각화 그래프 생성
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(14, 6))

    # 전체 활성 종목 수 추이 라인
    plt.plot(df['Date'], df['Stock_Count'], color='#2c3e50', linewidth=1.2, label='Active Tickers')
    plt.fill_between(df['Date'], df['Stock_Count'], color='#3498db', alpha=0.3)

    # 결측일(0개인 구간)을 강렬한 빨간색 점으로 마킹
    plt.scatter(missing_df['Date'], missing_df['Stock_Count'], color='#e74c3c', s=20, label=f'Missing / Closed Days ({missing_days_count} days)', zorder=5)

    plt.title("Server Raw HTML: Active Tickers & Missing Distribution", fontsize=16, fontweight='bold', pad=15)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Active Tickers", fontsize=12)
    plt.legend(loc='upper left', fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    # 이미지 파일 저장
    output_img = "missing_distribution_plot.png"
    plt.savefig(output_img, dpi=300)
    print(f"\n[성공] 결측 분포 시각화 자료가 '{output_img}'로 안전하게 저장되었습니다!")
else:
    print("⚠️ 지정된 경로에 날짜별 폴더가 없습니다. 경로를 다시 확인해주세요.")
