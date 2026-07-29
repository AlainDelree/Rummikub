"use strict";

// Avatars SVG et helpers genrés : voir commun.js (AVATARS, avatarPour,
// elementAvatar, avatarAleatoirePourPrenom) + genres.js (genrePrénom).
const NIVEAUX = ["Débutant", "Facile", "Intermédiaire", "Avancé", "Expert"];
const MAX_ADVERSAIRES = 3;

// État local de l'accueil
const etat = {
  reglages: null,
  avatarIndex: 0,
  adversaires: [],   // [{nom, avatar, niveau}] — avatar = nom de fichier SVG
};

// ---------------------------------------------------------------- init
async function init() {
  // Titres en tuiles
  afficherTitreEnTuiles("RUMMIKUB", document.getElementById("titre-container"));
  afficherTitreEnTuiles("JOUEURS", document.getElementById("label-joueurs"));
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

  // Aucun adversaire par défaut : l'utilisateur en ajoute au moins un.
  afficherJoueurs();
  afficherParties(data.parties || []);

  // Pré-remplir les champs de réglages
  remplirChampsReglages();
}

// ---------------------------------------------------------------- joueurs (humain + IA)
function slugNiveau(niv) {
  return (niv || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function afficherJoueurs() {
  const cont = document.getElementById("liste-joueurs");
  cont.innerHTML = "";

  // Carte humain (en premier, fond bleu clair, pas de bouton ✕)
  const carteH = document.createElement("div");
  carteH.className = "carte-joueur humain";
  const avH = elementAvatar(avatarPour(etat.avatarIndex), "avatar-joueur");
  avH.id = "avatar-humain";
  carteH.appendChild(avH);
  const nomH = document.createElement("span");
  nomH.className = "nom-joueur";
  nomH.id = "nom-humain";
  nomH.contentEditable = "true";
  nomH.textContent = (etat.reglages && etat.reglages.prenom) || "Joueur";
  carteH.appendChild(nomH);
  cont.appendChild(carteH);

  // Cartes IA (fond violet clair, badge niveau, bouton ✕)
  etat.adversaires.forEach((adv, index) => {
    const carte = document.createElement("div");
    carte.className = "carte-joueur ia";

    const av = elementAvatar(adv.avatar, "avatar-joueur");
    carte.appendChild(av);

    const bloc = document.createElement("div");
    bloc.style.flex = "1";

    const nom = document.createElement("div");
    nom.className = "nom-joueur";
    nom.textContent = adv.nom;
    const badge = document.createElement("span");
    badge.className = "badge-niveau-ia niveau-" + slugNiveau(adv.niveau);
    badge.textContent = adv.niveau;
    nom.appendChild(badge);
    bloc.appendChild(nom);
    carte.appendChild(bloc);

    const suppr = document.createElement("button");
    suppr.className = "btn-suppr-adv";
    suppr.textContent = "✕";
    suppr.title = "Retirer";
    suppr.addEventListener("click", () => supprimerAdversaire(index));
    carte.appendChild(suppr);

    cont.appendChild(carte);
  });

  majBoutonsAjout();
  majBoutonLancer();
}

function majBoutonsAjout() {
  const max = etat.adversaires.length >= MAX_ADVERSAIRES;
  document.querySelectorAll(".btn-ajout-niveau").forEach((b) => {
    b.disabled = max;
    b.title = max ? "Maximum " + MAX_ADVERSAIRES + " adversaires" : "";
  });
}

// Griser « Lancer la partie » tant qu'aucun adversaire n'est présent.
function majBoutonLancer() {
  const btn = document.getElementById("btn-lancer");
  if (!btn) return;
  const aucun = etat.adversaires.length === 0;
  btn.disabled = aucun;
  btn.title = aucun ? "Ajoutez au moins un adversaire" : "";
}

// Prénom aléatoire non dupliqué pour une nouvelle IA (via l'API Python).
async function nomIAAleatoire() {
  const nomHumain =
    (document.getElementById("nom-humain")?.textContent || "").trim() ||
    (etat.reglages && etat.reglages.prenom) || "";
  const exclure = [nomHumain, ...etat.adversaires.map((a) => a.nom)]
    .filter(Boolean);
  try {
    const r = await window.pywebview.api.nom_ia_aleatoire(exclure);
    if (r && r.nom) return r.nom;
  } catch (e) { /* repli ci-dessous */ }
  return "Ordinateur " + (etat.adversaires.length + 1);
}

async function ajouterAdversaire(niveau) {
  if (etat.adversaires.length >= MAX_ADVERSAIRES) {
    toast("Maximum " + MAX_ADVERSAIRES + " adversaires", "erreur");
    return;
  }
  const nom = await nomIAAleatoire();
  // Avatar accordé au genre du prénom tiré (genres.js), en évitant si
  // possible les avatars déjà pris par les autres adversaires.
  const avatar = avatarAleatoirePourPrenom(
    nom, etat.adversaires.map((a) => a.avatar));
  etat.adversaires.push({ nom, avatar, niveau });
  afficherJoueurs();
}

function supprimerAdversaire(index) {
  etat.adversaires.splice(index, 1);
  afficherJoueurs();
}

// ---------------------------------------------------------------- parties
function afficherParties(liste) {
  const cont = document.getElementById("liste-parties");
  cont.innerHTML = "";
  const src = liste || [];
  const nonTerminees = src.filter((p) => !p.terminee);
  const terminees    = src.filter((p) => p.terminee);
  const aAfficher = [];
  if (nonTerminees.length > 0) aAfficher.push(nonTerminees[0]);
  if (terminees.length > 0)    aAfficher.push(terminees[0]);
  if (aAfficher.length === 0) {
    cont.innerHTML = "<p>Aucune partie sauvegardée</p>";
    return;
  }
  aAfficher.forEach((p) => {
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

function reprendrePartie(pid) {
  // Fire and forget : la navigation vers jeu.html se fait côté Python.
  // Ne pas « await » (voir lancerPartie) : le callback JS disparaît avec la
  // page et pywebview lèverait une TypeError.
  try {
    window.pywebview.api.reprendre_partie(pid);
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
  document.getElementById("rgl-mise30").checked = (r.mise_initiale_min || 30) >= 30;
  document.getElementById("rgl-manches").value = r.nb_manches || 1;
  document.getElementById("rgl-vitesse").value = r.vitesse_ia || "Normale";
  const jokerVal = String(r.valeur_joker_penalite || 30);
  document.querySelectorAll("input[name='joker-val']").forEach((el) => {
    el.checked = el.value === jokerVal;
  });
  const modeReorg = r.mode_reorg || "clic";
  document.querySelectorAll("input[name='mode-reorg']").forEach((el) => {
    el.checked = el.value === modeReorg;
  });
  construireGrilleAvatars();
}

function construireGrilleAvatars() {
  const grille = document.getElementById("grille-avatars");
  grille.innerHTML = "";
  AVATARS.forEach((a, i) => {
    const b = document.createElement("button");
    b.className = "btn-avatar" + (i === etat.avatarIndex ? " selectionne" : "");
    b.appendChild(elementAvatar(a, "avatar-vignette"));
    b.addEventListener("click", () => {
      etat.avatarIndex = i;
      const avH = document.getElementById("avatar-humain");
      if (avH) avH.src = "avatars/" + avatarPour(i) + ".svg";
      construireGrilleAvatars();
    });
    grille.appendChild(b);
  });
}

async function sauvegarderReglages() {
  const jokerEl = document.querySelector("input[name='joker-val']:checked");
  const reorgEl = document.querySelector("input[name='mode-reorg']:checked");
  const data = {
    prenom: document.getElementById("rgl-prenom").value.trim() || "Joueur",
    avatar_index: etat.avatarIndex,
    mise_initiale_min: document.getElementById("rgl-mise30").checked ? 30 : 0,
    nb_manches: parseInt(document.getElementById("rgl-manches").value, 10) || 1,
    valeur_joker_penalite: jokerEl ? parseInt(jokerEl.value, 10) : 30,
    vitesse_ia: document.getElementById("rgl-vitesse").value,
    mode_reorg: reorgEl ? reorgEl.value : "clic",
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
  if (etat.adversaires.length === 0) {
    toast("Ajoutez au moins un adversaire", "erreur");
    return;
  }
  const nomHumain = document.getElementById("nom-humain").textContent.trim() || "Joueur";
  const joueurs = [
    { nom: nomHumain, est_ia: false, niveau: null, avatar_index: etat.avatarIndex },
  ];
  etat.adversaires.forEach((a) => {
    // Transmettre l'index de l'avatar genré choisi pour que le jeu affiche
    // exactement le même avatar (voir jeu.js / creer_partie).
    joueurs.push({
      nom: a.nom, est_ia: true, niveau: a.niveau,
      avatar_index: AVATARS.indexOf(a.avatar),
    });
  });

  const jokerEl = document.querySelector("input[name='joker-val']:checked");
  const regles = {
    mise_initiale_min: document.getElementById("rgl-mise30").checked ? 30 : 0,
    nb_manches: parseInt(document.getElementById("rgl-manches").value, 10) || 1,
    valeur_joker_penalite: jokerEl ? parseInt(jokerEl.value, 10) : 30,
    vitesse_ia: document.getElementById("rgl-vitesse").value,
  };

  // Fire and forget : la navigation vers jeu.html se fait côté Python.
  // Ne pas « await » : la page a déjà changé quand Python répond, donc le
  // callback JS n'existe plus et pywebview lèverait une TypeError.
  try {
    window.pywebview.api.lancer_nouvelle_partie({ joueurs, regles });
  } catch (e) {
    toast("Erreur : " + e, "erreur");
  }
}

// ---------------------------------------------------------------- événements
function brancherEvenements() {
  document.getElementById("btn-reglages").addEventListener("click", afficherReglages);
  document.getElementById("btn-fermer-rgl").addEventListener("click", fermerReglages);
  document.querySelectorAll(".btn-ajout-niveau").forEach((b) => {
    b.addEventListener("click", () => ajouterAdversaire(b.dataset.niveau));
  });
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
