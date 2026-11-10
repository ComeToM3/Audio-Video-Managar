# AVM-28F — Présélection des éditions MusicBrainz

**Verdict : PARTIEL — cause démontrée et corrigée dans le code; vérification de l’interface Windows après correction encore attendue.**

## Cause

Les traces AVM-28E utilisateur indiquaient `candidates=2`, `selected=None`, `auto=False`, puis album/artiste/année vides. Dans `rank_and_select_releases`, les candidats non bloqués TOC sont triés par score, mais l’embranchement « non équivalents » retournait `selected=None`. `identify_disc` n’appliquait le candidat que si `auto_selected=True`; le modèle conservait donc la fiche TOC et le combo restait sans édition sélectionnée. Le défaut ne venait ni du lanceur ni de la connexion Qt.

## Correction

- Pour plusieurs candidats viables non équivalents, le candidat le mieux classé est maintenant `selected`, avec `auto_selected=False` et `require_manual_choice=True`. Les candidats TOC bloquants ne sont toujours pas proposés.
- `identify_disc` applique le candidat présélectionné au modèle; titre, artiste, année, pistes, durées et autres champs sont visibles immédiatement. Le wizard indique « Proposition présélectionnée » et garde les autres éditions sélectionnables.
- La fiche reste `Pending`. « Continuer » demeure l’approbation explicite; « Extraire » reste distinct. Changer d’édition met à jour la fiche et conserve la confirmation avant remplacement de corrections manuelles.
- Aucun changement au ripper, SQLite, pipeline de publication, DVD ou `technical_test`.

## Vérification

- Scénario ciblé deux éditions non équivalentes : sélection du meilleur candidat, valeurs modèle/widgets, modification manuelle, alternative et retour refusé/accepté vérifiés.
- Tests ciblés : `test_edition_ranker.py` **8**, `test_musicbrainz_identify.py` **19**, `test_ui_w3_prefill.py` **18**; tous réussis. Diagnostics éditeur sans erreur; `git diff --check` réussi.
- Aucun rip n’a été lancé. Les tests utilisent des TOC et éditions synthétiques; aucune lecture CD ou requête MusicBrainz physique n’a été effectuée par l’assistant.

## Confirmation utilisateur requise

Fermer toutes les instances AVM, laisser le CD réel présent, puis relancer une fois `Lancer-AudioVideoManager.bat`. Attendre que la fiche se remplisse et vérifier album, artiste, année et premières pistes. Ne pas cliquer sur « Continuer » ni « Extraire ». Renvoyer le résultat visible et les lignes `AVM28E_TRACE`; elles confirmeront que l’instance réelle a chargé le correctif.

**Pas de commit ni de push. Arrêt AVM-28F en attente de cette observation.**