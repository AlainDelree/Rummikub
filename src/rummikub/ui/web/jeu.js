"use strict";

// Avatars SVG et helpers genrés : voir commun.js (AVATARS, avatarPour,
// elementAvatar, avatarStablePourPrenom) + genres.js (genrePrénom).
const COULEURS_ORDRE = { rouge: 0, bleu: 1, jaune: 2, noir: 3 };

// ------------------------------------------------------------ état local
let etat = null;              // état complet de la partie (dict serveur)
let chevaletLocal = [];       // ordre local du chevalet, conservé entre les tours
let tuileSelectionnee = null; // id de tuile sélectionnée sur le chevalet
let tuilesCeTour = [];        // ids des tuiles posées ce tour
let plateauLocal = [];        // tapis existant, potentiellement étendu ce tour
let travail = [[], []];       // 2 zones de pose (issue #128), chacune = [dict_tuile, ...]
let rangeeActive = 0;         // index 0-1 de la rangée de travail active
let reorgSource = null;       // id de la tuile source d'un échange (réorg clic-long)
let tuilesOrigineTapis = [];  // ids des tuiles PRISES sur le tapis ce tour
let trouJoker = null;         // { combo, pos } : trou laissé par un joker pris (guidage)
let comboActive = null;       // index de la combo ciblée pour l'insertion, ou null (issue #47)
let dernierClicChevalet = { id: null, temps: 0 }; // détection du double-clic
// Détection du double-clic sur une tuile du tapis (issue #103) : attachée à
// TOUTE tuile manipulable, quel que soit le mode, elle compare l'id de la
// tuile (donnée du modèle, pas la référence DOM — fiable même après un
// rafraîchissement). Sur 2e clic détecté : prend la tuile (prendreTuileTapis)
// ET finalise immédiatement (finaliserSelectionTapis), pour un dépôt en une
// seule interaction, comme le double-clic sur le chevalet.
let dernierClicTapis = { id: null, temps: 0 };
// Cas particulier où le 1er clic lui-même prend déjà la tuile (aucune autre
// tuile en attente, cf. branche « tapisManipulable » ci-dessous) : la tuile
// quitte alors le DOM immédiatement, donc le 2e clic du geste ne peut plus
// retrouver son id — il retombe sur sa combinaison source (le conteneur
// « combo-cliquable »). On mémorise cette combinaison et l'horodatage pour
// que ce 2e clic soit simplement absorbé (finaliserSelectionTapis) plutôt que
// reciblé comme destination (issue #133).
let derniereTuilePriseTapis = { idxCombo: null, temps: 0 };
// Détection de l'appui long (500 ms) sur une tuile du chevalet → active la réorg
let appuiLong = { timer: null, id: null, declenche: false };
let dragSourceId = null;      // id de la tuile en cours de glisser-déposer
let dernierePositionSouris = { x: 0, y: 0 }; // dernière position connue du curseur (fantôme, issue #50)
let triAutoActif = false;     // case "Tri automatique" (issue #126) : insère les tuiles piochées déjà triées
let indexAutoIAProgramme = null; // index_joueur_actuel pour lequel un jeu auto de l'IA est déjà programmé (issue #126)
let dezoomAutoActif = true;     // réglage "Dé-zoom automatique du tapis" (issue #135) ;
                                  // persisté via Reglages

// Signatures (listes d'ids jointes par "|") des combinaisons signalées comme
// invalides par le dernier contrôle serveur (Vérifier/Jouer) — issue #136.
// Une combinaison dont le contenu change (ajout/retrait d'une tuile) ne
// correspond plus à sa signature et perd donc automatiquement le surlignage.
let combosInvalidesSignatures = [];

// ------------------------------------------------------------ utilitaires
function clone(x) { return JSON.parse(JSON.stringify(x)); }

// Signature d'une combinaison (liste de dicts tuile) pour la comparer aux
// combos_invalides renvoyés par le serveur (issue #136).
function signatureCombo(tuiles) { return tuiles.map((t) => t.id).join("|"); }

function indexHumain() {
  if (!etat) return 0;
  const i = etat.joueurs.findIndex((j) => !j.est_ia);
  return i >= 0 ? i : 0;
}

function joueurCourantEstIA() {
  return !!(etat && etat.joueurs[etat.index_joueur_actuel] &&
            etat.joueurs[etat.index_joueur_actuel].est_ia);
}

function estMonTour() {
  return etat && etat.index_joueur_actuel === indexHumain() &&
         !etat.manche_terminee;
}

// Le tapis est manipulable dès que c'est le tour du joueur humain et que sa
// mise initiale est faite (comme au jeu physique). Le bouton « Annuler »
// couvre les fausses manipulations. Remplace l'ancien toggle « Mode tapis ».
function tapisManipulable() {
  return estMonTour() &&
         !!(etat.joueurs[indexHumain()] &&
            etat.joueurs[indexHumain()].mise_initiale_faite);
}

function decrireTuile(d) {
  if (!d) return "?";
  if (d.est_joker) return "Joker";
  return d.couleur + " " + d.valeur;
}

// Construit un élément .tuile-jeu à partir d'un dict tuile.
function tuileDepuisDict(d) {
  const el = creerTuileJeu(d.valeur, d.couleur, d.est_joker);
  el.dataset.id = d.id;
  return el;
}

// ------------------------------------------------------------ fantôme (issue #50)
// Retrouve le dict d'une tuile par son id (chevalet, zone de travail ou tapis).
function trouverDictTuile(id) {
  const c = chevaletLocal.find((t) => t.id === id);
  if (c) return c;
  for (const rangee of travail) {
    const t = rangee.find((x) => x.id === id);
    if (t) return t;
  }
  for (const combo of plateauLocal) {
    const t = combo.find((x) => x.id === id);
    if (t) return t;
  }
  return null;
}

// Marque (transparence) toutes les tuiles d'origine d'id `id` : elles « volent ».
function marquerFantomeSource(id) {
  document.querySelectorAll(".tuile-jeu").forEach((t) => {
    if (t.dataset.id === id) t.classList.add("fantome-source");
  });
}

// Crée le fantôme : copie visuelle agrandie de la tuile, suivant le curseur.
function creerFantome(id) {
  detruireFantome();
  const d = trouverDictTuile(id);
  if (!d) return;
  const el = tuileDepuisDict(d);
  el.id = "tuile-fantome";
  el.classList.add("tuile-fantome");
  el.style.left = dernierePositionSouris.x + "px";
  el.style.top = dernierePositionSouris.y + "px";
  document.body.appendChild(el);
  marquerFantomeSource(id);
}

// Détruit le fantôme et rend leur opacité aux tuiles d'origine.
function detruireFantome() {
  const f = document.getElementById("tuile-fantome");
  if (f) f.remove();
  document.querySelectorAll(".tuile-jeu.fantome-source").forEach(
    (t) => t.classList.remove("fantome-source"));
}

// Synchronise le fantôme avec l'état de sélection : le (re)crée si une tuile est
// sélectionnée, le détruit sinon. À appeler APRÈS les rafraîchissements de rendu
// (les éléments source doivent exister pour recevoir `fantome-source`).
function majFantome() {
  if (tuileSelectionnee !== null) creerFantome(tuileSelectionnee);
  else detruireFantome();
}

// Repli SVG du sac (utilisé si Sac_de_jeu.png est absent / ne charge pas).
function sacSvgHtml(nb) {
  return `
    <svg width="54" height="60" viewBox="0 0 54 60"
         xmlns="http://www.w3.org/2000/svg">
      <path d="M20 14 Q20 6 27 6 Q34 6 34 14"
            fill="none" stroke="#c9a961" stroke-width="2.5"
            stroke-linecap="round"/>
      <rect x="6" y="14" width="42" height="38" rx="10" ry="10"
            fill="#f5e6c8" stroke="#c9a961" stroke-width="2"/>
      <ellipse cx="16" cy="22" rx="5" ry="3"
               fill="rgba(255,255,255,0.4)"/>
      <text x="27" y="40" text-anchor="middle"
            font-family="system-ui, sans-serif"
            font-size="${nb > 99 ? 14 : nb > 9 ? 17 : 20}"
            font-weight="700" fill="#3b2f1a">${nb}</text>
    </svg>`;
}

// Bascule sur le SVG de repli si l'image du sac ne se charge pas.
function sacImgFallback(img) {
  const cont = img.closest("#compteur-pioche");
  if (!cont) return;
  const nb = cont.dataset.nb || "0";
  cont.innerHTML = sacSvgHtml(nb) + `<div class="sac-label">tuiles</div>`;
}

// Redessine l'icône « sac de pioche » (image + nombre superposé).
function mettreAJourSac(nb) {
  const cont = document.getElementById("compteur-pioche");
  if (!cont) return;
  cont.dataset.nb = nb;
  cont.innerHTML = `
    <div class="sac-pioche">
      <img src="Sac_de_jeu.png" alt="Sac de pioche" class="sac-img"
           onerror="sacImgFallback(this)">
      <span class="sac-nombre">${nb}</span>
    </div>
    <div class="sac-label">tuiles</div>`;
}

// ------------------------------------------------------------ rafraîchissement
function rafraichirTout() {
  if (!etat) return;
  rafraichirFichesJoueurs();
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
  rafraichirBoutonRejouerIA();
  mettreAJourSac((etat.pioche || []).length);
  if (etat.manche_terminee) afficherFinDeManche();
  verifierAutoIA();
}

// Jeu automatique du tour de l'IA (issue #126, réglage "Jouer automatiquement
// le tour de l'ordinateur") : dès que c'est le tour d'une IA, programme son
// coup après une latence d'environ 1 s (pour ne pas paraître brusque). Le
// bouton « Jouer » manuel est masqué pendant ce temps (issue #129, voir
// rafraichirFichesJoueurs) : plus de risque de double déclenchement.
function verifierAutoIA() {
  if (!etat || etat.manche_terminee || !joueurCourantEstIA()) {
    indexAutoIAProgramme = null;
    return;
  }
  if (!(etat.config && etat.config.ia_auto)) return;
  if (indexAutoIAProgramme === etat.index_joueur_actuel) return; // déjà programmé
  indexAutoIAProgramme = etat.index_joueur_actuel;
  setTimeout(() => {
    const btnIA = document.querySelector(".btn-jouer-ia");
    if (btnIA && btnIA.disabled) return; // déjà déclenché manuellement entre-temps
    if (etat && !etat.manche_terminee && joueurCourantEstIA()) jouerIA();
  }, 1000);
}

