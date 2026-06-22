import os
import sys
import re
import time
import subprocess
import webbrowser
from threading import Thread
from io import BytesIO
import logging

# إخفاء التنبيهات غير الضرورية
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)

# ========================================================================
# [1] الإعدادات والثوابت
# ========================================================================
PORT = "8502"
USERS_TRACKER = "active_staff.txt"
TUNNEL_FILE = "tunnel_url.txt"
PASSWORD = "12"  # اتركها فارغة كما كانت أو ضع كلمة مرور

try:
    import qrcode

    HAS_QR = True
except ImportError:
    HAS_QR = False

# ========================================================================
# [2] قواعد البيانات الطبية
# ========================================================================

EMERGENCY_CASES_DB = {
    "Snake Bites (Venomous)": {
        "Immediate First Action": "• Reassure the patient completely and immobilize the affected limb using a splint to restrict lymphatic spread of venom.\n• Immediately remove rings, bracelets, and tight clothing before significant edema develops.",
        "Clinical Work Protocol": "• Establish two large-bore IV lines (14G or 16G) and initiate IV fluid resuscitation.\n• Evaluate indication for Anti-Snake Venom (ASV): Infuse 5–10 vials intravenously if systemic signs or rapid local swelling occur.\n• Administer a booster dose of Tetanus Toxoid vaccine.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Incision/slashing of the wound, oral suction, direct ice application, or applying a tight arterial tourniquet that compromises arterial perfusion."
    },
    "Scorpion Stings": {
        "Immediate First Action": "• Wash the sting site thoroughly with water and soap, then apply cold packs to minimize localized pain.\n• Continuous, close monitoring of vital signs (especially in pediatric patients).",
        "Clinical Work Protocol": "• In the presence of systemic toxicity (salivation, tachycardia, altered mental status, or seizures): Administer Anti-Scorpion Venom intravenously (1–2 vials for mild systemic symptoms, 3–4 vials for pediatric or critical cases).\n• Control severe hypertension and cardiac arrhythmias.",
        "Critical Contraindications": "⚠️ Avoid using Morphine for pain management as it can cause synergistic respiratory depression with the scorpion neurotoxin in the central nervous system."
    },
    "Animal/Dog Bites (Suspected Rabies)": {
        "Immediate First Action": "• Wash the wound immediately and copiously under running water and soap for at least 15 minutes as a mechanical barrier to eliminate the virus.\n• Disinfect the area using Povidone-Iodine 7.5%.",
        "Clinical Work Protocol": "• Assess the exposure category (Category I, II, or III) according to the WHO Rabies guidelines.\n• Initiate PEP vaccine schedule immediately (Days 0, 3, 7, 14) and infiltrate Rabies Immune Globulin (RIG) deeply inside and around the wound margins for deep injuries.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Primary suturing/closure of the wound is contraindicated unless required for life-threatening hemorrhage or critical aesthetic facial reconstruction (only after thoroughRIG infiltration)."
    },
    "Hemorrhagic Shock": {
        "Immediate First Action": "• Apply firm, continuous direct pressure onto the source of external hemorrhage using sterile gauze dressings.\n• Perform temporary Passive Leg Raise (PLR) to optimize venous return and redistribute blood flow to vital organs.",
        "Clinical Work Protocol": "• Establish two large-bore peripheral IV lines (14G or 16G), infuse warmed crystalloids judiciously, and activate the Massive Transfusion Protocol (MTP) at a 1:1:1 ratio (PRBCs, FFP, Platelets).\n• Apply a pelvic binder for suspected fractures or a tactical tourniquet for severe exsanguinating extremity hemorrhage.",
        "Critical Contraindications": "⚠️ Avoid aggressive, high-volume crystalloid fluid resuscitation to prevent dilutional coagulopathy, disruption of formed clots, and exacerbation of bleeding."
    },
    "Traumatic Brain & Spinal Cord Injuries": {
        "Immediate First Action": "• Immediate, rigid immobilization of the cervical spine using a properly fitted rigid cervical collar (C-collar).\n• Secure and maintain a patent airway while strictly maintaining neutral spinal alignment along the axial plane.",
        "Clinical Work Protocol": "• Maintain Mean Arterial Pressure (MAP > 80 mmHg) to optimize cerebral perfusion pressure (CPP).\n• Perform serial assessments of pupillary light reflex and Glasgow Coma Scale (GCS) every 15 minutes.\n• Order an emergent non-contrast CT scan of the brain and cervical spine.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Do not move, log-roll, or flex the patient's neck prior to radiographically ruling out spinal fractures. Avoid hypoxia and hypotension as they double secondary brain injury mortality."
    },
    "Open & Comminuted Fractures": {
        "Immediate First Action": "• Control associated hemorrhage with direct pressure and cover protruding bone fragments loosely with sterile gauze moistened with normal saline.\n• Immobilize the affected limb in its presenting position to prevent further neurovascular compromise.",
        "Clinical Work Protocol": "• Administer empirical broad-spectrum IV antibiotics immediately in the ER (e.g., Cefazolin + Aminoglycoside) to prevent osteomyelitis.\n• Administer Tetanus booster prophylaxis and prepare the patient for urgent surgical debridement and external/internal fixation.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Never attempt to reduce, push back, or manipulate protruding bone fragments into the wound bed within the ER to avoid introducing superficial contamination into deep fascial spaces."
    },
    "Severe & Extensive Burns (>15%)": {
        "Immediate First Action": "• Extricate the victim from the thermal source, remove burnt non-adherent clothing, and cool the thermal injury using lukewarm running water (never ice) for 10 minutes.",
        "Clinical Work Protocol": "• Calculate Total Body Surface Area (TBSA) using the Rule of Nines and initiate fluid resuscitation according to the Parkland Formula: 4ml × kg × % TBSA, infusing the first half within the first 8 hours post-injury.\n• Secure the airway via early endotracheal intubation if an inhalation injury is suspected (evidenced by hoarseness, stridor, or nasal soot).",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Do not apply ice directly (causes severe vasoconstriction and deepens tissue necrosis). Do not apply non-medical home remedies like toothpaste, butter, or oils to burn wounds."
    },
    "Acute Myocardial Infarction (STEMI)": {
        "Immediate First Action": "• Enforce absolute bed rest immediately (strictly prohibit any physical exertion to minimize myocardial oxygen demand).\n• Administer 4 non-enteric-coated Aspirin tablets (300mg total) to be chewed immediately.",
        "Clinical Work Protocol": "• Obtain and interpret a 12-lead Electrocardiogram (ECG) within less than 10 minutes of arrival.\n• Administer supplemental oxygen if SpO2 < 90%, and give sublingual Glyceryl Trinitrate (GTN) provided hemodynamic stability is confirmed.\n• Coordinate urgent transfer for Primary Percutaneous Coronary Intervention (PCI) or administer fibrinolytic therapy if PCI is unavailable.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Do not administer Nitroglycerin (GTN) if systolic blood pressure is <90 mmHg or if there is clinical suspicion of a Right Ventricular Infarction."
    },
    "Acute Ischemic Stroke": {
        "Immediate First Action": "• Elevate the head of the bed to 30 degrees and protect the airway against aspiration risk.\n• Document the precise and exact 'Last Known Well' time (critical for determining eligibility for reperfusion therapies).",
        "Clinical Work Protocol": "• Obtain an emergent non-contrast Brain CT scan to definitively rule out intracranial hemorrhage.\n• If ischemic stroke is confirmed and symptom onset is within the 4.5-hour window, screen for and prepare intravenous thrombolysis (tPA).\n• Maintain permissive hypertension; avoid aggressive lowering of blood pressure unless dangerously elevated.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Do not administer Aspirin, Heparin, or any antiplatelets/anticoagulants in the ER prior to reviewing the non-contrast Brain CT scan to eliminate hemorrhagic stroke."
    },
    "Diabetic Ketoacidosis (DKA)": {
        "Immediate First Action": "• Establish two large-bore IV lines (16G or 18G).\n• Initiate rapid hydration with 0.9% Normal Saline (15–20 mL/kg/hr) to restore circulating volume and renal perfusion.",
        "Clinical Work Protocol": "• STAT Lab Panel: Glucose, electrolytes, BUN, Creatinine, VBG/ABG (pH), serum ketones (beta-hydroxybutyrate), and ECG.\n• Insulin Therapy: Start continuous regular insulin infusion at 0.1 units/kg/hr.\n• Glucose/Fluid Adjustment: When blood glucose reaches 250 mg/dL, add 5% Dextrose to the IV fluids (D5 1/2 NS) while continuing insulin infusion.\n• Potassium Management: Add 20–30 mEq of Potassium (KCl) to each liter of IV fluid if K+ is between 3.3 and 5.2 mEq/L.",
        "Critical Contraindications": "⚠️ WARNING: Do not initiate insulin if Serum K+ < 3.3 mEq/L. You must replace potassium first to prevent life-threatening cardiac arrhythmias and arrest. \n⚠️ WARNING: Avoid rapid fluid over-correction to prevent cerebral edema.\n⚠️ WARNING: Avoid routine bicarbonate administration unless pH < 6.9."
    },
    "Status Asthmaticus": {
        "Immediate First Action": "• Position the patient in an upright, high-Fowler's position and administer high-flow oxygen via a non-rebreather face mask.",
        "Clinical Work Protocol": "• Initiate continuous nebulized short-acting beta-agonists (Salbutamol/Ventolin) combined with anticholinergics (Ipratropium Bromide/Atrovent).\n• Administer systemic IV Corticosteroids (Hydrocortisone 100–200mg or Methylprednisolone) immediately.\n• For life-threatening, refractory bronchospasm: Infuse Magnesium Sulfate 2g IV over 20 minutes.",
        "Critical Contraindications": "⚠️ Avoid the administration of sedatives, anxiolytics, or hypnotics as they suppress the respiratory drive, accelerating respiratory fatigue, hypercapnic failure, and premature mechanical ventilation."
    },
    "Severe Septic Shock": {
        "Immediate First Action": "• Establish wide-bore IV access and immediately initiate aggressive fluid resuscitation with crystalloids at 30ml/kg to counteract profound endotoxin-induced vasodilation.",
        "Clinical Work Protocol": "• Obtain at least two sets of blood cultures from separate anatomical sites prior to administering antimicrobial therapy.\n• Infuse empiric, broad-spectrum, maximum-dose IV antibiotics within the first hour of recognition (The Golden Hour).\n• Initiate vasopressor therapy (Norepinephrine as first-line) if mean arterial pressure remains <65 mmHg despite adequate fluid loading.",
        "Critical Contraindications": "⚠️ Never delay the administration of empiric IV antibiotics while awaiting blood culture collections or secondary diagnostic test results; every hour of delay exponentially increases mortality."
    },
    "Acute Pulmonary Edema": {
        "Immediate First Action": "• Sit the patient fully upright with legs dangling over the edge of the bed to acutely reduce venous return (preload) to the failing heart.\n• Initiate immediate Non-Invasive Positive Pressure Ventilation (NIPPV via BiPAP or CPAP) with high fraction of inspired oxygen.",
        "Clinical Work Protocol": "• Administer an intravenous bolus of Furosemide (Lasix) at an acute dose of 40–80mg for rapid venodilation and subsequent diuresis.\n• Initiate a continuous IV Nitroglycerin (GTN) infusion to aggressively reduce both cardiac preload and afterload.",
        "Critical Contraindications": "⚠️ Strictly Prohibited: Beta-blockers are absolutely contraindicated during this acute decompensated phase, as they decrease myocardial contractility, worsening backward failure and pulmonary congestion."
    },
    "Anaphylactic Shock": {
        "Immediate First Action": "• **FIRST-LINE LIFE-SAVING INTERVENTION:** Administer Epinephrine (Adrenaline) 1:1000 dilution at a dose of 0.3–0.5mg intramuscularly (IM) into the anterolateral mid-thigh.\n• Place the patient supine with legs elevated to optimize cerebral perfusion and combat distributive shock.",
        "Clinical Work Protocol": "• Secure the airway; prepare for immediate endotracheal intubation or surgical airway if laryngeal edema or stridor develops.\n• Rapidly infuse massive volumes of IV crystalloids to support blood pressure.\n• Administer secondary adjunctive therapies: IV Antihistamines (H1 and H2 blockers) and IV Corticosteroids.",
        "Critical Contraindications": "⚠️ Never delay intramuscular Epinephrine administration; delayed IM epinephrine is the primary cause of anaphylaxis fatalities. Do not administer undiluted Epinephrine 1:1000 via direct IV push outside of cardiac arrest."
    },
    "Upper Gastrointestinal Bleed (UGIB)": {
        "Immediate First Action": "• Assess hemodynamics: Place two large-bore IVs. Keep patient NPO. Secure airway if massive hematemesis.",
        "Clinical Work Protocol": "• Initiate IV PPI (e.g., Pantoprazole 80mg or Omeprazole 80mg or Esomeprazole 80mg bolus). Start Octreotide if variceal bleed suspected. Correct coagulopathy (FFP/Platelets). Arrange urgent endoscopy.",
        "Critical Contraindications": "⚠️ Avoid over-transfusion; target Hb ~7-8 g/dL to avoid raising portal pressure."
    },
    "Status Epilepticus": {
        "Immediate First Action": "• Protect airway, place in lateral recumbent position, and administer O2. Check capillary blood glucose.",
        "Clinical Work Protocol": "• First-line: IV Benzodiazepines (Lorazepam 4mg or Diazepam 10mg). Second-line: IV Levetiracetam or Fosphenytoin.",
        "Critical Contraindications": "⚠️ Do not place objects (tongue depressors) in the patient's mouth during active seizures."
    },
    "Acute Agitated/Violent Patient": {
        "Immediate First Action": "• Ensure staff safety (keep exit clear). Use verbal de-escalation techniques first.",
        "Clinical Work Protocol": "• Pharmacological restraint: IM Haloperidol (5mg) + Promethazine (25mg) or Olanzapine (10mg). Maintain close ECG monitoring for QTc prolongation.",
        "Critical Contraindications": "⚠️ Avoid physical restraint as the first option; use it only as a last resort to prevent patient/staff injury."
    },
    "Suspected Drug Overdose (Toxidromes)": {
        "Immediate First Action": "• Manage ABCs. If opioid suspected, give Naloxone (0.4mg IV). If hypoglycemia, give Dextrose.",
        "Clinical Work Protocol": "• Activated charcoal if ingestion within 1 hour. Specific antidotes: N-acetylcysteine (Paracetamol), Naloxone (Opioids), Benzodiazepines (for stimulant toxicity).",
        "Critical Contraindications": "⚠️ Do not induce emesis (vomiting) as it increases the risk of aspiration pneumonia."
    }
}

