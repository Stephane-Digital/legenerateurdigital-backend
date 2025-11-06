# =============================================================
# 📚 ROUTES GUIDES — URSSAF & STATUT JURIDIQUE (PDF imprimables)
# =============================================================

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Literal, Optional, List
from datetime import datetime
import os
import tempfile

# ReportLab (PDF)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
from reportlab.lib import colors

router = APIRouter(prefix="/guides", tags=["Guides"])

# --------- Modèles ---------
class GuideRequest(BaseModel):
    guide: Literal["urssaf", "statut"]
    include_checklist: bool = True
    footer_note: Optional[str] = "LGD • Le Générateur Digital — https://app.legenerateurdigital.com"

# --------- Contenu des guides (statique pour v1) ---------
def content_urssaf():
    title = "Se déclarer à l’URSSAF — Guide pas à pas"
    intro = (
        "Ce guide t’accompagne pour te déclarer en micro-entreprise (auto-entrepreneur) "
        "pour une activité de prestation de services en marketing digital."
    )
    prereq = [
        "Carte d’identité (scan/photo)",
        "Adresse postale et e-mail valides",
        "Numéro de téléphone joignable",
        "Compte bancaire dédié recommandé (ou à ouvrir sous 30 jours)",
    ]
    steps = [
        "Rendez-vous sur formalites.entreprises.gouv.fr (guichet unique des formalités).",
        "Crée un compte (ou connecte-toi via FranceConnect).",
        "Choisis « Déclarer une entreprise » puis « Entreprise individuelle ».",
        "Choisis le régime « Micro-entreprise » (simplifié) et l’activité « Prestations de services ». "
        "Code APE fréquent : 7311Z (conseil/marketing publicitaire) ou 7022Z (conseil en gestion).",
        "Renseigne l’adresse, la date de début d’activité, et coche la franchise en base de TVA si éligible.",
        "Valide la protection sociale (URSSAF) et téléverse tes justificatifs.",
        "Signe et soumets le dossier ; tu recevras ton SIREN/SIRET par e-mail (INSEE) sous quelques jours.",
    ]
    after = [
        "Activer ton espace **URSSAF** (déclarations mensuelles/trimestrielles).",
        "Ouvrir (ou affecter) un **compte bancaire dédié**.",
        "Ajouter tes mentions légales et n° SIRET sur tes factures et CGV.",
        "Émettre ta **première facture** (numérotation chronologique).",
    ]
    checklist = [
        "Compte guichet unique créé",
        "Formulaire EI + micro-entreprise rempli",
        "Justificatifs téléversés",
        "Dossier signé & envoyé",
        "SIRET reçu",
        "Espace URSSAF activé",
        "Compte bancaire dédié OK",
        "Mentions légales / CGV à jour",
    ]
    return dict(title=title, intro=intro, prereq=prereq, steps=steps, after=after, checklist=checklist)

def content_statut():
    title = "Choisir son statut juridique — Par où commencer ?"
    intro = (
        "Au lancement, 80% des solo-preneurs démarrent en **micro-entreprise** pour sa simplicité. "
        "Ce guide t’aide à comparer rapidement avec les autres options les plus courantes."
    )
    points_forts_micro = [
        "Ouverture en ligne en quelques minutes (gratuite).",
        "Comptabilité ultra simplifiée (livre des recettes + factures).",
        "Cotisations sociales calculées sur le chiffre d’affaires encaissé.",
        "Franchise en base de TVA (jusqu’aux seuils), factures sans TVA.",
    ]
    limites_micro = [
        "Plafonds de CA (prestations de services) — attention au dépassement.",
        "Pas de déduction des charges réelles (abonnements, matériel, etc.).",
        "Image “individuelle“ (peut être perçue comme moins “corporate“).",
    ]
    alternatives = [
        ("EURL/SASU", "Utile dès qu’on dépasse les seuils, besoin d’investir fortement, ou pour se rémunérer via dividendes. Comptabilité et coûts plus élevés."),
        ("Entreprise individuelle (régime réel)", "Permet de déduire les charges réelles, mais obligations comptables plus lourdes."),
    ]
    starter_rules = [
        "Si tu **débutes** et veux aller vite → Micro-entreprise.",
        "Si tu **prévois des charges élevées** (pub, équipe, matos) → envisage le **réel**.",
        "Si tu **vises du scale** ou des **levées** → **SASU** après premiers revenus validés.",
    ]
    checklist = [
        "Valider ton choix pour 12 prochains mois",
        "Prévoir un suivi mensuel des revenus et charges",
        "Programmer une revue à M+6 pour ajuster (seuils/dépenses)",
    ]
    return dict(
        title=title,
        intro=intro,
        points_forts_micro=points_forts_micro,
        limites_micro=limites_micro,
        alternatives=alternatives,
        starter_rules=starter_rules,
        checklist=checklist,
    )

