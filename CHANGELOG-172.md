## Issue #172 — Retrait du contour bleu pointillé "tapis manipulable"

- `jeu.css` : suppression du contour pointillé bleu générique
  `.tuile-jeu.tapis-manipulable` (et son effet au survol), qui s'affichait
  en permanence sur toutes les tuiles du tapis dès la mise initiale faite et
  ne signalait donc plus rien d'utile, tout en créant de la confusion avec
  les vrais indicateurs de tour (vert #128/#129, orange #136/#139).
- Seul le curseur `move` est conservé sur `.tapis-manipulable` comme
  affordance de prise en main (sans contour visuel).
- Les règles combinées `.tuile-jeu.ce-tour.tapis-manipulable` (vert) et
  `.tuile-jeu.deplacee-tapis.tapis-manipulable` (orange) sont conservées et
  définissent désormais leur propre `outline` complet (plus seulement une
  surcouche de couleur), sans dépendre visuellement du contour de base
  supprimé. Comportement inchangé pour ces deux indicateurs.
