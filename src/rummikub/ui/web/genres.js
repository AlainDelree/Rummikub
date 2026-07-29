"use strict";

/*
 * genres.js — détection du genre d'un prénom français (fichier AUTONOME).
 *
 * Ne dépend d'AUCUN autre fichier : il est conçu pour être copié TEL QUEL
 * dans un autre projet (ex. Scrabble) sans la moindre modification.
 *
 * Expose :
 *   - PRENOMS_MASCULINS : liste de prénoms masculins courants
 *   - PRENOMS_FEMININS  : liste de prénoms féminins courants
 *   - genrePrénom(prenom) → "M" | "F" | "inconnu"
 *     (alias ASCII : genrePrenom, pour les contextes où l'accent gêne)
 *
 * Chargement : soit via <script src="genres.js"> (les symboles deviennent
 * globaux), soit via require() sous Node (module.exports).
 */

const PRENOMS_MASCULINS = [
  "Adam", "Adrien", "Alain", "Albert", "Alexandre", "Alexis", "André",
  "Antoine", "Arnaud", "Arthur", "Aurélien", "Axel", "Baptiste", "Bastien",
  "Benjamin", "Benoît", "Bernard", "Bruno", "Cédric", "Charles", "Christian",
  "Christophe", "Clément", "Cyril", "Damien", "Daniel", "David", "Denis",
  "Didier", "Dylan", "Edgar", "Édouard", "Émile", "Emmanuel", "Enzo", "Éric",
  "Étienne", "Fabien", "Fabrice", "Félix", "Ferdinand", "Florent", "Florian",
  "Francis", "François", "Franck", "Frédéric", "Gabriel", "Gaël", "Gaspard",
  "Geoffroy", "Georges", "Gérard", "Gilbert", "Gilles", "Grégoire", "Grégory",
  "Guillaume", "Guy", "Henri", "Hervé", "Hugo", "Jacques", "Jean", "Jérémy",
  "Jérôme", "Joël", "Jonathan", "Jordan", "José", "Joseph", "Julien", "Jules",
  "Kevin", "Kylian", "Laurent", "Léo", "Léon", "Lionel", "Loïc", "Louis",
  "Luc", "Lucas", "Ludovic", "Marc", "Marcel", "Martin", "Mathéo", "Mathias",
  "Mathis", "Mathieu", "Matthieu", "Maxime", "Maxence", "Michel", "Mickaël",
  "Nathan", "Nicolas", "Noah", "Noé", "Olivier", "Pascal", "Patrick", "Paul",
  "Philippe", "Pierre", "Quentin", "Raphaël", "Raymond", "Régis", "Rémi",
  "Rémy", "René", "Richard", "Robert", "Robin", "Rodolphe", "Roger", "Roland",
  "Romain", "Ronan", "Sacha", "Samuel", "Sébastien", "Serge", "Simon",
  "Stéphane", "Sylvain", "Théo", "Thibault", "Thibaut", "Thierry", "Thomas",
  "Timothée", "Tristan", "Valentin", "Victor", "Vincent", "William", "Xavier",
  "Yann", "Yanis", "Yohan", "Yves",
];

