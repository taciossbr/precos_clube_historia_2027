const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(value);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const platformNames = {
  amazon: "Amazon",
  estante_virtual: "Estante Virtual",
  mercado_livre: "Mercado Livre",
};
const platformColors = {amazon:"#d5784d",estante_virtual:"#39796f",mercado_livre:"#527aaf"};
const seriesNames = {
  vencedor_geral: "Melhor preço",
  amazon: "Amazon",
  estante_virtual: "Estante Virtual",
  mercado_livre: "Mercado Livre",
};
let productHistory = {};
let currentProduct = null;
let plot = null;
let resizeObserver = null;

function metric(label, value, tone = "") {
  return `<article class="${tone ? `metric-${tone}` : ""}"><span>${safe(label)}</span><strong>${safe(value)}</strong></article>`;
}

function amazonMedian(product, metrics) {
  const platformMedians = metrics.mediana_por_plataforma ?? {};
  if (Object.hasOwn(platformMedians, "amazon")) return platformMedians.amazon;
  if (metrics.mediana_amazon_referencia != null) return metrics.mediana_amazon_referencia;
  const prices = (product.links ?? [])
    .filter(link => link.plataforma === "amazon" && link.status === "sucesso" && link.preco_atual != null)
    .map(link => Number(link.preco_atual))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  if (!prices.length) return null;
  const middle = Math.floor(prices.length / 2);
  return prices.length % 2 ? prices[middle] : (prices[middle - 1] + prices[middle]) / 2;
}

function renderMetrics(product) {
  const metrics = product.metricas_atuais ?? {};
  const amazonMedianValue = amazonMedian(product, metrics);
  const discount = amazonMedianValue > 0 && metrics.menor_preco_geral != null
    ? (amazonMedianValue - metrics.menor_preco_geral) / amazonMedianValue
    : null;
  const discountPercentage = discount == null ? null : Math.round(Math.abs(discount) * 100);
  const discountText = discount == null
    ? "—"
    : discountPercentage === 0
      ? "na normal"
      : `${discountPercentage}% ${discount > 0 ? "abaixo" : "acima"} da normal`;
  const discountTone = discount == null || discountPercentage === 0
    ? "neutral"
    : discount > 0 ? "below" : "above";
  $("#detail-metrics").innerHTML = [
    metric("Melhor preço atual", money(metrics.menor_preco_geral)),
    metric("Plataforma vencedora", platformNames[metrics.plataforma_vencedora] ?? metrics.plataforma_vencedora ?? "—"),
    metric("Média", money(metrics.media)),
    metric("Mediana", money(metrics.mediana)),
    ...Object.entries(metrics.mediana_por_plataforma ?? {}).map(([platform, value]) =>
      metric(`Mediana ${platformNames[platform] ?? platform}`, money(value))
    ),
    ...(metrics.mediana_por_plataforma?.amazon == null && metrics.mediana_amazon_referencia != null
      ? [metric("Mediana Amazon (última válida)", money(metrics.mediana_amazon_referencia))]
      : []),
    metric("Alvo", `${((product.porcentagem_alvo ?? 0) * 100).toFixed(0)}%`),
    metric("Preço vs. normal", discountText, discountTone),
    metric("Prioridade", product.prioridade ?? "—"),
    metric("Falhas consecutivas", product.contador_falhas ?? 0),
  ].join("");
}

function renderPlatformPrices(product) {
  const metrics = product.metricas_atuais ?? {};
  const normalPrices = {...(metrics.mediana_por_plataforma ?? {})};
  if (normalPrices.amazon == null) normalPrices.amazon = amazonMedian(product, metrics);
  const currentPrices = {};
  const currentPriceReused = {};
  for (const link of product.links ?? []) {
    if (link.status !== "sucesso" || link.preco_atual == null) continue;
    const price = Number(link.preco_atual);
    if (Number.isFinite(price) && (currentPrices[link.plataforma] == null || price < currentPrices[link.plataforma])) {
      currentPrices[link.plataforma] = price;
      currentPriceReused[link.plataforma] = link.coletado_nesta_execucao === false;
    }
  }
  const platforms = [...new Set([
    ...(product.links ?? []).map(link => link.plataforma),
    ...Object.keys(normalPrices),
  ])].sort((a, b) => {
    const indexA = Object.keys(platformNames).indexOf(a);
    const indexB = Object.keys(platformNames).indexOf(b);
    return (indexA < 0 ? 99 : indexA) - (indexB < 0 ? 99 : indexB);
  });
  const values = (source, colored = false) => platforms.map(platform =>
    `<div><span>${safe(platformNames[platform] ?? platform)}</span><strong${colored ? ` style="color:${platformColors[platform] ?? "#183039"}"` : ""}>${money(source[platform])}</strong>${colored && currentPriceReused[platform] ? `<small>reutilizado</small>` : ""}</div>`
  ).join("");
  return `<section class="detail-platform-prices" aria-label="Preços normais e atuais por plataforma">
    <div class="detail-platform-price-line"><h2>Preços normais</h2><div>${values(normalPrices)}</div></div>
    <div class="detail-platform-price-line"><h2>Preços atuais</h2><div>${values(currentPrices, true)}</div></div>
  </section>`;
}

