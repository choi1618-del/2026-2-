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

# 수집 대상 종목 리스트
STOCK_INFO = {
    '000810': '삼성화재',
    '005830': 'DB손해보험',
    '001450': '현대해상',
    '000815': '삼성화재우',
    '000400': '롯데손해보험',
    '000370': '한화손해보험',
    '003690': '코리안리',
    '031210': '에이플러스에셋',
    '211050': '인카금융서비스',
    '244920': '프리시젼바이오',
    '000540': '흥국화재',
    '000545': '흥국화재우'
}


def clean_numeric(val):
    """문자열 형태의 수치를 숫자(int, float) 데이터로 정제합니다."""
    if pd.isna(val) or val is None:
        return None

    val_str = str(val).strip()
    if val_str in ['-', 'N/A', 'NaN', '', 'None', 'null']:
        return None

    val_str = val_str.replace(',', '')

    if '%' in val_str or '배' in val_str:
        clean_str = val_str.replace('%', '').replace('배', '').strip()
        try:
            return float(clean_str)
        except ValueError:
            return None

    if '백만' in val_str:
        num_part = re.sub(r'[^0-9\.-]', '', val_str)
        try:
            return int(float(num_part) * 1_000_000)
        except ValueError:
            return None

    if '조' in val_str or '억' in val_str:
        total = 0
        match_jo = re.search(r'([0-9\.]+)\s*조', val_str)
        match_eok = re.search(r'([0-9\.]+)\s*억', val_str)

        if match_jo:
            total += float(match_jo.group(1)) * 1_000_000_000_000
        if match_eok:
            total += float(match_eok.group(1)) * 100_000_000

        if total > 0:
            return int(total)

    clean_str = val_str.replace('원', '').replace('주', '').strip()

    try:
        if '.' in clean_str:
            return float(clean_str)
        return int(clean_str)
    except ValueError:
        return None


def get_52_week_data_direct(soup):
    """
    태그 구조를 무시하고 페이지 전체 텍스트에서 정규표현식으로 52주 최고/최저가를 직접 추출합니다.
    """
    # 페이지의 모든 텍스트를 공백 한 칸으로 연결하여 추출
    page_text = soup.get_text(separator=' ', strip=True)
    
    # '52주 최고' 또는 '52주최고' 뒤에 나오는 숫자(콤마 포함) 추출
    high_match = re.search(r'52주\s*최고\s*([0-9,]+)', page_text)
    # '52주 최저' 또는 '52주최저' 뒤에 나오는 숫자(콤마 포함) 추출
    low_match = re.search(r'52주\s*최저\s*([0-9,]+)', page_text)
    
    high_val = clean_numeric(high_match.group(1)) if high_match else None
    low_val = clean_numeric(low_match.group(1)) if low_match else None
    
    return high_val, low_val


def extract_metric(soup, keywords):
    """HTML 테이블에서 라벨 키워드 바로 다음 td 값을 1:1로 정확하게 매칭합니다."""
    if isinstance(keywords, str):
        keywords = [keywords]

    ignore_keywords = ['제공됩니다', '통합 기준', '안내', '기준으로']

    for tr in soup.find_all('tr'):
        children = tr.find_all(['th', 'td'])
        for i in range(len(children) - 1):
            curr = children[i]
            curr_text = curr.get_text(strip=True)

            if any(ign in curr_text for ign in ignore_keywords):
                continue

            for kw in keywords:
                if kw in ['PER', 'EPS'] and '추정' in curr_text:
                    continue

                if kw in curr_text:
                    next_elem = children[i + 1]
                    if next_elem.name == 'td':
                        val = next_elem.get_text(strip=True)
                        if val and val != '-':
                            return val

    for tag in soup.find_all(['dt', 'span', 'strong', 'th', 'td', 'div']):
        text = tag.get_text(strip=True)
        if len(text) > 20 or any(ign in text for ign in ignore_keywords):
            continue

        for kw in keywords:
            if kw in ['PER', 'EPS'] and '추정' in text:
                continue

            if kw in text:
                sibling = tag.find_next_sibling()
                if sibling and sibling.get_text(strip=True):
                    s_text = sibling.get_text(strip=True)
                    if not any(ign in s_text for ign in ignore_keywords) and s_text != '-':
                        return s_text

    return '-'


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
    url = f"https://stock.naver.com/domestic/stock/{code}/info/company"
    driver.get(url)
    time.sleep(3.5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # 기존 지표들은 기존 함수로 추출
    raw_data = {
        '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '종목코드': f'="{code}"',
        '종목명': STOCK_INFO[code],
        '기준가': extract_metric(soup, ['기준가']),
        '시가': extract_metric(soup, ['시가']),
        '고가': extract_metric(soup, ['고가']),
        '저가': extract_metric(soup, ['저가']),
        '거래량': extract_metric(soup, ['거래량']),
        '거래대금': extract_metric(soup, ['대금', '거래대금']),
        '시가총액': extract_metric(soup, ['시가총액', '시총']),
        '외인소진율': extract_metric(soup, ['외인소진율', '외국인지분율']),
        'PER': extract_metric(soup, ['PER']),
        'EPS': extract_metric(soup, ['EPS']),
        '추정PER': extract_metric(soup, ['추정PER']),
        '추정EPS': extract_metric(soup, ['추정EPS']),
        'PBR': extract_metric(soup, ['PBR']),
        'BPS': extract_metric(soup, ['BPS']),
        '배당수익률': extract_metric(soup, ['배당수익률']),
        '주당배당금': extract_metric(soup, ['주당배당금'])
    }

    # 💡 [핵심 변경 사항] 텍스트 전체에서 정규식으로 직접 추출하는 함수 호출
    high_52, low_52 = get_52_week_data_direct(soup)

    data = {
        '수집시간': raw_data['수집시간'],
        '종목코드': raw_data['종목코드'],
        '종목명': raw_data['종목명'],
        '기준가': clean_numeric(raw_data['기준가']),
        '시가': clean_numeric(raw_data['시가']),
        '고가': clean_numeric(raw_data['고가']),
        '저가': clean_numeric(raw_data['저가']), 
        '거래량': clean_numeric(raw_data['거래량']),
        '거래대금': clean_numeric(raw_data['거래대금']),
        '52주최고': high_52,                      
        '52주최저': low_52,                      
        '시가총액': clean_numeric(raw_data['시가총액']),
        '외인소진율': clean_numeric(raw_data['외인소진율']),
        'PER': clean_numeric(raw_data['PER']),
        'EPS': clean_numeric(raw_data['EPS']),
        '추정PER': clean_numeric(raw_data['추정PER']),
        '추정EPS': clean_numeric(raw_data['추정EPS']),
        'PBR': clean_numeric(raw_data['PBR']),
        'BPS': clean_numeric(raw_data['BPS']),
        '배당수익률': clean_numeric(raw_data['배당수익률']),
        '주당배당금': clean_numeric(raw_data['주당배당금'])
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
            
            if '기준가' in df.columns and '현재가' not in df.columns:
                df['현재가'] = df['기준가']
            
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