# --------- Génération PDF ---------
def build_pdf(filename: str, payload: GuideRequest):
    # Styles
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 18
    styles["Title"].leading = 22
    styles["Title"].alignment = TA_CENTER

    normal = ParagraphStyle(
        "normal", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=16, alignment=TA_JUSTIFY
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, spaceBefore=12, spaceAfter=6
    )

    story: List = []

    if payload.guide == "urssaf":
        data = content_urssaf()
        story.append(Paragraph(data["title"], styles["Title"]))
        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph(data["intro"], normal))
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("🧾 Prérequis", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"• {p}", normal)) for p in data["prereq"]], bulletType="bullet"))
        story.append(Spacer(1, 0.2*cm))

        story.append(Paragraph("🪜 Étapes", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"{i+1}. {s}", normal)) for i, s in enumerate(data["steps"])], bulletType="1"))
        story.append(Spacer(1, 0.2*cm))

        story.append(Paragraph("✅ Après validation", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"• {p}", normal)) for p in data["after"]], bulletType="bullet"))
        story.append(Spacer(1, 0.2*cm))

        if payload.include_checklist:
            story.append(Paragraph("📋 Checklist", h2))
            story.append(ListFlowable([ListItem(Paragraph(f"☐ {c}", normal)) for c in data["checklist"]], bulletType="bullet"))
            story.append(Spacer(1, 0.2*cm))

    elif payload.guide == "statut":
        data = content_statut()
        story.append(Paragraph(data["title"], styles["Title"]))
        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph(data["intro"], normal))
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("🎯 Pourquoi démarrer en micro-entreprise", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"• {p}", normal)) for p in data["points_forts_micro"]], bulletType="bullet"))
        story.append(Spacer(1, 0.2*cm))

        story.append(Paragraph("⚠️ Limites à connaître", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"• {p}", normal)) for p in data["limites_micro"]], bulletType="bullet"))
        story.append(Spacer(1, 0.2*cm))

        story.append(Paragraph("🔁 Alternatives", h2))
        alt_table = Table(
            [[Paragraph(f"<b>{k}</b>", normal), Paragraph(v, normal)] for (k, v) in data["alternatives"]],
            colWidths=[4*cm, 12*cm]
        )
        alt_table.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ]))
        story.append(alt_table)
        story.append(Spacer(1, 0.2*cm))

        story.append(Paragraph("🧭 Règles simples pour démarrer", h2))
        story.append(ListFlowable([ListItem(Paragraph(f"• {p}", normal)) for p in data["starter_rules"]], bulletType="bullet"))
        story.append(Spacer(1, 0.2*cm))

        if payload.include_checklist:
            story.append(Paragraph("📋 Checklist de départ", h2))
            story.append(ListFlowable([ListItem(Paragraph(f"☐ {c}", normal)) for c in data["checklist"]], bulletType="bullet"))
            story.append(Spacer(1, 0.2*cm))

    else:
        raise HTTPException(status_code=400, detail="Guide inconnu.")

    # Footer
    footer = payload.footer_note or ""
    if footer:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(footer, ParagraphStyle("footer", parent=normal, alignment=TA_CENTER, textColor=colors.grey)))

    # Génération
    doc = SimpleDocTemplate(
        filename, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm
    )
    doc.build(story)

# --------- Endpoints ---------
@router.get("/list")
def list_guides():
    """
    Liste des guides disponibles.
    """
    return {
        "guides": [
            {"key": "urssaf", "title": "Se déclarer à l’URSSAF — pas à pas"},
            {"key": "statut", "title": "Choisir son statut juridique — démarrer malin"},
        ]
    }

@router.post("/pdf")
def generate_pdf(req: GuideRequest):
    """
    Génère un PDF imprimable pour le guide demandé et renvoie le fichier.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            fname = f"guide_{req.guide}_{timestamp}.pdf"
            fpath = os.path.join(tmpdir, fname)
            build_pdf(fpath, req)
            return FileResponse(
                path=fpath,
                filename=fname,
                media_type="application/pdf"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération PDF: {e}")
