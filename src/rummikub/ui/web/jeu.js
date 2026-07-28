"use strict";

// Avatars emoji (cohérent avec accueil.js tant que web/avatars/ est vide)
const AVATARS = ["🧑","👩","👨","🧔","👵","👴","🧓","👱","👩‍🦰","👨‍🦰",
                 "👩‍🦱","👨‍🦱","🧑‍🎓","👩‍🎨","🦊"];
const COULEURS_ORDRE = { rouge: 0, bleu: 1, jaune: 2, noir: 3 };

// ------------------------------------------------------------ état local
let etat = null;              // état complet de la partie (dict serveur)
let tuileSelectionnee = null; // id de tuile sélectionnée sur le chevalet
let tuilesCeTour = [];        // ids des tuiles posées ce tour
let plateauLocal = [];        // copie manipulable du plateau ce tour

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
    meta.textContent = "🁢 " + nbT + " tuiles · " +
      (j.score_manche >= 0 ? "+" : "") + (j.score_manche || 0) + " pts";
    info.appendChild(meta);
    fiche.appendChild(info);

    if (i === idxH && i === etat.index_joueur_actuel && !etat.manche_terminee) {
      const badge = document.createElement("span");
      badge.className = "badge-actif";
      badge.textContent = "▶ À vous";
      fiche.appendChild(badge);
    }
    cont.appendChild(fiche);
  });
}

function rafraichirPlateau() {
  const zone = document.getElementById("zone-plateau");
  zone.innerHTML = "";
  plateauLocal.forEach((combo, idxCombo) => {
    const groupe = document.createElement("div");
    groupe.className = "groupe-combinaison";
    combo.forEach((d) => {
      const el = tuileDepuisDict(d);
      if (tuilesCeTour.includes(d.id)) {
        el.classList.add("ce-tour");
        el.addEventListener("click", () => reprendreTuile(d.id));
      }
      groupe.appendChild(el);
    });
    const insert = document.createElement("div");
    insert.className = "zone-insertion";
    insert.title = "Placer la tuile sélectionnée ici";
    insert.addEventListener("click", () => placerDansCombo(idxCombo));
    groupe.appendChild(insert);
    zone.appendChild(groupe);
  });
}

