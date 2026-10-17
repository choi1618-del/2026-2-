# -*- coding: utf-8 -*-
import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

class NaverMailNotifier:

    def __init__(self):
        # 로컬 테스트용 .env 로드 (깃허브 환경에서는 에러 없이 자연스럽게 무시됩니다)
        load_dotenv(override=True)

        self.smtp_server = 'smtp.naver.com'
        self.smtp_port = 587

        # 💡 [핵심 수정] 깃허브 Secrets에 등록한 이름과 똑같이 맞춰줍니다.
        raw_user = os.getenv('NAVER_ID', '').strip()
        self.naver_pw = os.getenv('NAVER_PW', '').strip()

        # 로그인 시 사용할 Pure ID
        self.login_id = raw_user.split('@')[0] if raw_user else ''

        # 송신/수신 이메일 주소
        self.sender_email = (
            f'{self.login_id}@naver.com' if self.login_id else ''
        )
        self.receiver_email = os.getenv('RECEIVER_EMAIL', self.sender_email)

    def _format_report_to_string(self, report):
        if isinstance(report, str):
            return report

        status_emoji = '✅' if report.get('status') == '정상' else '⚠️'

        body_lines = [
            '📊 [손해보험 주가 수집 검증 리포트]',
            f"• 수집 시각: {report.get('timestamp')}",
            f"• 검증 상태: {status_emoji} {report.get('status')}",
            f"• 수집 건수: {report.get('collected_count')}건 / 기대 {report.get('expected_count')}건",
            '',
        ]

        issues = report.get('issues', [])
        if issues:
            body_lines.append('⚠️ [감지된 이슈 목록]')
            for issue in issues:
                body_lines.append(f'  - {issue}')
        else:
            body_lines.append(
                '🎉 특이사항 없이 모든 데이터가 정상 수집되었습니다.'
            )

        return '\n'.join(body_lines)

    def send_report(self, report):
        if not self.login_id or not self.naver_pw:
            # 💡 [수정됨] 에러 메시지를 더 명확하게 변경했습니다.
            print(
                '❌ 메일 전송 실패: 환경변수(Secrets)에서 NAVER_ID 또는 NAVER_PW를 찾을 수 없습니다.'
            )
            return

        try:
            msg = MIMEMultipart()

            report_text = self._format_report_to_string(report)
            status_str = (
                report.get('status', '결과')
                if isinstance(report, dict)
                else '알림'
            )

            msg['Subject'] = Header(
                f'[주식 크롤링] 데이터 수집 검증 리포트 ({status_str})',
                'utf-8',
            )
            msg['From'] = self.sender_email
            msg['To'] = self.receiver_email

            body = MIMEText(report_text, 'plain', 'utf-8')
            msg.attach(body)

            # 네이버 SMTP 접속 및 발송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.login_id, self.naver_pw)
                server.sendmail(
                    self.sender_email, self.receiver_email, msg.as_string()
                )

            print('📧 [네이버 메일 알림 발송 성공!]')

        except Exception as e:
            print(f'❌ 메일 전송 실패: {e}')
