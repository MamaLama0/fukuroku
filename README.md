# Fukuroku

Gestionnaire de tables de poker **libre (MIT)**, **multiplateforme**
(Windows, Linux, macOS), **hors ligne** : aucun compte, aucune licence, aucun
serveur, aucune télémétrie. Toutes les fonctions sont disponibles.

Portage du gestionnaire de tables Jurojin : même interface (menu latéral,
pages, onglets, textes en 10 langues, sons, illustrations et polices
d'origine, réutilisés avec l'autorisation des ayants droit) et mêmes
fonctions de placement, sans la partie serveur. Voir
[docs/ANALYSE.md](docs/ANALYSE.md) pour la correspondance fonction par
fonction, ce qui a été retiré et ce qui n'est pas porté.

## Fonctions

- **Configuration des Tables** : layouts multi-écrans avec slots **Jeu**,
  **Observation**, **Action Requise** (+ file **Queue**), **In Hand**,
  **Replay** et **Lobby** ; piles de tables ; création manuelle,
  automatique, depuis les **préréglages d'origine** (1080p, 1440p, 4K,
  portrait) ou par clonage ; éditeur visuel ; **changement automatique de
  layout** selon le nombre de tables ; raccourci par layout.
- **Placement** : la table où c'est votre tour passe en slot Action Requise
  puis revient à son slot ; urgence de pile ; aimantation par zone ;
  réordonnancement à la fermeture ; auto-focus de la table la plus urgente ;
  verrouillage hors flux dynamique.
- **Configuration des Sites** : 26 salles préconfigurées, tiling par salle,
  destination des nouvelles tables, déclencheur In Hand, **contournement
  des hotkeys** (envoi des raccourcis du client), détection et calibration
  des clics et de la sonde « action requise ».
- **Raccourcis** : 66 actions (clavier, souris, molette, manette),
  **16 boutons de mise** (BB préflop / % du pot / multiplicateur /
  géométrique), mode de relance, Ctrl pour le 2ᵉ groupe de boutons, mise à
  la molette, tapis instantané.
- **Contrôleur** : manette XInput (Windows) ou SDL (Linux/macOS),
  vibration à votre tour.
- **Overlays** : boutons de mise et capture d'écran sur chaque table,
  compteurs flottants de tables en attente / empilées, **RNG**.
- **Temps de session** : minuteur flottant, widgets (tables ouvertes,
  tables AR, mains), notifications, historique des sessions.
- **Configuration générale** : bordure de table (dégradé ou couleurs),
  alarme et alarme différée avec les sons d'origine, langue, export/import
  des paramètres (.zip).
- **Aide** : guide, calculatrice poker (cote du pot, SPR, MDF, bluff, outs),
  diagnostic.

## Exécutables

Les versions prêtes à l'emploi (Windows `.exe`, Linux, macOS `.app`) sont
dans les [Releases](https://github.com/MamaLama0/fukuroku/releases). Elles
incluent Python, Tk, Pillow et pynput.

## Installation depuis les sources

Python ≥ 3.10 avec Tk (inclus sous Windows/macOS ; paquet `python3-tkinter`
ou `python3-tk` sous Linux).

```bash
pip install .
```

Options : manette sous Linux/macOS et icône dans la barre système :

```bash
pip install ".[gamepad,tray]"
```

### Linux

Les clients de poker tournent sous Wine/Proton/Lutris, donc en X11
(XWayland sous Wayland). Outils nécessaires :

```bash
sudo dnf install wmctrl xdotool xrandr xprop
```

(`apt install wmctrl xdotool x11-xserver-utils` sous Debian/Ubuntu.) Sous
Wayland, KDE Plasma laisse placer les fenêtres XWayland ; GNOME peut le
refuser — une session X11 reste la plus fiable.

### macOS

Autorisez l'application dans **Réglages Système → Confidentialité et
sécurité** : *Accessibilité* (placement, clics), *Surveillance de l'entrée*
(raccourcis) et *Enregistrement de l'écran* (sonde pixel). L'application
n'est pas signée : premier lancement par clic droit → *Ouvrir*.

## Utilisation

```bash
fukuroku                 # lancement normal
fukuroku --demo          # essai avec des tables simulées
fukuroku --list-windows  # vérifie quelles fenêtres sont reconnues
```

1. **Configuration des Sites** : vérifiez que votre salle est activée ;
   onglet *Détection & clics* pour calibrer les boutons (fold, check, bet,
   champ de mise…) et la **sonde « action requise »**.
2. **Configuration des Tables** : activez un layout ou créez-en un.
3. **Raccourcis Clavier** : cliquez sur une case de raccourci, appuyez sur la
   combinaison, *Entrée* pour enregistrer, *Échap* pour effacer.

Configuration : `%APPDATA%\Fukuroku` (Windows),
`~/Library/Application Support/Fukuroku` (macOS), `~/.config/fukuroku`
(Linux) ; variable `FUKUROKU_HOME` pour la déplacer.

## Brancher une source de données de main

La lecture interne des clients (DLL injectées de l'original) n'est pas
reproduite. Un module tiers (lecteur d'historiques, OCR…) peut alimenter
Fukuroku ; les mises en % du pot, les slots In Hand précis et les overlays
de données s'activent alors :

```python
from fukuroku.manager import TableDataSnapshot
manager.data_provider = lambda handle, title: TableDataSnapshot(pot=12.5, to_call=2, hero_stack=100, street="flop")
manager.submit(manager.set_action_required, handle, True)
```

## Construire les exécutables

```bash
pip install pyinstaller
python packaging/build.py
```

Le script produit `dist/Fukuroku` (Linux), `dist/Fukuroku.exe` (Windows) ou
`dist/Fukuroku.app` (macOS) sur la plateforme où il est lancé. Le workflow
GitHub Actions `.github/workflows/build.yml` construit les trois.

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Respect des salles

Les raccourcis déclenchent **une** action par appui de l'utilisateur ; rien
n'est automatisé. Vérifiez néanmoins les règles de votre salle concernant les
logiciels tiers.
