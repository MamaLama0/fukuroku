# Analyse du logiciel d'origine et correspondance avec Fukuroku

Analyse statique réalisée avec REA (inspection des métadonnées .NET, sans
exécution du logiciel) sur le dossier `Jurojin/` (build du 20/10/2026).
Fukuroku est une **réimplémentation** : aucun code de l'original n'est repris.
Les noms de types, de membres et d'énumérations ont servi de spécification
fonctionnelle. Depuis la 2.0, et avec l'autorisation des ayants droit, les
**ressources** de l'original (sons, images, polices, textes traduits, layouts
prédéfinis) sont réutilisées pour reproduire son apparence (voir § 6).

## 1. Composition du logiciel analysé

| Élément | Nature | Rôle |
|---|---|---|
| `JurojinUI.exe` (18 Mo) | .NET Framework 4.6.2, WPF, x86 | interface, services, overlays |
| `Jurojin.Core.dll` | .NET | moteur (métadonnées trop volumineuses pour REA) |
| `Jurojin.Core.Contracts.dll` | .NET | interfaces : placement, monitoring, Win32 |
| `Jurojin.Core.<Salle>.dll` ×26 | .NET | un module par salle de poker |
| `Jurojin.HotKeys.dll` | .NET | raccourcis clavier/souris/manette |
| `Jurojin.Rng.dll` | .NET | générateur aléatoire flottant |
| `Jurojin.ServerInterop.dll`, `JurojinUI.Core.dll` | .NET | serveur, licences, keep-alive |
| `Plugins/*.dll`, `ProcessCommunicator64.exe` | natif | DLL injectées dans les clients de poker |
| `Jurojin.ClientSecurity.dll` (12 Mo) | .NET protégé | protection / anti-altération |
| `Mixpanel.dll`, `AWSSDK.*`, `DeviceIdentifierAPI.dll` | tiers | télémétrie, envoi S3, empreinte machine |

