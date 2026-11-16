# 1주차 면담 준비 자료

---

## 1. 원본 HTML 자료 확인

- 데이터 수집 기간: 2024-03-27 \~ 2026-09-02
- 서번에 저장된 날짜 폴더 수: 591개(25년 7월 결측은 날짜 폴더 수에서 제외)
- 보유 종목 수: 4307개
- 결측일(주말/휴장/누락): 299일

[그림 1. 결측일 분포 그림]

[week1_submit.py](https://github.com/choi1618-del/2026-2-/blob/main/week1_submit.py "week1_submit.py")
[week1_scope_plot.png](https://github.com/choi1618-del/2026-2-/blob/main/week1_scope_plot.png "week1_scope_plot.png")

[그림 2. html 내의 데이터 확인]
C:\Users\gayou\Pictures\Screenshots\스크린샷 2026-11-09 024149.png

---

## 2. 데이터 확인을 토대로 csv파일로 압축

[extract_samsung.py](https://github.com/choi1618-del/2026-2-/blob/main/extract_samsung.py "extract_samsung.py")

ls -l samsung_fire_master_23vars.csv
head -n 5 samsung_fire_master_23vars.csv

- 삼성화재 파일(000810.html)이 없는 날:  8개
- 삼성화재 파일이 정상적으로 존재하는 날: 583개

---

## 3. 추가적인 결측 확인 및 다룸
- 다른 종목들은 2주차 실습에서 필요한 csv 파일로 압축 후 확인할 예정

### 3-1. 업종 재분류와 액면분할 처리

[상장주식수는 평상시엔 절대 변하지 않는 고정값 - 어제 주식 수와 오늘 주식 수의 차이가 있는 것을 탐지]
- 2025-05-19: 47,374,837주 ➔ 46,011,155주 (변동: -1,363,682주)
- 2026-04-17: 46,011,155주 ➔ 44,647,473주 (변동: -1,363,682주)
- 주식 수가 줄어듦을 확인 -> 주식들의 희소성이 커져 1주당 주가가 올라가는 주주환원 정책

### 3-2. 25년 7월 결측치 처리

fix_samsung_july.py

---

## 4. 면담 피드백

### 4-1. 피드백

1. 재무데이터와 그외 데이터들 포함시켜서 csv파일 만들기
2. 종목 전체 다 해보기....
3. 질문 자체는 깊을 필요없음. 내가 빅데이터를 읽어서 질문에 답할 수 있음에 집중. 빅데이터를 읽었다!!

---

# 2주차 면담 준비 자료

---

## 1. 전체 업종 csv파일로 압축

**전체 업종에 대한 csv파일 생성**

[extract_all_stocks.py](https://github.com/choi1618-del/2026-2-/blob/mainextract_all_stocks.py "extract_all_stocks.py")

- stock_csv_results 폴더 안에 종목별로 수백 개의 CSV 파일 저장
- /home/s202420495/stock_csv_results 폴더 안에 000810_history.csv, 005930_history.csv처럼 종목코드 이름표가 붙은 약 940여 개의 개별 파일 생성

**전체 업종 2025년 7월 결측치 이어붙이기(최종 csv 파일)**

[update_july_inplace.py]

---

## 2. 질문에 대한 답

### 2-1. 시가총액 순위는 2년 반 동안 얼마나 바뀌었는가. 2년 반 전 상위 종목 중 지금도 상위인 것은 무엇이고, 새로 들어온 종목은 어느 업종인가.

[analyze_q1_exact_2years.py]

- 우선주, ETF, 스팩을 제외
- 코스피만 있는 초반보다 모든 업종이 어느정도 다 들어왔을 때(24년 4월 15일)를 기분으로 첫 시가총액 순위를 봄

[2년 전(2024-04-15) 시가총액 TOP 10 보통주 현황]
| 시작 순위 | 종목명 | 종목코드 | 종료 순위 |
|---|---|---|---|
| 1 | 삼성전자 | 005930 | 1 |
| 2 | SK하이닉스 | 000660 | 2 |
| 3 | LG에너지솔루션 | 373220 | 4 |
| 4 | 삼성바이오로직스 | 207940 | 7 |
| 5 | 현대차 | 005380 | 3 |
| 6 | 기아 | 000270 | 9 |
| 7 | 셀트리온 | 068270 | 16 |
| 8 | POSCO홀딩스 | 005490 | 25 |
| 9 | NAVER | 035420 | 24 |
| 10 | LG화학 | 051910 | 33 |

[2026년 시가총액 TOP 10 보통주 현황]

| 종료 순위 | 종목명 | 종목코드 | 시작 순위 |
|---|---|---|---|
| 1 | 삼성전자 | 005930 | 1 |
| 2 | SK하이닉스 | 000660 | 2 |
| 3 | 현대차 | 005380 | 5 |
| 4 | LG에너지솔루션 | 373220 | 3 |
| 5 | SK스퀘어 | 402340 | 35 |
| 6 | 한화에어로스페이스 | 012450 | 38 |
| 7 | 삼성바이오로직스 | 207940 | 4 |
| 8 | 두산에너빌리티 | 034020 | 44 |
| 9 | 기아 | 000270 | 6 |
| 10 | KB금융 | 105560 | 13 |

[top10_rank_jump.png](https://github.com/choi1618-del/2026-2-/blob/main/top10_rank_jump.png "top10_rank_jump.png")

[2026년 TOP 20 중 2년 전(2024년) 20위 밖에서 치고 올라온 신흥 강자들]

| 종료 순위 | 시작 순위 | 종목명 | 종목코드 |
|---|---|---|---|
| 5 | 35 | SK스퀘어 | 402340 |
| 6 | 38 | 한화에어로스페이스 | 012450 |
| 8 | 44 | 두산에너빌리티 | 034020 |
| 13 | 39 | HD현대중공업 | 329180 |
| 15 | 34 | 삼성전기 | 009150 |
| 17 | 81 | 미래에셋증권 | 006800 |
| 18 | 45 | 한화오션 | 042660 |
| 20 | 50 | HD현대일렉트릭 | 267260 |

[emerging_climbers_jump.png](https://github.com/choi1618-del/2026-2-/blob/main/emerging_climbers_jump.png "emerging_climbers_jump.png")

- 새로 들어온 종목은 어느 업종: SK스퀘어, 한화에어로스페이스, 두산에너빌리티, KB금융
- 방산·조선·전력설비 계열(기계·중공업), 증권(가장 많이 올라 20위권에 들어옴) 업종이 커다란 폭으로 상승
- 액면분할 확인

### 2-2. 업종 간 수익률의 차이는 2년 반 동안 벌어졌는가, 좁혀졌는가. 몇 개 업종이 그 차이를 만들었는가.

[analyze_q2_official.py]

- 업종이 어디 속해있는지 종목별로 구분함
- 순수 보통주의 공식 업종 매핑표('sector_map.csv') 생성

[q2_sector_divergence.png](https://github.com/choi1618-del/2026-2-/blob/main/q2_sector_divergence.png "q2_sector_divergence.png")
[q2_top_sectors.png](https://github.com/choi1618-del/2026-2-/blob/main/q2_top_sectors.png "q2_top_sectors.png")
