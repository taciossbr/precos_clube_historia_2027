const $ = (selector) => document.querySelector(selector);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const platformNames = {
  amazon: "Amazon",
  estante_virtual: "Estante Virtual",
  mercado_livre: "Mercado Livre",
};

function renderProduct(product) {
  const rows = (product.links ?? []).map((link) => {
    const tipo = link.pesquisa
      ? `Pesquisa · até ${safe(link.top_n ?? 1)} resultados`
      : "Link direto";
    return `
      <li class="configured-link-row">
        <div class="configured-link-info">
          <strong>${safe(platformNames[link.plataforma] ?? link.plataforma)}</strong>
          <span>${tipo}</span>
        </div>
        <a class="configured-link-open" href="${safe(link.url)}" target="_blank" rel="noopener noreferrer">Abrir link ↗</a>
        <code>${safe(link.url)}</code>
        ${link.comentario ? `<p>${safe(link.comentario)}</p>` : ""}
      </li>`;
  }).join("");

  return `<article class="configured-product-card">
    <header><h3>${safe(product.nome)}</h3><span>Prioridade ${safe(product.prioridade)}</span></header>
    ${product.comentario ? `<p class="configured-product-comment">${safe(product.comentario)}</p>` : ""}
    <ul>${rows}</ul>
  </article>`;
}

async function init() {
  try {
    const response = await fetch("links-configurados.json");
    if (!response.ok) throw new Error("Falha ao carregar links-configurados.json");
    const products = await response.json();
    const totalLinks = products.reduce((total, product) => total + (product.links ?? []).length, 0);

    $("#result-count").textContent = `${products.length} ${products.length === 1 ? "produto" : "produtos"} · ${totalLinks} ${totalLinks === 1 ? "link" : "links"}`;
    $("#configured-links").innerHTML = products.length
      ? products.map(renderProduct).join("")
      : '<p class="empty">Nenhum produto configurado.</p>';
  } catch {
    $("#configured-links").innerHTML = '<p class="empty">Não foi possível carregar a configuração.</p>';
  }
}

init();
