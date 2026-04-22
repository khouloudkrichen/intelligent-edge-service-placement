# ═══════════════════════════════════════════════════════
# data/dataset.py — Chargement dataset + mappings
# ═══════════════════════════════════════════════════════

import json
from config import DATASET_FILE

with open(DATASET_FILE, "r", encoding="utf-8") as f:
    _data = json.load(f)

intentions  = _data["intentions"]
services    = _data["services"]
nodes       = _data["nodes"]
latency_map = _data["latency"]

SERVICES_BY_ID   = {s["id"]: s for s in services}
NODES_BY_ID      = {n["id"]: n for n in nodes}
INTENTIONS_BY_ID = {i["id"]: i for i in intentions}

print(f"✅ Dataset chargé : {len(nodes)} nœuds, {len(services)} services, {len(intentions)} intentions")

# ── Mots français pour détection de langue ──────────────
FR_WORDS = {
    "je", "tu", "il", "nous", "vous", "la", "le", "les", "un", "une",
    "est", "que", "qui", "comment", "veux", "dois", "puis", "faut",
    "déployer", "activer", "analyser", "détect"
}

# ── Mapping vocal intention → phrases-clés ──────────────
VOICE_MAPPING = {
    "i1":  ["replace power unit", "power unit", "remplacer unité"],
    "i2":  ["machine status", "operational status", "état machine", "statut",
            "operational stage", "machine stage", "operational state",
            "retrieve operational", "status of the machine"],
    "i3":  ["ar sequence", "ar assembly", "ar service", "deploy ar",
            "déployer ar", "service ar", "ar generator", "augmented reality",
            "show me the ar", "show ar", "ar for power", "ar for assembly"],
    "i4":  ["highlight errors", "errors assembly", "erreurs assemblage"],
    "i5":  ["motor temperature", "temperature anomaly", "température moteur",
            "motor overheat", "surchauffe moteur", "check temperature"],
    "i6":  ["lubrication", "lubrifier", "moving parts", "lubricate"],
    "i7":  ["ar belt", "belt replacement", "remplacement courroie", "belt ar"],
    "i8":  ["conveyor belt", "belt wear", "belt damage", "detect belt"],
    "i9":  ["ar gear", "gear alignment", "alignement engrenage"],
    "i10": ["vibration data", "vibration analysis", "analyse vibration",
            "abnormal patterns", "vibration abnormal"],
    "i11": ["electrical connections", "signal integrity", "connexions électriques"],
    "i12": ["ar safety overlay", "safety overlay", "ar safety"],
    "i13": ["temperature sensors", "current sensors", "monitor temperature"],
    "i14": ["detect errors", "error detection", "identify error",
            "error detector", "identify problem", "use error detector"],
    "i15": ["full diagnostics", "complete diagnostics", "diagnostic complet",
            "full dies", "diagnostics after maintenance", "perform full", "perform diagnostics"],
    "i16": ["predictive maintenance", "maintenance prédictive", "high risk"],
    "i17": ["ar troubleshoot", "ar fault guidance", "ar dépannage"],
    "i18": ["post maintenance efficiency", "operational efficiency", "post-maintenance",
            "post mantanons", "verify the post", "maintenance operational efficiency",
            "return system to production"],
    "i19": ["ar summary maintenance", "maintenance summary ar"],
    "i20": ["components attention", "maintenance alert"],
    "i21": ["belt tension", "conveyor tension", "belt alignment"],
    "i22": ["ar fan", "fan assembly", "ar ventilateur"],
    "i23": ["fan vibration", "vibration fan", "fan analysis"],
    "i24": ["ar hazard", "hazardous areas", "ar danger"],
    "i25": ["voice command", "voice conversion", "conversion vocale",
            "voice control", "commande vocale"],
    "i26": ["machine errors logs", "error logs", "retrieve logs"],
    "i27": ["ar valve", "valve replacement", "remplacement vanne"],
    "i28": ["hydraulic leak", "fuite hydraulique", "leak detection", "hydraulic"],
    "i29": ["pipeline pressure", "pressure levels", "pression pipeline"],
    "i30": ["ar gearpx", "gearbox inspection", "inspection gearbox"],
    "i31": ["gearbox teeth", "gear wear", "usure engrenage"],
    "i32": ["motor load", "motor vibration", "analyze motor", "charge moteur"],
    "i33": ["cable connections", "electrical cable", "câbles électriques"],
    "i34": ["ar reactivate", "ar safety reactivate"],
    "i35": ["sensor monitoring", "monitor sensors", "surveiller capteurs"],
    "i36": ["assembly inconsistency", "detect inconsistency"],
    "i37": ["system diagnostics", "full system diagnostics"],
    "i38": ["predictive alert", "high risk alert"],
    "i39": ["ar troubleshooting faults", "ar guidance troubleshoot"],
    "i40": ["post maintenance verify", "verify efficiency"],
    "i41": ["ar summary all steps", "ar all maintenance"],
    "i42": ["components alert", "alert components"],
    "i43": ["video capture", "quality review", "capture vidéo"],
    "i44": ["fault history", "historical fault data", "historique pannes"],
    "i45": ["ar motor replacement", "motor replacement ar"],
    "i46": ["motor anomaly", "motor current", "detect motor fault",
            "motor fault", "anomaly motor", "anomalie moteur",
            "activate anomaly", "anomaly analyzer", "activate anomaly analyzer"],
    "i47": ["alignment mechanical", "mechanical alignment", "verify alignment"],
    "i48": ["final check", "final system check", "vérification finale"],
    "i49": ["maintenance report", "generate report", "rapport maintenance"],
    "i50": ["maintenance cycle alert", "next maintenance cycle",
            "send alerts for component", "alerts for next maintenance",
            "components due for maintenance"],
}