function rafraichirFichesJoueurs() {
  const cont = document.getElementById("fiches-joueurs");
  cont.innerHTML = "";
  const idxH = indexHumain();
  etat.joueurs.forEach((j, i) => {
    const fiche = document.createElement("div");
    fiche.className = "fiche-joueur" +
      (i === etat.index_joueur_actuel ? " actif" : "");

    // Avatar : index explicite s'il existe (choisi à l'accueil), sinon avatar
    // stable accordé au genre du prénom (parties reprises sans avatar_index).
    const nomFichierAvatar = j.avatar_index != null
      ? avatarPour(j.avatar_index)
      : avatarStablePourPrenom(j.nom);
    const av = elementAvatar(nomFichierAvatar, "avatar-fiche");
    fiche.appendChild(av);

    const info = document.createElement("div");
    info.className = "info-fiche";
    const nom = document.createElement("div");
    nom.className = "nom-fiche";
    nom.textContent = j.nom;
    if (j.est_ia && j.niveau) {
      const bn = document.createElement("span");
      bn.className = "badge-niveau";
      bn.textContent = j.niveau;
      nom.appendChild(bn);
    }
    info.appendChild(nom);

    const meta = document.createElement("div");
    meta.className = "meta-fiche";
    const nbT = (j.chevalet || []).length;
    const sm = j.score_manche || 0;
    meta.textContent = "🁢 " + nbT + " tuiles" +
      (sm !== 0 ? " · " + (sm >= 0 ? "+" : "") + sm + " pts" : "");
    info.appendChild(meta);
    fiche.appendChild(info);

    if (i === idxH && i === etat.index_joueur_actuel && !etat.manche_terminee) {
      const badge = document.createElement("span");
      badge.className = "badge-actif";
      badge.textContent = "▶ À vous";
      fiche.appendChild(badge);
    }
    // Tour d'une IA : bouton « Jouer » pour déclencher son coup manuellement.
    // Masqué quand le réglage « Jouer automatiquement le tour de l'ordinateur »
    // (issue #126) est actif : le coup se déclenche déjà tout seul, et laisser
    // le bouton cliquable créerait une concurrence avec ce déclenchement
    // automatique (issue #129) — inutile puisqu'il n'a alors aucun sens.
    const iaAuto = !!(etat.config && etat.config.ia_auto);
    if (j.est_ia && i === etat.index_joueur_actuel && !etat.manche_terminee && !iaAuto) {
      const btnIA = document.createElement("button");
      btnIA.className = "btn-jouer-ia";
      btnIA.textContent = "Jouer";
      btnIA.addEventListener("click", jouerIA);
      fiche.appendChild(btnIA);
    }
    cont.appendChild(fiche);
  });
}

function rafraichirPlateau() {
  const zone = document.getElementById("zone-plateau");
  zone.innerHTML = "";
  const tuileSel = tuileSelectionnee !== null;
  // Mode « insertion ciblée » (issue #47) : quand le tapis est manipulable et
  // qu'une tuile de la main est prête, on ne déballe les zones d'insertion que
  // sur la SEULE combinaison ciblée (comboActive). Les autres restent en rendu
  // normal, cliquables pour devenir la cible.
  const modeCible = tapisManipulable() && tuileSel;
  plateauLocal.forEach((combo, idxCombo) => {
    const groupe = document.createElement("div");
    groupe.className = "groupe-combinaison";
    // Combinaison devenue invalide (<3 tuiles) suite à une manipulation, ou
    // signalée invalide par le dernier contrôle serveur (issue #136) :
    // signalée en rouge jusqu'à ce que le joueur la complète/corrige ou annule.
    const estSignaleeInvalide = combosInvalidesSignatures.includes(signatureCombo(combo));
    if (combo.length < 3 || estSignaleeInvalide) groupe.classList.add("combi-invalide");

    // En mode ciblé : cette combo est-elle celle qui montre ses zones ?
    const estActive = modeCible && comboActive === idxCombo;
    if (modeCible && !estActive) {
      // Combo non ciblée : conteneur cliquable pour la désigner comme cible.
      groupe.classList.add("combo-cliquable");
      groupe.addEventListener("click", () => {
        // Fin d'un double-clic sur une tuile de CETTE combo (issue #133) :
        // le premier clic l'a déjà prise et envoyée en zone de travail ; ce
        // second clic retombe ici (la tuile d'origine a disparu du DOM) et
        // ne doit pas la recibler comme destination mais simplement
        // finaliser le dépôt déjà effectué.
        if (idxCombo === derniereTuilePriseTapis.idxCombo &&
            Date.now() - derniereTuilePriseTapis.temps < 350) {
          derniereTuilePriseTapis = { idxCombo: null, temps: 0 };
          finaliserSelectionTapis();
          return;
        }
        comboActive = idxCombo;
        rafraichirPlateau();
      });
    } else if (estActive) {
      groupe.classList.add("combo-active");
    }

    // Les zones d'insertion s'affichent : hors mode ciblé, dès qu'une tuile est
    // prête (comportement historique) ; en mode ciblé, sur la combo active seule.
    const afficherZones = modeCible ? estActive : tuileSel;

    // Position du trou (index d'insertion) laissé par un joker retiré de CETTE
    // combinaison — pour surligner en orange la zone correspondante.
    const posTrou = (trouJoker && trouJoker.combo === combo) ? trouJoker.pos : -1;

    // Zone d'extension en début de combinaison (= insertion en position 0)
    const extDebut = document.createElement("div");
    extDebut.className = "zone-ext zone-ext-debut" + (afficherZones ? "" : " masquee") +
      (posTrou === 0 ? " trou-joker" : "");
    extDebut.title = "Ajouter la tuile sélectionnée en début";
    extDebut.addEventListener("click", (e) => { e.stopPropagation(); etendreTapis(idxCombo, "debut"); });
    groupe.appendChild(extDebut);

    combo.forEach((d, idxTuile) => {
      // Zone d'insertion interne entre la tuile précédente et celle-ci
      // (position exacte = idxTuile). Uniquement quand une tuile est prête.
      if (idxTuile > 0 && afficherZones) {
        const zi = document.createElement("div");
        zi.className = "zone-ext zone-ext-interne" +
          (posTrou === idxTuile ? " trou-joker" : "");
        zi.title = "Insérer la tuile sélectionnée ici";
        zi.addEventListener("click", (e) => { e.stopPropagation(); insererTuileTapis(idxCombo, idxTuile); });
        groupe.appendChild(zi);
      }

      const el = tuileDepuisDict(d);
      // Tuile posée sur le tapis pendant le tour en cours (via les rangées de
      // pose, un « Placer », une extension ou une récupération de joker),
      // pas encore validée par « Jouer » : pourtour coloré (issue #128). Elle
      // se réarrange avec EXACTEMENT le même mécanisme que les tuiles des
      // tours précédents (ci-dessous) — seule l'avant mise-initiale (où ce
      // mécanisme n'existe pas encore) garde un retour direct vers la main.
      // Parmi ces tuiles du tour, celles qui étaient déjà sur le tapis avant
      // ce tour et ont simplement été déplacées/réorganisées (tuilesOrigineTapis)
      // reçoivent un pourtour bleu plutôt que vert, pour les distinguer des
      // tuiles réellement nouvelles issues de la main (issue #136).
      const estCeTour = tuilesCeTour.includes(d.id);
      const estDeplaceeDuTapis = tuilesOrigineTapis.includes(d.id);
      if (estDeplaceeDuTapis) el.classList.add("deplacee-tapis");
      else if (estCeTour) el.classList.add("ce-tour");

      // Détecteur de double-clic (issue #103/#133) : attaché à TOUTE tuile
      // manipulable, quel que soit le mode, AVANT le handler de clic simple
      // ci-dessous. Au 1er clic, il ne fait qu'enregistrer l'id/horodatage et
      // laisse le clic simple suivre son cours normal. Au 2e clic (même id,
      // moins de 350 ms : fiable même si le re-rendu a remplacé l'élément DOM,
      // puisqu'on compare une donnée du modèle, pas une référence DOM), il
      // coupe le clic simple (stopImmediatePropagation) et prend la tuile
      // directement, puis finalise (pas de sélection/fantôme en attente).
      // Seule exception : la branche « prise immédiate » plus bas, où le clic
      // simple retire déjà la tuile du DOM — dans ce cas, le 2e clic du geste
      // ne retombe plus sur cette tuile et est géré séparément (voir le
      // conteneur « combo-cliquable » ci-dessus).
      if (tapisManipulable()) {
        el.addEventListener("click", (e) => {
          const maintenant = Date.now();
          if (dernierClicTapis.id === d.id &&
              maintenant - dernierClicTapis.temps < 350) {
            e.stopImmediatePropagation();
            dernierClicTapis = { id: null, temps: 0 };
            prendreTuileTapis(idxCombo, idxTuile);
            finaliserSelectionTapis();
            return;
          }
          dernierClicTapis = { id: d.id, temps: maintenant };
        });
      }

      if (!tapisManipulable() && estCeTour) {
        // Avant la mise initiale, le réarrangement façon tapis n'est pas
        // encore proposé (tapisManipulable() faux) : seule la reprise directe
        // vers la main reste disponible pour ces tuiles.
        el.addEventListener("click", (e) => { e.stopPropagation(); reprendreTuile(d.id); });
      } else if (modeCible) {
        // Insertion ciblée : sur la combo active, cliquer une tuile insère la
        // tuile sélectionnée AVANT elle — SAUF si la tuile ciblée est un
        // joker que la tuile de la main sélectionnée remplace exactement :
        // dans ce cas, c'est un échange (retrait du joker, insertion de la
        // tuile à sa place, joker libéré attaché au curseur), pas un simple
        // ajout à côté (#143, suite #137 : cette branche « modeCible », ajoutée
        // par #47 après la récupération de joker originale, est toujours
        // évaluée avant l'ancienne branche « joker-recuperable » plus bas, qui
        // de ce fait ne peut en réalité jamais s'exécuter pendant son propre
        // tour — tapisManipulable() y est alors systématiquement vrai).
        // L'échange est proposé dès le PREMIER clic, même si la combo n'est
        // pas encore active (#146, suite #143 qui ne le proposait qu'une fois
        // la combo activée) : activer une combo insère les zones d'extension
        // internes (afficherZones), ce qui décale horizontalement les tuiles
        // suivantes — un second clic de l'utilisateur au même endroit (geste
        // naturel pour « cliquer deux fois sur le joker ») rate alors sa
        // cible et retombe sur la tuile voisine, d'où l'ajout à côté au lieu
        // de l'échange, constaté sur un groupe où le joker n'est pas en tête.
        const tuileSelDict = trouverDictTuile(tuileSelectionnee);
        const estEchangeJoker = d.est_joker && tuileSelDict &&
          chevaletLocal.some((t) => t.id === tuileSelDict.id) &&
          peutRemplacerJoker(tuileSelDict, valeurJokerDansCombo(combo, idxTuile));
        if (estEchangeJoker) {
          el.classList.add("tapis-manipulable", "joker-recuperable");
          el.addEventListener("click", (e) => {
            e.stopPropagation();
            tenterRecupererJoker(idxCombo, idxTuile, d);
          });
        } else if (estActive) {
          el.classList.add("tapis-manipulable");
          el.addEventListener("click", (e) => {
            e.stopPropagation();
            insererTuileTapis(idxCombo, idxTuile);
          });
        }
        // Sur une combo non active et sans échange possible pour cette tuile,
        // aucun handler par tuile : le clic remonte au conteneur qui la
        // désigne comme cible.
      } else if (tapisManipulable()) {
        // Tapis manipulable (aucune tuile prête) : toute tuile peut être « prise »
        // (dès le 1er clic, elle rejoint directement la zone de travail active,
        // voir prendreTuileTapis). Un double-clic produit donc déjà ce résultat
        // dès son premier clic ; le second clic du geste, lui, retombe sur la
        // combinaison source (la tuile d'origine a disparu du DOM) et est
        // intercepté par le handler du conteneur ci-dessus (issue #133).
        el.classList.add("tapis-manipulable");
        el.addEventListener("click", () => {
          derniereTuilePriseTapis = { idxCombo, temps: Date.now() };
          prendreTuileTapis(idxCombo, idxTuile);
        });
      }
      groupe.appendChild(el);
    });

    // Zone d'extension en fin de combinaison (= insertion en fin)
    const extFin = document.createElement("div");
    extFin.className = "zone-ext zone-ext-fin" + (afficherZones ? "" : " masquee") +
      (posTrou === combo.length ? " trou-joker" : "");
    extFin.title = "Ajouter la tuile sélectionnée en fin";
    extFin.addEventListener("click", (e) => { e.stopPropagation(); etendreTapis(idxCombo, "fin"); });
    groupe.appendChild(extFin);

    zone.appendChild(groupe);
  });
}