const PRENOMS_FEMININS = [
  "Adèle", "Adeline", "Agathe", "Agnès", "Alice", "Aline", "Alix", "Amandine",
  "Amélie", "Anaïs", "Andrée", "Angèle", "Anne", "Annie", "Antoinette",
  "Ariane", "Aurélie", "Aurore", "Axelle", "Béatrice", "Bérénice", "Blanche",
  "Brigitte", "Camille", "Capucine", "Caroline", "Catherine", "Cécile",
  "Céline", "Chantal", "Charlotte", "Chloé", "Christelle", "Christiane",
  "Christine", "Claire", "Clara", "Clarisse", "Claude", "Claudine", "Clémence",
  "Colette", "Constance", "Coralie", "Corinne", "Delphine", "Denise", "Diane",
  "Dominique", "Dorothée", "Édith", "Éléonore", "Élisabeth", "Élise", "Ella",
  "Élodie", "Éloïse", "Émeline", "Emma", "Emmanuelle", "Estelle", "Eugénie",
  "Éva", "Fanny", "Fabienne", "Florence", "Françoise", "Gabrielle", "Gaëlle",
  "Geneviève", "Georgette", "Ginette", "Gisèle", "Hélène", "Héloïse", "Henriette",
  "Inès", "Irène", "Isabelle", "Jacqueline", "Jade", "Jeanne", "Jeannine",
  "Jenny", "Jessica", "Joëlle", "Joséphine", "Josette", "Josiane", "Judith",
  "Julie", "Juliette", "Justine", "Karine", "Laetitia", "Laure", "Laurence",
  "Léa", "Léonie", "Lilou", "Lina", "Lise", "Lorraine", "Louise", "Lucie",
  "Lucile", "Ludivine", "Lydie", "Madeleine", "Maëlys", "Manon", "Margaux",
  "Marguerite", "Marianne", "Marie", "Marine", "Marion", "Marlène", "Marthe",
  "Martine", "Maryse", "Mathilde", "Maud", "Mélanie", "Mélissa", "Michèle",
  "Mireille", "Monique", "Morgane", "Muriel", "Myriam", "Nadège", "Nadine",
  "Nathalie", "Nicole", "Nina", "Noémie", "Océane", "Odette", "Olivia",
  "Ophélie", "Pauline", "Paulette", "Peggy", "Perrine", "Prune", "Raphaëlle",
  "Raymonde", "Régine", "Renée", "Rose", "Roseline", "Rosalie", "Sabine",
  "Sabrina", "Salomé", "Sandra", "Sandrine", "Sarah", "Séverine", "Simone",
  "Solange", "Sonia", "Sophie", "Stéphanie", "Suzanne", "Sylvie", "Thérèse",
  "Valentine", "Valérie", "Vanessa", "Véronique", "Victoire", "Violette",
  "Virginie", "Viviane", "Yolande", "Zoé",
];

/** Retire les accents/diacritiques (é → e, ç → c, …). */
function _sansAccents(s) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/** Clé de comparaison : minuscule, sans accents, espaces de bordure ôtés. */
function _clePrenom(p) {
  return _sansAccents(String(p == null ? "" : p).trim().toLowerCase());
}

const _MASCULINS_SET = new Set(PRENOMS_MASCULINS.map(_clePrenom));
const _FEMININS_SET = new Set(PRENOMS_FEMININS.map(_clePrenom));

/**
 * Détermine le genre d'un prénom.
 * @param {string} prenom - prénom brut (accents, casse et espaces tolérés ;
 *   les prénoms composés « Jean-Pierre », « Marie Claire » sont acceptés).
 * @returns {"M"|"F"|"inconnu"}
 */
function genrePrénom(prenom) {
  const cle = _clePrenom(prenom);
  if (!cle) return "inconnu";
  // On teste le prénom entier puis son premier composant (avant espace,
  // trait d'union ou apostrophe), pour couvrir les prénoms composés.
  const candidats = [cle, cle.split(/[ \-']/)[0]];
  for (const c of candidats) {
    if (!c) continue;
    if (_MASCULINS_SET.has(c)) return "M";
    if (_FEMININS_SET.has(c)) return "F";
  }
  return "inconnu";
}

// Alias sans accent, pratique quand un identifiant accentué est malvenu.
const genrePrenom = genrePrénom;

// Publication : navigateur (variables globales via <script>) + Node (require).
if (typeof window !== "undefined") {
  window.PRENOMS_MASCULINS = PRENOMS_MASCULINS;
  window.PRENOMS_FEMININS = PRENOMS_FEMININS;
  window.genrePrénom = genrePrénom;
  window.genrePrenom = genrePrenom;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { PRENOMS_MASCULINS, PRENOMS_FEMININS, genrePrénom, genrePrenom };
}
