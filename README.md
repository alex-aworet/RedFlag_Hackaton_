# 🎙️ RedFlag – Détection de Toxicité en Jeu Vidéo

## 📌 Description
**Red Flag** est un système de **détection en temps réel de toxicité vocale** dans les jeux en ligne.  
Le projet s’appuie sur la **transcription de la voix en texte (speech-to-text)**, puis sur un module de classification qui identifie les propos offensants, injurieux ou menaçants.  

Lorsqu’un joueur adopte un comportement verbal toxique :  
- Un **score d’intensité** est calculé.  
- Si ce score dépasse un certain seuil, un **avertissement** est généré.  
- Après plusieurs avertissements, une **sanction automatique** est applliquée : Fermeture automatique du jeu.  

L’objectif est de **lutter contre la toxicité en ligne** et de protéger les joueurs d’expériences nocives.

Nos tests se basaient principalement l'usage de l'émulateur ''ppsspp'' dont nous avons adapté les paramètres réseaux afin de correspondre aux exigences de notre algorithme de surveillance.

---

## ⚙️ Fonctionnalités
- 🎤 Capture et transcription en direct de la voix des joueurs.  
- 🤖 Classification IA des propos avec un modèle entraîné sur +25 000 insultes et comportements toxiques.  
- 🚨 Système de sanctions progressives (avertissements → sanctions).  
- 📡 Déclenchement automatique via la surveillance du trafic réseau (`adhoc_monitor.py`).  
- 📝 Sauvegarde des transcriptions dans un fichier (`transcription.txt`).  

---

## 📂 Structure du projet
```
├── adhoc_monitor.py         # Sniffer réseau qui déclenche la détection --> code à lancer
├── live_voice_detection.py  # Détection et transcription vocale en direct
├── main.py                  # Gestion des trigger --> ne pas jouer directement
├── mistral.py               # Modèle de classification (LLM Mistral)
├── run.py                   # Orchestration du pipeline : classification + execution de la sanction
├── sanctions.py             # Gestion des avertissements et sanctions
├── utils.py                 # Fonctions utilitaires requises pour la surveillance
├── utils_classification.py  # Outils pour la classification
```

---

## 🚀 Installation

### 1. Prérequis
- Python 3.9+  
- `pip` ou `conda`  
- Microphone et accès réseau  

### 2. Cloner le projet
```bash
git clone https://github.com/alex-aworet/RedFlag_Hackaton_.git
cd RedFlag_Hackaton_
```

### 3. Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 4. Installer les dépendances
```bash
pip install -r requirements.txt
```

---

## ▶️ Utilisation

### Lancer la détection de traffic en direct
```bash
python adhoc_monitor.py
```

Ce code permettra que lorsque qu'un échange de données en ligne est repéré, les algorithmes de speech to text, de classification de parole ainsi que sanction seront exécutés en parallèle.

---

## ⚠️ Cas d'usage

Dans notre expérimentation, nous avons utilisé un émulateur de psp pour les simulations. Il suffit de lancer `adhoc_monitor.py` qui déclenchera les fonctions perception de voix, classification et sanction en parrallèle dès le moment où une partie en ligne est détectée.

Dans le cadre de la prise de décision, nous avons entrainé un modèle small de mistral ai sur les datasets suivant :

- [Jigsaw Toxic Comment Dataset](https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge/data)  
- [Hatebase](https://www.hatebase.org/)  
- Selected in-game chat logs for slang and context 

et avons décidé de labeliser comme suit :

| Score | Category |
|-------|----------|
| 1–2   | Non-toxic |
| 3–4   | Mild insult |
| 5–7   | Strong insult/obscene |
| 8–10  | Severe hate/threat |

---

## 📜 Licence
Ce projet est sous licence **MIT** – utilisation libre et open-source.  
