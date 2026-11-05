# 06 — Matrice des états

## 1. États session wizard

| État session | step | approval typique | CTA principal |
|--------------|------|------------------|---------------|
| `DISC_EMPTY` | 1 | — | Relire |
| `DISC_READY` | 1 | — | Continuer |
| `ID_LOADING` | 2 | Pending | (disabled) |
| `ID_READY` | 2 | Pending | Continuer |
| `APPROVE_EDIT` | 3 | Pending | Approuver si valid |
| `APPROVED` | 3 ou 4 | Approved | Continuer / Lancer |
| `APPROVED_DIRTY` | 3 | Pending* | Approuver à nouveau |
| `EXTRACT_RUNNING` | 4 | Approved | Annuler |
| `DONE_OK` | 5 | Approved | Autre CD |
| `DONE_WARN` | 5 | Approved | Autre CD |
| `DONE_FAIL` | 5 | Approved ou Pending | Réessayer / Hist. |

\*Pending après dirty A3.

## 2. Matrice événements × effets

| Événement | Précond. | Effet |
|-----------|----------|-------|
| Nav → Bibliothèque | not EXTRACT_RUNNING | Conserve session + approval |
| Retour W4→W3 | not running | Conserve Approved si pas dirty |
| Edit champ W3 | was Approved | → APPROVED_DIRTY |
| apply autre édition | was Approved | → APPROVED_DIRTY |
| Relire TOC ≠ disc_id | — | Reset identity path ; Pending ; warning |
| approve_sheet OK | validation ok | → APPROVED + fingerprint |
| Lancer archive | Approved & confirm | → EXTRACT_RUNNING |
| DiscMismatchError | — | Reste W4 idle ; erreur ; pas de rip |
| Job Completed | — | → DONE_OK / DONE_WARN |
| Job Failed/Cancel | — | → DONE_FAIL |

## 3. États widgets transverses

| Widget | empty | loading | error | ready |
|--------|-------|---------|-------|-------|
| CoverThumb | placeholder gris | spinner | icône cassée | pixmap |
| WarningList | hidden | — | — | visible max 5 |
| ErrorList | hidden | — | visible | — |
| Stepper step n | muted | current accent | — | check |

## 4. Bibliothèque items

| État item | Badge | Action Ouvrir |
|-----------|-------|---------------|
| OK path exists | — | enabled |
| path missing | Dossier manquant | disabled + tooltip |
| inbox only | En attente | ouvrir inbox |

## 5. Historique jobs

| `jobs.state` | Libellé FR | Actions |
|------------|------------|---------|
| Completed / CompletedWithWarnings | Terminé / Terminé avec avertissements | Ouvrir C, workdir |
| AwaitingPublishConfirmation | En attente de publication | Ouvrir inbox ; (futur publish) |
| Failed | Échec | Workdir, détail erreur |
| Cancelled / Interrupted | Annulé / Interrompu | Reprendre si éligible |
| Ripping / Tagging / … | En cours (rare si UI fermée) | — |

## 6. Conformité D-011…D-015

| Décision | Couverture états |
|----------|------------------|
| D-011 Gate | Pas de EXTRACT sans APPROVED |
| D-012 Placeholders | Bloqués dans APPROVE_EDIT via validation |
| D-013 Test technique | Hors wizard ; Settings Avancé |
| D-014 Ordre meta→rip | Stepper impose 3 avant 4 |
| D-015 Pref pays / no auto-approve | W2 texte ; pas d’auto Approved |
| A3 | APPROVED vs APPROVED_DIRTY vs nav |