// Rendu de la zone de travail (2 zones de pose, issue #128)
function rafraichirZoneTravail() {
  const tuileSel = tuileSelectionnee !== null;
  travail.forEach((rangee, i) => {
    const cont = document.querySelector(`.rangee-tuiles[data-rangee="${i}"]`);
    const wrap = document.querySelector(`.rangee-travail[data-rangee="${i}"]`);
    const ind  = document.querySelector(`.rangee-indicateur[data-rangee="${i}"]`);
    if (!cont || !wrap) return;
    cont.innerHTML = "";
    wrap.classList.toggle("active", i === rangeeActive);
    wrap.classList.toggle("non-vide", rangee.length > 0);
    // Rangée signalée invalide par le dernier contrôle serveur (issue #136),
    // tant que son contenu n'a pas changé depuis (voir signatureCombo).
    wrap.classList.toggle("combi-invalide",
      combosInvalidesSignatures.includes(signatureCombo(rangee)));
    if (ind) ind.classList.toggle("actif", i === rangeeActive);
    // Zone d'insertion avant la première tuile (position 0), visible quand une
    // tuile est prête à être posée. Même système que sur le tapis (issue #27).
    if (tuileSel && rangee.length > 0) cont.appendChild(zoneInsertionRangee(i, 0));
    rangee.forEach((d, idx) => {
      const el = tuileDepuisDict(d);
      // Tuile prise sur le tapis ce tour (déplacement) : pourtour bleu plutôt
      // que vert, pour la distinguer d'une tuile venant réellement de la main
      // ce tour-ci (issue #136).
      el.classList.add(tuilesOrigineTapis.includes(d.id) ? "deplacee-tapis" : "ce-tour");
      if (d.id === tuileSelectionnee) el.classList.add("selectionnee");
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        // Tuile prête (autre que celle-ci) : cliquer une tuile de la rangée
        // insère la tuile sélectionnée AVANT elle (miroir du tapis, issue #27).
        if (tuileSel && d.id !== tuileSelectionnee) insererTuileRangee(i, idx);
        else reprendreTuileRangee(d.id, i);
      });
      cont.appendChild(el);
      // Zone d'insertion après cette tuile (= avant la suivante, ou en fin de
      // rangée pour la dernière — l'ancien clic-sur-rangée reste en secours).
      if (tuileSel) cont.appendChild(zoneInsertionRangee(i, idx + 1));
    });
  });
}

// Crée une zone d'insertion (style .zone-ext-interne, 20px) pour la rangée de
// travail `indexRangee` à la position `pos`. Clic → insère la tuile
// sélectionnée à cette position exacte via splice().
function zoneInsertionRangee(indexRangee, pos) {
  const zi = document.createElement("div");
  zi.className = "zone-ext zone-ext-interne";
  zi.title = "Insérer la tuile sélectionnée ici";
  zi.addEventListener("click", (e) => {
    e.stopPropagation();
    insererTuileRangee(indexRangee, pos);
  });
  return zi;
}

// Réconcilie l'ordre local avec le contenu serveur après une action :
// conserve l'ordre local des tuiles encore présentes, retire celles jouées,
// et ajoute en fin les tuiles nouvellement piochées.
function reconcilierChevalet() {
  const serveur = (etat.joueurs[indexHumain()].chevalet) || [];
  const parId = new Map(serveur.map((d) => [d.id, d]));
  const nouveau = [];
  chevaletLocal.forEach((d) => {
    if (parId.has(d.id)) { nouveau.push(parId.get(d.id)); parId.delete(d.id); }
  });
  parId.forEach((d) => nouveau.push(d)); // tuiles piochées → en fin
  chevaletLocal = nouveau;
}

// Repart de l'ordre serveur (init, annulation, nouvelle manche).
function reinitChevaletLocal() {
  chevaletLocal = clone(etat.joueurs[indexHumain()].chevalet || []);
}

function rafraichirChevalet() {
  const chev = document.getElementById("chevalet");
  chev.innerHTML = "";
  const tuiles = chevaletLocal;
  const drag = modeReorgReglage() === "drag";
  tuiles.forEach((d) => {
    const el = tuileDepuisDict(d);
    if (d.id === tuileSelectionnee) el.classList.add("selectionnee");
    if (reorgSource !== null) {
      // Un échange est en cours : la source est surlignée, les autres sont cibles
      if (d.id === reorgSource) el.classList.add("source-reorg");
      else el.classList.add("cible-reorg");
    }
    if (drag) brancherDragChevalet(el, d);
    else brancherAppuiLongChevalet(el, d);
    chev.appendChild(el);
  });
  for (let i = tuiles.length; i < 14; i++) {
    const vide = document.createElement("div");
    vide.className = "emplacement-vide";
    // En mode glisser-déposer, un emplacement vide accepte une tuile → fin de rangée
    if (drag) brancherDropFin(vide);
    chev.appendChild(vide);
  }
  majHintChevalet();
}

// Indice discret sous le chevalet : rappelle le geste de réorganisation selon
// le mode réglé, et disparaît dès qu'une réorganisation est en cours.
function majHintChevalet() {
  const hint = document.getElementById("chevalet-hint");
  if (!hint) return;
  const drag = modeReorgReglage() === "drag";
  const reorgEnCours = reorgSource !== null || dragSourceId !== null;
  hint.textContent = drag
    ? "Glissez les tuiles pour les réordonner"
    : "Cliquez sur une tuile puis sur sa destination";
  hint.classList.toggle("masque", reorgEnCours);
}

// Mode de réorganisation choisi dans les réglages : "clic" (appui long + clic)
// ou "drag" (glisser-déposer). Repli sur "clic" si non défini.
function modeReorgReglage() {
  return (etat && etat.config && etat.config.mode_reorg) || "clic";
}

// Handler courant du bouton Piocher/Passer fusionné (issue #28). Mémorisé
// pour pouvoir retirer l'ancien écouteur avant d'en ajouter un nouveau.
let handlerBoutonPioche = null;

function rafraichirBoutons() {
  const aPose = tuilesCeTour.length > 0;
  const piocheVide = (etat.pioche || []).length === 0;
  const monTour = estMonTour();
  document.getElementById("btn-annuler").disabled = !aPose;
  document.getElementById("btn-jouer").disabled = !aPose || !monTour;
  // Bouton Piocher/Passer fusionné : devient « Passer » quand la pioche est
  // vide et que c'est mon tour, sinon reste « Piocher » (issue #28).
  const btnPiocher = document.getElementById("btn-piocher");
  const passerMode = piocheVide && monTour;
  const handler = passerMode ? onPasser : onPiocher;
  btnPiocher.textContent = passerMode ? "⏭ Passer" : "⬇ Piocher";
  btnPiocher.disabled = aPose || !monTour;
  // Retirer l'ancien écouteur avant d'ajouter le nouveau pour éviter les doublons.
  if (handlerBoutonPioche) {
    btnPiocher.removeEventListener("click", handlerBoutonPioche);
  }
  btnPiocher.addEventListener("click", handler);
  handlerBoutonPioche = handler;
}

// Active/désactive le bouton de rejeu selon qu'un coup IA est disponible
// (issue #144, remplace l'ancienne liste "Derniers coups").
function rafraichirBoutonRejouerIA() {
  const btn = document.getElementById("btn-rejouer-coup-ia");
  if (!btn) return;
  const coup = etat.dernier_coup_ia;
  btn.disabled = !coup;
  btn.textContent = coup
    ? "▶ Dernier coup joué par " + coup.nom
    : "▶ Dernier coup joué par l'ordinateur";
}

// ------------------------------------------------------------ sélection / placement
function selectionnerTuile(id) {
  tuileSelectionnee = (tuileSelectionnee === id) ? null : id;
  // Toute (dé)sélection remet la cible d'insertion à zéro : le joueur devra
  // (re)cliquer une combinaison pour dérouler ses zones d'insertion (issue #47).
  comboActive = null;
  rafraichirChevalet();
  rafraichirPlateau(); // afficher/masquer les zones d'extension du tapis
  // Afficher/masquer les zones d'insertion internes des rangées de travail
  // (sinon une tuile sélectionnée reste insérable seulement en fin de rangée,
  // issue #127).
  rafraichirZoneTravail();
  majFantome(); // (dé)sélection → crée / détruit le fantôme (issue #50)
}

// -------------------------------------------- réorganisation par appui long
// Un appui maintenu 500 ms sur une tuile du chevalet active le mode réorg pour
// cette tuile (reorgSource) ; un appui court reste une sélection normale.
function brancherAppuiLongChevalet(el, d) {
  el.addEventListener("pointerdown", () => demarrerAppuiLong(d));
  el.addEventListener("pointerup", () => finAppuiLong(d));
  el.addEventListener("pointerleave", annulerAppuiLong);
  el.addEventListener("pointercancel", annulerAppuiLong);
}

function demarrerAppuiLong(d) {
  if (!estMonTour()) return; // pas de réorg hors du tour (issue #96)
  annulerAppuiLong();
  appuiLong.id = d.id;
  appuiLong.declenche = false;
  appuiLong.timer = setTimeout(() => {
    appuiLong.declenche = true;
    // Active (ou désactive si déjà source) la réorg pour cette tuile.
    reorgSource = (reorgSource === d.id) ? null : d.id;
    rafraichirChevalet();
  }, 500);
}

function annulerAppuiLong() {
  if (appuiLong.timer) { clearTimeout(appuiLong.timer); appuiLong.timer = null; }
}

function finAppuiLong(d) {
  const declenche = appuiLong.declenche;
  annulerAppuiLong();
  appuiLong.declenche = false;
  // Appui long déjà traité (réorg activée) : ne pas déclencher le clic normal.
  if (declenche) return;
  onClickTuileChevalet(d);
}

// -------------------------------------------- réorganisation par glisser-déposer
function brancherDragChevalet(el, d) {
  el.draggable = true;
  el.addEventListener("dragstart", (e) => {
    if (!estMonTour()) { e.preventDefault(); return; } // pas de réorg hors tour (issue #96)
    dragSourceId = d.id;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", d.id); } catch (_) {}
    }
    el.classList.add("drag-en-cours");
    majHintChevalet();
  });
  el.addEventListener("dragend", () => {
    dragSourceId = null;
    el.classList.remove("drag-en-cours");
    majHintChevalet();
  });
  el.addEventListener("dragover", (e) => {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    el.classList.add("drag-survol");
  });
  el.addEventListener("dragleave", () => el.classList.remove("drag-survol"));
  el.addEventListener("drop", (e) => {
    e.preventDefault();
    el.classList.remove("drag-survol");
    const src = dragSourceId ||
      (e.dataTransfer ? e.dataTransfer.getData("text/plain") : null);
    deplacerTuileChevalet(src, d.id);
  });
  // Un clic simple (sans glisser) conserve la sélection normale.
  el.addEventListener("click", () => onClickTuileChevalet(d));
}

