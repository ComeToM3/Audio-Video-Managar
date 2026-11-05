# Rapport AVM-06G-P1 — Sécurisation des hardlinks

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Suite :** **127 passed** (115 + 12 tests P1)  
**Arrêt :** attendre validation explicite avant AVM-06H

---

## Verdict

| Critère | Résultat |
|---------|----------|
| Hardlinks staging / inbox sûrs | **GO** |
| Zone C indépendante (pas de hardlink publish) | **GO** |
| Mutations isolées (`ensure_exclusive_file`) | **GO** |
| Rollback publish (sources intactes, dest nettoyée) | **GO** |
| Repli `copy2` si `os.link` échoue | **GO** |
| CD remplacé / `disc_read` stale détecté | **GO** |
| Queen / bd40 / returncode / D-011…D-015 | **Préservés** |

**Recommandation : GO technique AVM-06G-P1.** **NO-GO AVM-06H** jusqu’à validation mandant.

---

## 1. Audit (constats)

### 1.1 Chaîne post-06G-P

| Étape | Avant P1 | Risque |
|-------|----------|--------|
| Staging → zone A | hardlink auto | Mutation de A = mutation source externe si hardlink |
| A → tagged | `copy2` + mutagen | OK (copie avant tag) |
| tagged → inbox | hardlink | Partage inode tagged↔inbox |
| tagged → **C** | hardlink | **C partagé avec tagged/inbox** — mutation d’un nom = tous |
| `disc_read` réutilisé sans relecture | skip TOC | **CD remplacé non détecté** si stale match fiche |

### 1.2 Tagging mutagen

`apply_flac_tags` → `audio.save()` **réécrit le fichier in-place**. Sur un chemin hardlinké, tous les noms liés changent. Avant P1 : pas d’isolation.

### 1.3 Rollback publish

`unlink` des dest écrites uniquement — source jamais consommée. Correct **si** dest = hardlink ou copy ; à vérifier par test (fait).

---

## 2. Correctifs appliqués

| ID | Correctif | Fichier |
|----|-----------|---------|
| H1 | `ensure_exclusive_file` : si `nlink>1`, `copy2` + `os.replace` avant mutation | `library/transfer.py` |
| H2 | Appel systématique dans `apply_flac_tags` | `library/tags.py` |
| H3 | Publish C : `transfer_file(..., independent=True)` **toujours copie** | `library/publish.py` |
| H4 | Rip réel : **toujours** `read_disc_toc` frais ; si `disc_read` identify ≠ fresh → `DiscMismatchError` | `orchestration/archive_job.py` |
| H5 | Helpers `same_file` / `link_count` | `library/transfer.py` |

### Gains 06G-P conservés

| Chemin | Hardlink auto | Commentaire |
|--------|---------------|-------------|
| Staging → A | **Oui** | + isolation si un jour tagué |
| tagged → inbox | **Oui** | Traçabilité B |
| tagged → C | **Non** (copie) | Immuabilité bibliothèque |
| Tagging A→tagged | Copie (inchangé) | Requis mutagen |

Impact perf attendu vs 06G-P « full hardlink » : perte du gain publish (~0,18 s / 381 Mo en banc) ; **conservation** staging+inbox (~0,35 s). Décodage inchangé.

---

## 3. Preuves de tests

Fichier : `tests/test_hardlink_security_06gp1.py`