function renderExtras(extras) {
  if (!extras || !Object.keys(extras).length) return "";
  const entries = Object.entries(extras).map(([key, value]) => {
    let display = value;
    if (typeof value === "boolean") display = value ? "Sim" : "Não";
    else if (typeof value === "number" && ["valor_sem_frete", "frete_aplicado"].includes(key)) display = money(value);
    return `<div><dt>${safe(key)}</dt><dd>${safe(display)}</dd></div>`;
  }).join("");
  return `<dl class="detail-extras">${entries}</dl>`;
}

function renderCandidate(candidate) {
  const title = candidate.url
    ? `<a href="${safe(candidate.url)}" target="_blank" rel="noopener noreferrer">${safe(candidate.titulo || candidate.url)}</a>`
    : safe(candidate.titulo || "Oferta");
  const price = candidate.preco_total ?? candidate.preco;
  const details = [
    candidate.autor ? `<span>Autor: ${safe(candidate.autor)}</span>` : "",
    candidate.valor_sem_frete != null ? `<span>Livro: ${money(candidate.valor_sem_frete)}</span>` : "",
    candidate.frete_aplicado != null ? `<span>Frete: ${money(candidate.frete_aplicado)}${candidate.frete_presumido ? " (presumido)" : ""}</span>` : "",
  ].filter(Boolean).join("");
  return `<li class="detail-candidate ${candidate.escolhido ? "chosen" : ""}"><div><strong>${title}</strong>${candidate.escolhido ? `<span class="chosen-label">Escolhido</span>` : ""}</div><strong>${money(price)}</strong>${details ? `<div class="candidate-facts">${details}</div>` : ""}</li>`;
}

function renderLink(link) {
  const title = platformNames[link.plataforma] ?? link.plataforma;
  const results = link.top_n_resultados?.length
    ? `<div class="candidate-section"><h3>Resultados da busca (${link.top_n_resultados.length})</h3><ul class="detail-candidates">${link.top_n_resultados.map(renderCandidate).join("")}</ul></div>`
    : "";
  return `<article class="detail-link-card">
    <div class="detail-link-head"><div><h3>${safe(title)}</h3><span class="detail-status ${link.status === "sucesso" ? "" : "error"}">${safe(link.status)}</span></div><strong class="detail-link-price">${money(link.preco_atual)}</strong></div>
    <a class="detail-configured-url" href="${safe(link.url)}" target="_blank" rel="noopener noreferrer">Abrir link configurado</a>
    ${link.titulo ? `<p class="detail-book-title">${safe(link.titulo)}</p>` : ""}
    ${link.comentario ? `<p class="detail-link-comment">${safe(link.comentario)}</p>` : ""}
    <div class="detail-link-facts"><span>${link.pesquisa ? `Pesquisa · top ${safe(link.top_n ?? 1)}` : "Link direto"}</span><span>Falhas consecutivas: ${safe(link.erros_consecutivos ?? 0)}</span>${link.coletado_nesta_execucao === false ? `<span>Dado reutilizado de coleta anterior</span>` : link.coletado_nesta_execucao === true ? `<span>Coletado nesta execução</span>` : ""}</div>
    ${link.erro ? `<p class="link-error">${safe(link.erro)}</p>` : ""}
    ${renderExtras(link.extras)}
    ${results}
  </article>`;
}

function historyPoints(series) {
  const history = series === "vencedor_geral"
    ? productHistory.vencedor_geral
    : productHistory.por_plataforma?.[series];
  return (history ?? [])
    .map(entry => ({time: Date.parse(entry.timestamp) / 1000, price: Number(entry.preco)}))
    .filter(entry => Number.isFinite(entry.time) && Number.isFinite(entry.price));
}

