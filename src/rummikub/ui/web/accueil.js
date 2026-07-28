"use strict";

// Avatars (emoji tant que web/avatars/ est vide — issue ultérieure : images)
const AVATARS = ["🧑","👩","👨","🧔","👵","👴","🧓","👱","👩‍🦰","👨‍🦰",
                 "👩‍🦱","👨‍🦱","🧑‍🎓","👩‍🎨","🦊"];
const NIVEAUX = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert"];
const MAX_ADVERSAIRES = 3;

// État local de l'accueil
const etat = {
  reglages: null,
  avatarIndex: 0,
  adversaires: [],   // [{nom, avatar, niveau}]
};

function avatarPour(i) {
  return AVATARS[((i % AVATARS.length) + AVATARS.length) % AVATARS.length];
}

// ---------------------------------------------------------------- init
async function init() {
  // Titres en tuiles
  afficherTitreEnTuiles("RUMMIKUB", document.getElementById("titre-container"));
  afficherTitreEnTuiles("MODE SOLO", document.getElementById("sous-titre-container"));
  afficherTitreEnTuiles("VOUS", document.getElementById("label-joueur"));
  afficherTitreEnTuiles("ADVERSAIRES", document.getElementById("label-adversaires"));
  afficherTitreEnTuiles("PARTIES", document.getElementById("label-parties"));

  brancherEvenements();

  let data = { reglages: {}, parties: [] };
  try {
    data = await window.pywebview.api.charger_accueil();
  } catch (e) {
    toast("Erreur de chargement", "erreur");
  }

  etat.reglages = data.reglages || {};
  etat.avatarIndex = etat.reglages.avatar_index || 0;

  document.getElementById("nom-humain").textContent = etat.reglages.prenom || "Joueur";
  document.getElementById("avatar-humain").textContent = avatarPour(etat.avatarIndex);

  // Un adversaire par défaut
  if (etat.adversaires.length === 0) {
    etat.adversaires.push(nouvelAdversaire(0));
  }
  afficherAdversaires();
  afficherParties(data.parties || []);

  // Pré-remplir les champs de réglages
  remplirChampsReglages();
}

function nouvelAdversaire(index) {
  return {
    nom: "Ordinateur " + (index + 1),
    avatar: avatarPour(index + 5),
    niveau: "Intermédiaire",
  };
}

// ---------------------------------------------------------------- adversaires
function afficherAdversaires() {
  const cont = document.getElementById("liste-adversaires");
  cont.innerHTML = "";
  etat.adversaires.forEach((adv, index) => {
    const carte = document.createElement("div");
    carte.className = "carte-joueur ia";

    const av = document.createElement("span");
    av.className = "avatar-joueur";
    av.textContent = adv.avatar;
    carte.appendChild(av);

    const bloc = document.createElement("div");
    bloc.style.flex = "1";

    const nom = document.createElement("div");
    nom.className = "nom-joueur";
    nom.textContent = adv.nom;
    bloc.appendChild(nom);

    const niveaux = document.createElement("div");
    niveaux.className = "btn-niveaux-ia";
    NIVEAUX.forEach((niv) => {
      const b = document.createElement("button");
      b.className = "btn-niveau" + (niv === adv.niveau ? " actif" : "");
      b.dataset.niveau = niv;
      b.textContent = niv;
      b.addEventListener("click", () => definirNiveauAdversaire(index, niv));
      niveaux.appendChild(b);
    });
    bloc.appendChild(niveaux);
    carte.appendChild(bloc);

    // Bouton suppression (sauf si c'est le seul adversaire)
    if (etat.adversaires.length > 1) {
      const suppr = document.createElement("button");
      suppr.className = "btn-suppr-adv";
      suppr.textContent = "✕";
      suppr.title = "Retirer";
      suppr.addEventListener("click", () => supprimerAdversaire(index));
      carte.appendChild(suppr);
    }

    cont.appendChild(carte);
  });

  document.getElementById("btn-ajouter-adv").style.display =
    etat.adversaires.length >= MAX_ADVERSAIRES ? "none" : "block";
}

function ajouterAdversaire() {
  if (etat.adversaires.length >= MAX_ADVERSAIRES) {
    toast("Maximum " + MAX_ADVERSAIRES + " adversaires", "erreur");
    return;
  }
  etat.adversaires.push(nouvelAdversaire(etat.adversaires.length));
  afficherAdversaires();
}

function supprimerAdversaire(index) {
  if (etat.adversaires.length <= 1) return;
  etat.adversaires.splice(index, 1);
  afficherAdversaires();
}

function definirNiveauAdversaire(index, niveau) {
  if (!etat.adversaires[index]) return;
  etat.adversaires[index].niveau = niveau;
  afficherAdversaires();
}

// ---------------------------------------------------------------- parties
function afficherParties(liste) {
  const cont = document.getElementById("liste-parties");
  cont.innerHTML = "";
  if (!liste || liste.length === 0) {
    cont.innerHTML = "<p>Aucune partie sauvegardée</p>";
    return;
  }
  liste.forEach((p) => {
    const carte = document.createElement("div");
    carte.className = "carte-partie";

    const infos = document.createElement("div");
    const noms = (p.joueurs || []).map((j) => j.nom).join(", ");
    const scores = (p.joueurs || []).map((j) => j.score).join(" / ");
    infos.innerHTML =
      "<strong>" + noms + "</strong><br>" +
      "<span style='opacity:0.7'>" + (p.date || "") +
      (scores ? " — " + scores : "") + "</span>";
    carte.appendChild(infos);

    const actions = document.createElement("div");
    if (p.terminee) {
      const badge = document.createElement("span");
      badge.className = "badge-terminee";
      badge.textContent = "Terminée";
      actions.appendChild(badge);
    }
    const btn = document.createElement("button");
    btn.className = "btn-niveau";
    btn.textContent = p.terminee ? "Consulter" : "Reprendre";
    btn.addEventListener("click", () => reprendrePartie(p.id));
    actions.appendChild(btn);
    carte.appendChild(actions);

    cont.appendChild(carte);
  });
}

