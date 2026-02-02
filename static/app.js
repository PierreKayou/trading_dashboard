async function loadMacro() {
  try {
    const res = await fetch('/api/macro/state');
    const data = await res.json();

    const badge = document.getElementById('macro-badge');
    const regimeLabel = data.macro_regime.label.toLowerCase();

    // Texte badge
    badge.textContent = data.macro_regime.label;

    // Couleur badge
    badge.className = 'badge ' + (
      regimeLabel.includes('risk-off') ? 'risk-off' :
      regimeLabel.includes('risk-on')  ? 'risk-on'  :
      'neutral'
    );

    // Confiance + stabilité
    document.getElementById('macro-confidence').textContent =
      `Confiance ${Math.round(data.macro_regime.confidence * 100)}% · ${data.macro_regime.stability}`;

    // Commentaire
    document.getElementById('macro-commentary').textContent =
      data.commentary;

    // Biais marchés
    document.getElementById('bias-equities').textContent =
      data.market_bias.equities;
    document.getElementById('bias-indices').textContent =
      data.market_bias.indices_us;
    document.getElementById('bias-commodities').textContent =
      data.market_bias.commodities;
    document.getElementById('bias-crypto').textContent =
      data.market_bias.crypto;

  } catch (err) {
    console.error('Erreur chargement macro:', err);
  }
}

// Chargement initial
loadMacro();

// Rafraîchissement toutes les 30 minutes
setInterval(loadMacro, 30 * 60 * 1000);