EMERGENCY_DRUGS_DB = {
    # تم الحفاظ على الأدوية بالكامل كما في كودك الأصلي
    "Adrenaline amp": {
        "Clinical Indication": "Acute anaphylactic shock, cardiac arrest resuscitation (CPR), and severe refractory septic shock.",
        "Acute Dosage": "• In Cardiac Arrest: 1mg IV/IO rapid push every 3–5 minutes during advanced life support.\n• In Anaphylaxis: 0.3 to 0.5mg Intramuscular (IM) injection.",
        "Critical Warnings": "Avoid direct IV bolus administration of undiluted 1:1,000 concentration outside of cardiac arrest.",
        "Drug Interactions": "Concomitant use with non-selective beta-blockers can induce severe hypertensive crises."
    },
    "Adenosine amp": {
        "Clinical Indication": "Immediate conversion and termination of paroxysmal supraventricular tachycardia (PSVT) involving narrow QRS complexes.",
        "Acute Dosage": "• Initial Dose: 6mg rapid IV bolus (over 1–2 seconds) followed immediately by a rapid 20ml NS flush.\n• Second Dose: 12mg rapid IV bolus after 2 minutes if needed.",
        "Critical Warnings": "Induces transient cardiac arrest/asystole for a few seconds. Absolutely contraindicated in severe asthma.",
        "Drug Interactions": "Theophylline/Aminophylline act as antagonists; Dipyridamole significantly potentiates its effects."
    },
    "Amiodarone amp": {
        "Clinical Indication": "Shock-refractory Ventricular Fibrillation (VF), pulseless Ventricular Tachycardia (pVT), and stable monomorphic VT.",
        "Acute Dosage": "• In Cardiac Arrest (VF/pVT): Initial dose of 300mg IV/IO bolus, diluted in Dextrose 5%, after the 3rd shock. Secondary dose: 150mg.",
        "Critical Warnings": "May precipitate acute severe hypotension and profound bradycardia. Continuous ECG monitoring is mandatory.",
        "Drug Interactions": "Significantly increases serum concentrations of Digoxin and Warfarin."
    },
    "Atropine amp": {
        "Clinical Indication": "Symptomatic and hemodynamically unstable bradycardia, and as a specific antidote for organophosphate poisoning.",
        "Acute Dosage": "• In Bradycardia: 1mg IV push every 3–5 minutes (up to a cumulative maximum total dose of 3mg).\n• In Organophosphate Poisoning: 2–5mg IV push, repeated every 5 minutes until pulmonary secretions dry.",
        "Critical Warnings": "Administering adult doses below 0.5mg can cause a paradoxical slowing of the heart rate (paradoxical bradycardia).",
        "Drug Interactions": "Antihistamines and tricyclic antidepressants (TCAs) potentiate its anticholinergic profile."
    },
    "A.S.A 100 tab": {
        "Clinical Indication": "Immediate first-line antiplatelet management for Acute Coronary Syndrome (ACS) and acute myocardial infarction (MI).",
        "Acute Dosage": "• 162mg to 325mg (2-3 tablets of 100mg) non-enteric-coated tablets to be chewed and swallowed immediately.",
        "Critical Warnings": "Strictly contraindicated in active gastrointestinal hemorrhage or verified severe hypersensitivity to aspirin/NSAIDs.",
        "Drug Interactions": "Concurrent administration with other anticoagulants exponentially increases the risk of internal hemorrhage."
    },
    "Clopidogrel 75 tab": {
        "Clinical Indication": "Antiplatelet therapy in Acute Coronary Syndrome (ACS) including STEMI and NSTEMI.",
        "Acute Dosage": "• Loading dose of 300mg to 600mg (4-8 tablets of 75mg) orally depending on the clinical pathway and reperfusion strategy.",
        "Critical Warnings": "Contraindicated in active pathological bleeding such as peptic ulcer or intracranial hemorrhage.",
        "Drug Interactions": "Proton pump inhibitors (especially Omeprazole) may diminish the therapeutic efficacy of Clopidogrel."
    },
    "G.T.N amp": {
        "Clinical Indication": "Acute angina pectoris, ischemic chest pain associated with MI, and decompensated heart failure with pulmonary edema.",
        "Acute Dosage": "• Continuous IV infusion starting at 5-10 mcg/min, titrating upward carefully based on hemodynamic response.",
        "Critical Warnings": "Absolutely contraindicated if systolic blood pressure is <90 mmHg, or in cases of suspected Right Ventricular Infarction.",
        "Drug Interactions": "Co-administration within 24–48 hours of phosphodiesterase-5 inhibitors (e.g., Sildenafil) causes fatal hypotension."
    },
    "G.T.N tab S.L.": {
        "Clinical Indication": "Immediate relief of acute angina pectoris or chest pain secondary to suspected myocardial ischemia.",
        "Acute Dosage": "• 1 sublingual tablet dissolved under the tongue every 5 minutes (maximum of 3 doses) while monitoring blood pressure.",
        "Critical Warnings": "Instruct patient not to swallow the tablet. Ensure patient is sitting down due to risk of orthostatic hypotension.",
        "Drug Interactions": "Severe profound hypotension if combined with PDE-5 inhibitors."
    },
    "Dopamine amp": {
        "Clinical Indication": "Hemodynamically significant hypotension or cardiogenic shock refractory to intravenous fluid resuscitation.",
        "Acute Dosage": "• Continuous IV infusion via a central line at 2 to 20 mcg/kg/min, titrated to maintain target mean arterial pressure (MAP).",
        "Critical Warnings": "Extravasation causes severe local tissue necrosis. Direct antidote is phentolamine infiltration.",
        "Drug Interactions": "MAO inhibitors significantly prolong and intensify the pressor effects of dopamine."
    },
    "Dobutamine amp": {
        "Clinical Indication": "Short-term management of acute decompensated heart failure and cardiogenic shock due to depressed myocardial contractility.",
        "Acute Dosage": "• Continuous IV infusion at 2 to 20 mcg/kg/min titrated based on cardiac output and systemic vascular resistance.",
        "Critical Warnings": "Can induce severe tachyarrhythmias and exacerbate myocardial ischemia by increasing oxygen demand.",
        "Drug Interactions": "Beta-blockers can directly antagonize the positive inotropic effects of dobutamine."
    },
    "Noradrenaline amp": {
        "Clinical Indication": "First-line vasopressor therapy for severe refractory septic shock and neurogenic shock.",
        "Acute Dosage": "• Continuous central IV infusion starting at 0.05–0.1 mcg/kg/min, titrated rapidly to achieve MAP >65 mmHg.",
        "Critical Warnings": "Potent vasoconstrictor; assess peripheral perfusion continuously. Central venous catheter administration is mandatory.",
        "Drug Interactions": "Tricyclic antidepressants and halogenated anesthetics increase cardiac irritability and arrhythmia risks."
    },
    "Digoxin amp": {
        "Clinical Indication": "Rate control in acute atrial fibrillation with rapid ventricular response, and adjunctive therapy in severe acute heart failure.",
        "Acute Dosage": "• IV loading dose of 0.25 to 0.5 mg slow IV over 15-30 minutes, followed by fractional doses every 6 hours.",
        "Critical Warnings": "Narrow therapeutic index. Monitor for signs of digitalis toxicity (anorexia, blurred green/yellow vision, arrhythmias).",
        "Drug Interactions": "Hypokalemia (induced by loop diuretics) heavily sensitizes the myocardium to digoxin toxicity."
    },
    "Hydralazine amp": {
        "Clinical Indication": "Severe hypertensive emergencies, particularly pre-eclampsia and eclampsia in pregnant patients.",
        "Acute Dosage": "• 5mg to 10mg via slow IV push, repeatable every 20 minutes as required to safely lower blood pressure.",
        "Critical Warnings": "Can cause reflex tachycardia and profound hypotension; monitor fetal heart rate continuously during administration.",
        "Drug Interactions": "Concomitant use with beta-blockers prevents reflex tachycardia and enhances hypotensive efficacy."
    },
    "Metoprolol amp": {
        "Clinical Indication": "Early management of suspected or confirmed acute myocardial infarction and hyperadrenergic tachyarrhythmias.",
        "Acute Dosage": "• 5mg slow IV push over 2 minutes, repeatable every 5 minutes to a maximum cumulative dose of 15mg.",
        "Critical Warnings": "Contraindicated if heart rate is <60 bpm, systolic BP is <100 mmHg, or if advanced heart block or active asthma is present.",
        "Drug Interactions": "Concurrent IV administration with calcium channel blockers (e.g., Verapamil) carries a high risk of complete heart block."
    },
    "Labetalol amp": {
        "Clinical Indication": "Acute hypertensive crises, aortic dissection, and severe hypertension in pregnancy.",
        "Acute Dosage": "• 20mg slow IV push over 2 minutes, followed by 40-80mg every 10 minutes (maximum 300mg) or via continuous infusion.",
        "Critical Warnings": "Monitor heart rate and blood pressure constantly. Ensure the patient remains supine to prevent profound orthostatic collapse.",
        "Drug Interactions": "Synergistic bradycardia and hypotensive effect when combined with halothane or volatile anesthetics."
    },
    "Sod.Nitroprusside": {
        "Clinical Indication": "Immediate reduction of blood pressure in severe, life-threatening hypertensive emergencies and acute aortic dissection.",
        "Acute Dosage": "• Continuous IV infusion starting at 0.3 mcg/kg/min, titrated meticulously to achieve controlled target blood pressure reduction.",
        "Critical Warnings": "Light-sensitive solution; wrap the container in foil. Prolonged infusion carries a major risk of cyanide and thiocyanate toxicity.",
        "Drug Interactions": "Concomitant antihypertensives significantly potentiate its rapid vasodilatory activity."
    },
    "Verapamil Amp": {
        "Clinical Indication": "Termination of paroxysmal supraventricular tachycardia (PSVT) and rate control in atrial fibrillation/flutter with rapid ventricular rates.",
        "Acute Dosage": "• 2.5mg to 5mg slow IV bolus over 2 minutes. A repeat dose of 5-10mg can be given after 15-30 minutes if needed.",
        "Critical Warnings": "Absolutely contraindicated in wide-complex tachycardias of unknown origin, Wolf-Parkinson-White (WPW) syndrome, and severe heart failure.",
        "Drug Interactions": "Increases plasma levels of digoxin. Combined with beta-blockers, it may induce severe bradycardia and asystole."
    },
    "Heparin Vial": {
        "Clinical Indication": "Acute treatment of unstable angina, acute myocardial infarction, deep vein thrombosis (DVT), and acute pulmonary embolism.",
        "Acute Dosage": "• IV bolus of 60-80 units/kg (max 4000-5000 units), followed immediately by a continuous maintenance infusion titrated to aPTT targets.",
        "Critical Warnings": "High risk of severe bleeding. Monitor platelet counts closely to watch for Heparin-Induced Thrombocytopenia (HIT).",
        "Drug Interactions": "Antiplatelet agents like Aspirin and Clopidogrel exponentially multiply the risk of major hemorrhage."
    },
    "Alteplase Vial": {
        "Clinical Indication": "Acute ischemic stroke (within 4.5 hours of symptom onset), acute massive pulmonary embolism, and STEMI when primary PCI is unavailable.",
        "Acute Dosage": "• Stroke Protocol: 0.9 mg/kg total dose (maximum 90mg); administer 10% as an immediate IV bolus over 1 minute, and the remaining 90% as a continuous 60-minute infusion.",
        "Critical Warnings": "Exposed to severe intracranial hemorrhage risk. Perform a thorough exclusion checklist (active internal bleeding, recent surgery, platelet count) before initiation.",
        "Drug Interactions": "Concomitant use of anticoagulants, antiplatelets, or NSAIDs increases systemic bleeding risks drastically."
    },
    "Tranexamic a. amp": {
        "Clinical Indication": "Immediate management of severe traumatic hemorrhage, postpartum hemorrhage (PPH), and surgical bleeding control.",
        "Acute Dosage": "• 1g slow IV infusion over 10 minutes administered within 3 hours of injury/onset, followed by another 1g infused over 8 hours.",
        "Critical Warnings": "Rapid IV injection can cause significant, transient hypotension. Ensure slow administration over at least 10 minutes.",
        "Drug Interactions": "Concurrent use with factor IX complex or hormonal contraceptives may increase the baseline risk of thromboembolism."
    },
    "Captopril tab": {
        "Clinical Indication": "Acute management of severe hypertension and reduction of afterload in congestive heart failure.",
        "Acute Dosage": "• 6.25mg to 25mg orally or sublingually, repeatable based on serial blood pressure assessments.",
        "Critical Warnings": "Can precipitate acute angioedema (airway emergency) or severe hyperkalemia. Contraindicated in bilateral renal artery stenosis.",
        "Drug Interactions": "Potentiates hyperkalemia if given with potassium supplements, potassium-sparing diuretics, or NSAIDs."
    },
    "Salbutamol Neb. ": {
        "Clinical Indication": "Relief of severe acute bronchospasm in asthma and COPD, and adjunctive therapy to shift potassium in hyperkalemia.",
        "Acute Dosage": "• Via Nebulization: 2.5 to 5mg diluted in normal saline, repeated as indicated based on clinical response.",
        "Critical Warnings": "Use with caution in patients with ischemic heart disease as it routinely induces tachycardia and palpitations.",
        "Drug Interactions": "Beta-blockers directly neutralize its bronchodilatory effects; loop diuretics can worsen hypokalemia."
    },
    "Ipratropium  neb": {
        "Clinical Indication": "Acute severe bronchospasm, acting as a synergistic anticholinergic adjunct to Salbutamol during acute asthma or COPD flare-ups.",
        "Acute Dosage": "• Via Nebulization: 500mcg mixed with Salbutamol solution every 20 minutes for up to 3 consecutive doses.",
        "Critical Warnings": "Ensure a tightly fitted mask; ocular exposure can precipitate acute pupillary dilation (mydriasis) and narrow-angle glaucoma.",
        "Drug Interactions": "Concomitant administration with systemic anticholinergics increases risks of dry mouth and acute urinary retention."
    },
    "Budesonide Nob.": {
        "Clinical Indication": "Reduction of airway inflammation in acute severe asthma exacerbations and croup in pediatric patients.",
        "Acute Dosage": "• Via Nebulization: 1mg to 2mg administered as a single dose or divided twice daily during acute stabilization phases.",
        "Critical Warnings": "Not intended for immediate single-agent first-line rescue of bronchospasm; always combine with short-acting beta-agonists.",
        "Drug Interactions": "No major acute interactions in short-term emergency inhalation use."
    },
    "Aminophylline amp": {
        "Clinical Indication": "Adjunctive management of severe acute bronchospasm refractory to first-line nebulizers and corticosteroids.",
        "Acute Dosage": "• IV Loading Dose: 5-6 mg/kg slow IV infusion over 20-30 minutes, followed by a continuous maintenance infusion.",
        "Critical Warnings": "Extremely narrow therapeutic index. Toxic signs include persistent vomiting, severe tachyarrhythmias, and generalized seizures.",
        "Drug Interactions": "Ciprofloxacin and Erythromycin markedly decrease its clearance, rapidly elevating plasma toxicity risks."
    },
    "H.C Vial": {
        "Clinical Indication": "Status asthmaticus, severe anaphylaxis, and acute adrenal (Addisonian) crisis.",
        "Acute Dosage": "• 100mg to 500mg slow IV push or IM injection, repeatable every 6 hours based on clinical response.",
        "Critical Warnings": "Promotes rapid acute elevation of blood glucose levels; requires close glycemic monitoring in diabetic patients.",
        "Drug Interactions": "Concomitant use with loop diuretics accelerates potassium wasting, predisposing the patient to hypokalemia."
    },
    "Prednisolone tab": {
        "Clinical Indication": "Intermediate oral anti-inflammatory management of severe asthma or COPD exacerbations post-stabilization.",
        "Acute Dosage": "• 40mg to 60mg orally as a single daily dose or divided, typically for a 5-day acute course.",
        "Critical Warnings": "Can cause acute gastrointestinal irritation, mood disturbances, and hyperglycemia.",
        "Drug Interactions": "NSAIDs concurrently administered increase the risk of gastrointestinal ulceration and hemorrhage."
    },
    "Insulin Soluble Vial": {
        "Clinical Indication": "Diabetic Ketoacidosis (DKA), Hyperosmolar Hyperglycemic State (HHS), and emergency management of severe hyperkalemia.",
        "Acute Dosage": "• In DKA/HHS: Continuous IV infusion at 0.1 units/kg/hour (verify serum potassium is >3.3 mEq/L before starting).\n• In Hyperkalemia: 10 units Regular Insulin IV administered with 50ml of Dextrose 50%.",
        "Critical Warnings": "Requires mandatory hourly capillary blood glucose and serial potassium monitoring to prevent fatal hypoglycemia.",
        "Drug Interactions": "Systemic corticosteroids directly counteract and elevate blood glucose levels."
    },
    "Glucagon amp": {
        "Clinical Indication": "Severe acute hypoglycemia when intravenous access cannot be established, and as a specific antidote for Beta-Blocker overdose.",
        "Acute Dosage": "• In Hypoglycemia: 1mg Intramuscular (IM) or Subcutaneous (SC) injection.\n• In Beta-Blocker Overdose: 5–10mg slow IV push, followed by continuous infusion.",
        "Critical Warnings": "Ineffective in patients with chronic starvation or advanced hepatic failure due to complete depletion of glycogen stores.",
        "Drug Interactions": "Repeated high doses can significantly potentiate the anticoagulant effect of Warfarin."
    },
    "Diazepam amp": {
        "Clinical Indication": "Acute status epilepticus, severe muscle spasms, and acute agitation associated with alcohol withdrawal.",
        "Acute Dosage": "• 5mg to 10mg slow IV push (rate not exceeding 5mg/minute), repeatable every 10–15 minutes up to a maximum of 30mg.",
        "Critical Warnings": "High risk of inducing severe respiratory depression and hypotension. Airway equipment must be ready at the bedside.",
        "Drug Interactions": "Concomitant administration with opioids or other CNS depressants multiplies the risk of fatal respiratory failure."
    },
    "Midazolam amp": {
        "Clinical Indication": "Procedural sedation, termination of acute status epilepticus, and induction of anesthesia prior to endotracheal intubation.",
        "Acute Dosage": "• For Sedation: 1mg to 2.5mg slow IV push over 2 minutes.\n• For Seizures (No IV Access): 10mg Intramuscular (IM) injection into the mid-thigh.",
        "Critical Warnings": "Exceptionall rapid onset; potent capability to induce respiratory depression and apnea.",
        "Drug Interactions": "Potent CYP3A4 inhibitors (e.g., Clarithromycin) significantly prolong the half-life and sedation depth."
    },
    "Phenytoin amp": {
        "Clinical Indication": "Status epilepticus control and prevention of seizures following neurosurgery or severe traumatic brain injury.",
        "Acute Dosage": "• Loading Dose: 15-20 mg/kg IV infusion, administered at a strict maximum rate of 50 mg/min, diluted exclusively in Normal Saline.",
        "Critical Warnings": " Infusion in Dextrose causes immediate chemical precipitation. Rapid push can precipitate fatal cardiovascular collapse and arrhythmias.",
        "Drug Interactions": "Amiodarone and Ciprofloxacin increase plasma phenytoin levels, elevating central nervous system toxicity risks."
    },
    "Phenobarbital amp": {
        "Clinical Indication": "Refractory status epilepticus following failure of first-line benzodiazepines and phenytoin.",
        "Acute Dosage": "• 15-20 mg/kg slow IV infusion at a maximum delivery rate of 50-100 mg/minute until seizures terminate.",
        "Critical Warnings": "Induces profound, deep sedation and prolonged respiratory depression; mechanical ventilatory support is almost universally required.",
        "Drug Interactions": "Potent inducer of hepatic CYP450 enzymes, significantly accelerating the metabolism and clearance of many emergency drugs."
    },
    "Chlorpromazine amp": {
        "Clinical Indication": "Acute psychiatric agitation, intractable hiccups, and severe nausea/vomiting refractory to other agents.",
        "Acute Dosage": "• 25mg to 50mg deep intramuscular injection, or via slow, heavily diluted IV infusion.",
        "Critical Warnings": "Can cause severe orthostatic hypotension and significant QT interval prolongation on the ECG.",
        "Drug Interactions": "Potentiates the sedative and respiratory depressive actions of all narcotics, barbiturates, and tranquilizers."
    },
    "Haloperidol amp": {
        "Clinical Indication": "Acute management of severe psychotic agitation, delirium in the elderly, and combativeness in the emergency department.",
        "Acute Dosage": "• 2.5mg to 10mg deep Intramuscular (IM) injection, repeatable every 30-60 minutes until behavioral control is achieved.",
        "Critical Warnings": "High risk of Extrapyramidal Symptoms (EPS) and neuroleptic malignant syndrome. Monitor ECG for QT prolongation.",
        "Drug Interactions": "Combined with other QT-prolonging drugs (e.g., Amiodarone, Ondansetron) exponentially increases torsades risks."
    },
    "Paracetamol Vial": {
        "Clinical Indication": "Short-term management of moderate to severe acute pain and immediate reduction of high hyperpyrexia.",
        "Acute Dosage": "• 1g (1000mg) intravenously via continuous infusion over 15 minutes, repeatable every 6 hours (maximum 4g/day).",
        "Critical Warnings": "Contraindicated in severe hepatic impairment or acute liver failure. Meticulously calculate dosing in malnourished patients.",
        "Drug Interactions": "Concomitant use with hepatotoxic medications or alcohol increases risks of irreversible hepatic necrosis."
    },
    "Diclofenac amp": {
        "Clinical Indication": "Acute management of severe renal colic, biliary colic, and acute musculoskeletal pain.",
        "Acute Dosage": "• 75mg via deep Intramuscular (IM) injection into the upper outer quadrant of the gluteal muscle.",
        "Critical Warnings": "Absolutely contraindicated in active gastrointestinal ulcers, severe heart failure, or severe renal impairment.",
        "Drug Interactions": "Concomitant use with anticoagulants (Heparin/Warfarin) increases systemic bleeding risks significantly."
    },
    "Nefopam amp": {
        "Clinical Indication": "Relief of acute post-operative pain or moderate-to-severe traumatic pain refractory to standard NSAIDs.",
        "Acute Dosage": "• 20mg slow Intramuscular (IM) injection or slow IV infusion over 15-30 minutes.",
        "Critical Warnings": "Can cause significant anticholinergic side effects (tachycardia, urinary retention, dry mouth). Contraindicated in patients with seizures.",
        "Drug Interactions": "Monoamine oxidase inhibitors (MAOIs) can precipitate severe hypertensive crisis if combined with nefopam."
    },
    "Tramadol amp": {
        "Clinical Indication": "Management of moderate to severe acute pain where non-opioid analgesics are insufficient or contraindicated.",
        "Acute Dosage": "• 50mg to 100mg slow IV injection (over 2-3 minutes) or deep Intramuscular injection, repeatable every 4-6 hours.",
        "Critical Warnings": "Can lower the seizure threshold. Use with extreme caution in patients with epilepsy or head injuries.",
        "Drug Interactions": "Highly dangerous with SSRIs or MAOIs, heavily increasing the clinical risk of Serotonين Syndrome."
    },
    "Dexamethasone amp": {
        "Clinical Indication": "Cerebral edema associated with brain tumors/trauma, severe croup, anaphylactic shock adjunct, and severe bacterial meningitis.",
        "Acute Dosage": "• 4mg to 10mg IV bolus initially, followed by fractional dosing every 6 hours based on etiology.",
        "Critical Warnings": "May cause acute psychiatric disturbances, transient perineal burning upon rapid IV injection, and hyperglycemia.",
        "Drug Interactions": "Diminishes the effectiveness of antidiabetic agents; clearance is accelerated by phenytoin."
    },
    "Xylocaine amp": {
        "Clinical Indication": "Local anesthesia for wound suturing, minor surgical procedures, and infiltration blocks.",
        "Acute Dosage": "• Infiltrate locally around wound edges; dose depends on the area, not to exceed 4.5 mg/kg of plain solution.",
        "Critical Warnings": "Never inject directly into blood vessels. Perform an aspiration test prior to injection to ensure needle placement is non-venous.",
        "Drug Interactions": "Cimetidine and beta-blockers decrease hepatic clearance of lidocaine, elevating systemic toxicity thresholds."
    },
    "Xylocaine Vial": {
        "Clinical Indication": "Local/regional nerve blockade, or management of acute ventricular arrhythmias (alternative to amiodarone in VF/pVT).",
        "Acute Dosage": "• Antiarrhythmic: IV bolus of 1-1.5 mg/kg over 2 minutes, followed by maintenance infusion.",
        "Critical Warnings": "Systemic toxicity (LAST) causes central nervous system excitation, seizures, followed by cardiovascular collapse.",
        "Drug Interactions": "Concomitant antiarrhythmics (like Amiodarone) potentiate myocardial depressive and neurological effects."
    },
    "Metoclopramide amp": {
        "Clinical Indication": "Symptomatic control of severe nausea and vomiting, and stimulation of upper GI motility.",
        "Acute Dosage": "• 10mg slow IV push over 1–2 minutes (slow delivery minimizes transient acute akathisia).",
        "Critical Warnings": "Can induce acute extrapyramidal symptoms (EPS), presenting as acute dystonia, particularly in young adults.",
        "Drug Interactions": "Concomitant use with antipsychotics is strictly contraindicated to prevent Neuroleptic Malignant Syndrome (NMS)."
    },
    "Ondansetron amp": {
        "Clinical Indication": "Prevention and management of severe acute nausea and vomiting associated with gastroenteritis or surgical emergencies.",
        "Acute Dosage": "• 4mg to 8mg slow IV push over 2 minutes, or deep intramuscular injection.",
        "Critical Warnings": "Can cause dose-dependent QT interval prolongation on the ECG. Use with caution in long-QT syndromic histories.",
        "Drug Interactions": "Concomitant use with other serotonergic drugs increases the risk of Serotonين Syndrome."
    },
    "Furosemide amp": {
        "Clinical Indication": "Acute pulmonary edema in heart failure, and fluid volume overload associated with renal failure.",
        "Acute Dosage": "• 20mg to 40mg slow IV push administered over 1–2 minutes.",
        "Critical Warnings": "Induces rapid, massive diuresis. Contraindicated in uncompensated hypovolemic shock and post-renal anuria.",
        "Drug Interactions": "Increases plasma toxicity thresholds of aminoglycoside antibiotics, worsening ototoxicity and nephrotoxicity."
    },
    "Calcium amp": {
        "Clinical Indication": "Myocardial membrane stabilization in severe hyperkalemia, acute symptomatic hypocalcemia, and magnesium toxicity.",
        "Acute Dosage": "• 10ml of a 10% solution via slow IV infusion over 5–10 minutes under continuous cardiac monitoring.",
        "Critical Warnings": "Rapid injection can provoke severe bradycardia and cardiac arrest. Never mix in the same line with sodium bicarbonate.",
        "Drug Interactions": "Heightens risk of lethal arrhythmias if administered to patients presenting with active Digoxin toxicity."
    },
    "Omeprazole Vial": {
        "Clinical Indication": "Acute upper gastrointestinal hemorrhage, bleeding peptic ulcers, and severe acute erosive gastritis.",
        "Acute Dosage": "• 80mg IV bolus over 5 minutes, followed by a continuous maintenance infusion or scheduled 40mg doses.",
        "Critical Warnings": "Ensure appropriate clinical verification of indication; not intended for routine non-bleeding abdominal pain.",
        "Drug Interactions": "Reduces the systemic clearance of phenytoin and may alter the absorption of pH-dependent medications."
    },
    "Esomeprazole Vial ": {
        "Clinical Indication": "Immediate reduction of gastric acid secretion in acute upper gastrointestinal bleeding and severe reflux presentations.",
        "Acute Dosage": "• 40mg to 80mg via slow intravenous injection or diluted continuous infusion.",
        "Critical Warnings": "Hypersensitivity reactions can occur. Monitor injection site for local thrombo-phlebitis signs.",
        "Drug Interactions": "Inhibits CYP2C19, which can decrease the metabolic conversion and efficacy of Clopidogrel."
    },
    "Hyoscine amp": {
        "Clinical Indication": "Acute symptomatic relief of severe spasmodic gastrointestinal cramps, biliary colic, and renal colic.",
        "Acute Dosage": "• 20mg via slow Intramuscular (IM) or Intravenous (IV) injection, repeatable after 30 minutes if required.",
        "Critical Warnings": "Contraindicated in patients with narrow-angle glaucoma, mechanical GI obstruction, or severe urinary retention.",
        "Drug Interactions": "Enhances the anticholinergic profile of tricyclic antidepressants and antihistamines."
    },
    "Diphenhydramine amp": {
        "Clinical Indication": "Acute allergic reactions, anaphylaxis adjunct, and treatment of drug-induced extrapyramidal dystonic reactions.",
        "Acute Dosage": "• 10mg to 50mg slow IV push or deep Intramuscular (IM) injection (maximum daily dose 400mg).",
        "Critical Warnings": "Marked sedative property. Can cause significant drowsiness, blurred vision, and urinary retention in elderly patients.",
        "Drug Interactions": "Synergistic CNS depression when administered with alcohol, opioids, or benzodiazepines."
    },
    "Chlorpheniramine amp": {
        "Clinical Indication": "Symptomatic control of acute allergic emergencies, urticaria, angioedema, and mild transfusion reactions.",
        "Acute Dosage": "• 10mg to 20mg slow IV push over 1 minute or via Intramuscular (IM) injection.",
        "Critical Warnings": "May cause significant sedation, dry mouth, and paradoxical central nervous system stimulation in pediatric profiles.",
        "Drug Interactions": "MAO inhibitors can significantly prolong and intensify the anticholinergic effects of chlorpheniramine."
    },
    "K.C.L amp": {
        "Clinical Indication": "Correction of documented severe, life-threatening hypokalemia.",
        "Acute Dosage": "• Must be heavily diluted in Normal Saline; typical maximum central line rate is 10-20 mEq/hour with continuous ECG tracking.",
        "Critical Warnings": "NEVER GIVE AS AN UNDILUTED IV PUSH. Direct injection causes immediate cardiac arrest and is invariably fatal.",
        "Drug Interactions": "Concomitant use of ACE inhibitors or K-sparing diuretics significantly increases the risk of hyperkalemic arrest."
    },
    "Hypertonic amp": {
        "Clinical Indication": "Emergency correction of severe, symptomatic, acute hyponatremia accompanied by seizures or altered sensorium.",
        "Acute Dosage": "• 100ml via slow IV infusion over 10-20 minutes, repeatable based on serial serum sodium reassessments.",
        "Critical Warnings": "Correct sodium slowly to avoid causing Central Pontine Myelinolysis (irreversible neurological destruction).",
        "Drug Interactions": "Requires close synchronization with any concurrent corticosteroid therapies."
    },
    "Sod. Bicarb amp": {
        "Clinical Indication": "Severe metabolic acidosis (pH <7.1), hyperkalemic cardiac arrest, and tricyclic antidepressant (TCA) toxic overdose.",
        "Acute Dosage": "• 50 mEq (1 ampule of 8.4%) slow IV push, repeatable based on serial arterial blood gas (ABG) monitoring.",
        "Critical Warnings": "Highly hypertonic; precipitates immediate chemical inactivation if mixed directly with catecholamines or calcium.",
        "Drug Interactions": "Alkalinization of urine accelerates the clearance of salicylates and phenobarbital."
    },
    "Mg Sulphate amp": {
        "Clinical Indication": "Control of seizures in eclampsia, severe refractory status asthmaticus, and treatment of Torsades de Pointes.",
        "Acute Dosage": "• Eclampsia: 4g IV loading dose infused over 15–20 minutes.\n• Torsades: 1–2g IV diluted in 100ml D5% infused over 10–15 minutes.",
        "Critical Warnings": "Toxicity precipitates loss of deep tendon reflexes, flaccid paralysis, and respiratory depression. Reversing antidote is Calcium Gluconate.",
        "Drug Interactions": "Concurrent use with calcium channel blockers can potentiate neuromuscular blockade and provoke severe hypotension."
    },
    "Ceftriaxone Vial": {
        "Clinical Indication": "Empiric treatment of severe infections, including bacterial meningitis, community-acquired pneumonia, and severe sepsis.",
        "Acute Dosage": "• 1g to 2g intravenously via slow infusion over 15-30 minutes, or reconstituted for deep intramuscular injection.",
        "Critical Warnings": " Never mix or co-administer with calcium-containing IV solutions (like Ringer's) to prevent fatal organ-depositing crystalline precipitates.",
        "Drug Interactions": "Increases risks of bleeding if administered concurrently with high-dose oral anticoagulants."
    },
    "Vancomycin Vial": {
        "Clinical Indication": "Severe MRSA infections, complicated skin/soft tissue infections, and severe septicemia.",
        "Acute Dosage": "• 15-20 mg/kg intravenously diluted heavily and infused slowly over a minimum duration of 60 minutes.",
        "Critical Warnings": " Rapid infusion induces 'Red Man Syndrome' (severe histamine-mediated flushing, pruritus, and profound hypotension).",
        "Drug Interactions": "Concurrent administration with aminoglycosides or loop diuretics multiplies risks of nephrotoxicity and ototoxicity."
    },
    "Amoxicillin Vial": {
        "Clinical Indication": "Suspected or verified susceptible bacterial infections involving the respiratory tract, skin structures, or urinary tract.",
        "Acute Dosage": "• 500mg to 1g intravenously or intramuscularly every 6-8 hours depending on clinical severity.",
        "Critical Warnings": "Absolutely contraindicated in patients with a history of documented anaphylactic immediate hypersensitivity to penicillins.",
        "Drug Interactions": "Probenecid concurrently decreases renal tubular secretion of amoxicillin, artificially elevating its plasma half-life."
    },
    "Gentamicin amp": {
        "Clinical Indication": "Severe gram-negative systemic infections, complicated urinary tract infections, and infective endocarditis synergism.",
        "Acute Dosage": "• 5-7 mg/kg intravenously via a single daily dose configuration, infused over 30-60 minutes.",
        "Critical Warnings": "Possesses severe dose-dependent nephrotoxicity and irreversible ototoxicity. Serial renal function tracking is mandatory.",
        "Drug Interactions": "Synergistic toxicity cascades if given alongside Furosemide or Vancomycin."
    },
    "Ciprofloxacin Vial": {
        "Clinical Indication": "Complicated intra-abdominal infections, severe urinary tract infections, and severe infectious gastroenteritis.",
        "Acute Dosage": "• 400mg intravenously infused slowly over a mandatory duration of 60 minutes, twice daily.",
        "Critical Warnings": "Associated with an increased baseline risk of tendon rupture, aortic aneurysm dissection, and severe QTc interval prolongation.",
        "Drug Interactions": "Significantly increases the systemic plasma levels of Aminophylline/Theophylline."
    },
    "Metronidazole bott.": {
        "Clinical Indication": "Anaerobic bacterial infections, severe amoebiasis, giardiasis, and empiric surgical intra-abdominal coverage.",
        "Acute Dosage": "• 500mg intravenously via continuous premixed bottle infusion administered over 20-30 minutes every 8 hours.",
        "Critical Warnings": " Causes a severe disulfiram-like reaction if alcohol is consumed during or within 48 hours of treatment.",
        "Drug Interactions": "Inhibits hepatic metabolism of Warfarin, exponentially increasing international normalized ratio (INR) bleeding outcomes."
    },
    "Acyclovir Vial": {
        "Clinical Indication": "Herpes simplex encephalitis, severe disseminated varicella-zoster, and severe initial mucocutaneous HSV in immunocompromised patients.",
        "Acute Dosage": "• 10 mg/kg intravenously infused slowly over 1 hour, repeated every 8 hours.",
        "Critical Warnings": "Can precipitate as crystals inside renal tubules, causing acute tubular necrosis. Maintain vigorous baseline IV hydration.",
        "Drug Interactions": "Concomitant nephrotoxic medications dramatically accelerate the risk of acute kidney injury."
    },
    "H.T Saline 3% bott.": {
        "Clinical Indication": "Immediate osmotic shift required in intracranial hypertension, cerebral edema, and severe acute hyponatremic encephalopathy.",
        "Acute Dosage": "• Infuse via a secure, verified large central line; typical rate is 100-250ml over 20-30 minutes depending on neurology.",
        "Critical Warnings": "Extremely high tonicity. Extravasation causes massive local tissue sloughing; monitor serum sodium continuously.",
        "Drug Interactions": "No major immediate pharmacological drug binding interactions."
    },
    "Tenofovir cap": {
        "Clinical Indication": "Post-exposure prophylaxis (PEP) for HIV following occupational needle-stick or non-occupational high-risk exposure.",
        "Acute Dosage": "• 300mg orally once daily, administered in combination with other antiretroviral agents for a strict 28-day course.",
        "Critical Warnings": "Assess baseline renal function; can cause acute or progressive renal impairment and bone mineral density loss.",
        "Drug Interactions": "Concomitant use of nephrotoxic NSAIDs should be strictly avoided during therapy."
    },
    "Charcoal Powder  ": {
        "Clinical Indication": "Emergency gastrointestinal decontamination following acute ingestion of specific toxic substances or pharmaceutical overdoses.",
        "Acute Dosage": "• 25g to 50g (or 1 g/kg) reconstituted in water to form a slurry, administered orally or via a nasogastric tube within 1-2 hours of ingestion.",
        "Critical Warnings": " Absolutely contraindicated in un-intubated patients with depressed consciousness (severe aspiration risk) and ingestion of corrosives/hydrocarbons.",
        "Drug Interactions": "Directly adsorbs and neutralizes oral antidotes (e.g., Acetaminophen antidote N-Acetylcysteine) if present in the stomach simultaneously."
    },
    "Anti Snake amp": {
        "Clinical Indication": "Immediate neutralization of circulating venom following bites by venomous snakes with systemic toxicity signs.",
        "Acute Dosage": "• Reconstitute 5 to 10 vials(10ml amp =500 LD50) immediately, dilute in 250–500ml of Normal Saline, and infuse intravenously over 30–60 minutes.",
        "Critical Warnings": " Exceptionally high risk of type-I anaphylactic shock. Epinephrine must be drawn and available at the bedside.",
        "Drug Interactions": "Pre-treatment with antihistamines does not reliably prevent anti-venom anaphylaxis; never replace epinephrine readiness."
    },
    "Anti Scorpion amp": {
        "Clinical Indication": "Neutralization of dangerous scorpion neurotoxins, specifically in pediatric or elderly presenting severe autonomic crisis.",
        "Acute Dosage": "• Administer 1 to 2 vials via slow direct IV injection, or diluted in 50ml of Normal Saline over 15 minutes.",
        "Critical Warnings": "Strictly avoid Morphine for pain control as it can synergistically compound venom-induced central respiratory depression.",
        "Drug Interactions": "Sedatives and central muscle relaxants interact synergistically with scorpion toxins on respiratory centers."
    },
    "A.R.V Vaccine": {
        "Clinical Indication": "Immediate post-exposure active immunization following suspected rabid animal bites or scratches.",
        "Acute Dosage": "• Inject a 1ml=~2.5IU dose Intramuscularly (IM) into the deltoid muscle on days 0, 3, 7, and 14. or two doses at first day and 7,21 ",
        "Critical Warnings": " Never inject into the gluteal region due to poor adipose drug absorption. Never mix with RIG in the same syringe.",
        "Drug Interactions": "High-dose systemic corticosteroids impair antibody production cascade responses to the vaccine."
    },
    "A.R IG": {
        "Clinical Indication": "Passive immediate viral neutralization following high-risk suspected rabid animal exposures (Category III wounds).",
        "Acute Dosage": "• Infiltrate the entire calculated dose (20 IU/kg for human RIG) deeply into and directly around all wound edges (syringe -2ml- = 300 IU ... kg / 15 = NO of syringes).",
        "Critical Warnings": " Any remaining volume not matching the wound margins must be injected IM at an anatomical site distant from the vaccine.",
        "Drug Interactions": "Do not administer at the same anatomical site or in the same syringe as the active Rabies Vaccine."
    },
    "A.T IG / ATS": {
        "Clinical Indication": "Immediate passive immunization and toxin neutralization for contaminated or deep devitalized injuries in non-immunized patients.",
        "Acute Dosage": "• Administer Tetanus Toxoid booster AND administer Human Tetanus Immune Globulin (HTIG) syringe = 250 IU IM into opposite limbs.",
        "Critical Warnings": " Always inject the Tetanus vaccine booster and the Immunoglobulin at completely separate anatomical sites to prevent in-vivo neutralization.",
        "Drug Interactions": "Active chemotherapy or immunosuppression lowers the long-term antibody synthesis response."
    },
    "Pralidoxime vial": {
        "Clinical Indication": "Specific antidote for severe organophosphate insecticide poisoning, acting to reactivate acetylcholinesterase.",
        "Acute Dosage": "• 1g to 2g intravenously via slow infusion over 15-30 minutes, repeatable every 6 hours or as a continuous infusion.",
        "Critical Warnings": "Must be administered in conjunction with Atropine. Rapid administration can induce neuromuscular blockade and hypertension.",
        "Drug Interactions": "Barbiturates are potentiated by anticholinesterase compounds; use with extreme caution if managing seizures."
    },
    "Naloxone Amp": {
        "Clinical Indication": "Complete or partial reversal of opioid-induced respiratory depression and toxic overdose.",
        "Acute Dosage": "• 0.4mg to 2mg IV (or IM/SC), repeatable every 2–3 minutes if desired respiratory baseline is not achieved.",
        "Critical Warnings": "In opioid-dependent individuals, it abruptly precipitates an acute, severe withdrawal syndrome with extreme agitation.",
        "Drug Interactions": "Acts as a direct, competitive antagonist across central opioid receptors, reversing all narcotic analgesia."
    },
    "N.A.C Amp": {
        "Clinical Indication": "Specific antidote for toxic Acetaminophen (Paracetamol) overdose to prevent severe irreversible hepatic necrosis.",
        "Acute Dosage": "• Three-bag IV protocol: 150 mg/kg over 1 hour, followed by 50 mg/kg over 4 hours, and 100 mg/kg over the remaining 16 hours.",
        "Critical Warnings": "Can induce significant anaphylactoid reactions (flushing, pruritus, bronchospasm); slow down the initial infusion rate if noted.",
        "Drug Interactions": "Activated charcoal adsorbs oral NAC; do not administer both orally within close temporal proximity."
    },
    "Flumazenil amp": {
        "Clinical Indication": "Complete or partial reversal of the sedative effects of benzodiazepines following general anesthesia or toxic overdose.",
        "Acute Dosage": "• 0.2mg intravenously over 30 seconds, repeatable at 0.5mg increments up to a maximum cumulative dose of 3mg.",
        "Critical Warnings": " Can precipitate severe, intractable, life-threatening seizures in chronic benzodiazepine users or cyclic antidepressant overdoses.",
        "Drug Interactions": "Directly blocks the central receptor pathway of all benzodiazepine-class structures."
    },
    "Protamine Amp": {
        "Clinical Indication": "Specific immediate neutralizing antidote to reverse life-threatening hemorrhage induced by Unfractionated Heparin toxicity.",
        "Acute Dosage": "• 1mg of Protamine neutralizes approximately 100 units of Heparin; administer via very slow IV infusion not exceeding 50mg over 10 minutes.",
        "Critical Warnings": " Hyper-rapid infusion can precipitate catastrophic systemic hypotension, severe bradycardia, and acute pulmonary vasoconstriction.",
        "Drug Interactions": "Forms an inert chemical salt complex when binding in vivo with circulating Heparin molecules."
    },
    "Digoxin FAB amp": {
        "Clinical Indication": "Specific antidote for life-threatening digitalis toxicity presenting with refractory ventricular arrhythmias or severe hyperkalemia.",
        "Acute Dosage": "• Dose is weight/ingestion dependent; typical initial empiric emergency loading is 4 to 10 vials dissolved and infused over 30 minutes.",
        "Critical Warnings": "Following administration, total serum digoxin levels will rise and become uninterpretable; monitor clinical ECG stability instead.",
        "Drug Interactions": "Binds and neutralizes circulating free digoxin, rapidly shifting potassium levels back into cellular structures."
    },
    "Prochlorperazine amp": {
        "Clinical Indication": "Severe acute vertigo, labyrinthine disorders, and symptomatic relief of severe refractory nausea and vomiting.",
        "Acute Dosage": "• 12.5mg deep Intramuscular (IM) injection, followed by oral maintenance titration if stable.",
        "Critical Warnings": "Associated with high rates of acute dystonic extrapyramidal reactions. Contraindicated in pediatric populations under 10kg.",
        "Drug Interactions": "Potentiates the central depressive effects of general anesthetics, tranquilizers, and barbiturates."
    },
    "Vit K  amp": {
        "Clinical Indication": "Correction of severe Warfarin-induced coagulopathy, elevated INR with active bleeding, and Vitamin K deficiency states.",
        "Acute Dosage": "• 5mg to 10mg slow IV infusion diluted in 50ml Normal Saline administered over 20-30 minutes.",
        "Critical Warnings": " Intravenous push is strictly contraindicated due to an exceptionally high risk of severe, fatal anaphylactoid shock.",
        "Drug Interactions": "Direct physiological antagonist to the competitive vitamin K epoxide reductase action of Warfarin."
    },
    "Vit B1 amp": {
        "Clinical Indication": "Prevention and treatment of acute Wernicke's Encephalopathy in chronic alcoholics or severely malnourished emergency admissions.",
        "Acute Dosage": "• 500mg intravenously infused over 30 minutes, administered three times daily for acute stabilization phases.",
        "Critical Warnings": " Always administer Vitamin B1 BEFORE or simultaneously with any hypertonic Dextrose solutions to prevent precipitating encephalopathy collapse.",
        "Drug Interactions": "No major chemical cross-binding interactions reported in emergency protocols."
    },
    "Vit B6 amp": {
        "Clinical Indication": "Specific acute antidote for systemic Isoniazid (INH) poisoning-induced seizures and peripheral neuropathies.",
        "Acute Dosage": "• Administer gram-for-gram equivalent to the ingested dose of Isoniazid (usually 5g IV) mixed in normal saline over 10-15 minutes.",
        "Critical Warnings": "High doses can occasionally cause transient sensory neuropathies; mandatory for refractory INH status epilepticus.",
        "Drug Interactions": "Directly complexes and reverses the neurotoxic GABA-depletion mechanisms of isoniazid toxicity."
    },
    "Hydroxy.C.Q. tab": {
        "Clinical Indication": "Adjunctive management of specific acute rheumatological flare-ups or targeted antimalarial protocols.",
        "Acute Dosage": "• 200mg to 400mg orally once daily, adjusted based on systemic clinical indication parameters.",
        "Critical Warnings": "Can cause acute gastrointestinal distress, macular changes with long-term use, and severe hypoglycemia.",
        "Drug Interactions": "May increase plasma digoxin levels; concurrent use with QT-prolonging drugs requires extreme monitoring vigilance."
    },
    "Tetracycline eye oin": {
        "Clinical Indication": "Prophylaxis and topical management of acute superficial ocular bacterial infections, conjunctivitis, and blepharitis.",
        "Acute Dosage": "• Apply a small thin ribbon (approximately 1 cm) into the lower conjunctival sac of the affected eye 2 to 4 times daily.",
        "Critical Warnings": "For topical ophthalmic application exclusively; may cause transient blurred vision immediately following application.",
        "Drug Interactions": "No clinically significant systemic drug interactions when localized to ophthalmic tissues."
    },
    "Fucidin oint.": {
        "Clinical Indication": "Topical management of localized superficial primary and secondary pyogenic skin infections, including impetigo and folliculitis.",
        "Acute Dosage": "• Apply gently to the affected clean skin surface 2 to 3 times daily, typically for a duration of 7 days.",
        "Critical Warnings": "Avoid application near open mucosal margins or eyes; discontinue if localized severe hypersensitivity or irritation develops.",
        "Drug Interactions": "No major localized interactions; safe for targeted multi-microbial skin presentations."
    },
    "Flamazine oint.": {
        "Clinical Indication": "Prevention and management of bacterial infection in second and third-degree severe burn wounds.",
        "Acute Dosage": "• Apply a thick layer (approximately 3-5mm) directly to the debrided burn surface daily using sterile technique.",
        "Critical Warnings": " Contraindicated in premature infants, newborns, and late-term pregnant patients due to the clinical risk of inducing kernicterus.",
        "Drug Interactions": "Proteolytic enzymes used concurrently for wound debridement may become inactivated by silver ions."
    },
    "Xylocaine oint.": {
        "Clinical Indication": "Temporary relief of pain associated with minor skin abrasions, localized burns, or prior to minor surface instrumentation.",
        "Acute Dosage": "• Apply thinly to the targeted dry surface area; do not exceed a maximum cumulative application of 5g within 24 hours.",
        "Critical Warnings": "Do not apply over extensive broken skin areas or deep traumatic lacerations to avoid systemic toxic absorption cascades.",
        "Drug Interactions": "Systemic local anesthetic toxicities multiply if given alongside concurrent antiarrhythmics."
    },
    "Normal Saline (N\\S 500 ml / N\\S 100 ml)": {
        "Clinical Indication": "Composition: Isotonic 0.9% Sodium Chloride aqueous solution.",
        "Acute Dosage": "Applications: Management of hypovolemic shock, severe dehydration, and serves as the vehicle for reconstituting medications.",
        "Critical Warnings": "Precautions: Avoid in congestive heart failure/renal impairment to prevent pulmonary edema.",
        "Drug Interactions": "Compatible with most emergency medications."
    },
    "Glucose Saline (G\\S 500 ml)": {
        "Clinical Indication": "Composition: Mixture of 0.9% NaCl and 5% Dextrose.",
        "Acute Dosage": "Applications: Maintenance of hydration and providing essential carbohydrate energy.",
        "Critical Warnings": "Precautions: Contraindicated for massive hemorrhagic resuscitation. Monitor glucose in diabetics.",
        "Drug Interactions": "Do not co-administer with blood transfusions."
    },
    "Glucose Water (G\\W 500 ml)": {
        "Clinical Indication": "Composition: Pure water containing 5% Dextrose.",
        "Acute Dosage": "Applications: Emergency correction of hypernatremia and treatment of severe hypoglycemia.",
        "Critical Warnings": "Precautions: Contraindicated in acute ischemic stroke or traumatic brain injury.",
        "Drug Interactions": "Causes hemolysis if mixed with blood products."
    },
    "Ringer's Solution / Ringer's Lactate": {
        "Clinical Indication": "Composition: Balance of NaCl, KCl, CaCl, and Sodium Lactate.",
        "Acute Dosage": "Applications: First-line for hemorrhagic shock, multi-trauma, and major burns.",
        "Critical Warnings": "Precautions: Strictly contraindicated to mix with Ceftriaxone. Use with caution in hepatic failure.",
        "Drug Interactions": "Incompatible with citrated whole blood."
    },
    "Mannitol Solution": {
        "Clinical Indication": "Composition: Hypertonic 20% Mannitol solution.",
        "Acute Dosage": "Applications: Reduction of intracranial pressure (ICP) and intraocular pressure (IOP).",
        "Critical Warnings": "Precautions: Contraindicated in active uncontrolled intracranial hemorrhage or anuric renal failure.",
        "Drug Interactions": "Potentiates loop diuretics."
    }
}

