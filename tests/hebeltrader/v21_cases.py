"""Synthetic layouts; only the five WKN/price pairs come from the user's regression table."""

from decimal import Decimal

from reportlab.pdfgen import canvas

CASES = [
    ("Hebeltrader_2025-95_Antero.pdf", "JF3KMQ", "0.18"),
    ("Hebeltrader_2026-03_Merck.pdf", "JZ0PSN", "0.24"),
    ("Hebeltrader_2026-93_Adidas.pdf", "DU0UHF", "0.19"),
    ("Hebeltrader_2026-97_Deere.pdf", "FE20SD", "1.06"),
    ("Hebeltrader_2025-02_EK_halfOK.pdf", "SY5DX4", "1.60"),
]


def build_case(path, index):
    name, wkn, price = CASES[index]
    entry = Decimal(price)

    def number(value):
        return str(value).replace(".", ",")

    pdf = canvas.Canvas(str(path), invariant=1)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 810, "SYNTHETISCHE TESTDATEN - keine Originalausgabe")
    pdf.drawString(40, 790, f"01.01.2025 # {index + 1}/2025")
    pdf.drawString(40, 650, "Erfundener Begleittext neben der Derivattabelle.")
    pdf.drawString(392, 670, f"Testaktie {index + 1}")
    if index == 4:
        headings = ["TURBO UNLIMITED", "LONG"]
    else:
        headings = ["Optionsschein Call"]
    y = 650
    for text in headings:
        pdf.drawString(392, y, text)
        y -= 18
    rows = [
        ("WKN", wkn),
        ("Akt. Kurs**" if index % 2 else "Akt. Kurs", number(entry) + " EUR"),
        ("Ziel 1", number(entry * 2) + " EUR"),
        ("Ziel 2", number(entry * 3) + " EUR"),
        ("Stopp 1", number(entry / 2) + " EUR"),
        ("Basispreis", "100,00 USD"),
        ("Laufzeit", "open end" if index == 4 else "18.12.26"),
    ]
    for key, value in rows:
        pdf.drawString(398, y, key)
        pdf.drawRightString(555, y, value)
        y -= 20
    pdf.showPage()
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 800, f"01.01.2025 # {index + 1}/2025")
    pdf.drawString(40, 740, "Ein frei erfundener Absatz fuer den Regressionstest:")
    pdf.drawString(
        40,
        720,
        "OPTIONSSCHEIN VS. AKTIE"
        if index == 4
        else "Optionsschein koennte im beschriebenen Testszenario steigen.",
    )
    pdf.drawString(400, 720, "Newsletter")
    pdf.drawString(40, 680, "Ein original genannter Testwert: (CRV) von 3,3!")
    pdf.showPage()
    pdf.save()
