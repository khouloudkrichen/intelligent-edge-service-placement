# 🚀 Placement Intelligent de Services Edge

> 🎓 Projet de Fin d’Année(PFA) — Institut International de Technologie de Sfax  
> 🤖 Intelligence Artificielle • Edge Computing • Intent-Based Networking • Industrie 5.0

---

## 📌 Présentation du projet

Ce projet consiste à concevoir et développer un système intelligent de **placement de services dans un environnement Edge Computing**, destiné à assister un technicien industriel.

Le système permet au technicien d’exprimer son besoin à travers une **commande vocale en langage naturel**. Cette commande est ensuite transcrite, analysée afin d’identifier une ou plusieurs intentions, puis transformée en une demande structurée permettant de déterminer les services nécessaires et de sélectionner les nœuds Edge les plus adaptés.

La solution intègre plusieurs composants complémentaires :

- 🎙️ Reconnaissance et traitement vocal
- 🧠 Détection intelligente des intentions
- 🔗 Association des intentions aux services
- ⚙️ Placement intelligent des services Edge
- 📡 Gestion des contraintes de qualité de service (QoS)
- 🗄️ Traçabilité des décisions avec Neo4j
- 📊 Dashboard de supervision en temps réel
- 🤖 Chatbot intelligent orienté Industrie 5.0
- 📚 Assistant conversationnel basé sur le RAG

L'objectif est de proposer une solution intelligente, modulaire et évolutive permettant d'automatiser la décision de placement tout en facilitant l'interaction entre le technicien et l'infrastructure Edge.

---

# 🎯 Problématique

Dans les environnements industriels modernes, les techniciens ont besoin d'accéder rapidement à différents services numériques tout en respectant des contraintes strictes de performance, de disponibilité et de qualité de service.

L'infrastructure Edge permet de rapprocher les services des utilisateurs afin de réduire la latence et d'améliorer les performances. Cependant, le choix du nœud Edge approprié devient complexe lorsque les ressources disponibles varient et que plusieurs contraintes doivent être respectées.

Par exemple :

- surcharge du CPU ;
- mémoire insuffisante ;
- bande passante limitée ;
- latence élevée ;
- espace disque insuffisant ;
- indisponibilité d'un nœud ;
- contraintes de priorité des services.

La problématique du projet peut donc être formulée ainsi :

> **Comment permettre à un technicien d'exprimer naturellement son besoin, puis identifier automatiquement les services nécessaires et sélectionner les nœuds Edge les plus adaptés à leur déploiement tout en respectant les contraintes de ressources et de QoS ?**

---

# 💡 Solution proposée

La solution repose sur une architecture modulaire permettant de transformer progressivement une commande vocale en une **décision intelligente de placement**.

Le pipeline global est le suivant :


🎙️ Commande vocale
        ↓
🔊 Prétraitement audio
        ↓
📝 Transcription Speech-to-Text
        ↓
🧠 Détection des intentions
        ↓
🔗 Association intentions → services
        ↓
📋 Calcul des ressources et contraintes QoS
        ↓
⚙️ Moteur de placement intelligent
        ↓
🖥️ Sélection du nœud Edge
        ↓
🗄️ Traçabilité avec Neo4j
        ↓
📊 Supervision en temps réel
