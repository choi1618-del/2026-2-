import time
import os
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from validator import StockDataValidator
from email_notifier import NaverMailNotifier

STOCK_INFO = {
    '000810': '삼성화재',
    '005830': 'DB손해보험',
    '001450': '현대해상',
    '000815': '삼성화재우',
    '000400': '롯데손해보험',
    '000370': '한화손해보험',
    '003690': '코리안리',
    '244920': '에이플러스에셋',
    '031210': '서울보증보험',
    '211050': '인카금융서비',
    '000540': '흥국화재',
    '000545': '흥국화재우'
}

def clean_numeric(val):
    """문자열 형태의 수치를 숫자(int, float) 데이터로 정제합니다."""
    if pd.isna(val) or val is None: return None
    val_str = str(val).strip()
    if val_str in ['-', 'N/A', 'NaN', '', 'None', 'null']: return None
    val_str = val_str.replace(',', '')

    if '%' in val_str or '배' in val_str:
        try: return float(val_str.replace('%', '').replace('배', '').strip())
        except ValueError: return None

    if '백만' in val_str:
        num_part = re.sub(r'[^0-9\.-]', '', val_str)
        try: return int(float(num_part) * 1_000_000)
        except ValueError: return None

    if '조' in val_str or '억' in val_str:
        total = 0
        match_jo = re.search(r'([0-9\.]+)\s*조', val_str)
        match_eok = re.search(r'([0-9\.]+)\s*억', val_str)
        if match_jo: total += float(match_jo.group(1)) * 1_000_000_000_000
        if match_eok: total += float(match_eok.group(1)) * 100_000_000
        if total > 0: return int(total)

    clean_str = val_str.replace('원', '').replace('주', '').strip()
    try:
        return float(clean_str) if '.' in clean_str else int(clean_str)
    except ValueError:
        return None

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


def crawl_stock_details(driver, code):
    # PC 메인 주소 접속 (수정주가 및 고정 태그 지원)
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # 1. 현재가 확실하게 추출
    current_price = None
    no_today = soup.select_one('.no_today .blind')
    if no_today:
        current_price = clean_numeric(no_today.text)

    # 2. 가격 관련 지표 추출 헬퍼
    def get_price_info(keyword):
        span = soup.find('span', string=re.compile(keyword))
        if span and span.parent:
            blind = span.parent.select_one('.blind')
            if blind: return clean_numeric(blind.text)
        return None

    # 3. 52주 최고/최저 (모든 업종 표기법 대응 및 수정주가 추출 정규식 적용)
    high_52, low_52 = None, None
    th_52 = soup.find('th', string=re.compile(r'52.*최고'))
    if th_52:
        td_52 = th_52.find_next_sibling('td')
        if td_52:
            nums = re.findall(r'([0-9,]+)', td_52.text)
            if len(nums) >= 2:
                high_52, low_52 = clean_numeric(nums[0]), clean_numeric(nums[1])

    # 4. 시가총액 (단위: 억원 -> 원 환산)
    market_sum = None
    ms_em = soup.select_one('#_market_sum')
    if ms_em:
        val = clean_numeric(ms_em.text)
        if val: market_sum = int(val * 100_000_000)

    # 5. 테이블 지표 추출
    def get_table_val(keyword):
        th = soup.find('th', string=re.compile(keyword))
        if th:
            td = th.find_next_sibling('td')
            if td:
                em = td.find('em')
                return clean_numeric(em.text) if em else clean_numeric(td.text)
        return None

    # 6. 주당배당금 추출
    div_yield = None
    th_div = soup.find('th', string=re.compile('주당배당금'))
    if th_div and th_div.parent:
        tds = th_div.parent.find_all('td')
        for td in reversed(tds):
            val = clean_numeric(td.text)
            if val is not None:
                div_yield = val
                break

    data = {
        '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '종목코드': f'="{code}"',
        '종목명': STOCK_INFO[code],
        '현재가': current_price,
        '기준가': get_price_info('전일'),
        '시가': get_price_info('시가'),
        '고가': get_price_info('고가'),
        '저가': get_price_info('저가'),
        '거래량': get_price_info('거래량'),
        '거래대금': int(get_price_info('거래대금') * 1_000_000) if get_price_info('거래대금') else None,
        '52주최고': high_52,
        '52주최저': low_52,
        '시가총액': market_sum,
        '외인소진율': get_table_val('외국인소진율'),
        'PER': clean_numeric(soup.select_one('#_per').text) if soup.select_one('#_per') else None,
        'EPS': clean_numeric(soup.select_one('#_eps').text) if soup.select_one('#_eps') else None,
        '추정PER': clean_numeric(soup.select_one('#_cns_per').text) if soup.select_one('#_cns_per') else None,
        '추정EPS': clean_numeric(soup.select_one('#_cns_eps').text) if soup.select_one('#_cns_eps') else None,
        'PBR': clean_numeric(soup.select_one('#_pbr').text) if soup.select_one('#_pbr') else None,
        'BPS': clean_numeric(soup.select_one('#_bps').text) if soup.select_one('#_bps') else None,
        '배당수익률': clean_numeric(soup.select_one('#_dvr').text) if soup.select_one('#_dvr') else None,
        '주당배당금': div_yield
    }
    return data

def main():
    print(f"🚀 손해보험 주가 크롤링 시작! ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    validator = StockDataValidator(STOCK_INFO)
    notifier = NaverMailNotifier()
    driver = setup_driver()

    try:
        all_data = []
        for code in STOCK_INFO.keys():
            print(f"[{STOCK_INFO[code]}] 수집 중...")
            stock_data = crawl_stock_details(driver, code)
            all_data.append(stock_data)

        if all_data:
            df = pd.DataFrame(all_data)
            
            file_name = f"insurance_stock_data_{datetime.now().strftime('%Y%m%d')}.csv"
            file_exists = os.path.exists(file_name)

            try:
                df.to_csv(file_name, mode='a', header=not file_exists, index=False, encoding='utf-8-sig')
                print(f"✅ 수집 완료! [{file_name}] 파일 저장 성공")
            except PermissionError:
                backup_file = f"insurance_stock_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                df.to_csv(backup_file, index=False, encoding='utf-8-sig')
                print(f"⚠️ [{file_name}] 파일이 열려 있어 [{backup_file}] 에 저장되었습니다.")

            print("🔍 [수집 데이터 검증 진행 중...]")
            report = validator.validate(df)

            print("📧 [네이버 메일 알림 발송 중...]")
            notifier.send_report(report)    

    except Exception as e:
        print(f"\n크롤링 중 오류가 발생했습니다: {e}")
    finally:
        driver.quit()
        print("🛑 브라우저 종료 및 크롤링 완료.")

if __name__ == "__main__":
    main()
