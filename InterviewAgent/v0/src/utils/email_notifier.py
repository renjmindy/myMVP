import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _score_color(score) -> str:
    if score is None:
        return "#888888"
    if score >= 70:
        return "#2e7d32"
    if score >= 50:
        return "#f57f17"
    return "#c62828"


def _rec_color(rec: str) -> str:
    colors = {"apply": "#2e7d32", "maybe": "#f57f17", "skip": "#c62828"}
    return colors.get(rec, "#888888")


def _ul(items: list) -> str:
    if not items:
        return "<em>None listed</em>"
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 465,
        sender_email: str = "",
        sender_password: str = "",
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def _send(self, recipient: str, subject: str, html_body: str):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = recipient
        msg.attach(MIMEText(html_body, "html"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ctx) as server:
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, recipient, msg.as_string())

    def _build_digest_html(self, jobs: list[dict], threshold: int = 0) -> str:
        filtered = [j for j in jobs if (j.get("fit_score") or 0) >= threshold]
        filtered.sort(key=lambda j: j.get("fit_score") or 0, reverse=True)

        if not filtered:
            return (
                "<html><body style='font-family:Arial,sans-serif;'>"
                "<p>No jobs matched your criteria this period.</p>"
                "</body></html>"
            )

        rows_html = ""
        for job in filtered:
            score = job.get("fit_score")
            rec = job.get("recommendation", "") or (
                (job.get("analysis") or {}).get("recommendation", "")
            )
            score_display = str(score) if score is not None else "—"
            color = _score_color(score)
            rec_color = _rec_color(rec)
            url = job.get("url", "#")
            rows_html += f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;">
                <a href="{url}" style="color:#1565c0;text-decoration:none;">
                  {job.get('title', '')}
                </a>
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee;">{job.get('company', '')}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;">{job.get('location', '')}</td>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">
                <span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;">
                  {score_display}
                </span>
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">
                <span style="background:{rec_color};color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;">
                  {rec}
                </span>
              </td>
            </tr>"""

        return f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;max-width:800px;margin:auto;">
          <h2 style="color:#1565c0;">Job Digest</h2>
          <p>{len(filtered)} job(s) found matching your criteria.</p>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="background:#e3f2fd;">
                <th style="padding:10px;text-align:left;">Title</th>
                <th style="padding:10px;text-align:left;">Company</th>
                <th style="padding:10px;text-align:left;">Location</th>
                <th style="padding:10px;text-align:center;">Fit Score</th>
                <th style="padding:10px;text-align:center;">Recommendation</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
          <p style="font-size:12px;color:#888;margin-top:24px;">
            Sent by Interview Agent &bull; Manage your preferences in Settings.
          </p>
        </body></html>"""

    def _build_alert_html(self, job: dict) -> str:
        analysis = job.get("analysis") or {}
        score = job.get("fit_score") or analysis.get("fit_score")
        rec = job.get("recommendation") or analysis.get("recommendation", "")
        color = _score_color(score)
        rec_color = _rec_color(rec)
        score_display = str(score) if score is not None else "—"

        matching = analysis.get("matching_skills", [])
        missing = analysis.get("missing_skills", [])
        summary = analysis.get("summary", "")
        key_req = analysis.get("key_requirements", [])

        return f"""
        <html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;">
          <h2 style="color:#1565c0;">New Job Alert: {job.get('title', '')}</h2>
          <table style="width:100%;margin-bottom:16px;">
            <tr>
              <td style="padding:6px;"><strong>Company:</strong> {job.get('company', '')}</td>
              <td style="padding:6px;"><strong>Location:</strong> {job.get('location', '')}</td>
            </tr>
            <tr>
              <td style="padding:6px;">
                <strong>Fit Score:</strong>
                <span style="background:{color};color:#fff;padding:2px 8px;border-radius:12px;">
                  {score_display}
                </span>
              </td>
              <td style="padding:6px;">
                <strong>Recommendation:</strong>
                <span style="background:{rec_color};color:#fff;padding:2px 8px;border-radius:12px;">
                  {rec}
                </span>
              </td>
            </tr>
          </table>
          <p><strong>Summary:</strong> {summary}</p>
          <h3 style="color:#1565c0;">Key Requirements</h3>{_ul(key_req)}
          <h3 style="color:#2e7d32;">Matching Skills</h3>{_ul(matching)}
          <h3 style="color:#c62828;">Missing Skills</h3>{_ul(missing)}
          <p style="margin-top:16px;">
            <a href="{job.get('url', '#')}"
               style="background:#1565c0;color:#fff;padding:10px 20px;
                      border-radius:4px;text-decoration:none;font-size:14px;">
              View Job Posting
            </a>
          </p>
          <p style="font-size:12px;color:#888;margin-top:24px;">
            Sent by Interview Agent &bull; Manage your preferences in Settings.
          </p>
        </body></html>"""

    def send_job_digest(
        self,
        recipient: str,
        jobs: list[dict],
        subject_prefix: str = "Job Digest",
        threshold: int = 0,
    ):
        filtered = [j for j in jobs if (j.get("fit_score") or 0) >= threshold]
        if not filtered:
            return

        html = self._build_digest_html(jobs, threshold=threshold)
        subject = f"{subject_prefix} — {len(filtered)} new job(s)"
        self._send(recipient, subject, html)

    def send_instant_alert(self, recipient: str, job: dict):
        analysis = job.get("analysis") or {}
        score = job.get("fit_score") or analysis.get("fit_score")
        score_display = str(score) if score is not None else "—"
        html = self._build_alert_html(job)
        subject = f"[Job Alert] {job.get('title', '')} at {job.get('company', '')} — Score: {score_display}"
        self._send(recipient, subject, html)