**Protection observée** : chaînes chiffrées (marqueurs
`{11111-22222-…}` typiques d'un obfuscateur commercial), noms de types
partiellement renommés, métadonnées volontairement invalides (2 lignes
`Module`/`Assembly`, flux factices `#Blop`/`#GUlD`). Cette protection n'a
**pas** été contournée : elle est inutile pour une réimplémentation.

Preuves REA (identifiants d'Evidence) :
- `ev_71c79ab5…` / `ev_6d60510e…` : JurojinUI.exe (classification, limite de taille)
- `ev_597a66b1…` : Jurojin.Core.Contracts.dll (236 types)
- `ev_52bfd06d…` : JurojinUI.Core.dll (keep-alive, licences, mises à jour)
- `ev_721b317a…`, `ev_3bb5d57c…` : Jurojin.HotKeys.dll (`AppHotKeyName`, `GamePadButtons`)
- `ev_098803ad…` : Jurojin.Rng.dll
- `ev_1b4c207f…` : Jurojin.ServerInterop.dll (API serveur, paiements)

## 2. Fonctionnalités reproduites

| Fonction d'origine (type/interface) | Fukuroku |
|---|---|
| Interface `AppWindowN` : menu latéral (Accueil, Configuration des Tables, des Sites, Raccourcis, Contrôleur, Overlays, Temps de Session, Configuration Générale, Aide, Journal), onglets, barre d'état | `ui/app.py`, `ui/pages/*` (même structure, mêmes textes, même palette `AppColors`) |
| Layouts & slots `SlotType` : Playing, Observer, ActionRequired, Queue (InHand), InHand, Replay, Lobby (`IPlacementOrchestrator`, `ITablePlacer`) | `layout.py`, `placement.py` |
| Créer un layout : manuellement, automatiquement (taille + marge), depuis un préréglage, cloner (`CreateNewLayout*ViewModel`) | les 4 méthodes ; préréglages d'origine `PresetLayouts/*.json` (1080p, 1440p, 4K, portrait) |
| Éditeur de layout, position/taille des slots, slots hors écran en rouge (`SlotsPositionSelector`, `SlotSizeSelection`) | `LayoutEditor` (glisser, coin de redimensionnement, X/Y/L/H, échelle, empilement, site du lobby) |
| Slots Action Requise + file Queue, retour au slot précédent (`IActionRequiredTablePositioningService`, `IARSlotsPositioningService`) | `PlacementEngine.set_action_required` / `_promote_queue` |
| Slots In Hand (nouvelle main / VPIP) | `set_in_hand` (fournisseur de données, sinon 1re action requise) |
| Changement automatique de layout selon le nombre de tables, demande de confirmation | `AutoSwitchSettings`, `TableManager._auto_switch` |
| Positionnement par site (tiling, nouvelle table → jeu / observation / rien) | `SiteDefinition.tiling` / `new_table` |
| Contournement des hotkeys (raccourcis du client) | `SiteDefinition.site_keys` |
| Bordure de table (transition vert→rouge ou 2 couleurs, clignotement, table focus) | `TableBorders`, onglet *Bordure de table* |
| Alarme / alarme différée « action requise » | sons d'origine, volume, délai |
| Urgence de pile (`IStackUrgencyManager`), table la plus urgente | `stack_urgency`, `FocusMostUrgentTable` |
| Aimantation (`IMagnetizer`) | `user_moved` |
| Verrouillage hors flux (`LockTableFromDynamicFlow`) | `toggle_lock` |
| Priorité aux hautes limites (`IHigherStakeQuotaPolicy`, `TableStakeTier`) | `prioritize_higher_stakes`, `StakeTier` |
| Lecture des blindes (`ITableStakeParser`) | `sites.parse_stakes` |
| 66 actions de raccourci (`AppHotKeyName`) | `hotkeys.Action` — liste identique |
| Clavier + souris + molette (`LowLevelHooker`, `MouseWheelInfo`) | `inputs.py` (pynput) |
| Manette, 38 boutons et combinaisons (`ControllerHooker`, `GamePadButtons`) | `gamepad.py` (XInput / pygame) |
| Détection de collisions et touches réservées (`HotKeyCollisionException`, `RestrictedHotkeysValidator`) | `HotKeyRegistry.bind` |
| Calibration manuelle des clics (`IManualClickCalibrationProfile`) | onglet Salles → Calibrer |
| 16 boutons de mise (BB préflop / % pot / multiplicateur / géométrique), mode de relance, Ctrl = 2e groupe, molette (`BetButtonsConfigViewModel`, `IComposedBetService`) | `betsizing.py`, page Raccourcis |
| Overlay « boutons de mise », capture d'écran de table, compteurs AR / ST | `TableOverlay`, `CounterWidget` |
| RNG flottant, déplacement sous le pointeur (`StandaloneRNGService`, `RNGMoveToPointer`) | `rng.py`, `RngOverlay` |
| Minuteur de session, widgets (tables ouvertes, AR, mains), notifications, sessions précédentes (`SessionTimeWindow`, `SessionCountersService`, `ARTablesCounterWindow`) | `session.py`, `SessionHistory`, page Temps de Session |
| Alertes sonores (`AudioPlaybackService`) | `sounds.py` (11 sons d'origine) |
| Manette : détection, vibration au tour, curseur | `gamepad.py`, page Contrôleur |
| 10 langues (`language.xx.loc`) | `i18n.py` |
| Pot Odds, SPR, MDF, EFFS, OUTS, Bluff Equity (overlays) | `pokermath.py`, onglet Calculatrice |
| Focus suit la souris (`IFocusTracker`, `IFocusGiver`) | `focus_follows_mouse` |
| Sit-out / sit-in / sit-out partout | actions correspondantes (clics calibrés) |
| Sauvegarde cloud de la configuration (`ConfigCloudBackupService`, S3) | export / import de fichier local |
| Journal des notifications (`NotificationsDebugWindow`) | Aide → Diagnostic |
| 26 salles (`Jurojin.Core.<Salle>.dll`) | `sites.DEFAULT_SITES` (motifs modifiables) |

## 3. Éléments supprimés (serveur, licences, traqueurs)

- **Licences / fonctionnalités payantes** : espace `PayedFeatures`
  (`ITablesTilingChecker`, `ILayoutsAndSlotsCheckingService`,
  `ITableStakeChecker`, `IFastPlacementStakeDeferPolicy`,
  `ITableOverlaysChecker`, `ITableBetsizesAcessChecker`), essais, droits de
  session → **aucune restriction** dans Fukuroku (rien à déverrouiller : ces
  contrôles n'existent pas).
- **Serveur** : `KeepAlive`, `ServerCommunicator`, `OpenConnection`,
  connexion/inscription/mot de passe, notifications serveur
  (`*ServerNotificationAction`), collision de connexion, mises à jour du
  lanceur et des plugins, signature des CGU.
- **Paiements** : Stripe, crypto, cartes cadeaux, boutique, dons.
- **Traqueurs et collecte** : Mixpanel, HubSpot, Mailchimp,
  `SessionMetadataEventTracker`, rapports d'appareil (`DeviceReportProvider`,
  `DisplayInfoDto`), empreinte machine (`DeviceIdentifierAPI`), envoi de
  journaux/crash vers S3, rapports forcés à distance.
- **Intrusif** : `FirewallManager`, `RegistryManipulationDll`,
  `HostsFileReportGuard`, `ClientSecurity`.
- **Divers en ligne** : chat de support (WebView2 `chat-bot.html`), Twitch,
  Discord, actualités, streamers de l'accueil.
- **Menu** : entrées *Compte* et *Boutique* retirées (rien à acheter ni à
  déverrouiller) ; les bandeaux « fonction verrouillée » n'existent pas.

Fukuroku n'ouvre **aucune connexion réseau** (aucun import de `socket`,
`urllib`, `http` dans le code).

## 4. Non porté et pourquoi

- **Plugins injectés dans les clients de poker** (`Plugins/*.dll`,
  `ProcessCommunicator64.exe`, `OverlayAPI`) : ils lisent l'état interne des
  clients (pot, tapis, cartes, tour d'action). Le code natif n'est pas
  reproduit et l'injection dans des logiciels tiers est exclue. Remplacement :
  - détection « action requise » par **sonde pixel** calibrable par salle ;
  - interface `TableManager.data_provider` (`TableDataSnapshot`) et
    `TableManager.set_action_required()` pour brancher une source de données
    (ex. lecteur d'historique de mains, OCR) ;
  - calculs des overlays disponibles en **calculatrice** manuelle.
- Les overlays affichés **sur** les tables (positions des joueurs, historique
  d'actions, masquage du board, affichage en BB) dépendent de ces données ;
  les actions de raccourci existent et sont relayées, mais n'ont d'effet
  visible qu'avec un fournisseur de données.
- Fonctions « confort » qui modifient l'affichage du client : conversion en BB,
  taille de police, auto-timebank, éviter le sit-out, garder les Spins,
  masquer le solde, copier le nom d'un joueur, couleurs des stacks ; ainsi que
  **Rebuy/Top-up automatique** et **gestion des popups**. Elles sont affichées
  (grisées, avec explication) dans la page Configuration des Sites.
- **Mises automatiques par nombre de joueurs / tranches de stack effectif**
  (`AUTOBET_*`) et overlays de sièges : nécessitent l'état de la main.
- « Déplacer la table en cliquant n'importe où » : demanderait d'intercepter
  les clics dans les clients ; la barre de titre reste utilisable.
- **Motifs de reconnaissance des salles** : chiffrés dans l'original ; les
  valeurs par défaut de Fukuroku proviennent de conventions publiques des
  clients et doivent être vérifiées (onglet Salles, `--list-windows`).

## 5. Inconnues restantes

- Algorithmes exacts de `Jurojin.Core.dll` (métadonnées hors budget REA,
  corps de méthodes protégés) : les comportements de placement sont déduits
  des noms d'interfaces et de modèles, pas du code.
- Points de clic par défaut et couleurs des sondes : à calibrer pour chaque
  client/skin.

## 6. Ressources reprises (avec autorisation)

Extraites statiquement de `JurojinUI.exe` et des DLL `Jurojin.Style`,
`Jurojin.Rng`, `OverlayWindows` (section ressources CLI, format
`.resources` 0xBEEFCACE, BAML décodé pour la palette et les dimensions) :

| Dossier `fukuroku/assets/` | Contenu |
|---|---|
| `sounds/` | les 11 sons d'alerte (Bell, Bubble, Ascending…) |
| `images/` | illustrations des réglages, layouts, sites, raccourcis, manette, session, overlays, aide, drapeaux, logo, icône, écran de démarrage |
| `fonts/` | Montserrat, Digital-7 Mono, Technology |
| `locale/` | 10 fichiers `language.xx.loc` (1 546 clés) ; le nom du produit y est remplacé à l'exécution |
| `presets/` | layouts prédéfinis par résolution |

Non repris : icônes vectorielles du menu (géométries binaires BAML) —
remplacées par des glyphes Unicode — et logos vectoriels des salles.
