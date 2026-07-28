"use strict";

// Avatars emoji (cohérent avec accueil.js tant que web/avatars/ est vide)
const AVATARS = ["🧑","👩","👨","🧔","👵","👴","🧓","👱","👩‍🦰","👨‍🦰",
                 "👩‍🦱","👨‍🦱","🧑‍🎓","👩‍🎨","🦊"];
const COULEURS_ORDRE = { rouge: 0, bleu: 1, jaune: 2, noir: 3 };

// ------------------------------------------------------------ état local
let etat = null;              // état complet de la partie (dict serveur)
let chevaletLocal = [];       // ordre local du chevalet, conservé entre les tours
let tuileSelectionnee = null; // id de tuile sélectionnée sur le chevalet
let tuilesCeTour = [];        // ids des tuiles posées ce tour
let plateauLocal = [];        // tapis existant, potentiellement étendu ce tour
let travail = [[], [], [], []]; // 4 rangées de pose, chacune = [dict_tuile, ...]
let rangeeActive = 0;         // index 0-3 de la rangée de travail active
let modeReorg = false;        // mode réorganisation du chevalet actif ?
let reorgSource = null;       // id de la tuile source d'un échange en cours

// ------------------------------------------------------------ utilitaires
function clone(x) { return JSON.parse(JSON.stringify(x)); }

function avatarPour(i) {
  return AVATARS[((i % AVATARS.length) + AVATARS.length) % AVATARS.length];
}

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

// ------------------------------------------------------------ rafraîchissement
function rafraichirTout() {
  if (!etat) return;
  rafraichirFichesJoueurs();
  rafraichirPlateau();
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
  rafraichirHistorique();
  document.getElementById("nb-pioche").textContent =
    (etat.pioche || []).length;
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

    const av = document.createElement("span");
    av.className = "avatar-fiche";
    av.textContent = avatarPour(
      j.avatar_index != null ? j.avatar_index : i + 5);
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

    // Zone d'extension en début de combinaison
    const extDebut = document.createElement("div");
    extDebut.className = "zone-ext zone-ext-debut" + (tuileSel ? "" : " masquee");
    extDebut.title = "Ajouter la tuile sélectionnée en début";
    extDebut.addEventListener("click", () => etendreTapis(idxCombo, "debut"));
    groupe.appendChild(extDebut);

    combo.forEach((d, idxTuile) => {
      const el = tuileDepuisDict(d);
      if (tuilesCeTour.includes(d.id)) {
        el.classList.add("ce-tour");
        el.addEventListener("click", () => reprendreTuile(d.id));
      } else if (d.est_joker && tuileSelectionnee !== null &&
                 etat.joueurs[indexHumain()].mise_initiale_faite) {
        el.classList.add("joker-recuperable");
        el.addEventListener("click", () =>
          tenterRecupererJoker(idxCombo, idxTuile, d));
      }
      groupe.appendChild(el);
    });

    // Zone d'extension en fin de combinaison
    const extFin = document.createElement("div");
    extFin.className = "zone-ext zone-ext-fin" + (tuileSel ? "" : " masquee");
    extFin.title = "Ajouter la tuile sélectionnée en fin";
    extFin.addEventListener("click", () => etendreTapis(idxCombo, "fin"));
    groupe.appendChild(extFin);

    zone.appendChild(groupe);
  });
}

// Rendu de la zone de travail (4 rangées)
function rafraichirZoneTravail() {
  travail.forEach((rangee, i) => {
    const cont = document.querySelector(`.rangee-tuiles[data-rangee="${i}"]`);
    const wrap = document.querySelector(`.rangee-travail[data-rangee="${i}"]`);
    const ind  = document.querySelector(`.rangee-indicateur[data-rangee="${i}"]`);
    if (!cont || !wrap) return;
    cont.innerHTML = "";
    wrap.classList.toggle("active", i === rangeeActive);
    wrap.classList.toggle("non-vide", rangee.length > 0);
    if (ind) ind.classList.toggle("actif", i === rangeeActive);
    rangee.forEach((d) => {
      const el = tuileDepuisDict(d);
      el.classList.add("ce-tour");
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        reprendreTuileRangee(d.id, i);
      });
      cont.appendChild(el);
    });
  });
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
  tuiles.forEach((d) => {
    const el = tuileDepuisDict(d);
    if (d.id === tuileSelectionnee) el.classList.add("selectionnee");
    if (reorgSource !== null) {
      // Un échange est en cours : la source est surlignée, les autres sont cibles
      if (d.id === reorgSource) el.classList.add("source-reorg");
      else el.classList.add("cible-reorg");
    } else if (modeReorg) {
      el.classList.add("mode-reorg");
    }
    el.addEventListener("click", () => onClickTuileChevalet(d));
    chev.appendChild(el);
  });
  for (let i = tuiles.length; i < 14; i++) {
    const vide = document.createElement("div");
    vide.className = "emplacement-vide";
    chev.appendChild(vide);
  }
}

