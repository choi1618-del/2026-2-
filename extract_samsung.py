import os
import glob
import pandas as pd
import re
from io import StringIO

ROOT = "/mnt/data/stock"
OUTPUT_CSV = "samsung_fire_all.csv"

def clean_num(val):
    try:
        cleaned = re.sub(r'[^0-9.-]', '', str(val))
        return float(cleaned) if cleaned else None
    except:
        return None

print("▶ 삼성화재(000810) 2년 반 치 전체 데이터 수집 시작 (자동 탐지 모드 적용)...")
rows = []

folders = sorted(glob.glob(os.path.join(ROOT, "20*")))
success_count = 0

for folder in folders:
    date_str = os.path.basename(folder)
    html_path = os.path.join(folder, "000810.html")
    
    if not os.path.exists(html_path):
        continue
        
    try:
        html_content = open(html_path, encoding="utf-8", errors="ignore").read()
        try:
            tables = pd.read_html(StringIO(html_content), flavor='lxml')
        except:
            tables = pd.read_html(StringIO(html_content), flavor='html5lib')
        
        close, foreign_net, inst_net, marcap, shares, foreign_rate, per, pbr = [None] * 8
        
        for t in tables:
            # 1. 외국인/기관 표 찾기
            cols_str = "".join([str(c) for c in t.columns])
            if '종가' in cols_str and '외국인' in cols_str:
                date_col = next((c for c in t.columns if '날짜' in str(c) or '일자' in str(c)), None)
                if date_col is not None:
                    valid_t = t[t[date_col].notna()]
                    if not valid_t.empty:
                        close_col = next((c for c in t.columns if '종가' in str(c)), None)
                        for_col = next((c for c in t.columns if '외국인' in str(c)), None)
                        inst_col = next((c for c in t.columns if '기관' in str(c)), None)
                        
                        if close_col: close = clean_num(valid_t.iloc[0][close_col])
                        if for_col: foreign_net = clean_num(valid_t.iloc[0][for_col])
                        if inst_col: inst_net = clean_num(valid_t.iloc[0][inst_col])

            # 2. 기업정보(시가총액, PER 등) 찾기
            for _, row in t.iterrows():
                for i in range(len(row) - 1):
                    # ★ 에러 원인 해결: row[i] 대신 강제 위치 지정인 row.iloc[i] 사용
                    key = str(row.iloc[i]).replace(' ', '')
                    val = str(row.iloc[i+1])
                    
                    if '시가총액' in key and '비중' not in key and '순위' not in key:
                        marcap = clean_num(val.split('억')[0]) if '억' in val else clean_num(val)
                    elif '상장주식수' in key:
                        shares = clean_num(val)
                    elif '외국인소진율' in key:
                        foreign_rate = clean_num(val)
                    elif 'PER' in key and '추정' not in key:
                        per = clean_num(val.split('배')[0].split('l')[0])
                    elif 'PBR' in key:
                        pbr = clean_num(val.split('배')[0].split('l')[0])
                        
        rows.append({
            'date': date_str, 'close': close, 'foreign_net': foreign_net,
            'inst_net': inst_net, 'marcap': marcap, 'shares': shares,
            'foreign_rate': foreign_rate, 'per': per, 'pbr': pbr
        })
        success_count += 1
        
    except Exception as e:
        continue

df_result = pd.DataFrame(rows)
df_result.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

print(f"\n[성공] 총 {success_count}일 치 전체 삼성화재 데이터가 '{OUTPUT_CSV}'로 추출되었습니다!")
