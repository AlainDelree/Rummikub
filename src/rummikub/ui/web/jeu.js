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
let travail = [[], [], [], []]; // 4 rangées de pose, chacune = [dict_tuile, ...]
let rangeeActive = 0;         // index 0-3 de la rangée de travail active
let reorgSource = null;       // id de la tuile source d'un échange (réorg clic-long)
let modeTapis = false;        // mode manipulation du tapis actif ?
let tuilesOrigineTapis = [];  // ids des tuiles PRISES sur le tapis ce tour
let trouJoker = null;         // { combo, pos } : trou laissé par un joker pris (guidage)
let dernierClicChevalet = { id: null, temps: 0 }; // détection du double-clic
// Détection de l'appui long (500 ms) sur une tuile du chevalet → active la réorg
let appuiLong = { timer: null, id: null, declenche: false };
let dragSourceId = null;      // id de la tuile en cours de glisser-déposer

// ------------------------------------------------------------ utilitaires
function clone(x) { return JSON.parse(JSON.stringify(x)); }

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

function decrireTuile(d) {
  if (!d) return "?";
  if (d.est_joker) return "Joker";
  return d.couleur + " " + d.valeur;
}

// Construit un élément .tuile-jeu à partir d'un dict tuile.
function tuileDepuisDict(d) {
  const el = creerTuileJeu(d.valeur, d.est_joker ? null : d.couleur);
  el.dataset.id = d.id;
  return el;
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
  rafraichirHistorique();
  mettreAJourSac((etat.pioche || []).length);
  if (etat.manche_terminee) afficherFinManche();
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
    // Tour d'une IA : bouton « Jouer » pour déclencher son coup manuellement
    if (j.est_ia && i === etat.index_joueur_actuel && !etat.manche_terminee) {
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
  plateauLocal.forEach((combo, idxCombo) => {
    const groupe = document.createElement("div");
    groupe.className = "groupe-combinaison";
    // Combinaison devenue invalide (<3 tuiles) suite à une manipulation :
    // signalée en rouge jusqu'à ce que le joueur la complète ou annule.
    if (combo.length < 3) groupe.classList.add("combi-invalide");

    // Position du trou (index d'insertion) laissé par un joker retiré de CETTE
    // combinaison — pour surligner en orange la zone correspondante.
    const posTrou = (trouJoker && trouJoker.combo === combo) ? trouJoker.pos : -1;

    // Zone d'extension en début de combinaison (= insertion en position 0)
    const extDebut = document.createElement("div");
    extDebut.className = "zone-ext zone-ext-debut" + (tuileSel ? "" : " masquee") +
      (posTrou === 0 ? " trou-joker" : "");
    extDebut.title = "Ajouter la tuile sélectionnée en début";
    extDebut.addEventListener("click", () => etendreTapis(idxCombo, "debut"));
    groupe.appendChild(extDebut);

    combo.forEach((d, idxTuile) => {
      // Zone d'insertion interne entre la tuile précédente et celle-ci
      // (position exacte = idxTuile). Uniquement quand une tuile est prête.
      if (idxTuile > 0 && tuileSel) {
        const zi = document.createElement("div");
        zi.className = "zone-ext zone-ext-interne" +
          (posTrou === idxTuile ? " trou-joker" : "");
        zi.title = "Insérer la tuile sélectionnée ici";
        zi.addEventListener("click", () => insererTuileTapis(idxCombo, idxTuile));
        groupe.appendChild(zi);
      }

      const el = tuileDepuisDict(d);
      if (tuilesCeTour.includes(d.id)) {
        el.classList.add("ce-tour");
        el.addEventListener("click", () => reprendreTuile(d.id));
      } else if (modeTapis && tuileSelectionnee !== null) {
        // Mode manipulation + tuile prête : cliquer une tuile du tapis insère
        // la tuile sélectionnée AVANT elle (simplification, issue #27).
        el.classList.add("tapis-manipulable");
        el.addEventListener("click", () => insererTuileTapis(idxCombo, idxTuile));
      } else if (modeTapis) {
        // Mode manipulation : toute tuile du tapis peut être « prise »
        el.classList.add("tapis-manipulable");
        el.addEventListener("click", () => prendreTuileTapis(idxCombo, idxTuile));
      } else if (d.est_joker && tuileSelectionnee !== null &&
                 etat.joueurs[indexHumain()].mise_initiale_faite) {
        el.classList.add("joker-recuperable");
        el.addEventListener("click", () =>
          tenterRecupererJoker(idxCombo, idxTuile, d));
      }
      groupe.appendChild(el);
    });

    // Zone d'extension en fin de combinaison (= insertion en fin)
    const extFin = document.createElement("div");
    extFin.className = "zone-ext zone-ext-fin" + (tuileSel ? "" : " masquee") +
      (posTrou === combo.length ? " trou-joker" : "");
    extFin.title = "Ajouter la tuile sélectionnée en fin";
    extFin.addEventListener("click", () => etendreTapis(idxCombo, "fin"));
    groupe.appendChild(extFin);

    zone.appendChild(groupe);
  });
}

// Rendu de la zone de travail (4 rangées)
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
    if (ind) ind.classList.toggle("actif", i === rangeeActive);
    // Zone d'insertion avant la première tuile (position 0), visible quand une
    // tuile est prête à être posée. Même système que sur le tapis (issue #27).
    if (tuileSel && rangee.length > 0) cont.appendChild(zoneInsertionRangee(i, 0));
    rangee.forEach((d, idx) => {
      const el = tuileDepuisDict(d);
      el.classList.add("ce-tour");
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
    : "Maintenez une tuile pour la déplacer";
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
  document.getElementById("btn-remettre").disabled = !aPose;
  // Mode tapis : réservé à mon tour ET après la mise initiale.
  const miseFaite = !!(etat.joueurs[indexHumain()] &&
                       etat.joueurs[indexHumain()].mise_initiale_faite);
  const btnTapis = document.getElementById("btn-mode-tapis");
  btnTapis.disabled = !monTour || !miseFaite;
  if (btnTapis.disabled && modeTapis) {
    // Le mode ne peut rester actif s'il n'est plus autorisé.
    modeTapis = false;
    btnTapis.classList.remove("actif");
  }
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

function rafraichirHistorique() {
  const liste = document.getElementById("liste-historique");
  liste.innerHTML = "";
  const h = etat.historique || [];
  document.getElementById("nb-coups").textContent = h.length;
  h.slice(-5).reverse().forEach((e) => {
    const div = document.createElement("div");
    div.className = "entree-historique";
    const pts = e.points ? " (" + (e.points > 0 ? "+" : "") + e.points + ")" : "";
    div.textContent = "T" + e.tour + " · " + e.description + pts;
    liste.appendChild(div);
  });
}

// ------------------------------------------------------------ sélection / placement
function selectionnerTuile(id) {
  tuileSelectionnee = (tuileSelectionnee === id) ? null : id;
  rafraichirChevalet();
  rafraichirPlateau(); // afficher/masquer les zones d'extension du tapis
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
  const i = travail[indexRangee].findIndex((t) => t.id === id);
  if (i < 0) return;
  if (tuilesOrigineTapis.includes(id)) {
    tuileSelectionnee = (tuileSelectionnee === id) ? null : id;
    rafraichirZoneTravail();
    rafraichirPlateau();
    rafraichirChevalet();
    return;
  }
  const d = travail[indexRangee].splice(i, 1)[0];
  chevaletLocal.push(d);
  tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
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
}

// ------------------------------------------------------------ mode manipulation du tapis
// Basculer le mode manipulation : toutes les tuiles du tapis deviennent
// « prenables » pour être redistribuées entre combinaisons / zone de travail.
function basculerModeTapis() {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  if (!(etat.joueurs[indexHumain()] &&
        etat.joueurs[indexHumain()].mise_initiale_faite)) {
    toast("Disponible après la mise initiale", "erreur");
    return;
  }
  modeTapis = !modeTapis;
  document.getElementById("btn-mode-tapis").classList.toggle("actif", modeTapis);
  rafraichirPlateau();
}

// Prendre une tuile à l'intérieur d'une combinaison du tapis : elle quitte
// plateauLocal, entre dans tuilesCeTour, atterrit dans la rangée de travail
// active et devient sélectionnée (pour la déplacer aussitôt vers une extension
// du tapis si voulu). La combinaison source vidée est retirée ; réduite à
// moins de 3 tuiles, elle reste affichée en rouge (voir rafraichirPlateau).
function prendreTuileTapis(idxCombo, idxTuile) {
  if (!estMonTour()) { toast("Ce n'est pas votre tour", "erreur"); return; }
  const combo = plateauLocal[idxCombo];
  if (!combo) return;
  const d = combo[idxTuile];
  if (!d) return;
  combo.splice(idxTuile, 1);
  tuilesCeTour.push(d.id);
  tuilesOrigineTapis.push(d.id);
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
      type: "groupe",
    };
  }
}

function peutRemplacerJoker(tuileSel, infoJoker) {
  if (!infoJoker) return false;
  if (tuileSel.valeur !== infoJoker.valeur) return false;
  if (infoJoker.type === "suite" && tuileSel.couleur !== infoJoker.couleur)
    return false;
  if (infoJoker.type === "groupe" && tuileSel.couleur === null)
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

  // 4. Le joker atterrit dans la rangée active
  travail[rangeeActive].push(dictJoker);

  // 5. Le joker aussi compte comme joué (il DOIT être rejoué)
  tuilesCeTour.push(dictJoker.id);

  // 6. Désélectionner
  tuileSelectionnee = null;

  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
  toast("Joker récupéré — placez-le dans votre zone de pose");
}

function reinitTour() {
  tuilesCeTour = [];
  tuilesOrigineTapis = [];
  tuileSelectionnee = null;
  trouJoker = null;
  plateauLocal = clone(etat.plateau || []);
  travail = [[], [], [], []];
  rangeeActive = 0;
  modeTapis = false;
  const btnTapis = document.getElementById("btn-mode-tapis");
  if (btnTapis) btnTapis.classList.remove("actif");
  const rc = document.getElementById("resultat-calcul");
  if (rc) { rc.textContent = ""; rc.className = ""; }
}

// ------------------------------------------------------------ actions serveur
async function onAnnuler() {
  try {
    const res = await window.pywebview.api.jeu_annuler();
    if (res && res.etat) etat = res.etat;
  } catch (e) { /* annulation purement locale en repli */ }
  reinitChevaletLocal(); // seul cas où on repart de l'ordre serveur
  reinitTour();
  rafraichirTout();
}

// « Remettre » : remet le tapis à son état de début de tour et rapatrie les
// tuiles que le joueur a posées ce tour dans la zone de pose (pas au chevalet),
// pour repartir d'une base propre après des manipulations complexes du tapis.
function onRemettre() {
  if (tuilesCeTour.length === 0) return;

  // Tuiles du joueur posées ce tour = tuilesCeTour privé des tuiles PRISES sur
  // le tapis (celles-ci reviennent d'elles-mêmes via la restauration du plateau).
  const idsJoueur = tuilesCeTour.filter((id) => !tuilesOrigineTapis.includes(id));

  // Dictionnaires de ces tuiles : selon où elles ont été posées ce tour, elles
  // sont actuellement sur le tapis (plateauLocal), en zone de travail, ou encore
  // dans un des chevalets. On construit une table id→dict à partir de toutes ces
  // sources ; le chevalet serveur — non modifié pour les poses en rangée — sert
  // de repli comme indiqué par l'issue.
  const parId = new Map();
  const ajouter = (d) => { if (d && !parId.has(d.id)) parId.set(d.id, d); };
  plateauLocal.forEach((combo) => combo.forEach(ajouter));
  travail.forEach((rangee) => rangee.forEach(ajouter));
  chevaletLocal.forEach(ajouter);
  ((etat.joueurs[indexHumain()] || {}).chevalet || []).forEach(ajouter);

  // Restaurer le tapis à l'état de début de tour : les tuiles d'origine tapis y
  // reviennent, et plus aucune tuile du joueur n'y figure.
  plateauLocal = clone(etat.plateau || []);

  // Répartir les tuiles du joueur dans les rangées de travail, dans l'ordre,
  // sans dépasser 13 tuiles par rangée (rangée 1 d'abord, puis 2, etc.).
  travail = [[], [], [], []];
  let r = 0;
  idsJoueur.forEach((id) => {
    const d = parId.get(id);
    if (!d) return;
    while (r < travail.length && travail[r].length >= 13) r++;
    if (r >= travail.length) return; // filet : 4×13 = 52 places, jamais atteint
    travail[r].push(clone(d));
    // Cohérence du chevalet serveur (compteur des fiches joueurs) : une tuile
    // posée sur le tapis en avait été retirée ; en zone de travail elle doit y
    // figurer à nouveau, comme toute tuile simplement déplacée vers une rangée.
    rendreAuChevaletServeur(clone(d));
  });

  // Les tuiles restent « posées ce tour » puisqu'elles occupent la zone de pose
  // (comportement identique à une pose manuelle en rangée) ; seules les
  // références liées au tapis sont remises à zéro.
  tuilesCeTour = idsJoueur;
  tuilesOrigineTapis = [];
  trouJoker = null;
  tuileSelectionnee = null;
  rangeeActive = 0;
  modeTapis = false;
  const btnTapis = document.getElementById("btn-mode-tapis");
  if (btnTapis) btnTapis.classList.remove("actif");

  rafraichirTout();
  rafraichirZoneTravail();
}

async function onVerifierCalc() {
  const zone = document.getElementById("resultat-calcul");
  const rangeesPosees = travail.filter((r) => r.length > 0);
  const plateauComplet = [...plateauLocal, ...rangeesPosees];
  try {
    const res = await window.pywebview.api.jeu_verifier_plateau(plateauComplet);
    if (res.valide) {
      zone.className = "ok";
      zone.textContent = "✓ Plateau valide — " + res.points_total + " points";
    } else {
      zone.className = "ko";
      zone.textContent = "✗ " + (res.erreurs || []).join(" ; ");
    }
  } catch (e) {
    zone.className = "ko";
    zone.textContent = "Erreur : " + e;
  }
}

async function onJouer() {
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
      toast("Coup joué", "succes");
    } else {
      toast((res && res.erreur) || "Coup invalide", "erreur");
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

async function onPiocher() {
  try {
    const res = await window.pywebview.api.jeu_piocher();
    if (res && res.ok) {
      etat = res.etat;
      const t = (res.tuiles_piochees || [])[0];
      reconcilierChevalet();
      reinitTour();
      // Rafraîchir tout SAUF le chevalet : la tuile piochée n'y apparaît
      // qu'à la fin de l'animation (elle est d'abord montrée en grand).
      rafraichirFichesJoueurs();
      rafraichirPlateau();
      rafraichirZoneTravail();
      rafraichirBoutons();
      rafraichirHistorique();
      mettreAJourSac((etat.pioche || []).length);
      animerPiochee(t, () => {
        rafraichirChevalet();
        if (etat.manche_terminee) afficherFinManche();
      });
    } else {
      toast((res && res.erreur) || "Impossible de piocher", "erreur");
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

async function onPasser() {
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

// L'humain clique « Jouer » sur la fiche de l'IA active pour déclencher son coup.
// Les tuiles posées par l'IA apparaissent une par une avec une animation lente
// et visible (jeu destiné à des personnes âgées).
async function jouerIA() {
  const btnIA = document.querySelector(".btn-jouer-ia");
  if (btnIA) btnIA.disabled = true;

  // Vitesse d'animation selon le réglage « Vitesse de l'IA »
  const VITESSES = {
    "Instantanée": { reflexion: 0,    tuile: 100 },
    "Rapide":      { reflexion: 400,  tuile: 400 },
    "Normale":     { reflexion: 800,  tuile: 700 },
    "Lente":       { reflexion: 1500, tuile: 1200 },
  };
  const vitesse = VITESSES[
    (etat.config && etat.config.vitesse_ia) || "Normale"
  ] || VITESSES["Normale"];
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

    // Calculer les tuiles ajoutées AVANT de mettre à jour l'état
    const ancienPlateau = clone(etat.plateau || []);
    const nouvelEtat    = res.etat;
    const tuiAjoutees   = trouverTuilesAjoutees(
      ancienPlateau, nouvelEtat.plateau || []);

    // Mettre à jour l'état (mais on reconstruit le plateau visible à la main)
    etat = nouvelEtat;
    reconcilierChevalet(); // le tour d'une IA ne change pas l'ordre du chevalet humain
    reinitTour();

    // Cas « pioche » ou « passe » : aucune tuile ajoutée
    if (tuiAjoutees.length === 0) {
      rafraichirFichesJoueurs();
      const h = nouvelEtat.historique || [];
      const action = (h.length ? h[h.length - 1].description : "") || "";
      const nomIA = (nouvelEtat.joueurs[idxIA] || {}).nom || "L'IA";
      toast(nomIA + " " +
        (action.includes("pioch") ? "pioche" : "passe son tour"));
      await new Promise(r => setTimeout(r, 800));
      rafraichirTout();
      return;
    }

    // Afficher d'abord le tapis SANS les nouvelles tuiles
    const idsAjoutees = new Set(tuiAjoutees.map(t => t.dict.id));
    plateauLocal = (etat.plateau || []).map(combo =>
      combo.filter(d => !idsAjoutees.has(d.id))
    ).filter(c => c.length > 0);

    rafraichirFichesJoueurs();
    rafraichirPlateau();
    rafraichirChevalet();
    rafraichirBoutons();
    rafraichirHistorique();
    mettreAJourSac((etat.pioche || []).length);

    // Poser les tuiles une par une avec animation
    for (let i = 0; i < tuiAjoutees.length; i++) {
      await new Promise(r =>
        setTimeout(r, i === 0 ? 200 : DELAI_ENTRE_TUILES));
      const { dict } = tuiAjoutees[i];

      // Reconstruire progressivement le plateau visible :
      // tuiles originales + tuiles déjà animées jusqu'à i inclus
      plateauLocal = clone(etat.plateau || []).map(combo =>
        combo.filter(d => {
          const dejaPosee = tuiAjoutees.slice(0, i + 1)
            .some(t => t.dict.id === d.id);
          return !idsAjoutees.has(d.id) || dejaPosee;
        })
      ).filter(c => c.length > 0);

      rafraichirPlateau();

      // Appliquer l'animation sur la tuile qui vient d'apparaître
      setTimeout(() => {
        document.querySelectorAll("#zone-plateau .tuile-jeu").forEach(el => {
          if (el.dataset.id === dict.id) {
            el.classList.add("tuile-ia-posee");
            setTimeout(() => {
              el.classList.remove("tuile-ia-posee");
              el.classList.add("tuile-ia-highlight");
            }, 700);
          }
        });
      }, 50);
    }

    // Attendre la fin de la dernière animation
    await new Promise(r => setTimeout(r, 800));

    // Finaliser : plateau complet + rafraîchissement normal
    plateauLocal = clone(etat.plateau || []);
    rafraichirPlateau();
    rafraichirTout();

    // Effacer les surbrillances dorées après 2 secondes
    setTimeout(() => {
      document.querySelectorAll(".tuile-ia-highlight").forEach(el => {
        el.classList.remove("tuile-ia-highlight");
      });
    }, 2000);

  } catch (e) {
    toast("Erreur IA : " + e, "erreur");
    rafraichirTout();
  }
}

// ------------------------------------------------------------ fin de manche
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
function trierChevalet() {
  const chev = chevaletLocal;
  chev.sort((a, b) => {
    if (a.est_joker) return 1;
    if (b.est_joker) return -1;
    const ca = COULEURS_ORDRE[a.couleur] ?? 9;
    const cb = COULEURS_ORDRE[b.couleur] ?? 9;
    if (ca !== cb) return ca - cb;
    return (a.valeur || 0) - (b.valeur || 0);
  });
  rafraichirChevalet();
}

// ------------------------------------------------------------ événements
function brancherEvenements() {
  document.getElementById("btn-retour").addEventListener("click", onRetourAccueil);
  document.getElementById("btn-trier").addEventListener("click", trierChevalet);
  document.getElementById("btn-annuler").addEventListener("click", onAnnuler);
  document.getElementById("btn-remettre").addEventListener("click", onRemettre);
  document.getElementById("btn-mode-tapis").addEventListener("click", basculerModeTapis);
  document.getElementById("btn-verifier-calc").addEventListener("click", onVerifierCalc);
  document.getElementById("btn-jouer").addEventListener("click", onJouer);
  // Le bouton #btn-piocher (fusion Piocher/Passer) reçoit son écouteur
  // dynamiquement dans rafraichirBoutons() selon le contexte (issue #28).
  document.getElementById("btn-nouvelle-manche").addEventListener("click", onNouvelleManche);
  document.getElementById("btn-fin-retour").addEventListener("click", onRetourAccueil);

  // Zone de travail : clic sur une rangée (fond ou numéro) = placer / activer
  document.querySelectorAll(".rangee-travail").forEach((rangeeEl) => {
    const i = parseInt(rangeeEl.dataset.rangee, 10);
    rangeeEl.addEventListener("click", (e) => {
      // Ignorer les clics sur une tuile ou sur le bouton vider
      if (e.target.classList.contains("btn-vider-rangee")) return;
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
  rafraichirTout();
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