function rafraichirBoutons() {
  const aPose = tuilesCeTour.length > 0;
  const piocheVide = (etat.pioche || []).length === 0;
  const monTour = estMonTour();
  document.getElementById("btn-annuler").disabled = !aPose;
  document.getElementById("btn-jouer").disabled = !aPose || !monTour;
  document.getElementById("btn-piocher").disabled = aPose || !monTour;
  document.getElementById("btn-passer").disabled =
    !piocheVide || aPose || !monTour;
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

// Bascule le mode réorganisation du chevalet (échange de tuiles sans jouer)
function basculerReorg() {
  modeReorg = !modeReorg;
  reorgSource = null;
  document.getElementById("btn-reorg").classList.toggle("actif", modeReorg);
  rafraichirChevalet();
}

// Clic sur une tuile du chevalet : réorganisation OU sélection pour pose
function onClickTuileChevalet(d) {
  if (reorgSource !== null) {
    // mode réorganisation : deuxième clic
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
  if (modeReorg) {
    // premier clic en mode réorg : sélectionner la source
    reorgSource = d.id;
    rafraichirChevalet();
    return;
  }
  // comportement normal : sélection pour pose
  selectionnerTuile(d.id);
}

function retirerDuChevalet(id) {
  const chev = chevaletLocal;
  const i = chev.findIndex((t) => t.id === id);
  if (i < 0) return null;
  return chev.splice(i, 1)[0];
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
  const d = retirerDuChevalet(tuileSelectionnee);
  if (!d) return;
  travail[rangeeActive].push(d);
  tuilesCeTour.push(d.id);
  tuileSelectionnee = null;
  rafraichirZoneTravail();
  rafraichirPlateau(); // masquer les zones d'extension
  rafraichirChevalet();
  rafraichirBoutons();
}

// Clic sur une tuile d'une rangée → retour au chevalet
function reprendreTuileRangee(id, indexRangee) {
  const i = travail[indexRangee].findIndex((t) => t.id === id);
  if (i < 0) return;
  const d = travail[indexRangee].splice(i, 1)[0];
  chevaletLocal.push(d);
  tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Vider toute une rangée → retour des tuiles au chevalet
function viderRangee(index) {
  const chev = chevaletLocal;
  const ids = travail[index].map((d) => d.id);
  travail[index].forEach((d) => { chev.push(d); });
  tuilesCeTour = tuilesCeTour.filter((id) => !ids.includes(id));
  travail[index] = [];
  rafraichirZoneTravail();
  rafraichirChevalet();
  rafraichirBoutons();
}

// ------------------------------------------------------------ extension du tapis
// Ajouter la tuile sélectionnée à l'extrémité d'une combinaison du tapis
function etendreTapis(idxCombo, position) {
  if (tuileSelectionnee === null) return;
  const d = retirerDuChevalet(tuileSelectionnee);
  if (!d) return;
  if (position === "fin") plateauLocal[idxCombo].push(d);
  else plateauLocal[idxCombo].unshift(d);
  tuilesCeTour.push(d.id);
  tuileSelectionnee = null;
  rafraichirPlateau();
  rafraichirChevalet();
  rafraichirBoutons();
}

// Reprendre une tuile ajoutée ce tour sur le tapis → retour au chevalet
function reprendreTuile(id) {
  for (const combo of plateauLocal) {
    const i = combo.findIndex((t) => t.id === id);
    if (i >= 0) {
      const d = combo.splice(i, 1)[0];
      chevaletLocal.push(d);
      break;
    }
  }
  tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
  rafraichirPlateau(); rafraichirChevalet(); rafraichirBoutons();
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
  tuileSelectionnee = null;
  plateauLocal = clone(etat.plateau || []);
  travail = [[], [], [], []];
  rangeeActive = 0;
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

async function onPiocher() {
  try {
    const res = await window.pywebview.api.jeu_piocher();
    if (res && res.ok) {
      etat = res.etat;
      const t = (res.tuiles_piochees || [])[0];
      toast("Vous piochez : " + decrireTuile(t));
      reconcilierChevalet();
      reinitTour();
      rafraichirTout();
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
    document.getElementById("nb-pioche").textContent =
      (etat.pioche || []).length;

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
  document.getElementById("btn-recommencer").addEventListener("click", () => {
    if (confirm("Recommencer la partie ?")) onNouvelleManche();
  });
  document.getElementById("btn-trier").addEventListener("click", trierChevalet);
  document.getElementById("btn-reorg").addEventListener("click", basculerReorg);
  document.getElementById("btn-annuler").addEventListener("click", onAnnuler);
  document.getElementById("btn-verifier-calc").addEventListener("click", onVerifierCalc);
  document.getElementById("btn-jouer").addEventListener("click", onJouer);
  document.getElementById("btn-piocher").addEventListener("click", onPiocher);
  document.getElementById("btn-passer").addEventListener("click", onPasser);
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
