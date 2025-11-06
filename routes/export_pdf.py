# =============================================================
# 📄 ROUTE PDF — Génération de fichiers Business Plan IA (LGD)
# =============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
import os

router = APIRouter(prefix="/export", tags=["Export PDF"])

class BusinessPlanData(BaseModel):
    nom_entreprise: str
    description: str
    objectifs: str
    strategie: str
    budget: str
    contact: str

@router.post("/business-plan")
def generate_business_plan(data: BusinessPlanData):
    try:
        output_dir = "generated_pdfs"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, "Business_Plan_IA.pdf")

        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="Title", fontSize=18, leading=22, spaceAfter=20, fontName="HeiseiKakuGo-W5"))
        styles.add(ParagraphStyle(name="Body", fontSize=12, leading=16, spaceAfter=10, fontName="HeiseiKakuGo-W5"))

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        elements = [
            Paragraph("📘 Business Plan IA — Le Générateur Digital", styles["Title"]),
            Paragraph(f"<b>Nom de l’entreprise :</b> {data.nom_entreprise}", styles["Body"]),
            Paragraph(f"<b>Description :</b> {data.description}", styles["Body"]),
            Paragraph(f"<b>Objectifs :</b> {data.objectifs}", styles["Body"]),
            Paragraph(f"<b>Stratégie :</b> {data.strategie}", styles["Body"]),
            Paragraph(f"<b>Budget :</b> {data.budget}", styles["Body"]),
            Paragraph(f"<b>Contact :</b> {data.contact}", styles["Body"]),
        ]
        doc.build(elements)
        return {"message": "✅ PDF généré avec succès", "file_path": pdf_path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du PDF : {e}")