function renderHistory() {
  resizeObserver?.disconnect();
  resizeObserver = null;
  plot?.destroy();
  plot = null;
  const host = $("#detail-chart");
  const series = $("#history-series").value;
  const points = historyPoints(series);
  const metrics = currentProduct?.metricas_atuais ?? {};
  host.innerHTML = "";

  if (!points.length) {
    host.hidden = true;
    $("#history-state").textContent = `Ainda não há histórico para ${seriesNames[series]}.`;
    return;
  }
  if (!window.uPlot) {
    host.hidden = true;
    $("#history-state").textContent = "O gráfico não pôde ser carregado.";
    return;
  }

  $("#history-state").textContent = `${points.length} ${points.length === 1 ? "registro" : "registros"} · ${seriesNames[series]}`;
  host.hidden = false;
  const colors = {vencedor_geral:"#096a6f", amazon:"#d5784d", estante_virtual:"#39796f", mercado_livre:"#527aaf"};
  const times = points.map(point => point.time);
  const amazonMedian = metrics.mediana_por_plataforma?.amazon ?? metrics.mediana_amazon_referencia;
  const data = [
    times,
    points.map(point => point.price),
    times.map(() => metrics.mediana),
    times.map(() => amazonMedian),
  ];
  const chartSeries = [{}, {
    label: seriesNames[series],
    stroke: colors[series],
    width: 2,
    points: {show: true, size: 6, fill: colors[series], stroke: "#fffefa", width: 2},
  },
  {label:"Mediana geral atual",stroke:"#d5784d",width:1,dash:[5,4]},
  {label:"Mediana Amazon",stroke:"#8a5ca8",width:1,dash:[2,3]},
  ];
  plot = new window.uPlot({
    width: host.clientWidth,
    height: 300,
    padding: [10, 10, 0, 0],
    scales: {x: {time: true}, y: {auto: true}},
    series: chartSeries,
    axes: [
      {stroke:"#677a82",grid:{stroke:"#e4e8e6",width:1},ticks:{stroke:"#dae0e0",width:1},size:32,values:(_,ticks)=>{
        const labelEvery=Math.max(1,Math.ceil(ticks.length/5));
        return ticks.map((time,index)=>index===0||index===ticks.length-1||index%labelEvery===0
          ? new Date(time*1000).toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"})
          : "");
      }},
      {stroke:"#677a82",grid:{stroke:"#e4e8e6",width:1},ticks:{stroke:"#dae0e0",width:1},size:82,values:(_,ticks)=>ticks.map(money)},
    ],
    legend: {show: true},
    cursor: {focus: {prox: 16}},
  }, data, host);
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => plot?.setSize({width:host.clientWidth,height:300}));
    resizeObserver.observe(host);
  }
}

function renderProduct(product, record) {
  currentProduct = product;
  document.title = `${product.nome} — Radar de preços`;
  $("#detail-title").textContent = product.nome;
  $("#detail-id").textContent = `ID: ${product.id}`;
  $("#detail-priority").textContent = `Prioridade ${product.prioridade}`;
  $("#detail-comment").textContent = product.comentario || "";
  $("#detail-comment").hidden = !product.comentario;
  const cover = product.capa_url
    ? `<img src="${safe(product.capa_url.startsWith("/") ? `https://www.estantevirtual.com.br${product.capa_url}` : product.capa_url)}" alt="Capa de ${safe(product.nome)}">`
    : `<span>${safe(product.nome)}</span>`;
  $("#detail-cover").innerHTML = cover;
  renderMetrics(product);
  $("#detail-platform-prices").innerHTML = renderPlatformPrices(product);
  $("#detail-links").innerHTML = (product.links ?? []).map(renderLink).join("") || `<p class="empty">Nenhum link configurado.</p>`;
  productHistory = record ?? {};
  $("#history-series").addEventListener("change", renderHistory);
  renderHistory();
  $("#detail-state").hidden = true;
  $("#detail-content").hidden = false;
}

async function init() {
  const productId = new URLSearchParams(window.location.search).get("id");
  if (!productId) {
    $("#detail-state").textContent = "Faltou informar qual livro você quer ver.";
    return;
  }
  try {
    const [snapshot, history] = await Promise.all([
      fetch("consolidado.json").then(response => {if (!response.ok) throw new Error(); return response.json();}),
      fetch("historico.json").then(response => response.ok ? response.json() : {}),
    ]);
    $("#updated").textContent = `ATUALIZADO ${new Date(snapshot.ultima_atualizacao).toLocaleString("pt-BR")}`;
    const product = (snapshot.produtos ?? []).find(item => item.id === productId);
    if (!product) {
      $("#detail-state").textContent = "Livro não encontrado no catálogo.";
      return;
    }
    renderProduct(product, history[product.id]);
  } catch {
    $("#detail-state").textContent = "Não foi possível carregar os dados do livro.";
    $("#updated").textContent = "DADOS INDISPONÍVEIS";
  }
}

init();
