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
