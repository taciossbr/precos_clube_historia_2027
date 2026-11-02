const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(value);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const platformNames = {amazon:"Amazon",estante_virtual:"Estante Virtual",mercado_livre:"Mercado Livre"};
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
  if (value == null) return null;
  const percentage = Math.round(Math.abs(value) * 100);
  if (percentage === 0) return {text:"na normal", tone:"neutral"};
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
function render() {
  clearCharts();
  const query=$("#search").value.trim().toLocaleLowerCase("pt-BR");
  const visible=sortItems(products).filter(p=>p.nome.toLocaleLowerCase("pt-BR").includes(query));
  $("#result-count").textContent=`${visible.length} ${visible.length===1?"livro":"livros"}`;
  $("#products").innerHTML=visible.length?visible.map(p=>{
    const price=p.metricas_atuais?.menor_preco_geral;
    const links=p.links??[];
    const winner=links.find(l=>l.status==="sucesso"&&l.preco_atual===price&&l.plataforma===p.metricas_atuais?.plataforma_vencedora)??links.find(l=>l.status==="sucesso");
    const winnerUrl=winner?.top_n_resultados?.find(r=>r.escolhido&&r.url)?.url??winner?.url;
    const broken=links.some(l=>l.status!=="sucesso");
    const platformMedians=Object.entries(p.metricas_atuais?.mediana_por_plataforma??{}).map(([platform,value])=>`<span>Mediana ${safe(platformNames[platform]??platform)}: ${money(value)}</span>`).join("");
    const amazonMedianReference=p.metricas_atuais?.mediana_por_plataforma?.amazon==null&&p.metricas_atuais?.mediana_amazon_referencia!=null?`<span>Mediana Amazon (última válida): ${money(p.metricas_atuais.mediana_amazon_referencia)}</span>`:"";
    const discountInfo=discountLabel(discount(p));
    const linkRows=links.map(l=>`<div class="link-row"><div class="link-heading"><strong>${safe(l.plataforma)}</strong><span class="status ${l.status==="sucesso"?"":"error"}">${safe(l.status)}</span></div><a href="${safe(l.url)}" target="_blank" rel="noopener noreferrer">${safe(l.url)}</a><div class="link-facts"><span>Preço: ${money(l.preco_atual)}</span><span>Erros seguidos: ${safe(l.erros_consecutivos??0)}</span>${l.pesquisa?`<span>Pesquisa · top ${safe(l.top_n??1)}</span>`:""}</div>${l.titulo?`<p class="link-title">${safe(l.titulo)}</p>`:""}${l.erro?`<p class="link-error">${safe(l.erro)}</p>`:""}${l.comentario?`<p>${safe(l.comentario)}</p>`:""}${l.top_n_resultados?.length?`<ul>${l.top_n_resultados.map(r=>`<li>${r.url?`<a href="${safe(r.url)}" target="_blank" rel="noopener noreferrer">${safe(r.titulo)}</a>`:safe(r.titulo)} — ${money(r.preco_total??r.preco)} ${r.escolhido?"(escolhido)":""}</li>`).join("")}</ul>`:""}</div>`).join("");
    return `<article class="card"><div class="card-head"><div class="title-line"><h3>${safe(p.nome)}</h3><span class="priority-pill">Prioridade ${safe(p.prioridade)}</span></div>${p.capa_url?`<img class="cover-thumb" src="${safe(p.capa_url)}" alt="Capa de ${safe(p.nome)}" loading="lazy">`:""}</div><div class="card-body">${p.comentario?`<p class="comment">${safe(p.comentario)}</p>`:""}<div class="price-row"><strong class="price">${money(price)}</strong><span class="platform">${safe(winner?.plataforma??"sem preço")}</span></div><div class="metrics"><span>Média: ${money(p.metricas_atuais?.media)}</span><span>Mediana: ${money(p.metricas_atuais?.mediana)}</span>${platformMedians}${amazonMedianReference}<span>Alvo: ${((p.porcentagem_alvo??0)*100).toFixed(0)}%</span></div><div class="product-facts"><span>ID: ${safe(p.id)}</span><span>Falhas do produto: ${safe(p.contador_falhas??0)}</span><span>Vencedora: ${safe(p.metricas_atuais?.plataforma_vencedora??"—")}</span></div><div class="status ${broken?"error":""}">${broken?"Falha em um ou mais links":"Coleta dos links bem-sucedida"}</div><details class="link-details"><summary>Links e resultados (${links.length})</summary>${linkRows||"<p>Sem links configurados.</p>"}</details>${chart(p)}<a class="details-button" href="detalhes.html?id=${encodeURIComponent(p.id)}">Ver detalhes</a>${winnerUrl?`<a class="buy" href="${safe(winnerUrl)}" target="_blank" rel="noopener noreferrer">Ver oferta escolhida</a>`:""}${discountInfo?`<p class="discount-summary discount-${discountInfo.tone}">${discountInfo.text}</p>`:""}</div></article>`;
  }).join(""):`<p class="empty">Nenhum livro encontrado.</p>`;
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