LAB_INTERPRETATION_GUIDE = {
    # تم الحفاظ على التحاليل بالكامل كما في كودك الأصلي
    "CBC - Hemoglobin (Hb)": {
        "Overview": "Measures the hemoglobin protein responsible for transporting oxygen.",
        "High": "🔴 Potential Etiologies: Severe dehydration, chronic smoking, or Polycythemia Vera.",
        "Low": "🔵 Potential Etiologies: Acute/chronic anemia, active hemorrhage, or IV fluid overload."
    },
    "Platelets": {
        "Overview": "Thrombocytes essential for blood clotting and hemostasis.",
        "High": "🔴 Potential Etiologies: Chronic inflammatory states, post-splenectomy.",
        "Low": "🔵 Potential Etiologies: ITP, DIC, or liver cirrhosis."
    },
    "INR": {
        "Overview": "International standardized ratio based on PT; monitors Warfarin therapy.",
        "High": "🔴 Potential Etiologies: Warfarin toxicity, acute hepatic failure, or DIC.",
        "Low": "🔵 Clinical Note: Subtherapeutic values carry a high risk of thromboembolism."
    },
    "WBC (White Blood Cells)": {
        "Overview": "Total leukocyte count reflecting the body's acute immune response.",
        "High": "🔴 Potential Etiologies: Acute bacterial infections, tissue necrosis, or leukemia.",
        "Low": "🔵 Potential Etiologies: Severe viral infections, bone marrow suppression."
    },
    "Prothrombin Time (PT)": {
        "Overview": "Evaluates extrinsic and common pathways; monitors liver synthesis.",
        "High": "🔴 Potential Etiologies: Advanced hepatic disease, vitamin K deficiency.",
        "Low": "🔵 Potential Etiologies: Hypercoagulable states."
    },
    "PTT (Partial Thromboplastin Time)": {
        "Overview": "Evaluates intrinsic and common pathways; monitors Heparin therapy.",
        "High": "🔴 Potential Etiologies: Unfractionated Heparin therapy, Hemophilia.",
        "Low": "🔵 Potential Etiologies: Acute phase response."
    },
    "D-Dimer": {
        "Overview": "Measures fibrin degradation products; excludes thromboembolism.",
        "High": "🔴 Potential Etiologies: DVT, PE, DIC, pregnancy, malignancy.",
        "Low": "🔵 Clinical Note: A normal result safely excludes thromboembolic events."
    },
    "S. Creatinine": {
        "Overview": "Primary endogenous biomarker for assessing renal filtration capacity.",
        "High": "🔴 Potential Etiologies: AKI, CKD, or severe prerenal hypoperfusion.",
        "Low": "🔵 Potential Etiologies: Severe muscle wasting or advanced malnutrition."
    },
    "Serum Potassium (K+)": {
        "Overview": "Critical electrolyte strictly regulating myocardial electrophysiology.",
        "High": "🔴 Potential Etiologies: Renal failure, tumor lysis syndrome (CRITICAL).",
        "Low": "🔵 Potential Etiologies: Profuse vomiting, loop/thiazide diuretics (CRITICAL)."
    },
    "Serum Chloride (Cl-)": {
        "Overview": "Major extracellular anion involved in hydration and acid-base balance.",
        "High": "🔴 Potential Etiologies: Severe dehydration, Renal Tubular Acidosis (RTA).",
        "Low": "🔵 Potential Etiologies: Prolonged vomiting or metabolic alkalosis."
    },
    "Blood Urea Nitrogen (BUN)": {
        "Overview": "Measures nitrogen derived from protein catabolism.",
        "High": "🔴 Potential Etiologies: Renal insufficiency, upper GI bleeding, or dehydration.",
        "Low": "🔵 Potential Etiologies: Advanced hepatic failure or malnutrition."
    },
    "Serum Sodium (Na+)": {
        "Overview": "Primary cation responsible for osmotic pressure and volume control.",
        "High": "🔴 Potential Etiologies: Pure water deficit (Diabetes Insipidus, heat stroke).",
        "Low": "🔵 Potential Etiologies: SIADH, CHF fluid retention, or aggressive diuretics."
    },
    "Total Serum Calcium (Ca++)": {
        "Overview": "Essential for skeletal integrity, cellular signaling, and coagulation.",
        "High": "🔴 Potential Etiologies: Hyperparathyroidism or osteolytic bone metastases.",
        "Low": "🔵 Potential Etiologies: Hypoalbuminemia, hypoparathyroidism, or acute pancreatitis."
    },
    "Troponin I": {
        "Overview": "Highly specific cardiac biomarker indicating myocardial cellular injury.",
        "High": "🔴 Potential Etiologies: Acute Coronary Syndrome (STEMI / NSTEMI).",
        "Low": "🔵 Clinical Note: Normal value excludes acute myocardial injury currently."
    },
    "NT-proBNP": {
        "Overview": "Released in response to volume expansion; vital for dyspnea triage.",
        "High": "🔴 Potential Etiologies: Acute Congestive Heart Failure (CHF) exacerbation.",
        "Low": "🔵 Clinical Note: Normal values rule out heart failure as a primary dyspnea cause."
    },
    "CK-MB": {
        "Overview": "Cardiac-specific isoenzyme confirmed for myocardial infarction.",
        "High": "🔴 Potential Etiologies: Acute MI, blunt cardiac trauma, or surgery.",
        "Low": "🔵 Clinical Note: Indicates the absence of recent acute myocardial damage."
    },
    "C-Reactive Protein (CRP)": {
        "Overview": "Acute-phase reactant synthesized in response to systemic inflammation.",
        "High": "🔴 Potential Etiologies: Acute bacterial infections or extensive burns.",
        "Low": "🔵 Clinical Note: Rules out widespread acute systemic inflammation."
    },
    "Arterial Blood pH": {
        "Overview": "Determines acid-base status and vital physiological homeostasis.",
        "High": "🔴 Alkalosis: Can be Respiratory or Metabolic.",
        "Low": "🔵 Acidosis: Can be Respiratory or Metabolic (DKA, shock)."
    },
    "HCO3 (Bicarbonate)": {
        "Overview": "Primary metabolic component of acid-base balance.",
        "High": "🔴 Potential Etiologies: Compensatory metabolic alkalosis.",
        "Low": "🔵 Potential Etiologies: Metabolic acidosis (DKA, renal failure)."
    },
    "Random Blood Sugar (RBS)": {
        "Overview": "Crucial triage test for altered mental status and seizures.",
        "High": "🔴 Potential Etiologies: DKA, HHS, or therapeutic non-compliance.",
        "Low": "🔵 Potential Etiologies: Insulin overdose or ethanol poisoning (CRITICAL)."
    },
    "pCO2": {
        "Overview": "Direct respiratory parameter of alveolar ventilation.",
        "High": "🔴 Potential Etiologies: Respiratory failure (COPD) or CNS depression.",
        "Low": "🔵 Potential Etiologies: Alveolar hyperventilation or metabolic acidosis compensation."
    },
    "Lactate": {
        "Overview": "Product of anaerobic metabolism indicating tissue hypoperfusion.",
        "High": "🔴 Potential Etiologies: Septic shock, ischemia, or severe hypoxemia.",
        "Low": "🔵 Clinical Note: Confirms adequate systemic tissue perfusion."
    },
    "ALT (SGPT)": {
        "Overview": "Specific marker for acute hepatocellular injury or necrosis.",
        "High": "🔴 Potential Etiologies: Acute viral hepatitis or drug overdose (Acetaminophen).",
        "Low": "🔵 Clinical Note: Lacks pathological significance generally."
    },
    "Total Bilirubin": {
        "Overview": "Bile pigment produced from erythrocyte breakdown.",
        "High": "🔴 Potential Etiologies: Biliary tract obstruction, acute hemolysis.",
        "Low": "🔵 Clinical Note: Subnormal levels lack clinical significance."
    },
    "Serum Lipase": {
        "Overview": "Specific pancreatic enzyme; diagnostic for acute pancreatitis.",
        "High": "🔴 Potential Etiologies: Acute pancreatitis (>3x upper limit).",
        "Low": "🔵 Clinical Note: Safely excludes acute pancreatic inflammation."
    },
    "AST (SGOT)": {
        "Overview": "Enzyme present in hepatic, myocardial, and skeletal tissues.",
        "High": "🔴 Potential Etiologies: Acute hepatocellular damage or MI.",
        "Low": "🔵 Clinical Note: Lacks acute pathological significance."
    },
    "Serum Amylase": {
        "Overview": "Digestive enzyme secreted by pancreas and salivary glands.",
        "High": "🔴 Potential Etiologies: Acute pancreatitis or intestinal obstruction.",
        "Low": "🔵 Potential Etiologies: Chronic pancreatic tissue destruction."
    }
}

