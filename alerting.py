"""
Alerting Module for Blog API Server

Slack Webhook, Email 알림을 지원합니다.
"""

import os
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from logger_config import get_logger

logger = get_logger(__name__)


class AlertSeverity(Enum):
    """알림 심각도 수준"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """알림 규칙"""
    name: str
    condition: str  # "error_rate > 5", "avg_response_time > 2000"
    severity: AlertSeverity
    enabled: bool = True
    cooldown_seconds: int = 300  # 알림 쿨다운 (초)
    _last_triggered: float = 0

    def should_trigger(self, metrics: Dict[str, Any]) -> bool:
        """알림 조건 확인"""
        import time

        # 쿨다운 체크
        if time.time() - self._last_triggered < self.cooldown_seconds:
            return False

        # 간단한 조건 평가
        try:
            if "error_rate" in self.condition:
                threshold = float(self.condition.split(">")[1].strip())
                error_rate = metrics.get("error_rate_percent", 0)
                if error_rate > threshold:
                    self._last_triggered = time.time()
                    return True
            elif "avg_response_time" in self.condition:
                threshold = float(self.condition.split(">")[1].strip())
                avg_time = metrics.get("avg_response_time_ms", 0)
                if avg_time > threshold:
                    self._last_triggered = time.time()
                    return True
            elif "slow_request_rate" in self.condition:
                threshold = float(self.condition.split(">")[1].strip())
                slow_rate = metrics.get("slow_request_rate_percent", 0)
                if slow_rate > threshold:
                    self._last_triggered = time.time()
                    return True
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to evaluate alert condition: {e}")

        return False


class SlackNotifier:
    """Slack Webhook 알림"""

    def __init__(self):
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

        if self.enabled:
            logger.info("Slack notifier initialized")
        else:
            logger.warning("SLACK_WEBHOOK_URL not set - Slack alerts disabled")

    def send(self, title: str, message: str, severity: AlertSeverity = AlertSeverity.INFO) -> bool:
        """Slack 알림 전송"""
        if not self.enabled:
            return False

        # 색상 매핑
        colors = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.ERROR: "#ff0000",
            AlertSeverity.CRITICAL: "#990000"
        }

        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }

        payload = {
            "attachments": [
                {
                    "color": colors.get(severity, colors[AlertSeverity.INFO]),
                    "title": f"{emoji.get(severity, '')} {title}",
                    "text": message,
                    "footer": "Blog API Server",
                    "ts": int(__import__('time').time())
                }
            ]
        }

        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Slack alert sent: {title}")
                return True
            else:
                logger.warning(f"Slack webhook error: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


class EmailNotifier:
    """이메일 알림"""

    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("ALERT_FROM_EMAIL")
        self.to_emails = os.getenv("ALERT_TO_EMAILS", "").split(",")

        self.enabled = bool(self.smtp_username and self.smtp_password and self.to_emails)

        if self.enabled:
            logger.info("Email notifier initialized")
        else:
            logger.warning("SMTP credentials not set - Email alerts disabled")

    def send(self, title: str, message: str, severity: AlertSeverity = AlertSeverity.INFO) -> bool:
        """이메일 알림 전송"""
        if not self.enabled:
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{severity.value.upper()}] {title}"
            msg["From"] = self.from_email or self.smtp_username
            msg["To"] = ", ".join(self.to_emails)

            # HTML 본문
            html = f"""
            <html>
            <body>
                <h2>{title}</h2>
                <p><strong>Severity:</strong> {severity.value.upper()}</p>
                <p>{message.replace(chr(10), '<br>')}</p>
                <hr>
                <p><small>Sent from Blog API Server</small></p>
            </body>
            </html>
            """

            part = MIMEText(html, "html")
            msg.attach(part)

            # SMTP 전송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False


class AlertManager:
    """알림 관리자"""

    def __init__(self):
        self.slack = SlackNotifier()
        self.email = EmailNotifier()
        self.rules: List[AlertRule] = []
        self._init_default_rules()

    def _init_default_rules(self):
        """기본 알림 규칙 초기화"""
        self.rules = [
            AlertRule(
                name="High Error Rate",
                condition="error_rate > 5",
                severity=AlertSeverity.WARNING,
                cooldown_seconds=300
            ),
            AlertRule(
                name="Critical Error Rate",
                condition="error_rate > 20",
                severity=AlertSeverity.CRITICAL,
                cooldown_seconds=60
            ),
            AlertRule(
                name="Slow Response Time",
                condition="avg_response_time > 2000",
                severity=AlertSeverity.WARNING,
                cooldown_seconds=600
            ),
            AlertRule(
                name="High Slow Request Rate",
                condition="slow_request_rate > 10",
                severity=AlertSeverity.WARNING,
                cooldown_seconds=300
            ),
        ]

    def check_and_alert(self, metrics: Dict[str, Any]):
        """메트릭 확인 후 알림 전송"""
        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.should_trigger(metrics):
                self._send_alert(rule, metrics)

    def _send_alert(self, rule: AlertRule, metrics: Dict[str, Any]):
        """알림 전송"""
        message = f"""
Alert Rule: {rule.name}
Condition: {rule.condition}

Current Metrics:
- Total Requests: {metrics.get('total_requests', 0)}
- Error Count: {metrics.get('error_count', 0)}
- Error Rate: {metrics.get('error_rate_percent', 0)}%
- Slow Requests: {metrics.get('slow_request_count', 0)}
- Slow Request Rate: {metrics.get('slow_request_rate_percent', 0)}%
"""

        # Slack 전송
        self.slack.send(
            title=f"Alert: {rule.name}",
            message=message.strip(),
            severity=rule.severity
        )

        # Email 전송 (CRITICAL만)
        if rule.severity == AlertSeverity.CRITICAL:
            self.email.send(
                title=f"🚨 CRITICAL: {rule.name}",
                message=message.strip(),
                severity=rule.severity
            )

    def send_manual_alert(self, title: str, message: str, severity: AlertSeverity = AlertSeverity.INFO):
        """수동 알림 전송"""
        self.slack.send(title, message, severity)
        if severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            self.email.send(title, message, severity)

    def add_rule(self, rule: AlertRule):
        """알림 규칙 추가"""
        self.rules.append(rule)
        logger.info(f"Alert rule added: {rule.name}")

    def remove_rule(self, name: str):
        """알림 규칙 제거"""
        self.rules = [r for r in self.rules if r.name != name]
        logger.info(f"Alert rule removed: {name}")

    def get_rules(self) -> List[Dict[str, Any]]:
        """알림 규칙 목록 반환"""
        return [
            {
                "name": r.name,
                "condition": r.condition,
                "severity": r.severity.value,
                "enabled": r.enabled,
                "cooldown_seconds": r.cooldown_seconds
            }
            for r in self.rules
        ]


# 전역 인스턴스
alert_manager = AlertManager()
