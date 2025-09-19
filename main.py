# main.py
import sys
from pynput import keyboard
import pygetwindow as gw
from sanctions import SanctionsManager

# Mots-clés pour reconnaître la fenêtre PPSSPP active (minuscule/majuscule non sensible)
PPSSPP_TITLES = ("ppsspp", "ppssppqt", "ppssppwindows")
# On instancie le manager une seule fois au chargement du module
sanctions = SanctionsManager()

def is_ppsspp_active() -> bool:
    try:
        win = gw.getActiveWindow()
        if not win:
            return False
        title = (win.title or "").lower()
        return any(k in title for k in PPSSPP_TITLES)
    except Exception as e:
        # En cas d'erreur, on retourne False (sécurité)
        print("is_ppsspp_active error:", e)
        return False

def main_sanction(valeur: int) -> bool:
    """
    Traite un seul score et retourne False s'il faut arrêter (valeur == -1), True sinon.
    """
    try:
        if valeur == -1:
            print("Fin du programme.")
            return False

        if valeur > 6:
            print(f"Valeur {valeur} > 6 → déclenchement de la sanction")
            sanctions.trigger_warning()
        else:
            print(f"Valeur {valeur} <= 6 → aucune sanction")

        return True

    except ValueError:
        print("⚠️ Entrée invalide, entre un nombre entier entre 0 et 10.")
        return True


if __name__ == "__main__":
    # Démo : traite chaque valeur individuellement
    for s in [4, 7, 8, 3, 9, -1]:
        if not main_sanction(s):
            break