LAB_TESTS_CONFIG = {
    "CBC - Hemoglobin (Hb)": {"unit": "g/dL", "min": 12.0, "max": 17.5},
    "WBC (White Blood Cells)": {"unit": "x10^3/µL", "min": 4.5, "max": 11.0},
    "Platelets": {"unit": "x10^3/µL", "min": 150.0, "max": 450.0},
    "PT (Prothrombin Time)": {"unit": "seconds", "min": 11.0, "max": 13.5},
    "PTT (Partial Thromboplastin Time)": {"unit": "seconds", "min": 25.0, "max": 35.0},
    "INR (International Normalized Ratio)": {"unit": "ratio", "min": 0.8, "max": 1.2},
    "D-Dimer": {"unit": "ng/mL", "min": 0.0, "max": 500.0},
    "S. Creatinine": {"unit": "mg/dL", "min": 0.6, "max": 1.2},
    "Blood Urea Nitrogen (BUN)": {"unit": "mg/dL", "min": 7.0, "max": 20.0},
    "Serum Potassium (K+)": {"unit": "mmol/L", "min": 3.5, "max": 5.1},
    "Serum Sodium (Na+)": {"unit": "mmol/L", "min": 135.0, "max": 145.0},
    "Serum Chloride (Cl-)": {"unit": "mmol/L", "min": 98.0, "max": 107.0},
    "Total Serum Calcium (Ca++)": {"unit": "mg/dL", "min": 8.5, "max": 10.5},
    "Troponin I": {"unit": "ng/mL", "min": 0.0, "max": 0.04},
    "CK-MB": {"unit": "ng/mL", "min": 0.0, "max": 5.0},
    "NT-proBNP": {"unit": "pg/mL", "min": 0.0, "max": 125.0},
    "CRP (C-Reactive Protein)": {"unit": "mg/L", "min": 0.0, "max": 5.0},
    "Lactate": {"unit": "mmol/L", "min": 0.5, "max": 2.2},
    "Random Blood Sugar (RBS)": {"unit": "mg/dL", "min": 70.0, "max": 140.0},
    "Arterial Blood pH": {"unit": "pH", "min": 7.35, "max": 7.45},
    "pCO2": {"unit": "mmHg", "min": 35.0, "max": 45.0},
    "HCO3 (Bicarbonate)": {"unit": "mEq/L", "min": 22.0, "max": 26.0},
    "Serum Amylase": {"unit": "U/L", "min": 30.0, "max": 110.0},
    "Serum Lipase": {"unit": "U/L", "min": 10.0, "max": 140.0},
    "ALT (SGPT)": {"unit": "U/L", "min": 7.0, "max": 56.0},
    "AST (SGOT)": {"unit": "U/L", "min": 10.0, "max": 40.0},
    "Total Bilirubin": {"unit": "mg/dL", "min": 0.2, "max": 1.2}
}


