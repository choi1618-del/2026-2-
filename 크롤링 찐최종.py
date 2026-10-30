import time
import os
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
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
    '244920': '에이플러스에셋',
    '031210': '서울보증보험',
    '211050': '인카금융서비',
    '000540': '흥국화재',
    '000545': '흥국화재우'
}

MAX_RETRY = 3  # 현재가 / 52주 값 수집 실패 시 재시도 횟수


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


# ──────────────────────────────────────────────────────────────
# 현재가 / 52주 최고·최저 수집 (화면 텍스트 기반)
# ──────────────────────────────────────────────────────────────
def get_body_text(driver, url, timeout=15):
    """페이지를 열고 '52주 최저' 문구와 현재가(○○원)가 화면에 뜰 때까지 기다린 뒤 보이는 텍스트를 반환."""
    driver.get(url)

    def loaded(d):
        txt = d.find_element(By.TAG_NAME, 'body').text
        return ('52주' in txt) and re.search(r'[0-9][0-9,]*\s*원', txt) is not None

    try:
        WebDriverWait(driver, timeout).until(loaded)
    except TimeoutException:
        pass  # 타임아웃이어도 일단 현재 텍스트로 시도
    time.sleep(1.0)  # 숫자가 완전히 렌더링될 여유 시간
    return driver.find_element(By.TAG_NAME, 'body').text


def parse_current_price(text):
    """상단 헤더(종목명 아래, '시세정보' 위)의 첫 번째 '○○,○○○원' 을 현재가로 사용."""
    head = text.split('시세정보')[0] if '시세정보' in text else text[:600]
    m = re.search(r'([0-9][0-9,]*)\s*원', head)
    return clean_numeric(m.group(1)) if m else None


def parse_52week_adjusted(text):
    """종목분석 표의 '52Weeks 최고/최저   64,800원 / 39,650원' (수정주가 기준) 추출. 반환: (최고, 최저)"""
    m = re.search(
        r'52\s*Weeks?\s*최고\s*/\s*최저\s*([0-9][0-9,]*)\s*원?\s*/\s*([0-9][0-9,]*)\s*원?',
        text, re.I)
    if m:
        return clean_numeric(m.group(1)), clean_numeric(m.group(2))
    return None, None


def _has_52weeks(d):
    return re.search(r'52\s*Weeks?', d.find_element(By.TAG_NAME, 'body').text, re.I)


def open_analysis_tab(driver, timeout=15):
    """'종목분석' 탭으로 이동. 링크(href)가 있으면 직접 이동, 없으면 클릭. 성공 여부 반환."""
    xpaths = [
        "//a[normalize-space()='종목분석']",
        "//button[normalize-space()='종목분석']",
        "//*[self::a or self::button or self::span or self::li][contains(normalize-space(.),'종목분석')]",
    ]
    for xp in xpaths:
        for el in driver.find_elements(By.XPATH, xp):
            href = el.get_attribute('href')
            try:
                if href and href.startswith('http'):
                    driver.get(href)
                else:
                    driver.execute_script("arguments[0].click();", el)
                WebDriverWait(driver, timeout).until(_has_52weeks)
                return True
            except Exception:
                continue
    return False


