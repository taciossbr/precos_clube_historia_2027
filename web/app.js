const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(value);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const platformNames = {amazon:"Amazon",estante_virtual:"Estante Virtual",mercado_livre:"Mercado Livre"};
const platformColors = {amazon:"#d5784d",estante_virtual:"#39796f",mercado_livre:"#527aaf"};
let products = [];
let history = {};
let chartInstances = [];
function discount(product) {
  const metrics = product.metricas_atuais ?? {};
  const price = metrics.menor_preco_geral;
  const mediana = amazonMedian(product);
  return price != null && mediana > 0 ? (mediana-price)/mediana : null;
}
function discountLabel(value) {
  if (value == null || Math.abs(value) < 0.03) return null;
  const percentage = Math.round(Math.abs(value) * 100);
  if (percentage === 0) return null;
  return value > 0
    ? {text:`${percentage}% abaixo da normal`, tone:"below"}
    : {text:`${percentage}% acima da normal`, tone:"above"};
}
function amazonMedian(product) {
  const metrics = product.metricas_atuais ?? {};
  if (Object.hasOwn(metrics.mediana_por_plataforma ?? {}, "amazon")) {
    return metrics.mediana_por_plataforma.amazon;
  }
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
function sortItems(items) {
  const sort = $("#sort").value;
  const title = (a,b) => a.nome.localeCompare(b.nome,"pt-BR");
  return [...items].sort((a,b) => {
    const ap=a.prioridade??Infinity,bp=b.prioridade??Infinity;
    const av=a.metricas_atuais?.menor_preco_geral,bv=b.metricas_atuais?.menor_preco_geral;
    if(sort==="priority") return ap-bp;
    if(sort==="price-asc") return (av??Infinity)-(bv??Infinity);
    if(sort==="price-desc") return (bv??-Infinity)-(av??-Infinity);
    if(sort==="title-asc") return title(a,b);
    if(sort==="title-desc") return title(b,a);
    if(sort==="discount-desc") return (discount(b)??-Infinity)-(discount(a)??-Infinity);
    if(sort==="discount-asc") return (discount(a)??Infinity)-(discount(b)??Infinity);
    return 0;
  });
}
function chart(product) {
  const points=(history[product.id]?.vencedor_geral??[]).filter(e=>Number.isFinite(Date.parse(e.timestamp))&&Number.isFinite(Number(e.preco)));
  if(points.length<2) return "";
  return `<details class="history" data-product-id="${safe(product.id)}"><summary>Ver variação de preço (${points.length} registros)</summary><div class="price-chart" role="img" aria-label="Gráfico do histórico de preços de ${safe(product.nome)}"></div></details>`;
}
function clearCharts() {
  chartInstances.forEach(({plot,observer})=>{observer?.disconnect();plot.destroy()});
  chartInstances=[];
}
function mountCharts() {
  document.querySelectorAll(".history[data-product-id]").forEach(details=>{
    details.addEventListener("toggle",()=>{
      if(!details.open||details.dataset.chartReady||!window.uPlot) return;
      const points=(history[details.dataset.productId]?.vencedor_geral??[]).filter(e=>Number.isFinite(Date.parse(e.timestamp))&&Number.isFinite(Number(e.preco)));
      const host=details.querySelector(".price-chart");
      const product=products.find(item=>item.id===details.dataset.productId);
      const metrics=product?.metricas_atuais??{};
      const times=points.map(e=>Date.parse(e.timestamp)/1000);
      const amazonMedian=metrics.mediana_por_plataforma?.amazon??metrics.mediana_amazon_referencia;
      const data=[times,points.map(e=>Number(e.preco)),times.map(()=>metrics.mediana),times.map(()=>amazonMedian)];
      const plot=new window.uPlot({
        width:host.clientWidth,
        height:190,
        padding:[8,8,0,0],
        scales:{x:{time:true},y:{auto:true}},
        series:[{},
          {label:"Melhor preço",stroke:"#096a6f",width:2,points:{show:true,size:5,fill:"#d5784d",stroke:"#fffefa",width:2}},
          {label:"Mediana geral atual",stroke:"#d5784d",width:1,dash:[5,4]},
          {label:"Mediana Amazon",stroke:"#8a5ca8",width:1,dash:[2,3]},
        ],
        axes:[
          {stroke:"#677a82",grid:{stroke:"#dae0e0",width:1},ticks:{stroke:"#dae0e0",width:1},size:12,values:(_,ticks)=>ticks.map(()=>"")},
          {stroke:"#677a82",grid:{stroke:"#dae0e0",width:1},ticks:{stroke:"#dae0e0",width:1},size:78,values:(_,ticks)=>ticks.map(money)},
        ],
        legend:{show:true},
        cursor:{focus:{prox:16}},
      },data,host);
      details.dataset.chartReady="true";
      const observer=window.ResizeObserver?new ResizeObserver(()=>plot.setSize({width:host.clientWidth,height:190})):null;
      observer?.observe(host);
      chartInstances.push({plot,observer});
    });
  });
}
function renderProductCard(product) {
  const metrics = product.metricas_atuais ?? {};
  const links = product.links ?? [];
  const price = metrics.menor_preco_geral;
  const winner = links.find(link => link.status === "sucesso" && link.preco_atual === price && link.plataforma === metrics.plataforma_vencedora)
    ?? links.find(link => link.status === "sucesso");
  const winnerUrl = winner?.top_n_resultados?.find(result => result.escolhido && result.url)?.url ?? winner?.url;
  const hasFailures = links.some(link => link.status !== "sucesso");
  const medians = {...(metrics.mediana_por_plataforma ?? {})};
  if (medians.amazon == null) medians.amazon = amazonMedian(product);
  const platformIds = [...new Set([
    ...links.map(link => link.plataforma),
    ...Object.keys(medians),
  ])].sort((a, b) => {
    const indexA = Object.keys(platformNames).indexOf(a);
    const indexB = Object.keys(platformNames).indexOf(b);
    return (indexA < 0 ? 99 : indexA) - (indexB < 0 ? 99 : indexB);
  });
  const currentPrices = {};
  for (const link of links) {
    if (link.status !== "sucesso" || link.preco_atual == null) continue;
    const value = Number(link.preco_atual);
    if (Number.isFinite(value) && (currentPrices[link.plataforma] == null || value < currentPrices[link.plataforma])) {
      currentPrices[link.plataforma] = value;
    }
  }
  const renderPlatformValues = (values, colored = false) => platformIds.map(platform =>
    `<div><span>${safe(platformNames[platform] ?? platform)}</span><strong${colored ? ` style="color:${platformColors[platform] ?? "#183039"}"` : ""}>${money(values[platform])}</strong></div>`
  ).join("");
  const percentage = product.porcentagem_alvo ?? 0.20;
  const targetAmount = product.alvo_real != null
    ? product.alvo_real
    : amazonMedian(product) == null ? null : amazonMedian(product) * (1 - percentage);
  const targetHtml = targetAmount == null
    ? "—"
    : product.alvo_real != null
      ? `<span class="real-target">${money(targetAmount)}</span>`
      : `${money(targetAmount)}*`;
  const discountInfo = discountLabel(discount(product));
  const linkRows = links.map(link =>
    `<div class="link-row"><div class="link-heading"><strong>${safe(platformNames[link.plataforma] ?? link.plataforma)}</strong><span class="status ${link.status === "sucesso" ? "" : "error"}">${safe(link.status)}</span></div><a href="${safe(link.url)}" target="_blank" rel="noopener noreferrer">${safe(link.url)}</a><div class="link-facts"><span>Preço: ${money(link.preco_atual)}</span><span>Erros seguidos: ${safe(link.erros_consecutivos ?? 0)}</span>${link.pesquisa ? `<span>Pesquisa · top ${safe(link.top_n ?? 1)}</span>` : ""}</div>${link.titulo ? `<p class="link-title">${safe(link.titulo)}</p>` : ""}${link.erro ? `<p class="link-error">${safe(link.erro)}</p>` : ""}${link.comentario ? `<p>${safe(link.comentario)}</p>` : ""}${link.top_n_resultados?.length ? `<ul>${link.top_n_resultados.map(result => `<li>${result.url ? `<a href="${safe(result.url)}" target="_blank" rel="noopener noreferrer">${safe(result.titulo)}</a>` : safe(result.titulo)} — ${money(result.preco_total ?? result.preco)} ${result.escolhido ? "(escolhido)" : ""}</li>`).join("")}</ul>` : ""}</div>`
  ).join("");

  return `<article class="card">
    <header class="card-head">
      <div class="card-title"><h3>${safe(product.nome)}</h3><span class="priority-pill">Prioridade ${safe(product.prioridade)}</span></div>
      <div class="priority-cover">${product.capa_url ? `<img class="cover-thumb" src="${safe(product.capa_url)}" alt="Capa de ${safe(product.nome)}" loading="lazy">` : `<div class="cover-empty">Sem capa</div>`}</div>
    </header>
    <div class="card-body">
      ${product.comentario ? `<p class="comment">${safe(product.comentario)}</p>` : ""}
      <section class="metrics" aria-label="Métricas e alvo">
        <div><span>Média:</span><strong>${money(metrics.media)}</strong></div>
        <div><span>Mediana:</span><strong>${money(metrics.mediana)}</strong></div>
        <div><span>Alvo:</span><strong>${(percentage * 100).toFixed(0)}% (${targetHtml})</strong></div>
      </section>
      <section class="platform-price-summary" aria-label="Preços por plataforma">
        <div class="platform-price-line"><h4>Preços normais</h4><div class="platform-price-values">${renderPlatformValues(medians)}</div></div>
        <div class="platform-price-line"><h4>Preços atuais</h4><div class="platform-price-values">${renderPlatformValues(currentPrices, true)}</div></div>
      </section>
      <section class="product-facts"><span><b>ID:</b> ${safe(product.id)}</span><span><b>Falhas:</b> ${safe(product.contador_falhas ?? 0)}</span><span><b>Vencedor atual:</b> ${safe(metrics.plataforma_vencedora ? platformNames[metrics.plataforma_vencedora] ?? metrics.plataforma_vencedora : "—")}</span></section>
      <div class="status ${hasFailures ? "error" : ""}">${hasFailures ? "Falha em um ou mais links" : "Coleta com Sucesso"}</div>
      <details class="link-details"><summary>Links e resultado (${links.length})</summary>${linkRows || `<p>Sem links configurados.</p>`}</details>
      ${chart(product)}
      ${discountInfo ? `<p class="discount-summary discount-${discountInfo.tone}">${discountInfo.text}</p>` : ""}
      <div class="card-actions"><a class="details-button" href="detalhes.html?id=${encodeURIComponent(product.id)}">Ver detalhes</a>${winnerUrl ? `<a class="buy" href="${safe(winnerUrl)}" target="_blank" rel="noopener noreferrer">Ver oferta escolhida</a>` : ""}</div>
    </div>
  </article>`;
}
function render() {
  clearCharts();
  const query=$("#search").value.trim().toLocaleLowerCase("pt-BR");
  const visible=sortItems(products).filter(p=>p.nome.toLocaleLowerCase("pt-BR").includes(query));
  $("#result-count").textContent=`${visible.length} ${visible.length===1?"livro":"livros"}`;
  $("#products").innerHTML=visible.length?visible.map(renderProductCard).join(""):`<p class="empty">Nenhum livro encontrado.</p>`;
  mountCharts();
}
async function init(){
  try{
    const [snapshot,hist]=await Promise.all([fetch("consolidado.json").then(r=>{if(!r.ok)throw Error();return r.json()}),fetch("historico.json").then(r=>r.ok?r.json():{})]);
    products=snapshot.produtos??[];history=hist;
    $("#updated").textContent=`ATUALIZADO ${new Date(snapshot.ultima_atualizacao).toLocaleString("pt-BR")}`;
    $("#total").textContent=snapshot.estatisticas_gerais?.total_produtos??products.length;
    $("#priced").textContent=snapshot.estatisticas_gerais?.produtos_com_preco??products.filter(p=>p.metricas_atuais?.menor_preco_geral!=null).length;
    $("#failed").textContent=snapshot.estatisticas_gerais?.produtos_com_falha??"—";
    const best=products.filter(p=>p.metricas_atuais?.menor_preco_geral!=null).sort((a,b)=>a.metricas_atuais.menor_preco_geral-b.metricas_atuais.menor_preco_geral)[0];
    $("#best").textContent=best?money(best.metricas_atuais.menor_preco_geral):"—";
    $("#best-title").textContent=best?.nome??"sem ofertas disponíveis";
    render();
  }catch{$("#products").innerHTML='<p class="empty">Não foi possível carregar os dados. Tente atualizar a página.</p>';$("#updated").textContent="DADOS INDISPONÍVEIS";}
}
$("#search").addEventListener("input",render);$("#sort").addEventListener("change",render);init();
