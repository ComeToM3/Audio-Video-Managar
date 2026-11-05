# 09 — Risques, arbitrages résiduels et validation

## 1. Risques

| Risque | Sévérité | Mitigation spec |
|--------|----------|-----------------|
| Fingerprint A3 incomplet (champ oublié) | Moyenne | Liste figée dans 05-contrats ; tests dirty |
| Identify long bloque UI | Haute | Worker async obligatoire (05 §2) |
| Utilisateur quitte pendant rip | Haute | Lock nav + confirm annulation |
| Replace mal compris | Haute | Libellé corbeille locale + confirm |
| Scope UI-1 trop large | Haute | UI-1 = wizard only ; biblio/hist après |
| Divergence spec 06A §A3 vs nuance 06B | Faible | 00-arbitrages-figes fait foi |
| Cover download CORS/HTTP | Faible | urllib déjà OK côté app ; cache local |

## 2. Incompatibilités techniques signalées

1. **A3 nuance vs ancien « révoquer au retour W3 »** — résolu : specs suivent la nuance (nav conserve ; data/identity invalide).
2. **Pas d’API métier `revoke_approval()`** — **résolu en AVM-06** : `metadata/approval_fingerprint.revoke_approval` + sync empreinte (gate D-011 inchangée).
3. **Messages progress `archive_job` parfois techniques** — couche traduction UI prévue ; pas de refonte métier obligatoire pour UI-1.
4. **Historique « Reprendre »** — capacités limitées (architecture) ; UI doit dire « non disponible » plutôt que promettre.

## 3. Arbitrages résiduels (mineurs — peuvent attendre l’implémentation)

| ID | Question | Défaut proposé |
|----|----------|----------------|
| R1 | Cache pochettes : `%LOCALAPPDATA%/…/cache/covers` vs `jobs/` | cache app dédié |
| R2 | Publish depuis inbox (job AwaitingPublish) dans UI-2 ? | Non dans UI-1 ; option UI-2+ |
| R3 | Hash fingerprint : json canonical vs tuple | json trié UTF-8 |

Ces R* **ne bloquent pas** le GO d’implémentation s’ils restent au défaut.

## 4. Livrable checklist AVM-06B

- [x] 4 sections spécifiées  
- [x] Wizard 5 étapes détaillé  
- [x] Écrans : composants, états, messages FR  
- [x] Wireframes structurés + a11y/resize  
- [x] Contrats services AVM-05  
- [x] Matrice états + A3  
- [x] AC + plan UI-0…4 + porte AVM-06C  
- [x] Risques / résiduels  

## 5. Validation — ARRÊT OBLIGATOIRE

Aucune écriture de code UI tant que non signé.

| Champ | Valeur |
|-------|--------|
| Relecteur | |
| Date | |
| Décision | **GO implémentation (UI-0→UI-1)** / **GO avec réserves** / **NO-GO** |
| Réserves (si besoin) | |

```
Commentaires :



```

Dès **GO**, enchaîner l’implémentation selon [08-acceptation-tests-plan.md](08-acceptation-tests-plan.md) **sans** élargir D-011…D-015, puis **AVM-06C** pour le premier rip réel contrôlé.
