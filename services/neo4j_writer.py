# ═══════════════════════════════════════════════════════
# services/neo4j_writer.py — Persistance Neo4j
# ═══════════════════════════════════════════════════════

import time
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DB

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("⚠️  neo4j non installé — pip install neo4j")

neo4j_driver = None


def connect() -> bool:
    global neo4j_driver
    if not NEO4J_AVAILABLE:
        return False
    try:
        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        neo4j_driver.verify_connectivity()
        print("✅ Neo4j connecté")
        return True
    except Exception as e:
        print(f"⚠️  Neo4j non disponible : {e}")
        neo4j_driver = None
        return False


def write_voice_placement(intent: dict, results: list, text: str):
    """Écrit ou met à jour le placement d'une intention dans Neo4j."""
    if not neo4j_driver:
        return
    try:
        with neo4j_driver.session(database=NEO4J_DB) as session:
            ts = time.strftime("%H:%M:%S")
            session.run(
                "MATCH (i:Intention {id:$iid})-[r:PLACED_ON]->() DELETE r",
                iid=intent["id"]
            )
            for r in results:
                if not r["node"]:
                    session.run("""
                        MERGE (i:Intention {id:$iid})
                        SET i.description=$desc, i.failed=true,
                            i.voice_text=$text, i.timestamp=$ts, i.success=false
                    """, iid=intent["id"], desc=intent["description"],
                        text=text[:80], ts=ts)
                else:
                    session.run("""
                        MERGE (i:Intention {id:$iid})
                        SET i.description=$desc, i.failed=false, i.success=true,
                            i.voice_text=$text, i.timestamp=$ts, i.services=$svcs
                        WITH i
                        MERGE (n:IbnNode {id:$nid})
                        MERGE (i)-[p:PLACED_ON]->(n)
                        SET p.latency=$lat, p.timestamp=$ts,
                            p.grouped=$grouped, p.voice=true
                    """, iid=intent["id"], desc=intent["description"],
                        text=text[:80], ts=ts,
                        svcs=", ".join(intent["services"]),
                        nid=r["node"], lat=r["lat"],
                        grouped=r.get("grouped", False))
            print(f"   📡 Neo4j mis à jour : {intent['id']}")
    except Exception as e:
        print(f"   ⚠️  Neo4j error : {e}")


# Connexion + nettoyage au démarrage
def clear_all():
    """Supprime toutes les données IBN au démarrage pour repartir propre."""
    if not neo4j_driver:
        return
    try:
        with neo4j_driver.session(database=NEO4J_DB) as session:
            session.run("MATCH (i:Intention) DETACH DELETE i")
            session.run("MATCH (n:IbnNode) DETACH DELETE n")
        print("🗑️  Neo4j nettoyé")
    except Exception as e:
        print(f"⚠️  Neo4j clear error : {e}")

connect()
clear_all()