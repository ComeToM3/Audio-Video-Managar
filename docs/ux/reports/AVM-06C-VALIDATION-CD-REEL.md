# Rapport AVM-06C — Premier archivage CD réel contrôlé

**Date (préparation) :** 2026-11-03  
**Version app :** 0.5.0  
**Disque cible :** Queen — *Greatest Hits* (17 pistes)  
**Statut du mandat :** **ARRÊT AVANT RIP** — extraction physique **non lancée**

---

## Verdict courant

| Phase | Verdict |
|-------|---------|
| Prérequis | **GO** |
| Identification réelle (TOC / MB / CAA) | **GO** (CA 1992 auto-sélectionnée comme départage D-015) |
| Isolation bibliothèque | **GO** |
| Garde Replace | **GO** (option désactivée) |
| Extraction / publication réelle | **NON EXÉCUTÉE** — en attente d’autorisation explicite |
| Verdict final archivage multi-CD | **À compléter après rip autorisé** |

---

## 1. Prérequis vérifiés

| Élément | Résultat |
|---------|----------|
| Lecteur optique Win32 | **D:** · `ATAPI iHAS324   C` · `MediaLoaded=True` |
| fre:ac / freaccmd | **OK** `C:\Program Files\freac\freaccmd.exe` |
| Mapping fre:ac → libdiscid | fre:ac drive `0` / designation modèle `… C` → **D:** (pas C:) |
| libdiscid DLL | **OK** `vendor/libdiscid/…/x64/discid.dll` · défaut `D:` |
| MusicBrainz (réseau) | **OK** — 2 candidats GH reçus |
| Cover Art Archive | **OK** — front + thumb ; cache local `…/cache/covers/e534e30a….jpg` (37 811 o) |
| PySide6 | **OK** 6.12.0 |
| Espace disque | **~342 Go** libres |
| Suite auto | **90 tests PASS** (89 + garde Replace) |

**Import direct `import discid` sans loader** échoue (PATH) — **normal** ; l’app utilise `import_discid()` / `prepare_libdiscid_search_path()`.

---

## 2. Bibliothèque de test isolée

| | |
|--|--|
| Racine test | `C:\Users\ComeToM3\Music\AVM-06C-Test-Library` |
| Marqueur | `.avm-06c-isolated` |
| Config `library_root` | pointée vers la racine test (2026-11-03) |
| Bibliothèque « principale » placeholder | `Music\AudioVideoManager` — **inexistante / non utilisée** |

Aucune écriture dans une collection principale existante.

---

## 3. Garde collision Replace

Sans dialogue de confirmation Replace dans UI-1 :

- radio **Remplacer** désactivée + tooltip + note FR ;
- `_collision_policy()` ignore Replace tant que le contrôle est désactivé ;
- défaut **Rename** ;
- test `tests/test_ui_collision_replace_disabled.py`.

---

## 4. Identification réelle (sans rip)

| Champ | Valeur observée |
|-------|-----------------|
| Disc ID | `DsXlPG1OQWhceSELb2Eiq5rx1wU-` (identique AVM-04 / 04B) |
| TOC | 17 pistes · offsets secteurs inchangés vs 04B |
| Durée piste 17 (TOC) | 262 000 ms |
| Candidats MB | US 1991 `aceaf449-…` / **CA 1992** `4662a6ff-…` |
| Sélection auto (pref CA) | **CA 1992** · cat. `CD 61265` · Hollywood Records · year 1992 |
| Message départage | explicite : préférence pays = **départage**, **pas** preuve de pressage |
| `toc_match` | **partial** (piste 17 TOC 262 000 vs MB 258 733) — non forcé en `exact` |
| Pochette | `cover_status=confirmed` |
| `approval` | **Pending** — gate D-011 bloque le rip |
| `is_compilation` trust | à **confirmer manuellement** dans W3 (case à cocher) avant Approuver |

### 17 pistes (prévisualisation MB/TOC)

| # | Titre | ms TOC |
|---|-------|--------|
| 01 | We Will Rock You | 122000 |
| 02 | We Are the Champions | 182000 |
| 03 | Another One Bites the Dust | 217000 |
| 04 | Killer Queen | 181000 |
| 05 | Somebody to Love | 297000 |
| 06 | Fat Bottomed Girls | 256000 |
| 07 | Bicycle Race | 183000 |
| 08 | You’re My Best Friend | 172000 |
| 09 | Crazy Little Thing Called Love | 164000 |
| 10 | Now I’m Here | 255000 |
| 11 | Play the Game | 212000 |
| 12 | Seven Seas of Rhye | 168000 |
| 13 | Body Language ↑⬱ | 274000 |
| 14 | Save Me | 229000 |
| 15 | Don’t Stop Me Now | 211000 |
| 16 | Good Old‐Fashioned Lover Boy | 175000 |
| 17 | I Want to Break Free | 262000 |

Avertissements à relire avant Approuver : écart piste 17, alternatives US/1991, collation compilation.

---

## 5. Checklist utilisateur — AVANT extraction

À faire **dans le wizard**, **sans** cliquer « Lancer l’archivage » tant que cette checklist n’est pas validée ici.

1. [ ] CD Queen GH toujours dans **D:** (ne pas changer de disque).
2. [ ] Lancer l’app : `python -m audio_video_manager` (venv activé).
3. [ ] **Paramètres** : dossier bibliothèque = `…\Music\AVM-06C-Test-Library` ; pays préféré `CA` ; fre:ac détecté.
4. [ ] **Archiver** → Relire le disque → Disc ID `DsXlPG1OQWhceSELb2Eiq5rx1wU-` · 17 pistes.
5. [ ] Identification : édition **CA 1992 / CD 61265** (ou choix manuel conscient US 1991).
6. [ ] Vérifier pochette affichée + avertissement TOC piste 17.
7. [ ] W3 : cocher/confirmer **compilation** si applicable ; titres OK ; **Approuver la fiche** explicitement.
8. [ ] W4 : **Publier…** coché ; collision = **Créer un nouveau dossier (Rename)** ; Replace grisé.
9. [ ] Confirmer ici au mandant : prêt pour rip → attendre **autorisation écrite**.
10. [ ] **Seulement après GO** : « Lancer l’archivage » — laisser le CD jusqu’à W5 succès.

---

## 6. Extraction / publication

**Non démarrée.** Section à remplir après autorisation :

| Contrôle | Résultat |
|----------|----------|
| Progression FR (vérif → extract → tags → publish) | |
| 17 FLAC + F-08a | |
| Tags MB / discid / titres | |
| Embed + `cover.jpg` | |
| Dossier zone C sous biblio test | |
| Collision | |
| Job SQLite / logs | |
| Lecture externe (ex. VLC / foobar2000) | |

---

## 7. Anomalies / limites (pré-rip)

1. Remplace désactivé volontairement (écart UX vs Replace complet).
2. Titre piste 13 conserve glyphes MB (`↑⬱`) — à normaliser manuellement si souhaité avant Approuver.
3. `toc_match=partial` piste 17 — attendu, documenté 04B/04C.
4. Aucune suppression destructive prévue ; trash Replace hors circuit.

---

## 8. Arrêt obligatoire

**Aucun rip physique n’a été lancé automatiquement.**

Prochaine action : **autorisation explicite du mandant** pour lancer l’extraction sur ce CD, vers la bibliothèque isolée uniquement.

Après rip + vérifications : compléter §6, § verdict final GO/NO-GO pour d’autres CD, puis **attendre décision** avant tout autre mandat.
