# sanctions.py
# -*- coding: utf-8 -*-

import os
import sys
import time
import psutil
import platform
from dataclasses import dataclass
from multiprocessing import Process
from PyQt5 import QtWidgets, QtCore, QtGui


@dataclass
class SanctionsConfig:
    lock_seconds: int = 5
    max_warnings: int = 3
    # Noms possibles du binaire PPSSPP (adapter si besoin)
    # Ajout de variations macOS / Linux
    emulator_process_names: tuple = (
        "PPSSPPWindows64.exe",
        "PPSSPPWindows.exe",
        "PPSSPPQt.exe",
        "PPSSPPSDL.exe",
        "PPSSPP",            # macOS/Linux binaire
        "PPSSPPQt",          # macOS/Linux
        "PPSSPPSDL",         # macOS/Linux
        "ppsspp",            # linux package
        "PPSSPP.app",        # bundle macOS (nom de process peut apparaître ainsi)
    )
    # Si PPSSPP a un nom différent sur ton système, ajoute-le ici.


# ---- Overlay (exécuté dans un process séparé) ----
def _run_overlay(seconds: int, level: int, max_warnings: int):
    app = QtWidgets.QApplication(sys.argv)

    class ScreenOverlay(QtWidgets.QWidget):
        def __init__(self, geometry: QtCore.QRect, alpha: int):
            super().__init__()
            self.alpha = alpha
            # Fenêtre sans décoration, au-dessus de tout, qui n'apparaît pas dans le Dock/Cmd-Tab
            flags = (
                QtCore.Qt.FramelessWindowHint
                | QtCore.Qt.WindowStaysOnTopHint
                | QtCore.Qt.Tool
            )
            self.setWindowFlags(flags)
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
            self.setCursor(QtCore.Qt.BlankCursor)
            self.setGeometry(geometry)

            # Spécifique macOS : rejoindre tous les Spaces et rester auxiliaire
            if platform.system() == "Darwin":
                self._macos_join_all_spaces_and_auxiliary()

        def _macos_join_all_spaces_and_auxiliary(self):
            """
            Utilise PyObjC (si présent) pour :
              - rejoindre tous les Espaces (Spaces)
              - autoriser l'affichage par-dessus une app en plein écran dans le même Espace
            Sans PyObjC, l’overlay reste au-dessus dans l’Espace courant et n’en crée pas un nouveau.
            """
            try:
                import objc
                from objc import ObjCInstance
                from ctypes import c_void_p
                from AppKit import (
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                )
                wid = int(self.winId())  # NSView*
                nsview = ObjCInstance(c_void_p(wid))
                nswindow = nsview.window()
                behavior = nswindow.collectionBehavior()
                behavior |= (
                    NSWindowCollectionBehaviorCanJoinAllSpaces
                    | NSWindowCollectionBehaviorFullScreenAuxiliary
                )
                nswindow.setCollectionBehavior_(behavior)
            except Exception:
                # PyObjC non installé ou API indisponible : ignorer silencieusement
                pass

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            color = QtGui.QColor(200, 10, 10, self.alpha)
            painter.fillRect(self.rect(), color)

    # ---- Opacité selon le niveau ----
    if level >= max_warnings:
        alpha = 255       # opaque
    elif level == 2:
        alpha = 180       # plus rouge
    else:
        alpha = 110       # léger voile rouge

    # Crée une fenêtre overlay par écran (pas de showFullScreen → pas de nouvel Espace sur macOS)
    overlays = []
    for screen in QtWidgets.QApplication.screens():
        geo = screen.geometry()
        w = ScreenOverlay(geo, alpha)
        overlays.append(w)

    # ---- Texte / message (sur tous les écrans pour cohérence multi-moniteurs) ----
    labels = []
    for w in overlays:
        label = QtWidgets.QLabel("", w)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setStyleSheet("color: white; font-size: 48px; font-weight: 800;")
        layout = QtWidgets.QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(1)
        w.setLayout(layout)
        w.setWindowModality(QtCore.Qt.ApplicationModal)
        w.show()
        labels.append(label)

    # Compte à rebours
    remaining = {"time": seconds}

    def update_label():
        t = remaining["time"]
        if level >= max_warnings:
            text = "SEUIL ATTEINT — FERMETURE DU JEU"
        else:
            text = f"AVERTISSEMENT — Langage agressif détecté\nBlocage {t} s"
        for lbl in labels:
            lbl.setText(text)
        remaining["time"] -= 1
        if remaining["time"] < 0:
            app.quit()

    update_label()
    timer = QtCore.QTimer()
    timer.timeout.connect(update_label)
    timer.start(1000)

    app.exec_()


class SanctionsManager:
    def __init__(self, config: SanctionsConfig = SanctionsConfig()):
        self.config = config
        self.warning_count = 0

    def _show_overlay(self, level: int):
        p = Process(target=_run_overlay, args=(self.config.lock_seconds, level, self.config.max_warnings))
        p.start()
        # on attend côté logique la même durée pour s'assurer du blocage côté "jeu"
        time.sleep(self.config.lock_seconds)
        # le process Qt se termine seul via app.quit()

    def _kill_emulator(self):
        killed_any = False
        # Normalise en minuscules pour comparaison
        targets = set(n.lower() for n in self.config.emulator_process_names)
        for proc in psutil.process_iter(attrs=["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if any(t in name for t in targets):
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed_any = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return killed_any

    def trigger_warning(self):
        """
        Appeler lorsque ton détecteur signale une agression.
        """
        self.warning_count += 1
        level = self.warning_count
        print(f"[Sanctions] Avertissement #{level}")

        # Affiche l'overlay adapté au niveau
        try:
            self._show_overlay(level)
        except Exception as e:
            print("[Sanctions] Erreur affichage overlay:", e)

        # Au seuil, fermer l'émulateur après l'overlay
        if level >= self.config.max_warnings:
            print("[Sanctions] Seuil atteint — tentative de fermeture de l'émulateur.")
            try:
                killed = self._kill_emulator()
                if killed:
                    print("[Sanctions] Emulateur fermé.")
                else:
                    print("[Sanctions] Aucun processus d'émulateur trouvé (vérifier emulator_process_names).")
            except Exception as e:
                print("[Sanctions] Erreur lors de la tentative de fermeture :", e)


# --- Petit test manuel ---
if __name__ == "__main__":
    # Exemple : simule 3 avertissements successifs
    mgr = SanctionsManager(SanctionsConfig(lock_seconds=3, max_warnings=3))
    for _ in range(3):
        mgr.trigger_warning()
        time.sleep(1)
