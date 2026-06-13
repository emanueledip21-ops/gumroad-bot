"""
Server Flask — Payhip Webhook
Riceve i dati dell'acquirente, genera il PDF personalizzato e lo invia via email.
"""

import os
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from flask import Flask, request, jsonify
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# ── Configurazione ────────────────────────────────────────────────────────────
GMAIL_ADDRESS   = "emanueledip21@gmail.com"
GMAIL_APP_PASS  = os.environ.get("GMAIL_APP_PASS", "")
OWNER_PASSWORD  = os.environ.get("OWNER_PASSWORD", "OWNER_SECRET_2026")
PDF_MASTER_PATH = "guadagna_di_piu_come_creator_contenuti_per_adulti.pdf"

PAGE_W, PAGE_H = A4
app = Flask(__name__)

# ── Funzioni ──────────────────────────────────────────────────────────────────

def create_watermark_page(buyer_name: str, buyer_email: str) -> io.BytesIO:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)

    c.saveState()
    c.setFillColor(colors.HexColor("#C0392B"), alpha=0.07)
    c.setFont("Helvetica-Bold", 28)
    c.translate(PAGE_W / 2, PAGE_H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, f"Acquistato da {buyer_name}")
    c.setFont("Helvetica", 18)
    c.drawCentredString(0, -36, buyer_email)
    c.restoreState()

    c.saveState()
    c.setFillColor(colors.HexColor("#1A1A1A"), alpha=0.55)
    c.rect(0, 0, PAGE_W, 0.85 * 28.35, fill=1, stroke=0)
    c.setFillColor(colors.white, alpha=0.9)
    c.setFont("Helvetica", 7)
    c.drawString(14, 7, f"Licenza personale non trasferibile | Acquirente: {buyer_name} | {buyer_email}")
    c.drawRightString(PAGE_W - 14, 7, "© Riproduzione e rivendita vietate")
    c.restoreState()

    c.save()
    buf.seek(0)
    return buf


def protect_pdf(buyer_name: str, buyer_email: str) -> io.BytesIO:
    wm_buf  = create_watermark_page(buyer_name, buyer_email)
    wm_page = PdfReader(wm_buf).pages[0]

    reader = PdfReader(PDF_MASTER_PATH)
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(wm_page)
        writer.add_page(page)

    writer.encrypt(
        user_password="",
        owner_password=OWNER_PASSWORD,
        use_128bit=True,
        permissions_flag=0,
    )

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


def send_email(buyer_name: str, buyer_email: str, pdf_bytes: io.BytesIO):
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = buyer_email
    msg["Subject"] = "Il tuo ebook — Guadagna di più come creator di contenuti per adulti"

    body = f"""Ciao {buyer_name},

grazie per il tuo acquisto! In allegato trovi il tuo ebook personalizzato.

Questo file è rilasciato con licenza personale non trasferibile.

Buona lettura!
"""
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEBase("application", "octet-stream")
    attachment.set_payload(pdf_bytes.read())
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"Ebook_{buyer_name.replace(' ', '_')}.pdf",
    )
    msg.attach(attachment)

  with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
        server.sendmail(GMAIL_ADDRESS, buyer_email, msg.as_string())


# ── Endpoint webhook ──────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or request.form

    buyer_name  = data.get("customer_name") or data.get("email", "Cliente")
    buyer_email = data.get("customer_email") or data.get("email", "")

    if not buyer_email:
        return jsonify({"error": "email mancante"}), 400

    try:
        pdf_bytes = protect_pdf(buyer_name, buyer_email)
        send_email(buyer_name, buyer_email, pdf_bytes)
        return jsonify({"status": "ok", "buyer": buyer_email}), 200
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return "Payhip Bot attivo ✅", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