# ========================================================================
# [3] وظائف التحكم الخلفية (تتبع المستخدم والنفق)
# ========================================================================

def track_user_activity():
    """وظيفة لتسجيل نشاط المستخدم الحالي في الملف"""
    try:
        user_id = str(os.getpid())
        now = time.time()
        with open(USERS_TRACKER, "a") as f:
            f.write(f"{user_id}|{now}\n")
    except:
        pass


def get_active_count():
    """حساب المستخدمين النشطين خلال الدقيقة الأخيرة"""
    try:
        if os.path.exists(USERS_TRACKER):
            with open(USERS_TRACKER, "r") as f:
                lines = f.readlines()
            now = time.time()
            active_sessions = set()
            for line in lines:
                try:
                    if "|" in line:
                        uid, t = line.strip().split("|")
                        if now - float(t) < 60:
                            active_sessions.add(uid)
                except:
                    pass
            return len(active_sessions)
    except:
        pass
    return 0


def run_streamlit_and_tunnel():
    """إطلاق السيرفر ونفق كلاودفلير تلقائياً"""
    current_file = os.path.abspath(sys.argv[0])
    # تشغيل Streamlit
    subprocess.Popen([sys.executable, "-m", "streamlit", "run", current_file,
                      "--server.headless", "true", "--server.port", PORT], shell=True)

    # محرك النفق
    def tunnel_engine():
        if os.name == 'nt': os.system("taskkill /f /im cloudflared.exe >nul 2>&1")
        while True:
            cmd = f"cloudflared tunnel --url http://127.0.0.1:{PORT}"
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, text=True)
            for line in iter(process.stdout.readline, ''):
                if "trycloudflare.com" in line:
                    url_match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                    if url_match:
                        with open(TUNNEL_FILE, "w", encoding="utf-8") as f:
                            f.write(url_match.group().strip())
                        break
            time.sleep(30)  # محاولة إعادة التشغيل في حال الفشل

    Thread(target=tunnel_engine, daemon=True).start()
    time.sleep(4)
    webbrowser.open(f"http://localhost:{PORT}")