// Emplacement vide : cible de dépôt qui envoie la tuile glissée en fin de chevalet.
function brancherDropFin(el) {
  el.addEventListener("dragover", (e) => { e.preventDefault(); });
  el.addEventListener("drop", (e) => {
    e.preventDefault();
    const src = dragSourceId ||
      (e.dataTransfer ? e.dataTransfer.getData("text/plain") : null);
    deplacerTuileChevalet(src, null);
  });
}

// Déplace la tuile `idSource` juste avant `idCible` dans chevaletLocal.
// Si `idCible` est null, la tuile est placée en fin de chevalet.
function deplacerTuileChevalet(idSource, idCible) {
  if (!idSource || idSource === idCible) return;
  const iS = chevaletLocal.findIndex((t) => t.id === idSource);
  if (iS < 0) return;
  const [d] = chevaletLocal.splice(iS, 1);
  if (idCible === null) {
    chevaletLocal.push(d);
  } else {
    const iC = chevaletLocal.findIndex((t) => t.id === idCible);
    if (iC < 0) chevaletLocal.push(d);
    else chevaletLocal.splice(iC, 0, d);
  }
  rafraichirChevalet();
}

// Clic sur une tuile du chevalet : échange (réorg en cours) OU sélection pour pose
function onClickTuileChevalet(d) {
  // Hors du tour du joueur humain, aucune sélection/manipulation de tuile n'est
  // permise, comme les boutons d'action déjà désactivés (issue #96).
  if (!estMonTour()) return;
  if (reorgSource !== null) {
    // réorganisation : clic sur une seconde tuile → échange
    if (d.id === reorgSource) { reorgSource = null; rafraichirChevalet(); return; }
    // Échanger les deux tuiles dans le chevalet
    const chev = chevaletLocal;
    const iA = chev.findIndex((t) => t.id === reorgSource);
    const iB = chev.findIndex((t) => t.id === d.id);
    if (iA >= 0 && iB >= 0) [chev[iA], chev[iB]] = [chev[iB], chev[iA]];
    reorgSource = null;
    rafraichirChevalet();
    return;
  }
  // comportement normal : un clic sélectionne, un double-clic pose directement.
  // Détection manuelle du double-clic : le re-rendu du chevalet remplace les
  // éléments DOM à chaque clic, donc l'événement natif « dblclick » n'est pas
  // fiable. On compare l'id de la tuile et l'horodatage du clic précédent.
  const maintenant = Date.now();
  if (dernierClicChevalet.id === d.id &&
      maintenant - dernierClicChevalet.temps < 350) {
    dernierClicChevalet = { id: null, temps: 0 };
    poserTuileDirectement(d);
    return;
  }
  dernierClicChevalet = { id: d.id, temps: maintenant };
  selectionnerTuile(d.id);
}

// Double-clic sur une tuile du chevalet : la placer directement dans la rangée
// active (rangeeActive vaut 0 par défaut si aucune n'a été activée).
function poserTuileDirectement(d) {
  tuileSelectionnee = d.id;
  placerTuileDansRangee(); // gère lui-même le blocage « pas votre tour »
}

function retirerDuChevalet(id) {
  const chev = chevaletLocal;
  const i = chev.findIndex((t) => t.id === id);
  if (i < 0) return null;
  return chev.splice(i, 1)[0];
}

// Depuis l'issue #14, chevaletLocal est un clone distinct du chevalet serveur
// (etat.joueurs[indexHumain()].chevalet). Les deux doivent rester synchronisés
// pendant le tour : sinon le compteur de tuiles de la fiche joueur (qui lit le
// chevalet serveur) se désynchronise. Ces helpers gardent le chevalet serveur
// en phase quand une tuile est déplacée vers/depuis le tapis.
function retirerDuChevaletServeur(id) {
  const chev = etat && etat.joueurs[indexHumain()] &&
    etat.joueurs[indexHumain()].chevalet;
  if (!chev) return;
  const i = chev.findIndex((t) => t.id === id);
  if (i >= 0) chev.splice(i, 1);
}

function rendreAuChevaletServeur(d) {
  const chev = etat && etat.joueurs[indexHumain()] &&
    etat.joueurs[indexHumain()].chevalet;
  if (!chev || !d) return;
  if (!chev.some((t) => t.id === d.id)) chev.push(d);
}

// Retire et retourne une tuile « plaçable » par id, qu'elle soit sur le
// chevalet ou déjà dans une rangée de travail (cas du mode tapis, où une tuile
// prise sur le tapis transite par la zone de travail avant d'être déplacée).
// Retourne { d, source: "chevalet"|"travail" } ou null.
function prelevereTuilePlacable(id) {
  const iC = chevaletLocal.findIndex((t) => t.id === id);
  if (iC >= 0) return { d: chevaletLocal.splice(iC, 1)[0], source: "chevalet" };
  for (let r = 0; r < travail.length; r++) {
    const iT = travail[r].findIndex((t) => t.id === id);
    if (iT >= 0) return { d: travail[r].splice(iT, 1)[0], source: "travail" };
  }
  return null;
}

// ------------------------------------------------------------ zone de travail
// Rendre une rangée active
function activerRangee(index) {
  rangeeActive = index;
  rafraichirZoneTravail();
}

// Placer la tuile sélectionnée du chevalet dans la rangée active
function placerTuileDansRangee() {
  if (tuileSelectionnee === null) return;
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const info = prelevereTuilePlacable(tuileSelectionnee);
  if (!info) return;
  travail[rangeeActive].push(info.d);
  // Une tuile venant du chevalet devient « posée ce tour » ; une tuile déjà
  // en zone de travail (déplacement entre rangées) y figure déjà.
  if (info.source === "chevalet") tuilesCeTour.push(info.d.id);
  tuileSelectionnee = null;
  detruireFantome(); // tuile posée → le fantôme disparaît (issue #50)
  rafraichirZoneTravail();
  rafraichirPlateau(); // masquer les zones d'extension
  rafraichirChevalet();
  rafraichirBoutons();
}

// Insérer la tuile sélectionnée à une position exacte `pos` d'une rangée de
// travail. Miroir de placerTuileDansRangee() mais via splice() : sert les zones
// d'insertion internes et le clic direct sur une tuile de la rangée (issue #31).
function insererTuileRangee(indexRangee, pos) {
  if (tuileSelectionnee === null) return;
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  rangeeActive = indexRangee;
  // Si la tuile sélectionnée est déjà dans CETTE rangée avant `pos` (déplacement
  // interne d'une tuile prise sur le tapis), son retrait décale les index.
  const jSel = travail[indexRangee].findIndex((t) => t.id === tuileSelectionnee);
  const info = prelevereTuilePlacable(tuileSelectionnee);
  if (!info) return;
  const posEff = (jSel >= 0 && jSel < pos) ? pos - 1 : pos;
  travail[indexRangee].splice(posEff, 0, info.d);
  // Une tuile venant du chevalet devient « posée ce tour » ; une tuile déjà en
  // zone de travail (déplacement) y figure déjà.
  if (info.source === "chevalet") tuilesCeTour.push(info.d.id);
  tuileSelectionnee = null;
  detruireFantome(); // tuile posée → le fantôme disparaît (issue #50)
  rafraichirZoneTravail();
  rafraichirPlateau(); // masquer les zones d'extension
  rafraichirChevalet();
  rafraichirBoutons();
}

