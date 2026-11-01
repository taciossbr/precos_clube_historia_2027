const $ = (selector) => document.querySelector(selector);
const money = (value) => value == null ? "—" : new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL"}).format(value);
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
let products = [];
let history = {};
function discount(product) {
  const {menor_preco_geral: price, mediana} = product.metricas_atuais ?? {};
  return price != null && mediana > 0 ? (mediana-price)/mediana : null;
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
  const points=(history[product.id]?.vencedor_geral??[]).map(e=>Number(e.preco)).filter(Number.isFinite);
  if(points.length<2) return "";
  const min=Math.min(...points),max=Math.max(...points),span=max-min||1;
  const coords=points.map((v,i)=>`${8+i*84/(points.length-1)},${58-(v-min)/span*46}`).join(" ");
  return `<details class="history"><summary>Ver variação de preço (${points.length} registros)</summary><svg class="chart" viewBox="0 0 100 68" preserveAspectRatio="none" role="img" aria-label="Gráfico do histórico de preços"><polyline points="${coords}" fill="none" stroke="#527a5d" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${coords.split(" ").at(-1).split(",")[0]}" cy="${coords.split(" ").at(-1).split(",")[1]}" r="3" fill="#d5784d" vector-effect="non-scaling-stroke"/></svg></details>`;
}
function render() {
  const query=$("#search").value.trim().toLocaleLowerCase("pt-BR");
  const visible=sortItems(products).filter(p=>p.nome.toLocaleLowerCase("pt-BR").includes(query));
  $("#result-count").textContent=`${visible.length} ${visible.length===1?"livro":"livros"}`;
  $("#products").innerHTML=visible.length?visible.map(p=>{
    const price=p.metricas_atuais?.menor_preco_geral;
    const links=p.links??[];
    const winner=links.find(l=>l.status==="sucesso"&&l.preco_atual===price)??links.find(l=>l.status==="sucesso");
    const broken=links.some(l=>l.status!=="sucesso");
    const linkRows=links.map(l=>`<div class="link-row"><div class="link-heading"><strong>${safe(l.plataforma)}</strong><span class="status ${l.status==="sucesso"?"":"error"}">${safe(l.status)}</span></div><a href="${safe(l.url)}" target="_blank" rel="noopener noreferrer">${safe(l.url)}</a><div class="link-facts"><span>Preço: ${money(l.preco_atual)}</span><span>Erros seguidos: ${safe(l.erros_consecutivos??0)}</span>${l.pesquisa?`<span>Pesquisa · top ${safe(l.top_n??1)}</span>`:""}</div>${l.titulo?`<p class="link-title">${safe(l.titulo)}</p>`:""}${l.erro?`<p class="link-error">${safe(l.erro)}</p>`:""}${l.comentario?`<p>${safe(l.comentario)}</p>`:""}${l.top_n_resultados?.length?`<ul>${l.top_n_resultados.map(r=>`<li>${r.url?`<a href="${safe(r.url)}" target="_blank" rel="noopener noreferrer">${safe(r.titulo)}</a>`:safe(r.titulo)} — ${money(r.preco_total??r.preco)} ${r.escolhido?"(escolhido)":""}</li>`).join("")}</ul>`:""}</div>`).join("");
    return `<article class="card"><div class="card-head"><div class="title-line"><h3>${safe(p.nome)}</h3><span class="priority-pill">Prioridade ${safe(p.prioridade)}</span></div>${p.capa_url?`<img class="cover-thumb" src="${safe(p.capa_url)}" alt="Capa de ${safe(p.nome)}" loading="lazy">`:""}</div><div class="card-body">${p.comentario?`<p class="comment">${safe(p.comentario)}</p>`:""}<div class="price-row"><strong class="price">${money(price)}</strong><span class="platform">${safe(winner?.plataforma??"sem preço")}</span></div><div class="metrics"><span>Média: ${money(p.metricas_atuais?.media)}</span><span>Mediana: ${money(p.metricas_atuais?.mediana)}</span><span>Alvo: ${((p.porcentagem_alvo??0)*100).toFixed(0)}%</span><span>${discount(p)==null?"":`${(discount(p)*100).toFixed(0)}% abaixo da mediana`}</span></div><div class="product-facts"><span>ID: ${safe(p.id)}</span><span>Falhas do produto: ${safe(p.contador_falhas??0)}</span><span>Vencedora: ${safe(p.metricas_atuais?.plataforma_vencedora??"—")}</span></div><div class="status ${broken?"error":""}">${broken?"Falha em um ou mais links":"Coleta dos links bem-sucedida"}</div><details class="link-details"><summary>Links e resultados (${links.length})</summary>${linkRows||"<p>Sem links configurados.</p>"}</details>${chart(p)}</div></article>`;
  }).join(""):`<p class="empty">Nenhum livro encontrado.</p>`;
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