# ========================================================================
# [4] واجهة Streamlit (نظام العرض)
# ==========================================================ي=============

if 'streamlit' in sys.modules:
    import streamlit as st

    # تسجيل النشاط في كل مرة يتم فيها تحديث الصفحة
    track_user_activity()

    # --- إعدادات الواجهة ---
    st.set_page_config(page_title=" Baghdad Teaching Hospital / Emergency Department", layout="wide")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Cairo', sans-serif; text-align: right; }
        div[data-testid="stExpander"] { border: 1px solid #333333; border-radius: 6px; margin-bottom: 8px; }
        </style>
        """, unsafe_allow_html=True)
    # الرابط الخاص بك
    APP_URL = "https://emergency-system-7pn2jhzpumphv7gt4ts44w.streamlit.app/"

    # --- داخل الـ Sidebar ---
    with st.sidebar:
        st.header("⚙️ لوحة التحكم")

        st.success("🔗 رابط الوصول:")
        st.code(APP_URL, language=None)

        # توليد الـ QR كود بناءً على الرابط الثابت
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(APP_URL)
        qr.make(fit=True)

        # اختيار الألوان للـ QR (اختياري)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = BytesIO()
        img.save(buf, format="PNG")

        st.image(buf.getvalue(), caption="Scan & Share")
        if st.button("🚪 تسجيل الخروج الآمن", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    # --- التحقق من الهوية ---
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:

        with st.form("login"):
            pwd = st.text_input("أدخل كلمة المرور", type="password")
            if st.form_submit_button("الدخول"):
                if pwd == PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("كلمة المرور غير صحيحة")
        st.stop()

    # --- محتوى الصفحة الرئيسي ---
    if "current_page" not in st.session_state: st.session_state.current_page = "Common Conditions"

    st.title(" Baghdad Teaching Hospital / Emergency Department")
    m1, m2, m3 = st.columns(3)
    if m1.button("🏠 Common Conditions", use_container_width=True): st.session_state.current_page = "Common Conditions"
    if m2.button("💊 Pharmacy", use_container_width=True): st.session_state.current_page = "Pharmacy"
    if m3.button("🔬 Laboratory", use_container_width=True): st.session_state.current_page = "Laboratory"
    st.write("---")

    # ======================================================================
    # ------------------------Common Emergency Conditions Home---------------------------
    # =======================================================================

    if st.session_state.current_page == "Common Conditions":
        st.header("🚑 Common Conditions & Immediate Management System")


        # Function to handle and render full-width horizontal expander cards
        def render_emergency_card(case_name):
            info = EMERGENCY_CASES_DB.get(case_name)
            if info is None:
                return

            # Using st.expander for instant full-width dropdown behavior
            with st.expander(f"🚨 {case_name}", expanded=False):
                # Displaying information in horizontal rows stretching across the screen
                st.markdown(f"**<u>🥇 Immediate First Action:</u>** {info['Immediate First Action'].replace('\n', ' ')}",
                            unsafe_allow_html=True)
                st.markdown(f"**<u>⚡ Clinical Work Protocol:</u>** {info['Clinical Work Protocol'].replace('\n', ' ')}",
                            unsafe_allow_html=True)
                st.markdown(
                    f"**<u>❌ Critical Contraindications:</u>** {info['Critical Contraindications'].replace('\n', ' ')}",
                    unsafe_allow_html=True)


        # Distribute medical conditions across three full-width open tabs
        tab_medical, tab_surgical, tab_bites = st.tabs([
            "Acute Medical & Cardiac Emergencies",
            "Surgical, Trauma & Shock",
            "Bites, Stings & Acute Poisoning"
        ])
        # --- : Acute Medical & Cardiac Emergencies ---
        with tab_medical:
            render_emergency_card("Acute Myocardial Infarction (STEMI)")
            render_emergency_card("Diabetic Ketoacidosis (DKA)")
            render_emergency_card("Severe Septic Shock")
            render_emergency_card("Acute Ischemic Stroke")
            render_emergency_card("Status Asthmaticus")
            render_emergency_card("Acute Pulmonary Edema")
            render_emergency_card("Upper Gastrointestinal Bleed (UGIB)")
            render_emergency_card("Acute Pancreatitis")
            render_emergency_card("Status Epilepticus")
            render_emergency_card("Hypertensive Emergency")
            render_emergency_card("Acute Agitated/Violent Patient")
            render_emergency_card("Suspected Drug Overdose (Toxidromes)")

            # ---: Surgical, Trauma & Shock ---
        with tab_surgical:
            render_emergency_card("Hemorrhagic Shock")
            render_emergency_card("Open & Comminuted Fractures")
            render_emergency_card("Traumatic Brain & Spinal Cord Injuries")
            render_emergency_card("Severe & Extensive Burns (>15%)")
            # --- : Bites, Stings & Acute Poisoning ---
        with tab_bites:
            # Full-width presentation stretching across the layout
            render_emergency_card("Snake Bites (Venomous)")
            render_emergency_card("Animal/Dog Bites (Suspected Rabies)")
            render_emergency_card("Scorpion Stings")
            render_emergency_card("Anaphylactic Shock")

    # =======================================================================
    # ---------------------PHARMACY DEPARTMENT------------------------
    # =======================================================================
    if st.session_state.current_page == "Pharmacy":
        st.header("🚑 Emergency Pharmacy & Critical Dosage Guide")


        # دالة معالجة وعرض بطاقة الدواء
        def render_drug_card(drug_name):
            info = EMERGENCY_DRUGS_DB.get(drug_name)
            if info is None:
                return

            with st.expander(f"🧪 {drug_name}", expanded=False):
                st.markdown(
                    f"**<u>📌 Clinical Indication :</u>**<br>{info['Clinical Indication'].replace('\n', '<br>')}",
                    unsafe_allow_html=True)
                st.markdown(f"**<u>💉 Acute Dosage Protocol:</u>**<br>{info['Acute Dosage'].replace('\n', '<br>')}",
                            unsafe_allow_html=True)
                st.markdown(f"**<u>⚠️ Critical Warnings:</u>**<br>{info['Critical Warnings'].replace('\n', '<br>')}",
                            unsafe_allow_html=True)
                st.markdown(f"**<u>🚫 Drug Interactions :</u>**<br>{info['Drug Interactions'].replace('\n', '<br>')}",
                            unsafe_allow_html=True)

            # توزيع كافة محتويات الملف على ألسنة تبويب تخصصية متناسقة وهندسية


        tab_antibiotics, tab_cardio, tab_resp, tab_endocrine, tab_neuro, tab_gi_renal, tab_supplies, tab_others = st.tabs(
            [
                "antibiotics & antivirals",
                " Cardiovascular & Thrombolytics",
                " Respiratory & Steroids",
                " Endocrine & Diabetes",
                " Neurology & Analgesics",
                " GI, Antimicrobials ",
                " Fluid Electrolytes",
                " Antidotes, Vaccines & Core Fluids"

            ], width="stretch")

        # --- 1. الأدوية القلبية والوعائية ---
        with tab_antibiotics:
            render_drug_card("Ceftriaxone Vial")
            render_drug_card("Vancomycin Vial")
            render_drug_card("Amoxicillin Vial")
            render_drug_card("Gentamicin amp")
            render_drug_card("Ciprofloxacin Vial")
            render_drug_card("Metronidazole bott.")
            render_drug_card("Acyclovir Vial")
            render_drug_card("Tenofovir cap")
        with tab_cardio:
            render_drug_card("Adrenaline amp")
            render_drug_card("Amiodarone amp")
            render_drug_card("Aspirin")
            render_drug_card("A.S.A 100 tab")
            render_drug_card("Clopidogrel 75 tab")
            render_drug_card("Adenosine amp")
            render_drug_card("Atropine amp")
            render_drug_card("G.T.N amp")
            render_drug_card("G.T.N tab S.L.")
            render_drug_card("Dopamine amp")
            render_drug_card("Dobutamine amp")
            render_drug_card("Noradrenaline amp")
            render_drug_card("Digoxin amp")
            render_drug_card("Hydralazine amp")
            render_drug_card("Metoprolol amp")
            render_drug_card("Labetalol amp")
            render_drug_card("Sod.Nitroprusside")
            render_drug_card("Verapamil Amp")
            render_drug_card("Heparin Vial")
            render_drug_card("Alteplase Vial")
            render_drug_card("Tranexamic a. amp")
            render_drug_card("Captopril tab")

            # --- 2. الأدوية التنفسية ---
            with tab_resp:
                render_drug_card("Salbutamol Neb. ")
                render_drug_card("Ipratropium  neb")
                render_drug_card("Budesonide Nob.")
                render_drug_card("Aminophylline amp")
                render_drug_card("H.C Vial")
                render_drug_card("Prednisolone tab")

            # --- 3. الغدد والسكري ---
            with tab_endocrine:
                render_drug_card("Insulin Soluble Vial")
                render_drug_card("Glucagon amp")

            # --- 4. الأعصاب ومسكنات الألم الحادة ---
            with tab_neuro:
                render_drug_card("Diazepam amp")
                render_drug_card("Midazolam amp")
                render_drug_card("Phenytoin amp")
                render_drug_card("Phenobarbital amp")
                render_drug_card("Chlorpromazine amp")
                render_drug_card("Haloperidol amp")
                render_drug_card("Paracetamol Vial")
                render_drug_card("Diclofenac amp")
                render_drug_card("Nefopam amp")
                render_drug_card("Tramadol amp")
                render_drug_card("Dexamethasone amp")
                render_drug_card("Xylocaine amp")
                render_drug_card("Xylocaine Vial")

            # --- 5. أدوية الجهاز الهضمي، المضادات الحيوية والمحاليل ---
            with tab_gi_renal:
                render_drug_card("Metoclopramide amp")
                render_drug_card("Ondansetron amp")
                render_drug_card("Furosemide amp")
                render_drug_card("Calcium amp")
                render_drug_card("Omeprazole Vial")
                render_drug_card("Esomeprazole Vial ")
                render_drug_card("Hyoscine amp")
                render_drug_card("Diphenhydramine amp")
                render_drug_card("Chlorpheniramine amp")
                render_drug_card("K.C.L amp")
                render_drug_card("Hypertonic amp")
                render_drug_card("Sod. Bicarb amp")
                render_drug_card("Mg Sulphate amp")
                render_drug_card("H.T Saline 3% bott.")

                render_drug_card("Charcoal Powder  ")

            with tab_supplies:
                render_drug_card("Normal Saline (N\\S 500 ml / N\\S 100 ml)")
                render_drug_card("Glucose Saline (G\\S 500 ml)")
                render_drug_card("Glucose Water (G\\W 500 ml)")
                render_drug_card("Ringer's Solution / Ringer's Lactate")
                render_drug_card("Mannitol Solution")

            with tab_others:
                render_drug_card("Anti Snake amp")
                render_drug_card("Anti Scorpion amp")
                render_drug_card("A.R.V Vaccine")
                render_drug_card("A.R IG")
                render_drug_card("A.T IG / ATS")
                render_drug_card("Pralidoxime vial")
                render_drug_card("Naloxone Amp")
                render_drug_card("N.A.C Amp")
                render_drug_card("Flumazenil amp")
                render_drug_card("Protamine Amp")
                render_drug_card("Digoxin FAB amp")
                render_drug_card("Prochlorperazine amp")
                render_drug_card("Vit K  amp")
                render_drug_card("Vit B1 amp")
                render_drug_card("Vit B6 amp")
                render_drug_card("Hydroxy.C.Q. tab")
                render_drug_card("Tetracycline eye oin")
                render_drug_card("Fucidin oint.")
                render_drug_card("Flamazine oint.")
                render_drug_card("Xylocaine oint.")

            st.write("---")
    # =======================================================================
    # ---------------------LABORATORY DEPARTMENT-------------------
    # =======================================================================

    elif st.session_state.current_page == "Laboratory":
        st.header(" Real-Time Laboratory Test Management & Interpretation System")


        def render_pure_test_card(test_name):
            config = LAB_TESTS_CONFIG.get(test_name)
            interpretation = LAB_INTERPRETATION_GUIDE.get(test_name, {
                "Overview": "لا توجد تفاصيل سريرية متاحة.",
                "High": "لم تُحدد احتمالات للارتفاع.",
                "Low": "لم تُحدد احتمالات للانخفاض."
            })

            if config is None:
                return

            with st.expander(f"🔬 {test_name}", expanded=False):
                # 1. النبذة السريرية في الأعلى وبشكل واضح جداً
                st.markdown(f"""
                <div style="background-color: #262730; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                    <h4 style="margin: 0; color: #4CAF50;">💡 Informations :</h4>
                    <p style="margin: 5px 0 0 0; font-size: 16px;">{interpretation['Overview']}</p>
                </div>
                """, unsafe_allow_html=True)

                st.write("")  # مسافة إضافية

                # 2. النطاق الطبيعي
                st.info(
                    f" **NORMAL:** {config.get('min', 0)} - {config.get('max', 0)} {config.get('unit', '')}")

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"""
                            <div style="background-color: #8B0000; padding: 12px; border-radius: 10px; color: white;">
                                <h4 style="color: #FFC0CB; margin-top: 0; margin-bottom: 5px; font-size: 16px;">🔼 HIGH:</h4>
                                <p style="color: white; font-weight: 400; font-size: 14px; margin: 0;">{interpretation['High']}</p>
                            </div>
                            """, unsafe_allow_html=True)

                with col2:
                    st.markdown(f"""
                            <div style="background-color: #00008B; padding: 12px; border-radius: 10px; color: white;">
                                <h4 style="color: #ADD8E6; margin-top: 0; margin-bottom: 5px; font-size: 16px;">🔽 LOW:</h4>
                                <p style="color: white; font-weight: 400; font-size: 14px; margin: 0;">{interpretation['Low']}</p>
                            </div>
                            """, unsafe_allow_html=True)


        # --- تجميع وتنسيق الصفحات (Tabs) ---
        sub_tab_hematology, sub_tab_renal, sub_tab_cardiac, sub_tab_abg, sub_tab_liver = st.tabs([
            " Hematology",
            " Renal & Electrolytes",
            " Cardiac & Inflammation",
            " Blood Gas & Metabolism",
            " Hepatic & Pancreatic"
        ])

        # --- 1. Hematology Panel ---
        with sub_tab_hematology:
            render_pure_test_card("CBC - Hemoglobin (Hb)")
            render_pure_test_card("Platelets")
            render_pure_test_card("INR (International Normalized Ratio)")
            render_pure_test_card("WBC (White Blood Cells)")
            render_pure_test_card("PT (Prothrombin Time)")
            render_pure_test_card("PTT (Partial Thromboplastin Time)")
            render_pure_test_card("D-Dimer")

        # --- 2. Renal & Electrolytes Panel ---
        with sub_tab_renal:
            render_pure_test_card("S. Creatinine")
            render_pure_test_card("Serum Potassium (K+)")
            render_pure_test_card("Serum Chloride (Cl-)")
            render_pure_test_card("Blood Urea Nitrogen (BUN)")
            render_pure_test_card("Serum Sodium (Na+)")
            render_pure_test_card("Total Serum Calcium (Ca++)")

        # --- 3. Cardiac Panel ---
        with sub_tab_cardiac:
            render_pure_test_card("Troponin I")
            render_pure_test_card("NT-proBNP")
            render_pure_test_card("CK-MB")
            render_pure_test_card("CRP (C-Reactive Protein)")

        # --- 4. Blood Gas & Metabolism Panel ---
        with sub_tab_abg:
            render_pure_test_card("Arterial Blood pH")
            render_pure_test_card("HCO3 (Bicarbonate)")
            render_pure_test_card("Random Blood Sugar (RBS)")
            render_pure_test_card("pCO2")
            render_pure_test_card("Lactate")

        # --- 5. Hepatic & Pancreatic Profiles ---
        with sub_tab_liver:
            render_pure_test_card("ALT (SGPT)")
            render_pure_test_card("Total Bilirubin")
            render_pure_test_card("Serum Lipase")
            render_pure_test_card("AST (SGOT)")
            render_pure_test_card("Serum Amylase")

    st.write("---")
# =========================================================================
# [5] نقطة انطلاق النظام (Main)
# =========================================================================
if __name__ == "__main__":
    # تشغيل النفق فقط إذا لم يكن السكربت مشغلاً بواسطة streamlit
    if "streamlit" not in sys.modules:
        run_streamlit_and_tunnel()
