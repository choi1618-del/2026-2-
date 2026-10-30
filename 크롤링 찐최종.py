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

# 수집 대상 종목 리스트 (서울보증보험 '031210' 정상 복구 완료)
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
    # 1단계: 기존에 잘 되던 모바일 종합(total) 탭에서 현재가 및 일반 지표 수집
    url_mobile = f"https://stock.naver.com/domestic/stock/{code}/total"
    driver.get(url_mobile)
    time.sleep(3.0)
    soup_mobile = BeautifulSoup(driver.page_source, 'html.parser')

    # 실시간 '현재가' 추출
    current_price_str = None
    price_tag = soup_mobile.select_one('strong[class*="price"]')
    if price_tag:
        current_price_str = price_tag.get_text(strip=True)
    else:
        title_text = soup_mobile.title.text if soup_mobile.title else ""
        match = re.search(r'([0-9,]+)\s*[+-]', title_text)
        if match:
            current_price_str = match.group(1)

    raw_data = {
        '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '종목코드': f'="{code}"',
        '종목명': STOCK_INFO[code],
        '현재가': current_price_str,
        '기준가': extract_metric(soup_mobile, ['기준가']),
        '시가': extract_metric(soup_mobile, ['시가']),
        '고가': extract_metric(soup_mobile, ['고가']),
        '저가': extract_metric(soup_mobile, ['저가']),
        '거래량': extract_metric(soup_mobile, ['거래량']),
        '거래대금': extract_metric(soup_mobile, ['대금', '거래대금']),
        '시가총액': extract_metric(soup_mobile, ['시가총액', '시총']),
        '외인소진율': extract_metric(soup_mobile, ['외인소진율', '외국인지분율']),
        'PER': extract_metric(soup_mobile, ['PER']),
        'EPS': extract_metric(soup_mobile, ['EPS']),
        '추정PER': extract_metric(soup_mobile, ['추정PER']),
        '추정EPS': extract_metric(soup_mobile, ['추정EPS']),
        'PBR': extract_metric(soup_mobile, ['PBR']),
        'BPS': extract_metric(soup_mobile, ['BPS']),
        '배당수익률': extract_metric(soup_mobile, ['배당수익률']),
        '주당배당금': extract_metric(soup_mobile, ['주당배당금'])
    }

    # 2단계: PC 종목분석 페이지로 이동해서 '수정주가' 기준의 52주 최고/최저가만 따로 정확히 읽어오기
    high_52, low_52 = None, None
    try:
        url_pc = f"https://finance.naver.com/item/main.naver?code={code}"
        driver.get(url_pc)
        time.sleep(1.5)
        soup_pc = BeautifulSoup(driver.page_source, 'html.parser')

        th_52 = soup_pc.find('th', string=re.compile(r'52.*최고'))
        if th_52:
            td_52 = th_52.find_next_sibling('td')
            if td_52:
                nums = re.findall(r'([0-9,]+)', td_52.text)
                if len(nums) >= 2:
                    high_52, low_52 = clean_numeric(nums[0]), clean_numeric(nums[1])
    except Exception as e:
        print(f"⚠️ [{STOCK_INFO[code]}] PC 52주 데이터 수집 중 예외 발생: {e}")

    data = {
        '수집시간': raw_data['수집시간'],
        '종목코드': raw_data['종목코드'],
        '종목명': raw_data['종목명'],
        '현재가': clean_numeric(raw_data['현재가']),
        '기준가': clean_numeric(raw_data['기준가']),
        '시가': clean_numeric(raw_data['시가']),
        '고가': clean_numeric(raw_data['고가']),
        '저가': clean_numeric(raw_data['저가']), 
        '거래량': clean_numeric(raw_data['거래량']),
        '거래대금': clean_numeric(raw_data['거래대금']),
        '52주최고': high_52,                      # PC 수정주가 기준 최고가 적용[cite: 1, 2]
        '52주최저': low_52,                      # PC 수정주가 기준 최저가 적용[cite: 1, 2]
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