function rafraichirChevalet() {
  const chev = document.getElementById("chevalet");
  chev.innerHTML = "";
  const tuiles = (etat.joueurs[indexHumain()].chevalet) || [];
  tuiles.forEach((d) => {
    const el = tuileDepuisDict(d);
    if (d.id === tuileSelectionnee) el.classList.add("selectionnee");
    el.addEventListener("click", () => selectionnerTuile(d.id));
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
}

function retirerDuChevalet(id) {
  const chev = etat.joueurs[indexHumain()].chevalet;
  const i = chev.findIndex((t) => t.id === id);
  if (i < 0) return null;
  return chev.splice(i, 1)[0];
}

function placerDansCombo(idxCombo) {
  if (!tuileSelectionnee) { toast("Sélectionnez d'abord une tuile"); return; }
  const d = retirerDuChevalet(tuileSelectionnee);
  if (!d) return;
  plateauLocal[idxCombo].push(d);
  tuilesCeTour.push(d.id);
  tuileSelectionnee = null;
  rafraichirPlateau(); rafraichirChevalet(); rafraichirBoutons();
}

function nouvelleCombinaison() {
  if (!tuileSelectionnee) { toast("Sélectionnez d'abord une tuile"); return; }
  const d = retirerDuChevalet(tuileSelectionnee);
  if (!d) return;
  plateauLocal.push([d]);
  tuilesCeTour.push(d.id);
  tuileSelectionnee = null;
  rafraichirPlateau(); rafraichirChevalet(); rafraichirBoutons();
}

function reprendreTuile(id) {
  // Retire la tuile de plateauLocal et la remet sur le chevalet.
  for (const combo of plateauLocal) {
    const i = combo.findIndex((t) => t.id === id);
    if (i >= 0) {
      const d = combo.splice(i, 1)[0];
      etat.joueurs[indexHumain()].chevalet.push(d);
      break;
    }
  }
  tuilesCeTour = tuilesCeTour.filter((x) => x !== id);
  // Supprime les combinaisons vides créées ce tour.
  plateauLocal = plateauLocal.filter((c) => c.length > 0);
  rafraichirPlateau(); rafraichirChevalet(); rafraichirBoutons();
}

function reinitTour() {
  tuilesCeTour = [];
  tuileSelectionnee = null;
  plateauLocal = clone(etat.plateau || []);
  document.getElementById("resultat-calcul").textContent = "";
  document.getElementById("resultat-calcul").className = "";
}

// ------------------------------------------------------------ actions serveur
async function onAnnuler() {
  try {
    const res = await window.pywebview.api.jeu_annuler();
    if (res && res.etat) etat = res.etat;
  } catch (e) { /* annulation purement locale en repli */ }
  reinitTour();
  rafraichirTout();
}

async function onVerifierCalc() {
  const zone = document.getElementById("resultat-calcul");
  try {
    const res = await window.pywebview.api.jeu_verifier_plateau(plateauLocal);
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
  try {
    const res = await window.pywebview.api.jeu_jouer_coup({
      ids_tuiles: tuilesCeTour,
      nouveau_plateau: plateauLocal,
    });
    if (res && res.ok) {
      etat = res.etat;
      reinitTour();
      rafraichirTout();
      toast("Coup joué", "succes");
      if (joueurCourantEstIA()) demarrerTourIA();
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
      reinitTour();
      rafraichirTout();
      if (joueurCourantEstIA()) demarrerTourIA();
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
      reinitTour();
      rafraichirTout();
      if (joueurCourantEstIA()) demarrerTourIA();
    } else {
      toast((res && res.erreur) || "Impossible de passer", "erreur");
    }
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// ------------------------------------------------------------ IA (stub issue 4)
function delaiIA() {
  const base = 700;
  const v = (etat && etat.config && etat.config.vitesse_ia) || "Normale";
  const mult = { "Instantanée": 0, "Rapide": 0.3, "Normale": 1, "Lente": 2 };
  return base * (mult[v] != null ? mult[v] : 1);
}

function demarrerTourIA() {
  if (!joueurCourantEstIA() || etat.manche_terminee) return;
  // Indication visuelle « réfléchit »
  const fiches = document.querySelectorAll(".fiche-joueur");
  const active = fiches[etat.index_joueur_actuel];
  if (active) {
    const meta = active.querySelector(".meta-fiche");
    if (meta) meta.textContent = "… réfléchit";
  }
  ["btn-jouer", "btn-annuler", "btn-piocher", "btn-passer"].forEach((id) => {
    document.getElementById(id).disabled = true;
  });
  setTimeout(async () => {
    try {
      const res = await window.pywebview.api.jeu_ia_jouer();
      if (res && res.ok && res.etat) {
        etat = res.etat;
        reinitTour();
        rafraichirTout();
        if (joueurCourantEstIA()) demarrerTourIA();
      } else {
        toast((res && res.erreur) || "Tour IA impossible", "erreur");
        rafraichirTout();   // restaure l'affichage / réactive les boutons
      }
    } catch (e) {
      toast("Erreur IA : " + e, "erreur");
      rafraichirTout();
    }
  }, delaiIA());
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

// ------------------------------------------------------------ vérificateur
function parserTuilesTexte(txt) {
  // "rouge_7,rouge_8,rouge_9" -> [dict tuile, ...]
  const tuiles = [];
  txt.split(",").map((s) => s.trim()).filter(Boolean).forEach((tok, i) => {
    const bas = tok.toLowerCase();
    if (bas === "joker" || bas === "j" || bas === "★") {
      tuiles.push({ id: "verif_joker_" + i, valeur: null, couleur: null,
                    est_joker: true });
      return;
    }
    const parts = tok.split("_");
    const couleur = parts[0];
    const valeur = parseInt(parts[1], 10);
    tuiles.push({ id: "verif_" + tok + "_" + i, valeur: valeur,
                  couleur: couleur, est_joker: false });
  });
  return tuiles;
}

async function onVerifier() {
  const zone = document.getElementById("resultat-verif");
  const txt = document.getElementById("input-verif").value;
  const tuiles = parserTuilesTexte(txt);
  if (tuiles.length === 0) { zone.className = ""; zone.textContent = ""; return; }
  try {
    const res = await window.pywebview.api.jeu_verifier_combinaison(tuiles);
    if (res.valide) {
      zone.className = "ok";
      zone.textContent = "✓ " + res.type + " — " + res.points + " points";
    } else {
      zone.className = "ko";
      zone.textContent = "✗ Ni suite ni groupe valide";
    }
  } catch (e) {
    zone.className = "ko";
    zone.textContent = "Erreur : " + e;
  }
}

// ------------------------------------------------------------ tri du chevalet
function trierChevalet() {
  const chev = etat.joueurs[indexHumain()].chevalet;
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
  document.getElementById("btn-nouvelle-combi").addEventListener("click", nouvelleCombinaison);
  document.getElementById("btn-trier").addEventListener("click", trierChevalet);
  document.getElementById("btn-annuler").addEventListener("click", onAnnuler);
  document.getElementById("btn-verifier-calc").addEventListener("click", onVerifierCalc);
  document.getElementById("btn-jouer").addEventListener("click", onJouer);
  document.getElementById("btn-piocher").addEventListener("click", onPiocher);
  document.getElementById("btn-passer").addEventListener("click", onPasser);
  document.getElementById("btn-verif").addEventListener("click", onVerifier);
  document.getElementById("input-verif").addEventListener("keydown", (e) => {
    if (e.key === "Enter") onVerifier();
  });
  document.getElementById("btn-nouvelle-manche").addEventListener("click", onNouvelleManche);
  document.getElementById("btn-fin-retour").addEventListener("click", onRetourAccueil);
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
  reinitTour();
  rafraichirTout();
  if (joueurCourantEstIA()) demarrerTourIA();
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
