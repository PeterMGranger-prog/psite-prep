from __future__ import annotations
import csv, re, sqlite3, sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
CSV_PATH=Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'plastic_surgery_question_bank_with_companions.csv'
DB=BASE/'psite_prep.db'
SECTIONS={
'Breast & Cosmetic': ['breast','mammaplast','mastopex','implant','augmentation','reduction','abdominoplast','liposuction','rhinoplast','rhytid','blepharoplast','cosmetic','aesthetic','gynecomastia'],
'Hand & Extremities': ['hand','finger','thumb','wrist','carpal','metacarp','phalange','tendon','upper extrem','lower extrem','brachial plexus','nerve repair','replant','dupuytren','burned hand'],
'Craniomaxillofacial': ['cranio','facial','face','mandib','maxill','orbit','cleft','palate','lip','orthognath','skull','craniosynost','ear','microtia','head and neck'],
'Comprehensive Integument': ['burn','wound','scar','melanoma','squamous','basal cell','pressure ulcer','skin','hidradenitis','necrotizing','vascular anomaly','hemangioma','lymphedema'],
'Core Surgical Principles': []}
SUBS=[
('Breast & Cosmetic','Breast Reconstruction',['mastectomy','breast reconstruction','tram','diep','latissimus']),
('Breast & Cosmetic','Aesthetic Breast',['augmentation','mastopexy','reduction mammaplasty','implant']),
('Breast & Cosmetic','Body Contouring',['abdominoplasty','liposuction','body contour']),
('Breast & Cosmetic','Facial Aesthetics',['rhytidectomy','blepharoplasty','rhinoplasty','botulinum','filler']),
('Hand & Extremities','Fractures & Dislocations',['fracture','dislocation','metacarp','phalange']),
('Hand & Extremities','Tendon',['flexor tendon','extensor tendon','tendon repair']),
('Hand & Extremities','Peripheral Nerve',['nerve','carpal tunnel','brachial plexus']),
('Hand & Extremities','Congenital Hand',['syndactyly','polydactyly','congenital hand']),
('Hand & Extremities','Replantation & Microsurgery',['replant','revascularization','microsurgery']),
('Craniomaxillofacial','Cleft Lip & Palate',['cleft','velopharyngeal']),
('Craniomaxillofacial','Craniosynostosis',['craniosynost','plagiocephaly']),
('Craniomaxillofacial','Facial Trauma',['facial fracture','mandible fracture','orbital fracture','le fort']),
('Craniomaxillofacial','Head & Neck Reconstruction',['head and neck','mandibulectomy','maxillectomy']),
('Craniomaxillofacial','Congenital Craniofacial',['microtia','hemifacial','treacher','craniofacial']),
('Comprehensive Integument','Burns',['burn','inhalation injury','electrical injury']),
('Comprehensive Integument','Wound Healing',['wound healing','wound dehiscence','chronic wound']),
('Comprehensive Integument','Skin Cancer',['melanoma','squamous cell','basal cell','mohs']),
('Comprehensive Integument','Pressure Injuries',['pressure ulcer','decubitus']),
('Comprehensive Integument','Vascular Anomalies',['hemangioma','vascular malformation']),
('Core Surgical Principles','Flaps & Grafts',['flap','skin graft','graft take','perforator']),
('Core Surgical Principles','Microsurgery',['microvascular','anastomosis','free tissue']),
('Core Surgical Principles','Anesthesia & Critical Care',['anesthesia','airway','shock','resuscitation']),
('Core Surgical Principles','Infection & Antibiotics',['infection','antibiotic','osteomyelitis']),
('Core Surgical Principles','Oncology & Pathology',['tumor','sarcoma','desmoid','cancer']),
]

def classify(text):
 t=text.lower(); scores={s:sum(t.count(k) for k in ks) for s,ks in SECTIONS.items()}
 section=max(scores,key=scores.get) if max(scores.values()) else 'Core Surgical Principles'
 for s,sub,keys in SUBS:
  if s==section and any(k in t for k in keys): return section,sub
 return section, {'Breast & Cosmetic':'General Breast & Cosmetic','Hand & Extremities':'General Hand & Extremities','Craniomaxillofacial':'General Craniomaxillofacial','Comprehensive Integument':'General Integument','Core Surgical Principles':'General Surgical Principles'}[section]

def parse_options(stem):
 matches=list(re.finditer(r'(?m)^([A-E])\)\s*(.+?)(?=\n[A-E]\)\s|\Z)',stem,re.S))
 opts={m.group(1):re.sub(r'\s+',' ',m.group(2)).strip() for m in matches}
 clean=re.split(r'(?m)^A\)\s',stem,maxsplit=1)[0].strip()
 return clean,opts

con=sqlite3.connect(DB); con.executescript((BASE/'schema.sql').read_text())
qcount=ccount=0
with CSV_PATH.open(encoding='utf-8-sig',newline='') as f:
 for row in csv.DictReader(f):
  stem,opts=parse_options(row['original_question'])
  if not all(x in opts for x in 'ABCD'): continue
  section,sub=classify(row['original_question']+' '+row['original_answer_and_rationale'])
  con.execute('''INSERT OR REPLACE INTO questions(source_id,source_file,section,subsection,stem,option_a,option_b,option_c,option_d,option_e,correct_option,correct_option_text,explanation,provenance,review_status)
  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(row['source_id'],row['source_file'],section,sub,stem,opts['A'],opts['B'],opts['C'],opts['D'],opts.get('E'),row['correct_option_letter'] or 'A',row['correct_option_text'],row['original_answer_and_rationale'],row['provenance'],row['review_status']))
  qcount+=1
  if row.get('generated_question'):
   con.execute('''INSERT OR REPLACE INTO flashcard_templates(source_id,section,subsection,front,back) VALUES(?,?,?,?,?)''',(row['source_id'],section,sub,row['generated_question'],row['generated_answer']))
   ccount+=1
con.commit(); con.close(); print(f'Imported {qcount} questions and {ccount} cards')
