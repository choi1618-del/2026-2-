import os
import re
from datetime import datetime
import numpy as np
import pandas as pd


class StockDataValidator:

    def __init__(self, target_stock_dict):
        """:param target_stock_dict: 수집 기대 대상 종목 사전 {'종목코드': '종목명'}"""
        self.target_stock_dict = target_stock_dict
        self.expected_count = len(target_stock_dict)

    def clean_numeric(self, val):
        """쉼표, 단위(원, 주, %, 배, 억, 조 등)가 포함된 문자열을 정수/실수로 변환 변환 불가 시 np.nan 반환"""
        if pd.isna(val) or val in ['-', 'N/A', 'NaN', '', 'None']:
            return np.nan

        val_str = str(val).replace(',', '').strip()

        # 1) 퍼센트(%) 및 배수(배) 단위 처리
        if '%' in val_str or '배' in val_str:
            val_str = val_str.replace('%', '').replace('배', '')
            try:
                return float(val_str)
            except ValueError:
                return np.nan

        # 2) 단순 화폐/수량 단위 제거
        val_str = val_str.replace('원', '').replace('주', '')

        # 3) 시가총액/거래대금 '조', '억' 복합 단위 정수 변환 (예: "11조 5355억" -> 11535500000000)
        if '조' in val_str or '억' in val_str:
            total = 0.0
            match_jo = re.search(r'([0-9\.]+)\s*조', val_str)
            match_eok = re.search(r'([0-9\.]+)\s*억', val_str)

            if match_jo:
                total += float(match_jo.group(1)) * 1_000_000_000_000
            if match_eok:
                total += float(match_eok.group(1)) * 100_000_000
            if total > 0:
                return total

        try:
            if '.' in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return np.nan

    def validate(self, df):
        """수집된 DataFrame에 대해 종합 검증을 수행하고 결과 리포트를 반환"""
        issues = []
        status = '정상'

        # -------------------------------------------------------------
        # 검증 1. 수집 건수 및 종목 일치 검증
        # -------------------------------------------------------------
        collected_codes = [
            str(code).replace('="', '').replace('"', '').zfill(6)
            for code in df['종목코드']
        ]
        collected_count = len(collected_codes)
        missing_codes = set(self.target_stock_dict.keys()) - set(collected_codes)

        if collected_count != self.expected_count or missing_codes:
            status = '경고'
            issues.append(
                f'[건수 불일치] 기대: {self.expected_count}건 / 실제: {collected_count}건'
                f' (누락 종목: {list(missing_codes)})'
            )

        # -------------------------------------------------------------
        # 검증 2. 사이트 구조 변경 감지 (Silent Failure 방지)
        # -------------------------------------------------------------
        # 모든 종목의 필수 지표(현재가)가 결측치('-')인 경우 사이트 구조 변경으로 간주
        invalid_prices = df['현재가'].apply(lambda x: x in ['-', 'N/A', '', None]).sum()
        if len(df) > 0 and invalid_prices == len(df):
            status = '경고'
            issues.append(
                '[사이트 구조 변경 의심] 모든 종목의 현재가 수집에 실패했습니다.'
                ' HTML 태그/ID 변경 여부를 확인하세요.'
            )

        # -------------------------------------------------------------
        # 검증 3. 수치 정제 및 변환 검증
        # -------------------------------------------------------------
        df_cleaned = df.copy()
        check_cols = ['현재가', '시가', '고가', '저가', '거래량', '시가총액', 'PER', 'PBR']

        conversion_errors = 0
        for col in check_cols:
            if col in df_cleaned.columns:
                df_cleaned[col + '_clean'] = df_cleaned[col].apply(self.clean_numeric)
                if col in ['현재가', '시가총액']:
                    failed_cnt = df_cleaned[col + '_clean'].isna().sum()
                    if failed_cnt > 0:
                        conversion_errors += failed_cnt

        if conversion_errors > 0:
            if status != '경고':
                status = '주의'
            issues.append(
                f'[수치 변환 오류] 필수 수치 데이터 변환 실패건: {conversion_errors}건'
            )

        # -------------------------------------------------------------
        # 검증 4. 가격제한폭(±30%) 초과 및 수치 이상치 검증
        # -------------------------------------------------------------
        price_anomalies = []
        for idx, row in df_cleaned.iterrows():
            current_p = row.get('현재가_clean', np.nan)
            open_p = row.get('시가_clean', np.nan)

            if pd.notna(current_p) and pd.notna(open_p) and open_p > 0:
                change_rate = (current_p - open_p) / open_p
                if abs(change_rate) > 0.30:
                    price_anomalies.append(
                        f"{row['종목명']}(시가 대비 {change_rate*100:+.1f}%)"
                    )

        if price_anomalies:
            status = '경고'
            issues.append(
                f"[가격제한폭 초과] 시가 대비 ±30% 이상 급변동: {', '.join(price_anomalies)}"
            )

        # -------------------------------------------------------------
        # 검증 5. 비논리적 음수값 검증
        # -------------------------------------------------------------
        negative_issues = []
        for col in ['현재가_clean', '시가총액_clean', '거래량_clean']:
            if col in df_cleaned.columns:
                neg_cnt = (df_cleaned[col] <= 0).sum()
                if neg_cnt > 0:
                    negative_issues.append(f"{col.replace('_clean', '')}(0 이하 {neg_cnt}건)")

        if negative_issues:
            status = '경고'
            issues.append(f"[비논리 수치] {', '.join(negative_issues)}")

        # -------------------------------------------------------------
        # 최종 리포트 반환
        # -------------------------------------------------------------
        return {
            'status': status,
            'collected_count': collected_count,
            'expected_count': self.expected_count,
            'issues': issues,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'df_cleaned': df_cleaned,
        }

    def print_random_sample_crosscheck(self, df, sample_n=2):
        """화면 원자료 대조용 샘플 출력 함수"""
        sample_df = df.sample(min(sample_n, len(df)))
        print('\n' + '=' * 60)
        print('🔍 [수동 원자료 대조 샘플 출력]')
        print('=' * 60)
        for _, row in sample_df.iterrows():
            print(f"• 종목명: {row['종목명']} ({row['종목코드']})")
            print(f"  - 원본 현재가: {row['현재가']} | 원본 시가총액: {row['시가총액']}")
            print(f"  - 원본 PER: {row['PER']} | 원본 PBR: {row['PBR']}")
        print('=' * 60 + '\n')
