const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(value);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const platformNames = {
  amazon: "Amazon",
  estante_virtual: "Estante Virtual",
  mercado_livre: "Mercado Livre",
};
const seriesNames = {
  vencedor_geral: "Melhor preço",
  amazon: "Amazon",
  estante_virtual: "Estante Virtual",
  mercado_livre: "Mercado Livre",
};
let productHistory = {};
let plot = null;
let resizeObserver = null;

function metric(label, value) {
  return `<article><span>${safe(label)}</span><strong>${safe(value)}</strong></article>`;
}

function renderMetrics(product) {
  const metrics = product.metricas_atuais ?? {};
  const discount = metrics.mediana > 0 && metrics.menor_preco_geral != null
    ? `${(((metrics.mediana - metrics.menor_preco_geral) / metrics.mediana) * 100).toFixed(0)}%`
    : "—";
  $("#detail-metrics").innerHTML = [
    metric("Melhor preço atual", money(metrics.menor_preco_geral)),
    metric("Plataforma vencedora", platformNames[metrics.plataforma_vencedora] ?? metrics.plataforma_vencedora ?? "—"),
    metric("Média", money(metrics.media)),
    metric("Mediana", money(metrics.mediana)),
    metric("Alvo", `${((product.porcentagem_alvo ?? 0) * 100).toFixed(0)}%`),
    metric("Abaixo da mediana", discount),
    metric("Prioridade", product.prioridade ?? "—"),
    metric("Falhas consecutivas", product.contador_falhas ?? 0),
  ].join("");
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
    <div class="detail-link-facts"><span>${link.pesquisa ? `Pesquisa · top ${safe(link.top_n ?? 1)}` : "Link direto"}</span><span>Falhas consecutivas: ${safe(link.erros_consecutivos ?? 0)}</span></div>
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
  plot = new window.uPlot({
    width: host.clientWidth,
    height: 300,
    padding: [10, 10, 0, 0],
    scales: {x: {time: true}, y: {auto: true}},
    series: [{}, {
      label: seriesNames[series],
      stroke: colors[series],
      width: 2,
      points: {show: true, size: 6, fill: colors[series], stroke: "#fffefa", width: 2},
    }],
    axes: [
      {stroke:"#677a82",grid:{stroke:"#e4e8e6",width:1},ticks:{stroke:"#dae0e0",width:1},size:32,values:(_,ticks)=>{
        const labelEvery=Math.max(1,Math.ceil(ticks.length/5));
        return ticks.map((time,index)=>index===0||index===ticks.length-1||index%labelEvery===0
          ? new Date(time*1000).toLocaleDateString("pt-BR",{day:"2-digit",month:"2-digit"})
          : "");
      }},
      {stroke:"#677a82",grid:{stroke:"#e4e8e6",width:1},ticks:{stroke:"#dae0e0",width:1},size:82,values:(_,ticks)=>ticks.map(money)},
    ],
    legend: {show: false},
    cursor: {focus: {prox: 16}},
  }, [points.map(point=>point.time), points.map(point=>point.price)], host);
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => plot?.setSize({width:host.clientWidth,height:300}));
    resizeObserver.observe(host);
  }
}

function renderProduct(product, record) {
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