def dump_debug(driver, code, tag):
    """수집 실패 시 화면 캡처/텍스트/HTML을 저장해 원인 분석에 사용."""
    try:
        base = f"debug_{code}_{tag}"
        driver.save_screenshot(base + ".png")
        with open(base + ".txt", "w", encoding="utf-8") as f:
            f.write(driver.find_element(By.TAG_NAME, 'body').text)
        with open(base + ".html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"🛠 디버그 파일 저장: {base}.png / .txt / .html")
    except Exception as e:
        print(f"디버그 저장 실패: {e}")


INFO_URL = "https://stock.naver.com/domestic/stock/{code}/info/company"


def fetch_52week_adjusted(driver, code, timeout=15):
    """종목분석 페이지에서 '52Weeks 최고/최저'(수정주가)를 읽어 (최고, 최저) 반환."""
    name = STOCK_INFO[code]
    driver.get(INFO_URL.format(code=code))
    try:
        WebDriverWait(driver, timeout).until(_has_52weeks)
    except TimeoutException:
        print(f"⚠️ [{name}] 종목분석 페이지에서 '52Weeks' 항목이 로딩되지 않음")
        return None, None
    time.sleep(0.5)
    body = driver.find_element(By.TAG_NAME, 'body').text
    high_52, low_52 = parse_52week_adjusted(body)
    if high_52 is None:
        print(f"⚠️ [{name}] '52Weeks 최고/최저' 값을 읽지 못함")
    else:
        print(f"✔ [{name}] 종목분석 페이지(수정주가) 52주 수집: {high_52:,} / {low_52:,}")
    return high_52, low_52


def fetch_price_and_52week(driver, code):
    """
    - 현재가: 왼쪽 헤더 (화면에 보이는 값)
    - 52주 최고/최저: 오른쪽 종목분석 표 '52Weeks 최고/최저' (수정주가 기준)
    값이 비면 최대 MAX_RETRY회 재시도합니다.
    """
    url = f"https://stock.naver.com/domestic/stock/{code}/total"
    name = STOCK_INFO[code]
    price, high_52, low_52 = None, None, None
    soup = None

    for attempt in range(1, MAX_RETRY + 1):
        text = get_body_text(driver, url)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 1) 현재가
        price = parse_current_price(text)
        if price is None:
            title_text = soup.title.text if soup.title else ""
            m = re.search(r'([0-9][0-9,]{2,})', title_text)
            if m:
                price = clean_numeric(m.group(1))

        # 2) 종목분석(기업현황) 페이지 직접 접속 → 52Weeks 최고/최저 (수정주가)
        high_52, low_52 = fetch_52week_adjusted(driver, code)
        if high_52 is None:
            dump_debug(driver, code, f"try{attempt}")

        if price is not None and high_52 is not None and low_52 is not None and low_52 <= high_52:
            if not (low_52 <= price <= high_52):
                print(f"ℹ️ [{name}] 현재가({price})가 52주 범위({low_52}~{high_52}) 밖입니다 "
                      f"(NXT 시세 등 기준 차이일 수 있음)")
            break

        print(f"⚠️ [{name}] 시도 {attempt}/{MAX_RETRY} - 현재가={price}, 52주최고={high_52}, 52주최저={low_52}")
        time.sleep(1.5)

    # 폴백: PC 종목분석 페이지
    if high_52 is None or low_52 is None:
        try:
            driver.get(f"https://finance.naver.com/item/main.naver?code={code}")
            time.sleep(1.5)
            soup_pc = BeautifulSoup(driver.page_source, 'html.parser')
            th_52 = soup_pc.find('th', string=re.compile(r'52.*최고'))
            if th_52:
                td_52 = th_52.find_next_sibling('td')
                if td_52:
                    nums = re.findall(r'([0-9,]+)', td_52.text)
                    if len(nums) >= 2:
                        high_52, low_52 = clean_numeric(nums[0]), clean_numeric(nums[1])
                        print(f"❗ [{name}] 종목분석 탭 수집 실패 → 기존 PC 페이지 값으로 대체됨 (요청한 값과 다를 수 있음)")
        except Exception as e:
            print(f"⚠️ [{name}] PC 52주 폴백 중 예외 발생: {e}")

    if price is None or high_52 is None or low_52 is None:
        print(f"❌ [{name}] 최종 수집 실패: 현재가={price}, 52주최고={high_52}, 52주최저={low_52}")

    return price, high_52, low_52, soup


def crawl_stock_details(driver, code):
    # 현재가 + 52주 최고/최저 (재시도/검증 포함)
    price, high_52, low_52, soup_mobile = fetch_price_and_52week(driver, code)

    raw_data = {
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

    data = {
        '수집시간': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '종목코드': f'="{code}"',
        '종목명': STOCK_INFO[code],
        '현재가': price,
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
            print(f"   → 현재가 {stock_data['현재가']} / "
                  f"52주 최고 {stock_data['52주최고']} / 최저 {stock_data['52주최저']}")
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
