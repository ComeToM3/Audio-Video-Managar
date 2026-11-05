# 08 — Plan d’implémentation priorisé (post-validation)

**Prérequis :** GO sur [09-arbitrage-a-valider.md](09-arbitrage-a-valider.md).  
**Mandat suivant suggéré :** AVM-06B — implémentation UI (sans changer règles métier).

## Phase UI-0 — Fondations coquille (0,5–1 j)

- Shell : nav 4 sections + thème tokens CSS/Qt.
- Déplacer paramètres actuels → section Paramètres.
- Masquer probes / schéma / test technique dans Avancé.

**AC UX**
- Au lancement, l’utilisateur voit « Archiver un disque » par défaut, pas les probes.
- Redimensionnement &lt; 900 px : nav utilisable.

## Phase UI-1 — Wizard Archiver (priorité absolue)

- Stepper 5 étapes branché sur APIs existantes.
- Pochette image (téléchargement miniature).
- Messages d’erreur actionnables.
- Progression nommée + écran Terminé (ouvrir dossier).

**AC fonctionnels**
- Impossible d’archiver sans Approved (régression gate).
- Disc mismatch → stop avec message clair.
- Publish toujours confirmé à l’étape 4.

**AC UX**
- Utilisateur novice complète le parcours sans lire la doc dev.
- Jargon technique uniquement sous « Détails ».

## Phase UI-2 — Historique

- Liste jobs SQLite + détail + ouvrir chemins.
- Abandonner / reprendre selon règles actuelles.

**AC**
- Chaque archive Completed apparaît avec chemin C si publié.

## Phase UI-3 — Ma bibliothèque

- Scan léger `library_root` + jointure `releases`.
- Recherche + ouvrir dossier.

**AC**
- Album publié visible sans redémarrer l’app (rafraîchir).

## Phase UI-4 — Polish & accessibilité

- Focus clavier, contrastes, textes d’aide.
- Premier archivage réel guidé (mandat validation séparé AVM-06C).

## Hors plan immédiat

DVD UI active, lecteur audio, cloud, auto-approve.

## Risques d’implémentation

| Risque | Mitigation |
|--------|------------|
| Refonte trop large | Ne pas toucher `archive_job` / validation sauf adaptateurs UI |
| Régression gate | Garder tests AVM-03…05 ; ajouter tests UI smoke si possible |
| Perf scan bibliothèque | Index SQLite d’abord ; scan FS lazy |
| Scope creep DVD | Placeholder non cliquable seulement si arbitrage A5 = oui |
