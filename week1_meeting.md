# 1주차 면담 준비 자료

---

## 1. 원본 HTML 자료 확인

- 데이터 수집 기간: 2024-03-27 \~ 2026-09-02
- 서번에 저장된 날짜 폴더 수: 591개(25년 7월 결측은 날짜 폴더 수에서 제외)
- 보유 종목 수: 4307개
- 결측일(주말/휴장/누락): 299일

**[그림 1. 결측일 분포 그림]**

[week1_submit.py](https://github.com/choi1618-del/2026-2-/blob/main/week1_submit.py "week1_submit.py")

[week1_scope_plot.png](https://github.com/choi1618-del/2026-2-/blob/main/week1_scope_plot.png "week1_scope_plot.png")

**[그림 2. html 내의 데이터 확인]**

C:\Users\gayou\Pictures\Screenshots\스크린샷 2026-11-09 024149.png



---

## 2. 데이터 확인을 토대로 csv파일로 압축

[extract_samsung.py](https://github.com/choi1618-del/2026-2-/blob/main/extract_samsung.py "extract_samsung.py")

ls -l samsung_fire_all.csv

head -n 5 samsung_fire_all.csv

- 삼성화재 파일(000810.html)이 없는 날:  8개
- 삼성화재 파일이 정상적으로 존재하는 날: 583개



## 3. 추가적인 결측 확인 및 다룸
- 다른 종목들은 2주차 실습에서 필요한 csv 파일로 압축 후 확인할 예정

### 3-1. 업종 재분류와 액면분할 처리

[상장주식수는 평상시엔 절대 변하지 않는 고정값 - 어제 주식 수와 오늘 주식 수의 차이가 있는 것을 탐지]
- 2025-05-19: 47,374,837주 ➔ 46,011,155주 (변동: -1,363,682주)
- 2026-04-17: 46,011,155주 ➔ 44,647,473주 (변동: -1,363,682주)
- 주식 수가 줄어듦을 확인 -> 주식들의 희소성이 커져 1주당 주가가 올라가는 주주환원 정책

### 3-2. 25년 7월 결측치 처리

- 생성한 CSV 파일명:
- 변환 후 데이터 행 수:
- 변환 후 컬럼 수:
- 저장된 데이터 기간:
- 변환 과정에서 확인한 문제:

**[그림 4. CSV 파일 생성 및 데이터 확인 화면]**



---

## 4. 면담 피드백

### 4-1. 면담 사항

1. 

### 4-2. 피드백

1. 
