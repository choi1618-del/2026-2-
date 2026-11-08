import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

print("데이터 스캔 중... (메모리 최적화 모드)")

root = Path("/mnt/data/stock")
records = []

# 1. 파일 내용 대신 파일 개수만 카운트 (용량/메모리 문제 원천 차단)
for folder in sorted(root.glob("202*")):
    if folder.is_dir():
        date_str = folder.name
        file_count = len(list(folder.glob("*.html")))
        records.append({'Date': date_str, 'Stock_Count': file_count})

df = pd.DataFrame(records)
df['Date'] = pd.to_datetime(df['Date'])

# 2. 결측일 파악을 위한 전체 캘린더 생성
all_days = pd.date_range(start=df['Date'].min(), end=df['Date'].max())
df = df.set_index('Date').reindex(all_days).fillna(0).reset_index()
df.rename(columns={'index': 'Date'}, inplace=True)

# 3. 콘솔 결과 출력
missing_days = len(df[df['Stock_Count'] == 0])
print(f"데이터 기간: {df['Date'].min().date()} ~ {df['Date'].max().date()}")
print(f"최대 보유 종목 수: {int(df['Stock_Count'].max())}개")
print(f"결측일(주말/휴장/누락): {missing_days}일")

# 4. 시각화 (깃헙 업로드용 그림 생성)
plt.figure(figsize=(12, 5))

# 전체 종목 수 흐름 (생성/소멸 트렌드)
plt.plot(df['Date'], df['Stock_Count'], color='#2c3e50', linewidth=1.2)
plt.fill_between(df['Date'], df['Stock_Count'], color='#3498db', alpha=0.3)

# 결측 분포(데이터가 0인 구간)를 빨간색으로 명확히 마킹
missing_df = df[df['Stock_Count'] == 0]
plt.scatter(missing_df['Date'], missing_df['Stock_Count'], color='#e74c3c', s=15, label='Missing (Weekends/Holidays)', zorder=5)

plt.title("Dataset Scope & Missing Value Distribution", fontsize=16, fontweight='bold')
plt.xlabel("Date", fontsize=12)
plt.ylabel("Number of Tickers", fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

# 그림 파일 저장
plt.savefig("week1_scope_plot.png", dpi=300)
print("\n[성공] 깃헙 업로드용 'week1_scope_plot.png' 생성 완료!")