// Clic sur une tuile d'une rangée.
// - Tuile prise sur le tapis : on la (dé)sélectionne pour pouvoir la déplacer
//   vers une extension du tapis ou une autre rangée (jamais vers le chevalet :
//   elle n'appartient pas au joueur).
// - Tuile du chevalet : retour au chevalet comme auparavant.
function reprendreTuileRangee(id, indexRangee) {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const i = travail[indexRangee].findIndex((t) => t.id === id);
  if (i < 0) return;
  if (tuilesOrigineTapis.includes(id)) {
    tuileSelectionnee = (tuileSelectionnee === id) ? null : id;
    rafraichirZoneTravail();
    rafraichirPlateau();
    rafraichirChevalet();
    majFantome(); // (dé)sélection d'une tuile du tapis (issue #50)
    return;
  }
  const d = travail[indexRangee].splice(i, 1)[0];
  chevaletLocal.push(d);
  rendreAuChevaletServeur(d); // symétrie avec etendreTapis/insererTuileTapis (#138)
  tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Placer les tuiles d'une zone de pose sur le tapis, SANS valider le tour
// (issue #128) : elles rejoignent plateauLocal comme une nouvelle combinaison,
// visuellement distinguée par leur pourtour coloré (classe "ce-tour", déjà
// posée par tuilesCeTour) et dès lors réarrangeables avec le mécanisme du
// tapis — y compris en les combinant avec d'autres tuiles du tour en cours.
// Rien n'est envoyé au serveur ici : seul « Jouer » valide définitivement.
function placerRangee(index) {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const tuiles = travail[index];
  if (tuiles.length === 0) return;
  plateauLocal.push(tuiles);
  travail[index] = [];
  // La tuile sélectionnée, si elle vient de cette rangée, n'existe plus en
  // zone de pose (elle est désormais sur le tapis) : désélectionner.
  if (tuiles.some((t) => t.id === tuileSelectionnee)) tuileSelectionnee = null;
  comboActive = null;
  trouJoker = null;
  detruireFantome();
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Vider une rangée → retour des tuiles au chevalet. Les tuiles prises sur le
// tapis n'appartiennent pas au joueur : elles restent dans la rangée (seul
// « Annuler » remet le tapis dans son état de début de tour).
function viderRangee(index) {
  const restants = [];
  travail[index].forEach((d) => {
    if (tuilesOrigineTapis.includes(d.id)) {
      restants.push(d);
    } else {
      chevaletLocal.push(d);
      tuilesCeTour = tuilesCeTour.filter((id) => id !== d.id);
    }
  });
  travail[index] = restants;
  if (restants.length > 0 && tuileSelectionnee === null) {
    toast("Tuiles du tapis : utilisez « Annuler » pour tout remettre");
  }
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// ------------------------------------------------------------ extension du tapis
// Ajouter la tuile sélectionnée à l'extrémité d'une combinaison du tapis
function etendreTapis(idxCombo, position) {
  if (tuileSelectionnee === null) return;
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const info = prelevereTuilePlacable(tuileSelectionnee);
  if (!info) return;
  const d = info.d;
  if (info.source === "chevalet") {
    // Retirer la tuile des DEUX vues du chevalet (locale + serveur) pour éviter
    // la désynchronisation introduite à l'issue #14.
    retirerDuChevaletServeur(d.id);
    tuilesCeTour.push(d.id);
  }
  // (source "travail" : la tuile figure déjà dans tuilesCeTour)
  if (position === "fin") plateauLocal[idxCombo].push(d);
  else plateauLocal[idxCombo].unshift(d);
  tuileSelectionnee = null;
  detruireFantome(); // tuile posée → le fantôme disparaît (issue #50)
  comboActive = null; // retour au rendu normal du tapis (issue #47)
  trouJoker = null; // le guidage a rempli son rôle
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Insérer la tuile sélectionnée à une position exacte `pos` d'une combinaison
// du tapis. Miroir de etendreTapis() mais via splice() : sert les zones
// d'insertion internes et le clic direct sur une tuile en mode tapis.
function insererTuileTapis(idxCombo, pos) {
  if (tuileSelectionnee === null) return;
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const combo = plateauLocal[idxCombo];
  if (!combo) return;
  const info = prelevereTuilePlacable(tuileSelectionnee);
  if (!info) return;
  const d = info.d;
  if (info.source === "chevalet") {
    // Symétrie avec etendreTapis : retirer des deux vues du chevalet.
    retirerDuChevaletServeur(d.id);
    tuilesCeTour.push(d.id);
  }
  // (source "travail" : la tuile figure déjà dans tuilesCeTour)
  combo.splice(pos, 0, d);
  tuileSelectionnee = null;
  detruireFantome(); // tuile posée → le fantôme disparaît (issue #50)
  comboActive = null; // insertion faite → retour au rendu normal (issue #47)
  trouJoker = null; // le trou (le cas échéant) est comblé
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Reprendre une tuile ajoutée ce tour sur le tapis.
// - Tuile du chevalet posée sur le tapis → retour au chevalet.
// - Tuile prise sur le tapis (mode manipulation) → retour en zone de travail
//   et sélectionnée, prête à être redéplacée (jamais renvoyée au chevalet).
function reprendreTuile(id) {
  for (let ic = 0; ic < plateauLocal.length; ic++) {
    const combo = plateauLocal[ic];
    const i = combo.findIndex((t) => t.id === id);
    if (i < 0) continue;
    const d = combo.splice(i, 1)[0];
    if (tuilesOrigineTapis.includes(id)) {
      travail[rangeeActive].push(d);
      tuileSelectionnee = d.id;
    } else {
      chevaletLocal.push(d);
      rendreAuChevaletServeur(d); // symétrie avec etendreTapis
      tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
    }
    if (combo.length === 0) plateauLocal.splice(ic, 1);
    break;
  }
  rafraichirPlateau(); rafraichirZoneTravail(); rafraichirChevalet(); rafraichirBoutons();
  majFantome(); // la tuile reprise du tapis peut redevenir sélectionnée (issue #50)
}

// ------------------------------------------------------------ manipulation du tapis
// Prendre une tuile à l'intérieur d'une combinaison du tapis : elle quitte
// plateauLocal, entre dans tuilesCeTour, atterrit dans la rangée de travail
// active et devient sélectionnée (pour la déplacer aussitôt vers une extension
// du tapis si voulu, ou la rendre à la main si elle en vient — issue #138).
// La combinaison source vidée est retirée ; réduite à moins de 3 tuiles, elle
// reste affichée en rouge (voir rafraichirPlateau).
function prendreTuileTapis(idxCombo, idxTuile) {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const combo = plateauLocal[idxCombo];
  if (!combo) return;
  const d = combo[idxTuile];
  if (!d) return;
  // Une tuile déjà posée ce tour depuis la main (ex. placée sur le tapis puis
  // redéplacée au sein du tapis ce même tour) garde son origine « main » : si
  // on ne la reconnaît pas ici, elle serait marquée à tort « origine tapis »
  // et ne pourrait plus repartir en main sans « Annuler » tout le tour (#138).
  const venaitDeLaMain = tuilesCeTour.includes(d.id) &&
                         !tuilesOrigineTapis.includes(d.id);
  combo.splice(idxTuile, 1);
  if (!tuilesCeTour.includes(d.id)) tuilesCeTour.push(d.id);
  if (!venaitDeLaMain && !tuilesOrigineTapis.includes(d.id)) {
    tuilesOrigineTapis.push(d.id);
  }
  travail[rangeeActive].push(d);
  tuileSelectionnee = d.id;
  // Un joker retiré laisse un trou à mettre en évidence (guidage pour placer la
  // tuile de remplacement) ; toute autre prise efface un éventuel guidage.
  trouJoker = (d.est_joker && combo.length > 0) ? { combo, pos: idxTuile } : null;
  if (combo.length === 0) plateauLocal.splice(idxCombo, 1);
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
  majFantome(); // la tuile prise sur le tapis devient sélectionnée (issue #50)
}

// Fin d'un double-clic sur une tuile du tapis (issue #133) : le premier clic
// l'a déjà prise et déposée dans la zone de travail active via
// prendreTuileTapis (même résultat que poserTuileDirectement pour le
// chevalet). Le second clic du geste ne retombe plus sur la tuile d'origine
// (elle a quitté le DOM) mais sur sa combinaison source ; il ne doit donc pas
// la recibler comme destination, seulement nettoyer la sélection en attente
// (fantôme, cible d'insertion) pour terminer le geste en une seule interaction.
function finaliserSelectionTapis() {
  tuileSelectionnee = null;
  comboActive = null;
  trouJoker = null;
  detruireFantome();
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// ------------------------------------------------------------ récupération de joker
// Détermine la valeur/couleur que le joker représente dans sa combinaison.
// Retourne { valeur, couleur, type } ou null si indéterminable.
function valeurJokerDansCombo(combo, idxJoker) {
  const reelles = combo.filter((d) => !d.est_joker);
  if (reelles.length === 0) return null;

  const couleursUniques = [...new Set(reelles.map((d) => d.couleur))];

  if (couleursUniques.length === 1) {
    // Suite : même couleur, valeurs consécutives.
    // La valeur du joker = sa position dans la séquence depuis le 1er réel.
    const premiereReelle = combo.find((d) => !d.est_joker);
    const idxPremiere = combo.indexOf(premiereReelle);
    const base = premiereReelle.valeur - idxPremiere;
    return {
      valeur: base + idxJoker,
      couleur: couleursUniques[0],
      type: "suite",
    };
  } else {
    // Groupe : même valeur, couleurs différentes.
    const valeur = reelles[0].valeur;
    const couleursPresentes = reelles.map((d) => d.couleur);
    const toutesColors = ["rouge", "bleu", "jaune", "noir"];
    const couleurManquante = toutesColors.find(
      (c) => !couleursPresentes.includes(c)) || null;
    return {
      valeur: valeur,
      couleur: couleurManquante,
      couleursPresentes: couleursPresentes,
      type: "groupe",
    };
  }
}

function peutRemplacerJoker(tuileSel, infoJoker) {
  if (!infoJoker) return false;
  if (tuileSel.valeur !== infoJoker.valeur) return false;
  if (infoJoker.type === "suite" && tuileSel.couleur !== infoJoker.couleur)
    return false;
  // Un joker ne peut pas en remplacer un autre (les jokers ont désormais une
  // couleur réelle : on teste est_joker, plus l'absence de couleur).
  if (infoJoker.type === "groupe" && tuileSel.est_joker)
    return false;
  // Groupe : refuser si la couleur proposée est déjà présente ailleurs dans
  // le groupe (sinon le remplacement créerait un doublon de couleur, #142).
  if (
    infoJoker.type === "groupe" &&
    infoJoker.couleursPresentes.includes(tuileSel.couleur)
  )
    return false;
  return true;
}

// Tenter de récupérer un joker du tapis en le remplaçant par la tuile sélectionnée.
function tenterRecupererJoker(idxCombo, idxTuile, dictJoker) {
  if (!tuileSelectionnee) return;
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }

  const chev = chevaletLocal;
  const idxSel = chev.findIndex((t) => t.id === tuileSelectionnee);
  if (idxSel < 0) return;
  const tuileSel = chev[idxSel];

  const infoJoker = valeurJokerDansCombo(plateauLocal[idxCombo], idxTuile);
  if (!peutRemplacerJoker(tuileSel, infoJoker)) {
    toast("Cette tuile ne peut pas remplacer ce joker", "erreur");
    return;
  }

  // 1. Retirer la tuile du chevalet
  chev.splice(idxSel, 1);

  // 2. Remplacer le joker par la tuile dans plateauLocal
  plateauLocal[idxCombo][idxTuile] = tuileSel;

  // 3. La tuile compte comme jouée ce tour
  tuilesCeTour.push(tuileSel.id);

  // 4. Le joker atterrit dans la rangée active, marqué comme venant du tapis
  // (même traitement qu'une tuile prise directement dessus, issue #137).
  travail[rangeeActive].push(dictJoker);
  tuilesOrigineTapis.push(dictJoker.id);

  // 5. Le joker aussi compte comme joué (il DOIT être rejoué)
  tuilesCeTour.push(dictJoker.id);

  // 6. Le joker libéré devient la tuile sélectionnée, attaché au curseur comme
  // s'il venait d'être pris sur le tapis, prêt à être replacé ailleurs (#137).
  tuileSelectionnee = dictJoker.id;

  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
  majFantome(); // le joker libéré suit le curseur (issue #50 / #137)
  toast("Joker récupéré — placez-le dans votre zone de pose");
}

function reinitTour() {
  tuilesCeTour = [];
  tuilesOrigineTapis = [];
  combosInvalidesSignatures = [];
  tuileSelectionnee = null;
  detruireFantome(); // pas de fantôme résiduel entre les tours (issue #50)
  comboActive = null;
  trouJoker = null;
  plateauLocal = clone(etat.plateau || []);
  travail = [[], []];
  rangeeActive = 0;
  const rc = document.getElementById("resultat-calcul");
  if (rc) { rc.textContent = ""; rc.className = ""; }
}

// ------------------------------------------------------------ actions serveur
async function onAnnuler() {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  try {
    const res = await window.pywebview.api.jeu_annuler();
    if (res && res.etat) etat = res.etat;
  } catch (e) { /* annulation purement locale en repli */ }
  reinitChevaletLocal(); // seul cas où on repart de l'ordre serveur
  reinitTour();
  rafraichirTout();
}

async function onVerifierCalc() {
  const zone = document.getElementById("resultat-calcul");
  const rangeesPosees = travail.filter((r) => r.length > 0);
  const plateauComplet = [...plateauLocal, ...rangeesPosees];
  try {
    const res = await window.pywebview.api.jeu_verifier_plateau(plateauComplet);
    // Surligne en rouge, directement sur le tapis/zones de pose, la ou les
    // combinaisons fautives (issue #136) — remplacé à chaque nouveau contrôle.
    combosInvalidesSignatures = (res.combos_invalides || []).map((ids) => ids.join("|"));
    if (res.valide) {
      zone.className = "ok";
      zone.textContent = "✓ Plateau valide — " + res.points_total + " points";
    } else {
      zone.className = "ko";
      zone.textContent = "✗ " + (res.erreurs || []).join(" ; ");
    }
    rafraichirPlateau();
    rafraichirZoneTravail();
  } catch (e) {
    zone.className = "ko";
    zone.textContent = "Erreur : " + e;
  }
}

async function onJouer() {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const rangeesPosees = travail.filter((r) => r.length > 0);
  const nouveauPlateau = [...plateauLocal, ...rangeesPosees];
  try {
    const res = await window.pywebview.api.jeu_jouer_coup({
      ids_tuiles: tuilesCeTour,
      nouveau_plateau: nouveauPlateau,
    });
    if (res && res.ok) {
      etat = res.etat;
      reconcilierChevalet();
      reinitTour();
      rafraichirTout();
      autoZoomSiTapisDeborde(); // issue #104 : dézoome d'un cran si le tapis déborde
      toast("Coup joué", "succes");
    } else {
      toast((res && res.erreur) || "Coup invalide", "erreur");
      // Surligne en rouge la ou les combinaisons fautives signalées par le
      // serveur, directement sur le tapis/zones de pose (issue #136).
      combosInvalidesSignatures = (res && res.combos_invalides || []).map((ids) => ids.join("|"));
      rafraichirPlateau();
      rafraichirZoneTravail();
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// Affiche la tuile piochée en grand au centre de l'écran (~1 s), puis l'anime
// en la rétrécissant et la glissant vers le bas en direction du chevalet.
// À la fin, l'overlay est retiré et le callback `apres` est appelé (il se
// charge d'afficher la tuile dans le chevalet). Repli immédiat si `dict` est
// absent (on ne bloque jamais le déroulement du tour).
function animerPiochee(dict, apres) {
  if (!dict) { apres(); return; }

  const overlay = document.createElement("div");
  overlay.id = "overlay-pioche";

  const el = tuileDepuisDict(dict);
  el.classList.add("tuile-piochee-grande");
  overlay.appendChild(el);
  document.body.appendChild(overlay);

  // Phase 1 : tuile grande et centrée pendant 1 s.
  setTimeout(() => {
    // Phase 2 : glissement/rétrécissement vers le chevalet (transition CSS 500 ms).
    el.classList.add("vers-chevalet");
    setTimeout(() => {
      overlay.remove();
      apres();
    }, 500);
  }, 1000);
}

// Variante de animerPiochee() pour un joueur IA (issue #145) : la tuile est
// montrée dos visible (valeur non révélée) et glisse du centre de l'écran
// vers la fiche du joueur IA concerné (position calculée dynamiquement,
// car elle dépend du nombre de joueurs et de la mise en page).
function animerPiocheeIA(idxIA, apres) {
  const overlay = document.createElement("div");
  overlay.id = "overlay-pioche";

  const el = creerTuileDos();
  el.classList.add("tuile-piochee-grande");
  overlay.appendChild(el);
  document.body.appendChild(overlay);

  const fiche = document.querySelectorAll(".fiche-joueur")[idxIA];
  let dx = 0, dy = -42 * window.innerHeight / 100; // repli : vers le haut
  if (fiche) {
    const rFiche = fiche.getBoundingClientRect();
    dx = rFiche.left + rFiche.width / 2 - window.innerWidth / 2;
    dy = rFiche.top + rFiche.height / 2 - window.innerHeight / 2;
  }
  el.style.setProperty("--dx", dx + "px");
  el.style.setProperty("--dy", dy + "px");

  setTimeout(() => {
    el.classList.add("vers-ia");
    setTimeout(() => {
      overlay.remove();
      apres();
    }, 500);
  }, 1000);
}

async function onPiocher() {
  // Garde client en plus du bouton désactivé (#146) : un clic en vol juste
  // avant que rafraichirBoutons() ne désactive le bouton (ex. la fenêtre de
  // latence avant le coup auto de l'IA) ne doit rien déclencher — le serveur
  // refuse de toute façon l'action hors tour, mais autant l'éviter ici aussi.
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  try {
    const res = await window.pywebview.api.jeu_piocher();
    if (res && res.ok) {
      etat = res.etat;
      const t = (res.tuiles_piochees || [])[0];
      reconcilierChevalet();
      if (triAutoActif && t) insererTrie(t);
      reinitTour();
      // Rafraîchir tout SAUF le chevalet : la tuile piochée n'y apparaît
      // qu'à la fin de l'animation (elle est d'abord montrée en grand).
      rafraichirFichesJoueurs();
      rafraichirPlateau();
      rafraichirZoneTravail();
      rafraichirBoutons();
      rafraichirBoutonRejouerIA();
      mettreAJourSac((etat.pioche || []).length);
      animerPiochee(t, () => {
        rafraichirChevalet();
        if (etat.manche_terminee) afficherFinDeManche();
        verifierAutoIA();
      });
    } else {
      toast((res && res.erreur) || "Impossible de piocher", "erreur");
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

async function onPasser() {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  try {
    const res = await window.pywebview.api.jeu_passer();
    if (res && res.ok) {
      etat = res.etat;
      reconcilierChevalet();
      reinitTour();
      rafraichirTout();
    } else {
      toast((res && res.erreur) || "Impossible de passer", "erreur");
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// ------------------------------------------------------------ IA (déclenchée par l'humain)
// Vitesse d'animation selon le réglage « Vitesse de l'ordinateur ».
const VITESSES_IA = {
  "Instantanée": { reflexion: 0,    tuile: 100 },
  "Rapide":      { reflexion: 400,  tuile: 400 },
  "Normale":     { reflexion: 800,  tuile: 700 },
  "Lente":       { reflexion: 1500, tuile: 1200 },
};
function vitesseIA() {
  return VITESSES_IA[(etat.config && etat.config.vitesse_ia) || "Normale"]
    || VITESSES_IA["Normale"];
}

// Compare l'ancien et le nouveau plateau et retourne les tuiles nouvellement
// posées par l'IA, dans l'ordre de pose (pour l'animation une par une).
function trouverTuilesAjoutees(ancienPlateau, nouveauPlateau) {
  const idsAncien = new Set(
    (ancienPlateau || []).flatMap(combo => combo.map(d => d.id))
  );
  const ajoutees = [];
  (nouveauPlateau || []).forEach((combo, idxCombo) => {
    combo.forEach((d, idxTuile) => {
      if (!idsAncien.has(d.id)) {
        ajoutees.push({ dict: d, idxCombo, idxTuile });
      }
    });
  });
  return ajoutees;
}

// Compare l'ancien et le nouveau plateau et retourne les tuiles déjà posées
// (présentes dans l'ancien plateau) qui ont rejoint une combinaison
// différente — cas du réarrangement par l'IA (ex. _coup_scission, qui
// détache une tuile d'une suite pour former un groupe). Pour chaque
// combinaison de l'ancien plateau, ses tuiles sont regroupées selon la
// combinaison du nouveau plateau où elles se retrouvent ; le groupe
// d'arrivée majoritaire est considéré comme la « continuation » de la
// combinaison (une simple extension ou une scission qui raccourcit une
// combinaison sans la vider reste ainsi sa propre continuation), les tuiles
// parties dans un autre groupe d'arrivée sont, elles, comptées comme
// déplacées. Une approche par simple différence de voisinage compterait à
// tort les tuiles restées groupées (ex. le reste d'une suite scindée) comme
// déplacées dès qu'une seule tuile quitte leur combinaison (issue #149).
function trouverTuilesDeplacees(ancienPlateau, nouveauPlateau) {
  const comboApresParId = new Map();
  (nouveauPlateau || []).forEach((combo, idxCombo) => {
    combo.forEach((d, idxTuile) => {
      comboApresParId.set(d.id, { dict: d, idxCombo, idxTuile });
    });
  });

  const idsDeplaces = new Set();
  (ancienPlateau || []).forEach(comboAvant => {
    const parCible = new Map();
    comboAvant.map(d => d.id).forEach(id => {
      const info = comboApresParId.get(id);
      if (!info) return; // ne devrait pas arriver : une tuile posée n'est jamais retirée du plateau
      if (!parCible.has(info.idxCombo)) parCible.set(info.idxCombo, []);
      parCible.get(info.idxCombo).push(id);
    });
    if (parCible.size <= 1) return; // toutes les tuiles sont restées ensemble

    let cibleContinuation = null, max = -1;
    parCible.forEach((ids, cible) => {
      if (ids.length > max) { max = ids.length; cibleContinuation = cible; }
    });
    parCible.forEach((ids, cible) => {
      if (cible !== cibleContinuation) ids.forEach(id => idsDeplaces.add(id));
    });
  });

  return [...idsDeplaces].map(id => comboApresParId.get(id));
}

// Anime sur le tapis, dans l'ordre : d'abord les tuiles déjà posées qui
// changent de combinaison (`tuilesDeplacees`, surbrillance bleue — cas d'un
// réarrangement comme _coup_scission), puis les tuiles neuves venues de la
// main (`tuiAjoutees`, surbrillance dorée), une par une au rythme
// `delaiEntreTuiles`. Part de `plateauAvant` (état initial, donc les tuiles
// déplacées encore dans leur ancienne combinaison) et converge vers
// `plateauApres`. Utilisé pour le coup IA en direct (jouerIA) et pour son
// rejeu à la demande (issue #144 ; réarrangement + rythme : issue #149).
async function animerPoseTuiles(tuiAjoutees, tuilesDeplacees, plateauAvant, plateauApres, delaiEntreTuiles) {
  const etapes = [
    ...tuilesDeplacees.map(t => ({ ...t, deplacee: true })),
    ...tuiAjoutees.map(t => ({ ...t, deplacee: false })),
  ];
  const idsAReveler = new Set(etapes.map(e => e.dict.id));
  const idsRevelees = new Set();

  // Rythme : un coup à plusieurs tuiles défile trop vite pour être bien suivi
  // visuellement — on ralentit le délai entre chaque tuile dès qu'il y en a
  // plus de 3 à animer (issue #149).
  const delaiEffectif = etapes.length > 3
    ? Math.round(delaiEntreTuiles * 1.4)
    : delaiEntreTuiles;

  plateauLocal = clone(plateauAvant || []).filter(c => c.length > 0);
  rafraichirPlateau();

  for (let i = 0; i < etapes.length; i++) {
    await new Promise(r =>
      setTimeout(r, i === 0 ? 200 : delaiEffectif));
    idsRevelees.add(etapes[i].dict.id);

    // Reconstruire progressivement le plateau visible à partir du plateau
    // final : tuiles non concernées par l'animation + tuiles déjà révélées.
    plateauLocal = (plateauApres || []).map(combo =>
      combo.filter(d => !idsAReveler.has(d.id) || idsRevelees.has(d.id))
    ).filter(c => c.length > 0);

    rafraichirPlateau();

    const { dict } = etapes[i];
    const classeApparition = etapes[i].deplacee ? "tuile-ia-deplacee" : "tuile-ia-posee";
    // Appliquer l'animation sur la tuile qui vient d'apparaître / de bouger
    setTimeout(() => {
      document.querySelectorAll("#zone-plateau .tuile-jeu").forEach(el => {
        if (el.dataset.id === dict.id) {
          el.classList.add(classeApparition);
          setTimeout(() => {
            el.classList.remove(classeApparition);
            el.classList.add("tuile-ia-highlight");
          }, 700);
        }
      });
    }, 50);
  }

  // Attendre la fin de la dernière animation
  await new Promise(r => setTimeout(r, 800));
}

// Efface les surbrillances dorées laissées par animerPoseTuiles.
function effacerSurbrillanceIA() {
  setTimeout(() => {
    document.querySelectorAll(".tuile-ia-highlight").forEach(el => {
      el.classList.remove("tuile-ia-highlight");
    });
  }, 2000);
}

// L'humain clique « Jouer » sur la fiche de l'IA active pour déclencher son coup.
// Les tuiles posées par l'IA apparaissent une par une avec une animation lente
// et visible (jeu destiné à des personnes âgées).
async function jouerIA() {
  const btnIA = document.querySelector(".btn-jouer-ia");
  if (btnIA) btnIA.disabled = true;

  const vitesse = vitesseIA();
  const delaiReflexion     = vitesse.reflexion;
  const DELAI_ENTRE_TUILES = vitesse.tuile;

  // Index de l'IA qui joue (avant que l'état ne soit écrasé)
  const idxIA = etat.index_joueur_actuel;

  // Mettre la fiche IA en mode « réfléchit… »
  const ficheActive = document.querySelectorAll(".fiche-joueur")[idxIA];
  if (ficheActive) {
    ficheActive.classList.add("ia-reflechit", "ia-joue");
    const meta = ficheActive.querySelector(".meta-fiche");
    if (meta) meta.textContent = "réfléchit";
  }

  try {
    // Lancer la requête ET le délai de « réflexion » en parallèle : le jeu
    // paraît plus naturel même si le serveur répond instantanément.
    const [res] = await Promise.all([
      window.pywebview.api.jeu_ia_jouer(),
      new Promise(r => setTimeout(r, delaiReflexion))
    ]);

    if (!res || !res.ok || !res.etat) {
      toast((res && res.erreur) || "Tour IA impossible", "erreur");
      if (ficheActive) ficheActive.classList.remove("ia-reflechit", "ia-joue");
      rafraichirTout();
      return;
    }

    // Calculer les tuiles ajoutées / déplacées AVANT de mettre à jour l'état
    const ancienPlateau   = clone(etat.plateau || []);
    const nouvelEtat      = res.etat;
    const tuiAjoutees     = trouverTuilesAjoutees(
      ancienPlateau, nouvelEtat.plateau || []);
    const tuilesDeplacees = trouverTuilesDeplacees(
      ancienPlateau, nouvelEtat.plateau || []);

    // Mettre à jour l'état (mais on reconstruit le plateau visible à la main)
    etat = nouvelEtat;
    reconcilierChevalet(); // le tour d'une IA ne change pas l'ordre du chevalet humain
    reinitTour();

    // Cas « pioche » ou « passe » : aucune tuile ajoutée ni déplacée
    if (tuiAjoutees.length === 0 && tuilesDeplacees.length === 0) {
      rafraichirFichesJoueurs();
      mettreAJourSac((etat.pioche || []).length);
      const h = nouvelEtat.historique || [];
      const action = (h.length ? h[h.length - 1].description : "") || "";
      const nomIA = (nouvelEtat.joueurs[idxIA] || {}).nom || "L'IA";
      const estPioche = action.includes("pioch");
      toast(nomIA + " " + (estPioche ? "pioche" : "passe son tour"));
      if (estPioche) {
        await new Promise((r) => animerPiocheeIA(idxIA, r));
      } else {
        await new Promise(r => setTimeout(r, 800));
      }
      rafraichirTout();
      return;
    }

    rafraichirFichesJoueurs();
    rafraichirChevalet();
    rafraichirBoutons();
    rafraichirBoutonRejouerIA();
    mettreAJourSac((etat.pioche || []).length);

    await animerPoseTuiles(
      tuiAjoutees, tuilesDeplacees,
      ancienPlateau, clone(etat.plateau || []), DELAI_ENTRE_TUILES);

    // Finaliser : plateau complet + rafraîchissement normal
    plateauLocal = clone(etat.plateau || []);
    rafraichirPlateau();
    rafraichirTout();
    autoZoomSiTapisDeborde(); // issue #104 : dézoome d'un cran si le tapis déborde

    effacerSurbrillanceIA();

  } catch (e) {
    toast("Erreur IA : " + e, "erreur");
    rafraichirTout();
  }
}

// Modale stylée (remplace confirm() natif, issue #147) demandant de
// confirmer la remise en main des tuiles non validées du tour en cours
// avant de rejouer le dernier coup de l'IA. Résout true/false selon le
// bouton cliqué.
function confirmerRejeuIA(nomIA) {
  return new Promise((resolve) => {
    const overlay = document.getElementById("overlay-confirm-rejeu");
    document.getElementById("titre-confirm-rejeu").textContent =
      "Dernier coup de " + nomIA;
    const btnOui = document.getElementById("btn-confirm-rejeu-oui");
    const btnNon = document.getElementById("btn-confirm-rejeu-non");
    const conclure = (val) => {
      overlay.className = "overlay-cache";
      btnOui.removeEventListener("click", surOui);
      btnNon.removeEventListener("click", surNon);
      resolve(val);
    };
    const surOui = () => conclure(true);
    const surNon = () => conclure(false);
    btnOui.addEventListener("click", surOui);
    btnNon.addEventListener("click", surNon);
    overlay.className = "overlay-visible";
  });
}

// Bouton « Dernier coup joué par l'ordinateur » : rejoue à la demande
// l'animation du dernier coup de pose de l'IA, sans rien changer à l'état de
// la partie. Si le tour en cours d'Alain a déjà des tuiles posées sur le
// tapis (non validées), elles doivent d'abord retourner dans sa main pour
// ne pas brouiller le rejeu — on prévient donc avant de les y remettre
// (issue #144, modale stylée en #147).
async function rejouerDernierCoupIA() {
  const coup = etat.dernier_coup_ia;
  if (!coup) return;

  if (tuilesCeTour.length > 0) {
    const ok = await confirmerRejeuIA(coup.nom);
    if (!ok) return;
    await onAnnuler(); // remet les tuiles du tour en cours dans la main
  }

  const tuiAjoutees = trouverTuilesAjoutees(
    coup.plateau_avant, coup.plateau_apres);
  const tuilesDeplacees = trouverTuilesDeplacees(
    coup.plateau_avant, coup.plateau_apres);
  if (tuiAjoutees.length === 0 && tuilesDeplacees.length === 0) return;

  const btn = document.getElementById("btn-rejouer-coup-ia");
  if (btn) btn.disabled = true;

  await animerPoseTuiles(
    tuiAjoutees, tuilesDeplacees,
    coup.plateau_avant, coup.plateau_apres, vitesseIA().tuile);

  plateauLocal = clone(etat.plateau || []);
  rafraichirPlateau();
  if (btn) btn.disabled = false;
  effacerSurbrillanceIA();
}

// ------------------------------------------------------------ fin de manche
// Dispatcher appelé à chaque fin de manche : si c'est aussi la dernière
// manche de la partie, le message de fin de manche serait redondant avec le
// classement final qui affiche le même résultat — on saute donc directement
// à ce dernier (issue #141). Sinon, overlay intermédiaire classique.
function afficherFinDeManche() {
  if (etat.terminee) {
    afficherClassementFinal();
  } else {
    afficherFinManche();
  }
}

// Overlay récapitulatif de la manche (non-finale) : score_manche + score_cumul
// de chaque joueur, gagnant mis en avant, bouton « Manche suivante ».
function afficherFinManche() {
  const overlay = document.getElementById("overlay-fin");
  const gi = etat.gagnant_manche_index;
  const gagnant = (gi != null && etat.joueurs[gi]) ? etat.joueurs[gi].nom : "—";
  document.getElementById("titre-fin").textContent = "🏆 " + gagnant + " remporte la manche";

  const table = document.getElementById("tableau-scores");
  let html = "<tr><th>Joueur</th><th>Manche</th><th>Total</th></tr>";
  etat.joueurs.forEach((j, i) => {
    const cls = (i === gi) ? " class='gagnant'" : "";
    html += "<tr" + cls + "><td>" + j.nom + "</td><td>" +
      (j.score_manche >= 0 ? "+" : "") + (j.score_manche || 0) + "</td><td>" +
      (j.score_cumul || 0) + "</td></tr>";
  });
  table.innerHTML = html;

  overlay.className = "overlay-visible";
}

// Overlay de classement final : joueurs classés par score_cumul décroissant,
// accompagné d'une animation de feu d'artifice (issue #141).
function afficherClassementFinal() {
  const overlay = document.getElementById("overlay-classement");
  const classement = etat.joueurs
    .map((j) => ({ nom: j.nom, score: j.score_cumul || 0 }))
    .sort((a, b) => b.score - a.score);

  const gagnant = classement.length ? classement[0].nom : "—";
  document.getElementById("titre-classement").textContent =
    "🏁 " + gagnant + " remporte la partie !";

  const table = document.getElementById("tableau-classement");
  let html = "<tr><th>Rang</th><th>Joueur</th><th>Score total</th></tr>";
  const MEDAILLES = ["🥇", "🥈", "🥉"];
  classement.forEach((j, rang) => {
    const cls = (rang === 0) ? " class='gagnant'" : "";
    const medaille = MEDAILLES[rang] ? MEDAILLES[rang] + " " : "";
    html += "<tr" + cls + "><td>" + medaille + (rang + 1) + "</td><td>" +
      j.nom + "</td><td>" + j.score + "</td></tr>";
  });
  table.innerHTML = html;
  lancerFeuArtifice();
  overlay.className = "overlay-visible";
}

// Génère les particules du feu d'artifice affiché derrière la carte du
// classement final : plusieurs bouquets, chacun formé de particules qui
// jaillissent du centre du bouquet dans des directions aléatoires (CSS pour
// le mouvement, JS seulement pour randomiser position/couleur/délai).
function lancerFeuArtifice() {
  const zone = document.getElementById("feu-artifice");
  if (!zone) return;
  const COULEURS_FEU = ["#fde047", "#f87171", "#60a5fa", "#4ade80", "#f472b6", "#fb923c"];
  const BOUQUETS = [{ x: 18, y: 28 }, { x: 82, y: 22 }, { x: 50, y: 60 }, { x: 15, y: 70 }, { x: 85, y: 68 }];
  let html = "";
  BOUQUETS.forEach((bouquet, ib) => {
    const delaiBouquet = ib * 0.35;
    for (let i = 0; i < 14; i++) {
      const angle = (360 / 14) * i;
      const distance = 50 + (i % 3) * 15;
      const couleur = COULEURS_FEU[(ib + i) % COULEURS_FEU.length];
      html += `<span class="particule-feu" style="--fx:${bouquet.x}%; --fy:${bouquet.y}%; ` +
        `--angle:${angle}deg; --distance:${distance}px; --couleur:${couleur}; ` +
        `--delai:${delaiBouquet}s;"></span>`;
    }
  });
  zone.innerHTML = html;
}

async function onNouvelleManche() {
  try {
    const res = await window.pywebview.api.jeu_nouvelle_manche();
    if (res && res.ok) {
      etat = res.etat;
      reinitChevaletLocal(); // nouvelle donne → ordre serveur
      reinitTour();
      document.getElementById("overlay-fin").className = "overlay-cache";
      rafraichirTout();
    } else {
      toast((res && res.erreur) || "Indisponible", "erreur");
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

async function onRetourAccueil() {
  try { await window.pywebview.api.jeu_retour_accueil(); }
  catch (e) { toast("Erreur : " + e, "erreur"); }
}

// ------------------------------------------------------------ tri du chevalet
// Ordre de référence : couleur puis valeur croissante, jokers en fin
// (partagé par le bouton "Trier" et l'insertion automatique à la pioché).
function comparerTuiles(a, b) {
  if (a.est_joker) return 1;
  if (b.est_joker) return -1;
  const ca = COULEURS_ORDRE[a.couleur] ?? 9;
  const cb = COULEURS_ORDRE[b.couleur] ?? 9;
  if (ca !== cb) return ca - cb;
  return (a.valeur || 0) - (b.valeur || 0);
}

function trierChevalet() {
  chevaletLocal.sort(comparerTuiles);
  rafraichirChevalet();
}

// Insère `tuile` dans chevaletLocal à sa place triée (issue #126, case "Tri
// automatique"). Le chevalet n'étant pas forcément déjà trié (distribution
// initiale aléatoire, réorg manuelle), une simple recherche de position
// linéaire ne garantit pas que la tuile finisse à sa VRAIE place triée
// globale (issue #130) : on retrie donc tout le chevalet après l'ajout,
// comme le fait le bouton « Trier ».
function insererTrie(tuile) {
  const iExistant = chevaletLocal.findIndex((t) => t.id === tuile.id);
  if (iExistant < 0) chevaletLocal.push(tuile);
  chevaletLocal.sort(comparerTuiles);
}

// Tri d'une rangée de la zone de pose par valeur croissante (issue #66).
// Ex. 9,10,8 → 8,9,10. Les jokers sont renvoyés en fin de rangée.
function trierRangee(index) {
  travail[index].sort((a, b) => {
    if (a.est_joker) return 1;
    if (b.est_joker) return -1;
    return (a.valeur || 0) - (b.valeur || 0);
  });
  rafraichirZoneTravail();
}

// ------------------------------------------------------------ événements
function brancherEvenements() {
  document.getElementById("btn-retour").addEventListener("click", onRetourAccueil);
  document.getElementById("btn-trier").addEventListener("click", trierChevalet);
  document.getElementById("chk-tri-auto").addEventListener("change", (e) => {
    triAutoActif = e.target.checked;
    window.pywebview.api.sauvegarder_reglages({ tri_auto: triAutoActif });
  });
  document.getElementById("btn-annuler").addEventListener("click", onAnnuler);
  document.getElementById("btn-rejouer-coup-ia")
    .addEventListener("click", rejouerDernierCoupIA);
  document.getElementById("btn-verifier-calc").addEventListener("click", onVerifierCalc);
  document.getElementById("btn-jouer").addEventListener("click", onJouer);
  // Le bouton #btn-piocher (fusion Piocher/Passer) reçoit son écouteur
  // dynamiquement dans rafraichirBoutons() selon le contexte (issue #28).
  document.getElementById("btn-nouvelle-manche").addEventListener("click", onNouvelleManche);
  document.getElementById("btn-fin-retour").addEventListener("click", onRetourAccueil);
  document.getElementById("btn-classement-retour").addEventListener("click", onRetourAccueil);

  brancherZoomTapis();

  // Zone de travail : clic sur une rangée (fond ou numéro) = placer / activer
  document.querySelectorAll(".rangee-travail").forEach((rangeeEl) => {
    const i = parseInt(rangeeEl.dataset.rangee, 10);
    rangeeEl.addEventListener("click", (e) => {
      // Ignorer les clics sur une tuile ou sur les boutons vider / trier / placer
      if (e.target.classList.contains("btn-vider-rangee")) return;
      if (e.target.classList.contains("btn-trier-rangee")) return;
      if (e.target.classList.contains("btn-placer-rangee")) return;
      if (e.target.closest(".tuile-jeu")) return;
      if (tuileSelectionnee !== null) {
        rangeeActive = i;
        placerTuileDansRangee();
      } else {
        activerRangee(i);
      }
    });
  });
  document.querySelectorAll(".btn-vider-rangee").forEach((btn) => {
    const i = parseInt(btn.dataset.rangee, 10);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      viderRangee(i);
    });
  });
  document.querySelectorAll(".btn-trier-rangee").forEach((btn) => {
    const i = parseInt(btn.dataset.rangee, 10);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      trierRangee(i);
    });
  });
  document.querySelectorAll(".btn-placer-rangee").forEach((btn) => {
    const i = parseInt(btn.dataset.rangee, 10);
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      placerRangee(i);
    });
  });

  // Fantôme (issue #50) : la tuile sélectionnée suit le curseur.
  document.addEventListener("mousemove", (e) => {
    dernierePositionSouris = { x: e.clientX, y: e.clientY };
    const f = document.getElementById("tuile-fantome");
    if (f) {
      f.style.left = e.clientX + "px";
      f.style.top = e.clientY + "px";
    }
  });
  // Clic droit n'importe où → relâche la tuile tenue (toggle sélection → null),
  // détruit le fantôme et supprime le menu contextuel natif.
  document.addEventListener("contextmenu", (e) => {
    if (tuileSelectionnee !== null) {
      e.preventDefault();
      selectionnerTuile(tuileSelectionnee); // toggle → null → majFantome() détruit
    }
  });
}

// ------------------------------------------------------------ zoom du tapis
// Le zoom (issue #92) applique un transform: scale sur le SEUL #zone-plateau ;
// la zone de travail et le chevalet ne sont pas touchés. Le niveau choisi est
// mémorisé (localStorage) pour être restauré au chargement suivant.
const ZOOM_TAPIS_CLE = "rummikub_zoom_tapis";

function appliquerZoomTapis(valeur) {
  const plateau = document.getElementById("zone-plateau");
  if (!plateau) return;
  plateau.style.setProperty("--zoom-tapis", valeur);
  // Surbrillance du bouton correspondant.
  document.querySelectorAll("#zoom-tapis .btn-zoom").forEach((b) => {
    b.classList.toggle("actif", b.dataset.zoom === valeur);
  });
}

function brancherZoomTapis() {
  const boutons = document.querySelectorAll("#zoom-tapis .btn-zoom");
  if (!boutons.length) return;
  // Restauration du dernier niveau (défaut 100%).
  let initial = "1";
  try {
    const memo = localStorage.getItem(ZOOM_TAPIS_CLE);
    if (memo && [...boutons].some((b) => b.dataset.zoom === memo)) initial = memo;
  } catch (e) { /* localStorage indisponible : on reste à 100% */ }
  appliquerZoomTapis(initial);
  boutons.forEach((b) => {
    b.addEventListener("click", () => {
      appliquerZoomTapis(b.dataset.zoom);
      try { localStorage.setItem(ZOOM_TAPIS_CLE, b.dataset.zoom); } catch (e) {}
    });
  });
}

// Zoom automatique au débordement (issue #104) : après une pose de tuiles, si le
// contenu du tapis dépasse la zone visible (#zone-plateau-scroll : hauteur bornée
// + défilement), on réduit le zoom d'UN cran (100% → 75% → 50%) pour rendre la
// combinaison posée visible. On ne descend jamais sous le niveau minimal et on ne
// fait rien si tout est déjà visible. Le joueur garde la main : il peut ensuite
// zoomer/dézoomer librement, l'automatisme ne se redéclenche qu'à la pose suivante.
// Peut être désactivé via le réglage "Dé-zoom automatique du tapis" (issue #135).
//
// issue #140 (suite #135) : ce niveau n'est PLUS mémorisé dans localStorage (contrairement
// à un clic manuel sur un bouton de zoom, cf. brancherZoomTapis). Sinon, un dé-zoom
// automatique survenu une seule fois lors d'une ancienne partie restait collé comme
// « préférence » et faisait démarrer TOUTES les parties suivantes déjà dézoomées dès
// la première tuile posée — ce qui, en usage réel prolongé (localStorage persistant
// entre les parties, contrairement à un test Playwright isolé qui repart toujours
// d'un stockage vide), donnait l'impression d'un dé-zoom prématuré systématique.
// Le réexamen à chaque chargement de page (voir l'appel dans init()) suffit à
// retrouver le bon niveau pour une partie reprise dont le tapis est déjà chargé.
function autoZoomSiTapisDeborde() {
  if (!dezoomAutoActif) return; // réglage désactivé (issue #135)
  const scroll = document.getElementById("zone-plateau-scroll");
  const plateau = document.getElementById("zone-plateau");
  if (!scroll || !plateau) return;
  // La lecture de scrollHeight/scrollWidth force un reflow : les dimensions
  // reflètent donc le contenu fraîchement rendu.
  const deborde = scroll.scrollHeight > scroll.clientHeight
    || scroll.scrollWidth > scroll.clientWidth;
  if (!deborde) return;
  // Niveaux disponibles dans l'ordre des boutons (du plus grand au plus petit),
  // pour rester synchronisé avec le HTML sans coder les valeurs en dur ici.
  const niveaux = [...document.querySelectorAll("#zoom-tapis .btn-zoom")]
    .map((b) => b.dataset.zoom);
  if (!niveaux.length) return;
  const actuel = (plateau.style.getPropertyValue("--zoom-tapis") || "").trim()
    || niveaux[0];
  const idx = niveaux.indexOf(actuel);
  // Niveau inconnu, ou déjà au minimal : on ne réduit pas davantage.
  if (idx === -1 || idx >= niveaux.length - 1) return;
  const suivant = niveaux[idx + 1];
  appliquerZoomTapis(suivant);
}

// ------------------------------------------------------------ init
async function init() {
  brancherEvenements();
  try {
    etat = await window.pywebview.api.jeu_get_etat();
  } catch (e) {
    toast("Erreur de chargement de la partie", "erreur");
    return;
  }
  if (!etat || !etat.joueurs) {
    toast("Aucune partie en cours", "erreur");
    return;
  }
  reinitChevaletLocal();
  reinitTour();
  // Restaure l'état de la case "Tri automatique" tel que persisté (issue #130).
  triAutoActif = !!(etat.config && etat.config.tri_auto);
  const chkTriAuto = document.getElementById("chk-tri-auto");
  if (chkTriAuto) chkTriAuto.checked = triAutoActif;
  // Réglage "Dé-zoom automatique du tapis" (issue #135) : absent (vieille
  // partie reprise sans ce champ) ⇒ comportement historique conservé (actif).
  dezoomAutoActif = !(etat.config && etat.config.dezoom_auto === false);
  // Tapis vide (nouvelle partie, ou reprise avant la première pose) : remet le
  // zoom à 100% même si une ancienne valeur dézoomée traîne en mémoire (issue
  // #140). Sans ce correctif, un dé-zoom automatique déclenché une seule fois
  // dans une partie précédente restait collé indéfiniment (localStorage
  // persiste entre les parties, contrairement à un test isolé qui repart
  // toujours à zéro) : chaque NOUVELLE partie démarrait déjà dézoomée, dès la
  // première tuile posée, donnant l'impression d'un dé-zoom prématuré.
  if (!etat.plateau || etat.plateau.length === 0) {
    appliquerZoomTapis("1");
    try { localStorage.setItem(ZOOM_TAPIS_CLE, "1"); } catch (e) {}
  }
  rafraichirTout();
  // Réévalue le dé-zoom automatique sur le tapis tel que chargé (issue #140) :
  // une partie reprise avec un tapis déjà bien rempli doit retrouver le bon
  // niveau de zoom dès l'affichage, sans attendre la pose suivante — et sans
  // dépendre du niveau mémorisé par une partie précédente sans rapport.
  autoZoomSiTapisDeborde();
}

let _initFait = false;
function initUneFois() {
  if (_initFait) return;
  _initFait = true;
  init();
}
window.addEventListener("pywebviewready", initUneFois);
document.addEventListener("DOMContentLoaded", () => {
  if (window.pywebview) initUneFois();
});