async function reprendrePartie(pid) {
  try {
    const r = await window.pywebview.api.reprendre_partie(pid);
    if (!r || !r.ok) toast((r && r.erreur) || "Impossible de reprendre", "erreur");
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// ---------------------------------------------------------------- réglages
function afficherReglages() {
  remplirChampsReglages();
  const ov = document.getElementById("overlay-reglages");
  ov.className = "overlay-visible";
}

function fermerReglages() {
  sauvegarderReglages();
  document.getElementById("overlay-reglages").className = "overlay-cache";
}

function remplirChampsReglages() {
  const r = etat.reglages || {};
  document.getElementById("rgl-prenom").value = r.prenom || "Joueur";
  document.getElementById("rgl-theme").value = r.theme || "Classique";
  document.getElementById("rgl-mise30").checked = (r.mise_initiale_min || 30) >= 30;
  document.getElementById("rgl-manches").value = r.nb_manches || 1;
  document.getElementById("rgl-vitesse").value = r.vitesse_ia || "Normale";
  const jokerVal = String(r.valeur_joker_penalite || 30);
  document.querySelectorAll("input[name='joker-val']").forEach((el) => {
    el.checked = el.value === jokerVal;
  });
  construireGrilleAvatars();
}

function construireGrilleAvatars() {
  const grille = document.getElementById("grille-avatars");
  grille.innerHTML = "";
  AVATARS.forEach((a, i) => {
    const b = document.createElement("button");
    b.className = "btn-avatar" + (i === etat.avatarIndex ? " selectionne" : "");
    b.textContent = a;
    b.addEventListener("click", () => {
      etat.avatarIndex = i;
      document.getElementById("avatar-humain").textContent = avatarPour(i);
      construireGrilleAvatars();
    });
    grille.appendChild(b);
  });
}

async function sauvegarderReglages() {
  const jokerEl = document.querySelector("input[name='joker-val']:checked");
  const data = {
    prenom: document.getElementById("rgl-prenom").value.trim() || "Joueur",
    avatar_index: etat.avatarIndex,
    theme: document.getElementById("rgl-theme").value,
    mise_initiale_min: document.getElementById("rgl-mise30").checked ? 30 : 0,
    nb_manches: parseInt(document.getElementById("rgl-manches").value, 10) || 1,
    valeur_joker_penalite: jokerEl ? parseInt(jokerEl.value, 10) : 30,
    vitesse_ia: document.getElementById("rgl-vitesse").value,
  };
  try {
    etat.reglages = await window.pywebview.api.sauvegarder_reglages(data);
    document.getElementById("nom-humain").textContent = etat.reglages.prenom;
    toast("Réglages enregistrés", "succes");
  } catch (e) {
    toast("Erreur d'enregistrement", "erreur");
  }
}

function ouvrirOnglet(nom) {
  document.querySelectorAll(".onglet").forEach((o) => {
    o.classList.toggle("actif", o.dataset.onglet === nom);
  });
  document.getElementById("panneau-general").classList.toggle("cache", nom !== "general");
  document.getElementById("panneau-regles").classList.toggle("cache", nom !== "regles");
}

// ---------------------------------------------------------------- lancement
async function lancerPartie() {
  const nomHumain = document.getElementById("nom-humain").textContent.trim() || "Joueur";
  const joueurs = [
    { nom: nomHumain, est_ia: false, niveau: null, avatar_index: etat.avatarIndex },
  ];
  etat.adversaires.forEach((a) => {
    joueurs.push({ nom: a.nom, est_ia: true, niveau: a.niveau });
  });

  const jokerEl = document.querySelector("input[name='joker-val']:checked");
  const regles = {
    mise_initiale_min: document.getElementById("rgl-mise30").checked ? 30 : 0,
    nb_manches: parseInt(document.getElementById("rgl-manches").value, 10) || 1,
    valeur_joker_penalite: jokerEl ? parseInt(jokerEl.value, 10) : 30,
    vitesse_ia: document.getElementById("rgl-vitesse").value,
    theme: document.getElementById("rgl-theme").value,
  };

  try {
    const r = await window.pywebview.api.lancer_nouvelle_partie({ joueurs, regles });
    if (!r || !r.ok) toast((r && r.erreur) || "Impossible de lancer", "erreur");
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// ---------------------------------------------------------------- événements
function brancherEvenements() {
  document.getElementById("btn-reglages").addEventListener("click", afficherReglages);
  document.getElementById("btn-fermer-rgl").addEventListener("click", fermerReglages);
  document.getElementById("btn-ajouter-adv").addEventListener("click", ajouterAdversaire);
  document.getElementById("btn-lancer").addEventListener("click", lancerPartie);
  document.querySelectorAll(".onglet").forEach((o) => {
    o.addEventListener("click", () => ouvrirOnglet(o.dataset.onglet));
  });
}

// Attendre que pywebview soit prêt
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
