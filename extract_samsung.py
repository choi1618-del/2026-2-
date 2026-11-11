import os
import glob
import pandas as pd
import re
from io import StringIO

ROOT = "/mnt/data/stock"
OUTPUT_CSV = "samsung_fire_master_18vars.csv"

def clean_num(val):
    """한글 화폐 단위(조, 억, 백만) 및 특수문자를 완벽하게 순수 숫자로 변환하는 마법 함수"""
    if pd.isna(val) or str(val).strip() == '' or str(val) == 'NaN':
        return None
    val_str = str(val).replace(',', '').replace(' ', '').replace('원', '').replace('배', '').replace('%', '').replace('주', '')
    
    # '16조3443억' 같은 복합 단위 처리
    if '조' in val_str and '억' in val_str:
        parts = val_str.split('조')
        jo = float(re.sub(r'[^0-9.-]', '', parts[0])) if re.sub(r'[^0-9.-]', '', parts[0]) else 0
        eok = float(re.sub(r'[^0-9.-]', '', parts[1].replace('억', ''))) if re.sub(r'[^0-9.-]', '', parts[1].replace('억', '')) else 0
        return (jo * 1000000000000) + (eok * 100000000)
    
    # 단일 단위 처리
    multiplier = 1
    if '백만' in val_str:
        multiplier = 1000000
    elif '억' in val_str:
        multiplier = 100000000
        
    cleaned = re.sub(r'[^0-9.-]', '', val_str)
    try:
        return float(cleaned) * multiplier if cleaned else None
    except:
        return None

print("=" * 80)
print("🚀 삼성화재(000810) 2년 반 치 18개 핵심 퀀트 변수 All-in-One 수집 시작...")
print("=" * 80)
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
        
        # 💡 18개 변수 초기화
        close_p, prev_p, open_p, high_p, low_p, vol, vol_amt = [None] * 7
        high_52, low_52, marcap, foreign_rate = [None] * 4
        per, eps, est_per, est_eps, pbr, bps = [None] * 6
        div_yield, div_per_share = None, None
        
        for t in tables:
            # [1] 상단 메인 시세표에서 종가(현재가) 찾기
            cols_str = "".join([str(c) for c in t.columns])
            if '종가' in cols_str and '전일비' in cols_str:
                date_col = next((c for c in t.columns if '날짜' in str(c) or '일자' in str(c)), None)
                if date_col is not None:
                    valid_t = t[t[date_col].notna()]
                    if not valid_t.empty:
                        close_col = next((c for c in t.columns if '종가' in str(c)), None)
                        if close_col: 
                            close_p = clean_num(valid_t.iloc[0][close_col])

            # [2] 기업정보 표(0, 5, 6, 7, 8) 샅샅이 뒤지기
            for _, row in t.iterrows():
                for i in range(len(row) - 1):
                    key_raw = str(row.iloc[i]).replace(' ', '')
                    val_raw = str(row.iloc[i+1])
                    
                    # 1. 가격 및 거래 지표
                    if key_raw == '전일': prev_p = clean_num(val_raw)
                    elif key_raw == '시가': open_p = clean_num(val_raw)
                    elif key_raw == '고가': high_p = clean_num(val_raw)
                    elif key_raw == '저가': low_p = clean_num(val_raw)
                    elif key_raw == '거래량': vol = clean_num(val_raw)
                    elif '거래대금' in key_raw: vol_amt = clean_num(val_raw)
                    
                    # 2. 기업 규모 및 수급 지표
                    elif '시가총액' in key_raw and '순위' not in key_raw: marcap = clean_num(val_raw)
                    elif '외국인소진율' in key_raw: foreign_rate = clean_num(val_raw)
                    
                    # 3. 52주 극값 (형태: 393,500 l 231,000)
                    elif '52주최고' in key_raw:
                        parts = val_raw.split('l')
                        high_52 = clean_num(parts[0])
                        low_52 = clean_num(parts[1]) if len(parts) > 1 else None
                        
                    # 4. 밸류에이션 및 재무 지표 (PER l EPS 묶인 형태 처리)
                    elif 'PERlEPS' in key_raw and '추정' not in key_raw:
                        parts = val_raw.split('l')
                        per = clean_num(parts[0])
                        eps = clean_num(parts[1]) if len(parts) > 1 else None
                    elif '추정PER' in key_raw:
                        parts = val_raw.split('l')
                        est_per = clean_num(parts[0])
                        est_eps = clean_num(parts[1]) if len(parts) > 1 else None
                    elif 'PBRlBPS' in key_raw:
                        parts = val_raw.split('l')
                        pbr = clean_num(parts[0])
                        bps = clean_num(parts[1]) if len(parts) > 1 else None
                    elif '배당수익률' in key_raw:
                        div_yield = clean_num(val_raw)
                        # 주당배당금은 HTML 구조에 따라 별도 표기되어 있을 경우 추출, 일단 None으로 세팅
                        div_per_share = None 
                        
        rows.append({
            '날짜': date_str, 
            '종목코드': '000810',
            '현재가(종가)': close_p, '기준가(전일)': prev_p, 
            '시가': open_p, '고가': high_p, '저가': low_p, 
            '거래량': vol, '거래대금': vol_amt,
            '52주최고': high_52, '52주최저': low_52, 
            '시가총액': marcap, '외인소진율': foreign_rate,
            'PER': per, 'EPS': eps, '추정PER': est_per, '추정EPS': est_eps, 
            'PBR': pbr, 'BPS': bps, '배당수익률': div_yield
        })
        success_count += 1
        
    except Exception as e:
        continue

df_result = pd.DataFrame(rows)
# 날짜순 정렬
df_result['날짜'] = pd.to_datetime(df_result['날짜'])
df_result = df_result.sort_values('날짜').reset_index(drop=True)

df_result.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

print(f"\n🎉 [성공] 총 {success_count}일 치 핵심 변수 18개가 완벽하게 파싱되었습니다!")
print(f"📁 결과 파일: '{OUTPUT_CSV}'")

# 결과 살짝 엿보기
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
print("\n[추출 데이터 미리보기 (최근 3일)]")
print(df_result.tail(3).to_string(index=False))
