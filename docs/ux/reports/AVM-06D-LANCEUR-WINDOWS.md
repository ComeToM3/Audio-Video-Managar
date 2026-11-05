# Rapport AVM-06D — Lanceur Windows

**Date :** 2026-11-03  
**Version :** 0.5.0  
**Livrable :** `Lancer-AudioVideoManager.bat` (racine du dépôt)

---

## Verdict

**GO** pour usage quotidien (double-clic / raccourci bureau), sous réserve que `.venv` soit déjà créé et le paquet installé (`pip install -e ".[dev]"`).

Aucune modification du pipeline CD, de l’UI ni des données utilisateur.

---

## Utilisation (instructions courtes)

1. Une fois le projet installé (venv + dépendances), double-cliquer **`Lancer-AudioVideoManager.bat`** à la racine du dépôt.  
2. **Raccourci bureau :** clic droit sur le `.bat` → *Créer un raccourci* → déplacer le raccourci sur le bureau. Ne pas recopier seulement le `.bat` hors du dépôt.  
3. Équivalent terminal : `python -m audio_video_manager` dans le venv (inchangé).

Le lanceur :

- se place dans **son** dossier (`%~dp0`), pas le dossier du raccourci ni le cwd ;
- appelle uniquement `.venv\Scripts\python.exe -m audio_video_manager` ;
- **ne** touche pas au PATH système, **ne** demande pas l’admin, **ne** télécharge rien ;
- en cas d’échec, affiche un message FR et `pause` pour laisser lire l’erreur / la traceback.

Config, SQLite, jobs, logs et bibliothèques restent sous `%LOCALAPPDATA%\AudioVideoManager` / chemins configurés (inchangés).

---

## Conception

| Exigence | Mise en œuvre |
|----------|----------------|
| Chemins relatifs | `%~dp0` + `cd /d "%~dp0"` |
| Espaces / caractères spéciaux | Guillemets sur tous les chemins |
| Python isolé | `.venv\Scripts\python.exe` uniquement |
| Contrôles préalables | Existence de l’interpréteur + `audio_video_manager\__main__.py` |
| Code de sortie | Propagé ; pause seulement si ≠ 0 |
| Pas d’exe / pas de deps | Script `.bat` seul |

---

## Tests réalisés

| Cas | Résultat |
|-----|----------|
| Absence de `.venv\Scripts\python.exe` | Exit **1** + message FR + pause |
| Absence de `audio_video_manager\__main__.py` | Exit **1** + message FR + pause |
| Jonction Windows dont le chemin contient des **espaces** | Import module OK ; bat trouve python + entry |
| Lancement réel GUI via le bat | Processus `python -m audio_video_manager` démarré (logs fre:ac / lecteurs) |
| Cwd ≠ dossier projet | Résolu via `%~dp0` (conception vérifiée) |

Non testé volontairement : installation silencieuse de dépendances (hors mandat), élévation UAC (non requise).

---

## Limites

1. Le `.venv` doit exister **dans** le dépôt ; le lanceur ne le crée pas.  
2. Un raccourci doit pointer vers le `.bat` **dans** le clone ; déplacer le bat seul casse les chemins relatifs.  
3. Console : une fenêtre cmd peut flasher au démarrage (normal pour un `.bat`) ; en succès elle se ferme avec l’app.  
4. En échec, `pause` attend une touche (voulu pour lire l’erreur).  
5. Pas de `.exe` / PyInstaller (hors mandat).

---

## Note labo (tests)

Un test « chemins avec espaces » a utilisé une **jonction** Windows vers le dépôt. Le nettoyage a brièvement effacé des fichiers racine via cette jonction (`README.md`, `LICENSE`, `pyproject.toml`, `.gitignore`). Ils ont été **restaurés** immédiatement (transcript + contenu connu). Aucune donnée `%LOCALAPPDATA%\AudioVideoManager` ni bibliothèque musicale n’a été touchée. Ne plus utiliser de jonction vers l’arbre vivant pour les tests.

---

## Fichiers touchés

- `Lancer-AudioVideoManager.bat` (nouveau)  
- `README.md`, `docs/engineering/development.md` (mention courte)  
- ce rapport  

**Arrêt :** attendre validation mandant avant autre modification.
