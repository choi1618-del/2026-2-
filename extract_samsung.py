import os
import glob
import pandas as pd
import re
from io import StringIO

ROOT = "/mnt/data/stock"
OUTPUT_CSV = "samsung_fire_all.csv"

# 숫자만 깔끔하게 추출하는 함수
def clean_num(val):
    try:
        cleaned = re.sub(r'[^0-9.-]', '', str(val))
        return float(cleaned) if cleaned else None
    except:
        return None

print("▶ 삼성화재(000810) 전용 데이터 수집을 시작합니다...")
rows = []

folders = sorted(glob.glob(os.path.join(ROOT, "20*")))
success_count = 0

for folder in folders:
    date_str = os.path.basename(folder)
    html_path = os.path.join(folder, "000810.html")
    
    # 파일이 없으면 조용히 건너뜀 (휴장일 등)
    if not os.path.exists(html_path):
        continue
        
    try:
        html_content = open(html_path, encoding="utf-8", errors="ignore").read()
        
        # lxml 파서 에러 방지용 안전 장치
        try:
            tables = pd.read_html(StringIO(html_content), flavor='lxml')
        except:
            tables = pd.read_html(StringIO(html_content), flavor='html5lib')
        
        close, foreign_net, inst_net, marcap, shares, foreign_rate, per, pbr = [None] * 8
        
        # 1. [표 2] 종가, 외국인/기관 순매수 추출
        if len(tables) > 2:
            t2 = tables[2]
            valid_t2 = t2[t2['날짜'].notna()]
            if not valid_t2.empty:
                close = clean_num(valid_t2.iloc[0]['종가'])
                foreign_net = clean_num(valid_t2.iloc[0].get('외국인'))
                inst_net = clean_num(valid_t2.iloc[0].get('기관'))
        
        # 2. [표 5] 시가총액, 상장주식수 추출 (순위 혼동 방지 로직 적용)
        if len(tables) > 5:
            t5 = tables[5]
            for _, row in t5.iterrows():
                key = str(row[0]).replace(' ', '')
                val = str(row[1])
                if '시가총액' in key and '비중' not in key and '순위' not in key:
                    marcap = clean_num(val.split('억')[0]) if '억' in val else clean_num(val)
                elif '상장주식수' in key:
                    shares = clean_num(val)
                    
        # 3. [표 6] 외국인소진율 추출
        if len(tables) > 6:
            t6 = tables[6]
            for _, row in t6.iterrows():
                key = str(row[0]).replace(' ', '')
                val = str(row[1])
                if '외국인소진율' in key:
                    foreign_rate = clean_num(val)
                    
        # 4. [표 8] PER, PBR 추출
        if len(tables) > 8:
            t8 = tables[8]
            for _, row in t8.iterrows():
                key = str(row[0]).replace(' ', '')
                val = str(row[1])
                if 'PER' in key and '추정' not in key:
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

# 결과 저장
df_result = pd.DataFrame(rows)
df_result.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

print(f"\n[성공] 총 {success_count}일 치 삼성화재 데이터가 '{OUTPUT_CSV}' 파일로 안전하게 저장되었습니다!")
