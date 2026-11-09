import pandas as pd

# 1. 최종 완성된 CSV 파일 불러오기
csv_file = "samsung_fire_all.csv"
df = pd.read_csv(csv_file)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

print("=" * 60)
print(f"📌 삼성화재(000810) 최종 시계열 데이터 무결성 검증 리포트")
print(f"총 데이터 기간: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')} (총 {len(df)}일)")
print("=" * 60)

# ==========================================
# [검증 1] 컬럼별 결측치(NaN) 전수 조사
# ==========================================
print("\n[1] 컬럼별 결측치(NaN) 현황:")
missing_summary = df.isnull().sum()
for col, count in missing_summary.items():
    status = f"❌ {count}개 누락" if count > 0 else "✔ 정상 (0개)"
    print(f"  - {col}: {status}")

# 구체적으로 결측치가 있는 날짜 출력
missing_rows = df[df.isnull().any(axis=1)]
if not missing_rows.empty:
    print("\n⚠️ 결측치가 포함된 상세 날짜:")
    print(missing_rows[['date', 'close', 'per', 'pbr', 'foreign_net', 'inst_net']].to_string(index=False))

print("-" * 60)

# ==========================================
# [검증 2] 상장주식수 변동 (자사주 소각 등) 탐지
# ==========================================
df['shares_prev'] = df['shares'].shift(1)
splits = df[
    (df['shares'].notna()) & 
    (df['shares_prev'].notna()) & 
    (df['shares'] != df['shares_prev'])
]

print(f"\n[2] 상장주식수 변동(자사주 소각 등) 이벤트: 총 {len(splits)}건 발견")
if not splits.empty:
    for _, row in splits.iterrows():
        prev = int(row['shares_prev'])
        curr = int(row['shares'])
        diff = curr - prev
        print(f"  - [{row['date'].strftime('%Y-%m-%d']}] {prev:,}주 ➔ {curr:,}주 (변동폭: {diff:,}주)")
else:
    print("  - 변동 없음")

print("=" * 60)
print("▶ 모든 데이터 검증이 완료되었습니다!")
