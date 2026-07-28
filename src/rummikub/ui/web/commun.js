function toast(msg, type = "info") {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.className = "visible" + (type !== "info" ? " " + type : "");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.className = "", 3000);
}

function creerTuileJeu(valeur, couleur) {
  const d = document.createElement("div");
  d.className = "tuile-jeu" + (couleur ? " " + couleur : " joker");
  d.dataset.valeur = valeur; d.dataset.couleur = couleur || "joker";
  if (couleur) {
    d.textContent = valeur;
    const mini = document.createElement("span");
    mini.className = "tuile-valeur-mini";
    mini.textContent = valeur; d.appendChild(mini);
  } else {
    d.textContent = "★";
  }
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
