function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = "visible" + (type !== "info" ? " " + type : "");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.className = "", 3000);
}

// Visage souriant « lune » du joker, façon vraie tuile Rummikub (rouge, SVG).
const SVG_JOKER_FACE = `
<svg class="joker-face" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"
     fill="none" stroke="#cc2200" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="20" cy="20" r="15.2" stroke-width="1.6"/>
  <path d="M10.5 15.2 Q13.8 12.4 17 15" stroke-width="1.4"/>
  <path d="M23 15 Q26.2 12.4 29.5 15.2" stroke-width="1.4"/>
  <circle cx="14" cy="18" r="1.5" fill="#cc2200" stroke="none"/>
  <circle cx="26" cy="18" r="1.5" fill="#cc2200" stroke="none"/>
  <path d="M20 17.5 L20 24 Q22.2 24 22.6 22.2" stroke-width="1.3"/>
  <path d="M12.8 26.5 Q20 33 27.2 26.5" stroke-width="1.7"/>
</svg>`;

function creerTuileJeu(valeur, couleur) {
  const d = document.createElement("div");
  const estJoker = !couleur;
  d.className = "tuile-jeu" + (couleur ? " " + couleur : " joker");
  d.dataset.valeur = valeur; d.dataset.couleur = couleur || "joker";

  const cercle = document.createElement("span");
  cercle.className = "tuile-cercle";
  if (estJoker) {
    cercle.innerHTML = SVG_JOKER_FACE;
  } else {
    const num = document.createElement("span");
    num.className = "tuile-num";
    num.textContent = valeur;
    cercle.appendChild(num);
  }

  const marque = document.createElement("span");
  marque.className = "tuile-marque";
  marque.textContent = "Rummikub";

  d.appendChild(cercle);
  d.appendChild(marque);
  return d;
}

function creerTuileTitre(lettre) {
  const d = document.createElement("div");
  d.className = "tuile-titre" + (lettre === " " ? " espace" : "");
  d.textContent = lettre === " " ? "" : lettre;
  return d;
}

function afficherTitreEnTuiles(texte, container) {
  container.innerHTML = "";
  for (const c of texte) container.appendChild(creerTuileTitre(c));
}

/* ------------------------------------------------------------ avatars SVG
 * Avatars du projet Scrabble (fichiers dans web/avatars/). Ils sont groupés
 * par genre pour pouvoir accorder l'avatar au prénom du joueur (voir
 * genres.js → genrePrénom). Le genre de chaque avatar a été déduit du contenu
 * visuel du SVG : cheveux longs et/ou boucles d'oreilles → féminin ; cheveux
 * courts, casquette, casque, barbe, calvitie → masculin. (Les noms de fichiers
 * étant neutres « avatar-NN », la déduction se fait sur le dessin.)
 */
// Genre déduit du dessin de chaque SVG (voir avatars/) :
//   02 cheveux longs + boucles d'oreilles, 08 nœud dans les cheveux,
//   10 cheveux longs + boucles d'oreilles, 15 bandeau + fleur → féminin.
//   Les autres portent barbe, moustache, casquette, cheveux courts/bouclés
//   ou casque, sans marqueur féminin → masculin.
const AVATARS_F = ["avatar-02", "avatar-08", "avatar-10", "avatar-15"];
const AVATARS_M = ["avatar-01", "avatar-03", "avatar-04", "avatar-05",
                   "avatar-06", "avatar-07", "avatar-09", "avatar-11",
                   "avatar-12", "avatar-13", "avatar-14"];
// Liste ordonnée complète : sert de grille de sélection (l'index reste stable,
// c'est lui qui est persisté dans les réglages via `avatar_index`).
const AVATARS = ["avatar-01", "avatar-02", "avatar-03", "avatar-04", "avatar-05",
                 "avatar-06", "avatar-07", "avatar-08", "avatar-09", "avatar-10",
                 "avatar-11", "avatar-12", "avatar-13", "avatar-14", "avatar-15"];

// Nom de fichier d'avatar pour un index (modulo, tolère les index négatifs).
function avatarPour(i) {
  return AVATARS[((i % AVATARS.length) + AVATARS.length) % AVATARS.length];
}

// Élément <img> pointant vers le SVG d'un avatar (nom SANS extension).
function elementAvatar(nomFichier, className) {
  const img = document.createElement("img");
  if (className) img.className = className;
  img.src = "avatars/" + nomFichier + ".svg";
  img.alt = "";
  return img;
}

// Groupe d'avatars cohérent avec le genre d'un prénom (genres.js). Repli sur
// la liste complète si genres.js absent ou genre inconnu.
function _avatarsPourPrenom(prenom) {
  const g = (typeof genrePrénom === "function") ? genrePrénom(prenom) : "inconnu";
  if (g === "F") return AVATARS_F;
  if (g === "M") return AVATARS_M;
  return AVATARS;
}

// Petit hash déterministe d'une chaîne (avatar stable d'un tour à l'autre).
function _hashChaine(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// Avatar aléatoire du bon genre pour un prénom, en évitant si possible ceux
// déjà attribués (`exclus` = liste de noms de fichiers).
function avatarAleatoirePourPrenom(prenom, exclus) {
  const base = _avatarsPourPrenom(prenom);
  const exset = new Set(exclus || []);
  const libres = base.filter((a) => !exset.has(a));
  const pool = libres.length ? libres : base;
  return pool[Math.floor(Math.random() * pool.length)];
}

// Avatar STABLE (déterministe) du bon genre pour un prénom : même prénom →
// même avatar à chaque affichage (utile en jeu, redessiné souvent).
function avatarStablePourPrenom(prenom) {
  const base = _avatarsPourPrenom(prenom);
  return base[_hashChaine(String(prenom || "")) % base.length];
}