| Test | Garantie |
|------|----------|
| `test_hardlink_same_inode_and_unlink_one_keeps_other` | Identité NTFS ; unlink d’un lien laisse l’autre |
| `test_transfer_falls_back_to_copy_when_os_link_fails` | Repli `copy2` (injection `OSError` sur `os.link`) |
| `test_transfer_link_mode_raises_without_fallback` | Mode `link` strict |
| `test_ensure_exclusive_breaks_hardlink_before_mutation` | Isolation ; mutation alias ≠ source |
| `test_apply_flac_tags_isolates_hardlinked_source` | Tags n’altèrent pas l’autre lien |
| `test_publish_c_is_independent_copy_not_hardlink` | C non `samefile` staging ; mutation staging ≠ C |
| `test_publish_rollback_unlinks_dest_keeps_source` | Échec mid-publish → 0 FLAC C ; sources OK |
| `test_inbox_may_hardlink_tagged_but_c_independent` | Pipeline : inbox lié possible, C isolé |
| `test_disc_swap_detected_via_fresh_toc_vs_sheet` | Fresh ≠ fiche → refus |
| `test_stale_identify_read_vs_fresh_same_sheet_detected` | `changé depuis` si identify désync |
| `test_stale_matching_disc_read_still_requires_fresh_toc` | TOC toujours relu avant rip |
| `test_independent_flag_ignores_auto_hardlink` | `independent=True` force copy |

Aucun rip physique ; dossiers temporaires pytest uniquement. Queen 17 + bd40 17 non modifiés.

---

## 4. Scénarios de défaillance couverts

| Scénario | Résultat attendu | Statut |
|----------|------------------|--------|
| `os.link` échoue (volume / droits) | `copy2` auto | **OK** |
| Publish échoue au 2ᵉ fichier | Rollback unlink dest ; sources intactes | **OK** |
| Tag sur fichier hardlinké | Copie exclusive puis tag | **OK** |
| CD changé vs fiche | Refus DiscMismatch | **OK** |
| `disc_read` identify ≠ lecteur actuel (fiche OK) | Refus « changé depuis » | **OK** |
| Suppression d’un hardlink inbox | tagged / C inchangés (C déjà copie) | **OK** (modèle) |

---

## 5. Risques résiduels

| ID | Gravité | Description | Mitigation |
|----|---------|-------------|------------|
| R-H1 | P2 | tagged↔inbox restent hardlinkés : outil externe éditant inbox mute tagged (pas C) | Documenté ; C isolé |
| R-H2 | Info | Staging hardlink depuis source externe : ne jamais taguer la zone A in-place | Pipeline copie vers tagged avant tag |
| R-H3 | Info | `AVM_TRANSFER=link` sans repli peut échouer en cross-volume | Usage diagnostic seulement |
| R-H4 | P2 | AccurateRip / outils tiers hors AVM | Hors périmètre |

---

## 6. Lien avec AVM-06G-P

| Affirmation 06G-P | Ajustement P1 |
|-------------------|---------------|
| Hardlink publish C | **Retiré** — copie indépendante obligatoire |
| Réutilisation `disc_read` sans optique | **Corrigé** — relecture obligatoire avant rip ; `disc_read` = contrôle anti-désync seulement |
| Hardlink staging / inbox | **Conservé** |
| Spans perf / banc | Toujours valides pour staging/inbox ; republish C = coût copy |

---

## 7. Critères GO / NO-GO

| # | Critère | Statut |
|---|---------|--------|
| G1 | Hardlinks sûrs ou copie sur chemin critique | **GO** |
| G2 | Mutations isolées | **GO** |
| G3 | Rollback vérifié | **GO** |
| G4 | Repli `copy2` fiable | **GO** |
| G5 | Pas d’archivage silencieux CD remplacé | **GO** |
| G6 | Pas de régression tests | **127 passed** |
| H0 | Validation mandant → 06H | **EN ATTENTE** |

---

## 8. Fichiers

| Chemin | Rôle |
|--------|------|
| `library/transfer.py` | exclusive / independent / same_file |
| `library/tags.py` | isolation avant save |
| `library/publish.py` | C toujours `independent=True` |
| `orchestration/archive_job.py` | TOC fraîche + anti-swap |
| `tests/test_hardlink_security_06gp1.py` | régressions |
| `docs/ux/reports/AVM-06G-P1-SECURITE-HARDLINKS.md` | ce rapport |

---

**Fin AVM-06G-P1 — arrêt obligatoire. Attendre GO explicite avant AVM-06H.**
