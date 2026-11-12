import os
import glob
import pandas as pd
import re
from io import StringIO
from collections import defaultdict

ROOT = "/mnt/data/stock"
OUTPUT_DIR = "/home/s202420495/stock_csv_results" 
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_num(val):
    if pd.isna(val) or str(val).strip() == '' or str(val) == 'NaN': return None
    val_str = str(val).replace(',', '').replace(' ', '').replace('원', '').replace('배', '').replace('%', '').replace('주', '').replace('위', '')
    if '조' in val_str and '억' in val_str:
        parts = val_str.split('조')
        jo = float(re.sub(r'[^0-9.-]', '', parts[0])) if re.sub(r'[^0-9.-]', '', parts[0]) else 0
        eok = float(re.sub(r'[^0-9.-]', '', parts[1].replace('억', ''))) if re.sub(r'[^0-9.-]', '', parts[1].replace('억', '')) else 0
        return (jo * 1000000000000) + (eok * 100000000)
    
    multiplier = 1000000 if '백만' in val_str else 100000000 if '억' in val_str else 1
    cleaned = re.sub(r'[^0-9.-]', '', val_str)
    try: return float(cleaned) * multiplier if cleaned else None
    except: return None

print("=" * 80)
print("🚀 [전체 종목] 교수님 과제 대응: 23개 핵심 퀀트/재무 변수 대량 추출 시작...")
print("=" * 80)

data_by_stock = defaultdict(list)
folders = sorted(glob.glob(os.path.join(ROOT, "20*")))
total_folders = len(folders)

for idx, folder in enumerate(folders, 1):
    date_str = os.path.basename(folder)
    html_files = glob.glob(os.path.join(folder, "*.html"))
    print(f"▶ 진행률: {idx}/{total_folders} | {date_str} 데이터 처리 중... (종목 수: {len(html_files)}개)")
    
    for html_path in html_files:
        stock_code = os.path.basename(html_path).replace('.html', '')
        
        try:
            html_content = open(html_path, encoding="utf-8", errors="ignore").read()
            try: tables = pd.read_html(StringIO(html_content), flavor='lxml')
            except: tables = pd.read_html(StringIO(html_content), flavor='html5lib')
            
            close_p, prev_p, open_p, high_p, low_p, vol, vol_amt = [None] * 7
            high_52, low_52, marcap, foreign_rate, marcap_rank = [None] * 5
            per, eps, est_per, est_eps, pbr, bps = [None] * 6
            div_yield, roe, debt_ratio, op_profit, op_margin = [None] * 5
            
            for t in tables:
                cols_str = "".join([str(c) for c in t.columns])
                if '종가' in cols_str and '전일비' in cols_str:
                    date_col = next((c for c in t.columns if '날짜' in str(c) or '일자' in str(c)), None)
                    if date_col is not None:
                        valid_t = t[t[date_col].notna()]
                        if not valid_t.empty:
                            close_col = next((c for c in t.columns if '종가' in str(c)), None)
                            if close_col: close_p = clean_num(valid_t.iloc[0][close_col])

                for _, row in t.iterrows():
                    row_header = str(row.iloc[0]).replace(' ', '')
                    if 'ROE' in row_header or '부채비율' in row_header or '영업이익' in row_header:
                        for v in reversed(row.values[1:]):
                            clean_v = clean_num(v)
                            if clean_v is not None:
                                if 'ROE' in row_header: roe = clean_v
                                elif '부채비율' in row_header: debt_ratio = clean_v
                                elif '영업이익률' in row_header: op_margin = clean_v
                                elif '영업이익' in row_header and '률' not in row_header: op_profit = clean_v
                                break 

                    for i in range(len(row)):
                        cell_str = str(row.iloc[i]).replace(' ', '')
                        
                        if type(cell_str) == str and not cell_str.isdigit():
                            nums = re.findall(r'\d{1,3}(?:,\d{3})+|\d+', cell_str)
                            if nums:
                                first_num = float(nums[0].replace(',', ''))
                                if '시가' in cell_str and '시가총액' not in cell_str: open_p = first_num
                                elif '고가' in cell_str: high_p = first_num
                                elif '저가' in cell_str: low_p = first_num
                                elif '거래량' in cell_str and '매수' not in cell_str and '매도' not in cell_str: vol = first_num
                                elif '거래대금' in cell_str: vol_amt = first_num * 1000000 if '백만' in cell_str else first_num
                                elif '전일' in cell_str and '전일비' not in cell_str: prev_p = first_num

                        if i < len(row) - 1:
                            key_raw = str(row.iloc[i]).replace(' ', '')
                            val_raw = str(row.iloc[i+1])
                            
                            if '시가총액' in key_raw and '순위' not in key_raw: marcap = clean_num(val_raw)
                            elif '시가총액순위' in key_raw: marcap_rank = clean_num(re.sub(r'[^0-9]', '', val_raw))
                            elif '외국인소진율' in key_raw: foreign_rate = clean_num(val_raw)
                            elif '52주최고' in key_raw:
                                parts = val_raw.split('l')
                                high_52 = clean_num(parts[0])
                                low_52 = clean_num(parts[1]) if len(parts) > 1 else None
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
                            elif '배당수익률' in key_raw: div_yield = clean_num(val_raw)
                            
            data_by_stock[stock_code].append({
                '날짜': date_str, '종목코드': stock_code,
                '현재가(종가)': close_p, '기준가(전일)': prev_p, 
                '시가': open_p, '고가': high_p, '저가': low_p, 
                '거래량': vol, '거래대금': vol_amt,
                '52주최고': high_52, '52주최저': low_52, 
                '시가총액': marcap, '시가총액순위': marcap_rank, '외인소진율': foreign_rate,
                'PER': per, 'EPS': eps, '추정PER': est_per, '추정EPS': est_eps, 
                'PBR': pbr, 'BPS': bps, '배당수익률': div_yield,
                '영업이익': op_profit, '영업이익률': op_margin, 'ROE': roe, '부채비율': debt_ratio
            })
            
        except Exception as e:
            continue

print("\n" + "=" * 80)
print("💾 개별 종목 CSV 파일 저장 중...")

success_files = 0
for stock_code, rows in data_by_stock.items():
    df_result = pd.DataFrame(rows)
    df_result['날짜'] = pd.to_datetime(df_result['날짜'])
    df_result = df_result.sort_values('날짜').reset_index(drop=True)
    
    # 💡 에러 방지용 .round() 추가 완료
    int_cols = ['현재가(종가)', '기준가(전일)', '시가', '고가', '저가', '거래량', '거래대금', '52주최고', '52주최저', '영업이익', '시가총액순위']
    for col in int_cols:
        df_result[col] = pd.to_numeric(df_result[col], errors='coerce').round().astype('Int64')
    
    output_filename = os.path.join(OUTPUT_DIR, f"{stock_code}_history.csv")
    df_result.to_csv(output_filename, index=False, encoding='utf-8-sig')
    success_files += 1

print(f"🎉 [Phase 1 완료] 총 {success_files}개 종목의 데이터(23개 변수)가 '{OUTPUT_DIR}' 폴더에 개별 CSV로 저장되었습니다!")
