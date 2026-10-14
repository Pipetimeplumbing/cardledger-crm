const $ = selector => document.querySelector(selector);
const money = cents => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD'}).format(cents / 100);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = {cards:[],clients:[],sales:[],totals:{}}, page='dashboard', editor={};
const titles = {
  dashboard:['WORKSPACE OVERVIEW','Dashboard','Your inventory, customer relationships, and sales performance.','＋ Add cards'],
  inventory:['INVENTORY MANAGEMENT','Card inventory','Manage stock levels, purchase costs, and estimated market values.','＋ Add cards'],
  sales:['SALES MANAGEMENT','Sales & profit','Review transactions, customer purchases, and realized earnings.','＋ Record sale'],
  clients:['CUSTOMER RELATIONSHIPS','Contacts','A complete view of your buyers, contact details, and sales history.','＋ Add contact']
};
function setPage(next) {
  if (!titles[next]) return;
  page=next;
  $('#breadcrumb-page').textContent=next==='dashboard'?'Dashboard':next==='clients'?'Contacts':next==='inventory'?'Inventory':'Sales & profit';
  document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==page);
  document.querySelectorAll('.sidebar [data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  ['#page-eyebrow','#page-title','#page-description','#primary-action'].forEach((id,i)=>$(id).textContent=titles[page][i]);
  history.replaceState(null,'',`#${page}`);
}
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>setPage(el.dataset.page)));
$('#primary-action').onclick=()=>openEditor(page==='sales'?'sale':page==='clients'?'client':'card');
function empty(title,description) {return `<div class="empty"><div class="empty-symbol">◇</div><h3>${escapeHTML(title)}</h3><p>${escapeHTML(description)}</p></div>`;}
function cardTitle(card) {return `${card.player}${card.year?' · '+card.year:''}${card.brand?' '+card.brand:''}`;}
function cardCell(card) {return `<div class="card-name"><span class="card-thumb">${escapeHTML((card.sport||'C').slice(0,1))}</span><div><strong>${escapeHTML(card.player)}</strong><small>${escapeHTML([card.year,card.brand,card.card_number&&'#'+card.card_number,card.grade].filter(Boolean).join(' · '))}</small></div></div>`;}
function salesTable(sales) {
  if (!sales.length) return empty('No sales to show','Record a sale to track revenue, profit, and the cards leaving your collection.');
  return `<table><thead><tr><th>CARD</th><th>DATE / CLIENT</th><th>QTY</th><th>REVENUE</th><th>COST / FEES / SHIPPING</th><th>PROFIT</th></tr></thead><tbody>${sales.map(s=>{
    const profit=s.revenue-s.cost_basis-s.fees-s.shipping;
    return `<tr><td>${cardCell(s)}<small>${escapeHTML(s.channel||'Direct sale')}</small></td><td>${escapeHTML(s.sold_on)}<small>${escapeHTML(s.client_name||'Unassigned buyer')}</small></td><td>${s.quantity}</td><td>${money(s.revenue)}</td><td>${money(s.cost_basis)} / ${money(s.fees)} / ${money(s.shipping)}</td><td class="${profit<0?'loss-text':'profit-text'}">${money(profit)}</td></tr>`;
  }).join('')}</tbody></table>`;
}
function render() {
  const t=state.totals;
  $('#stock-badge').textContent=t.stock;
  $('#metric-stock').textContent=t.stock.toLocaleString();
  $('#metric-unique').textContent=`${t.unique_cards} unique card listings in stock`;
  $('#metric-value').textContent=money(t.market_value);
  $('#metric-revenue').textContent=money(t.revenue);
  $('#metric-sold').textContent=`${t.sold} pieces sold · all time`;
  $('#metric-profit').textContent=money(t.profit);
  $('#cost-basis').textContent=money(t.cost_value);
  $('#value-market').textContent=money(t.market_value);
  $('#value-difference').textContent=money(t.market_value-t.cost_value);
  $('#recent-sales').innerHTML=salesTable(state.sales.slice(0,5));
  renderInventory();renderSales();renderClients();renderChart();renderCRM();
}
function renderInventory() {
  const query=$('#inventory-search').value.toLowerCase();
  const cards=state.cards.filter(c=>(!$('#in-stock-only').checked||c.quantity>0)&&[c.player,c.sport,c.year,c.brand,c.card_number,c.grade].join(' ').toLowerCase().includes(query));
  $('#inventory-table').innerHTML=cards.length?`<table><thead><tr><th>CARD</th><th>SPORT</th><th>IN STOCK</th><th>AVG COST / CARD</th><th>EST. VALUE / CARD</th><th>TOTAL EST. VALUE</th><th>ACTIONS</th></tr></thead><tbody>${cards.map(c=>`<tr><td>${cardCell(c)}</td><td>${escapeHTML(c.sport)}</td><td><span class="badge ${c.quantity?'':'zero'}">${c.quantity} pieces</span></td><td>${c.quantity?money(c.total_cost/c.quantity):'—'}</td><td>${money(c.market_price)}</td><td>${money(c.market_price*c.quantity)}</td><td><div class="mini-actions"><button data-edit-card="${c.id}">Edit</button><button data-restock="${c.id}">Restock</button>${c.quantity?`<button data-sell="${c.id}">Sell</button>`:''}</div></td></tr>`).join('')}</tbody></table>`:empty(state.cards.length?'No matching cards':'Start building your inventory',state.cards.length?'Try another search or change the stock filter.':'Add your first card with its quantity, purchase cost, and estimated value.');
}
function renderSales() {
  const q=$('#sales-search').value.toLowerCase();
  $('#sales-table').innerHTML=salesTable(state.sales.filter(s=>[s.player,s.brand,s.client_name,s.channel].join(' ').toLowerCase().includes(q)));
}
function renderClients() {
  const q=$('#clients-search').value.toLowerCase();
  const clients=state.clients.filter(c=>[c.name,c.email,c.phone].join(' ').toLowerCase().includes(q));
  $('#contact-summary').innerHTML=`<span><strong>${state.clients.length}</strong> total contacts</span><span><strong>${state.clients.filter(c=>c.sale_count>0).length}</strong> purchasing customers</span><span><strong>${clients.length}</strong> matching records</span>`;
  $('#client-grid').innerHTML=clients.length?`<table><thead><tr><th>CONTACT</th><th>EMAIL</th><th>PHONE</th><th>RELATIONSHIP</th><th>TRANSACTIONS</th><th>TOTAL SPEND</th><th>ACTIONS</th></tr></thead><tbody>${clients.map(c=>`<tr><td><button class="contact-name" data-profile="${c.id}"><span class="client-avatar">${initials(c.name)}</span><span><strong>${escapeHTML(c.name)}</strong><small>Contact #${String(c.id).padStart(4,'0')}</small></span></button></td><td>${escapeHTML(c.email||'—')}</td><td>${escapeHTML(c.phone||'—')}</td><td><span class="badge">${c.sale_count?'Customer':'Contact'}</span></td><td>${c.sale_count}</td><td><strong>${money(c.spend)}</strong></td><td><div class="mini-actions"><button data-profile="${c.id}">View record</button><button data-edit-client="${c.id}">Edit</button></div></td></tr>`).join('')}</tbody></table>`:empty('No contacts to show','Add a contact to organize customer details and connect them to sales.');
}
function initials(name) {return escapeHTML(name.split(/\s+/).slice(0,2).map(n=>n[0]).join(''));}
function renderCRM() {
  const top=[...state.clients].filter(c=>c.sale_count>0).sort((a,b)=>b.spend-a.spend).slice(0,4);
  $('#top-clients').innerHTML=top.length?top.map(c=>`<button class="relationship-row" data-profile="${c.id}"><span class="client-avatar">${initials(c.name)}</span><span><strong>${escapeHTML(c.name)}</strong><small>${c.sale_count} transactions</small></span><b>${money(c.spend)} <span>→</span></b></button>`).join(''):empty('Build your customer book','Add contacts and assign them to sales to see your customer relationships here.');
  const events=[...state.cards.map(c=>({date:c.created_at,title:'Inventory added',detail:cardTitle(c),icon:'▥'})),...state.sales.map(s=>({date:s.created_at,title:'Sale recorded',detail:`${s.player} · ${money(s.revenue)} · ${s.client_name||'Unassigned buyer'}`,icon:'↗'}))].sort((a,b)=>b.date.localeCompare(a.date)).slice(0,4);
  $('#activity-feed').innerHTML=events.length?events.map(e=>`<div class="activity-row"><span class="activity-icon">${e.icon}</span><div><strong>${e.title}</strong><p>${escapeHTML(e.detail)}</p><small>${escapeHTML(e.date)} UTC</small></div></div>`).join(''):empty('No activity yet','New card records and sales will appear as you build your business.');
}
function openProfile(id) {
  const c=state.clients.find(c=>c.id===id);if(!c)return;
  const sales=state.sales.filter(s=>s.client_id===id);
  $('#profile-title').textContent=c.name;
  $('#profile-content').innerHTML=`<div class="profile-overview"><span class="client-avatar">${initials(c.name)}</span><div><span class="badge">${c.sale_count?'Customer':'Contact'}</span><p>${escapeHTML(c.email||'No email added')}<br>${escapeHTML(c.phone||'No phone added')}</p></div></div><div class="profile-metrics"><div><small>Transactions</small><strong>${c.sale_count}</strong></div><div><small>Total sales revenue</small><strong>${money(c.spend)}</strong></div><div><small>Pieces purchased</small><strong>${sales.reduce((sum,s)=>sum+s.quantity,0)}</strong></div></div><h3>Contact notes</h3><p class="profile-notes">${escapeHTML(c.notes||'No notes added.')}</p><h3>Purchase history</h3><div class="table-wrap">${salesTable(sales)}</div>`;
  $('#client-profile').showModal();
}
$('#close-profile').onclick=()=>$('#client-profile').close();
document.addEventListener('click',event=>{const button=event.target.closest('[data-profile]');if(button)openProfile(Number(button.dataset.profile));});
$('#quick-client').onclick=()=>openEditor('client');
$('#quick-sale').onclick=()=>openEditor('sale');
$('#global-search-form').addEventListener('submit',event=>{
  event.preventDefault();const scope=$('#global-search-scope').value;setPage(scope);
  $(scope==='clients'?'#clients-search':scope==='sales'?'#sales-search':'#inventory-search').value=$('#global-search').value;
  if(scope==='clients')renderClients();else if(scope==='sales')renderSales();else renderInventory();
});
function renderChart() {
  const now=new Date();const months=[];
  for(let i=5;i>=0;i--){const d=new Date(now.getFullYear(),now.getMonth()-i,1);months.push({key:`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`,label:d.toLocaleString('en-US',{month:'short'}),revenue:0,profit:0});}
  for(const sale of state.sales){const m=months.find(m=>m.key===sale.sold_on.slice(0,7));if(m){m.revenue+=sale.revenue;m.profit+=sale.revenue-sale.cost_basis-sale.fees-sale.shipping;}}
  const max=Math.max(1,...months.flatMap(m=>[m.revenue,Math.abs(m.profit)]));
  $('#chart').innerHTML=months.map(m=>`<div class="chart-month" title="${m.key}: revenue ${money(m.revenue)}, profit ${money(m.profit)}"><div class="chart-bars"><div class="bar" style="height:${m.revenue/max*145}px"></div><div class="bar profit ${m.profit<0?'loss':''}" style="height:${Math.abs(m.profit)/max*145}px"></div></div><span>${m.label}</span></div>`).join('');
  $('#chart').setAttribute('aria-label','Monthly sales and profit chart. Hover or tap a month for amounts; red bars indicate losses.');
}
async function refresh() {
  const response=await fetch('/api/state');if(!response.ok)throw Error('Unable to load your collection. Check that the server is running.');
  state=await response.json();render();
}
const input=(name,label,value='',type='text',extra='')=>`<label class="field">${label}<input name="${name}" type="${type}" value="${escapeHTML(value)}" ${extra}></label>`;
const select=(name,label,options,value='',extra='')=>`<label class="field">${label}<select name="${name}" ${extra}>${options.map(([v,l])=>`<option value="${escapeHTML(v)}" ${String(value)===String(v)?'selected':''}>${escapeHTML(l)}</option>`).join('')}</select></label>`;
const notes=value=>`<label class="field wide">Notes <textarea name="notes" maxlength="3000" rows="3">${escapeHTML(value||'')}</textarea></label>`;
const amount=(name,label,value=0)=>input(name,label,(value/100).toFixed(2),'number','min="0" max="10000000" step="0.01" required');
function openEditor(kind,id=null) {
  editor={kind,id};$('#form-status').textContent='';
  let html='',title='',endpoint='',method='POST';
  if(kind==='card') {
    const card=state.cards.find(c=>c.id===id)||{};
    title=id?'Edit card details':'Add cards to inventory';endpoint=id?`/api/cards/${id}`:'/api/cards';method=id?'PATCH':'POST';
    html=input('player','Player / card name',card.player||'','text','required maxlength="200"')+select('sport','Sport',['Baseball','Basketball','Football','Hockey','Soccer','Other'].map(s=>[s,s]),card.sport||'Baseball')+input('year','Year',card.year||'','text','maxlength="200"')+input('brand','Brand / set',card.brand||'','text','maxlength="200"')+input('card_number','Card number',card.card_number||'','text','maxlength="200"')+input('grade','Grade / condition',card.grade||'','text','placeholder="PSA 10, BGS 9.5, raw…" maxlength="200"');
    if(!id)html+=input('quantity','Pieces purchased',1,'number','min="1" max="1000000" step="1" required')+amount('unit_cost','Purchase cost per card ($)');
    html+=amount('market_price','Estimated market value per card ($)',card.market_price||0)+notes(card.notes)+`<p class="form-help">${id?'Use Restock to add pieces at their purchase cost. Existing sales keep their recorded cost basis.':'Include acquisition costs in your per-card purchase cost. Group only equivalent cards and grades.'} Market estimates are entered manually.</p>`;
  } else if(kind==='restock') {
    const c=state.cards.find(c=>c.id===id);title='Restock cards';endpoint=`/api/cards/${id}/restock`;
    html=`<p class="form-help">${escapeHTML(cardTitle(c))} · ${c.quantity} currently in stock. New purchase costs are added to the remaining inventory cost basis.</p>`+input('quantity','Pieces to add',1,'number','min="1" max="1000000" step="1" required')+amount('unit_cost','Purchase cost per card ($)');
  } else if(kind==='client') {
    const c=state.clients.find(c=>c.id===id)||{};title=id?'Edit client':'Add a client';endpoint=id?`/api/clients/${id}`:'/api/clients';method=id?'PATCH':'POST';
    html=input('name','Client name',c.name||'','text','required maxlength="200"')+input('email','Email',c.email||'','email','maxlength="200"')+input('phone','Phone',c.phone||'','tel','maxlength="200"')+notes(c.notes);
  } else {
    const stock=state.cards.filter(c=>c.quantity>0);
    if(!stock.length){$('#global-status').textContent='Add or restock cards before recording a sale.';setPage('inventory');return;}
    title='Record a sale';endpoint='/api/sales';
    const now=new Date();const today=`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    html=select('card_id','Card',stock.map(c=>[c.id,`${cardTitle(c)} · ${c.grade||'Raw'} · ${c.quantity} in stock`]),id||stock[0].id,'required')+select('client_id','Buyer',[['','Unassigned buyer'],...state.clients.map(c=>[c.id,c.name])])+input('quantity','Pieces sold',1,'number','min="1" max="1000000" step="1" required')+amount('unit_price','Sale price per card ($)')+amount('fees','Total selling fees ($)')+amount('shipping','Total shipping cost ($)')+input('sold_on','Sale date',today,'date',`max="${today}" required`)+input('channel','Sales channel','','text','placeholder="eBay, card show, direct…" maxlength="200"')+notes('')+'<p class="form-help" id="sale-preview"></p><p class="form-help">Recording a sale reduces stock immediately. Fees and shipping are totals for this sale, not per-card amounts. Recorded sales cannot be edited or voided in this version.</p>';
  }
  editor.endpoint=endpoint;editor.method=method;
  $('#modal-title').textContent=title;$('#form-fields').innerHTML=html;$('#save-button').textContent=kind==='sale'?'Record sale':'Save';$('#modal').showModal();
  if(kind==='sale')salePreview();
}
function salePreview() {
  if(editor.kind!=='sale')return;
  const form=$('#editor'),card=state.cards.find(c=>c.id===Number(form.elements.card_id.value));
  const qty=Number(form.elements.quantity.value);const revenue=Math.round(Number(form.elements.unit_price.value)*100)*qty;
  const basis=card.quantity?Math.round(card.total_cost*qty/card.quantity):0;
  const profit=revenue-basis-Math.round(Number(form.elements.fees.value)*100)-Math.round(Number(form.elements.shipping.value)*100);
  $('#sale-preview').textContent=qty>card.quantity?`Only ${card.quantity} pieces are available.`:`Revenue: ${money(revenue)} · Estimated cost basis: ${money(basis)} · Profit: ${money(profit)}`;
}
$('#editor').addEventListener('input',salePreview);
$('#close-modal').onclick=$('#cancel-modal').onclick=()=>$('#modal').close();
$('#editor').addEventListener('submit',async event=>{
  event.preventDefault();const button=$('#save-button');button.disabled=true;$('#form-status').textContent='';
  let saved=false;
  try {
    const response=await fetch(editor.endpoint,{method:editor.method,headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData($('#editor'))))});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Unable to save.');
    saved=true;$('#modal').close();$('#global-status').textContent='';await refresh();
  }catch(error){(saved?$('#global-status'):$('#form-status')).textContent=saved?`Saved successfully, but the display could not refresh. Reload the page. ${error.message}`:error.message;}
  finally{button.disabled=false;}
});
document.addEventListener('click',event=>{
  const button=event.target.closest('[data-edit-card],[data-restock],[data-sell],[data-edit-client]');if(!button)return;
  if(button.dataset.editCard)openEditor('card',Number(button.dataset.editCard));
  if(button.dataset.restock)openEditor('restock',Number(button.dataset.restock));
  if(button.dataset.sell)openEditor('sale',Number(button.dataset.sell));
  if(button.dataset.editClient)openEditor('client',Number(button.dataset.editClient));
});
$('#inventory-search').oninput=$('#in-stock-only').onchange=renderInventory;
$('#sales-search').oninput=renderSales;$('#clients-search').oninput=renderClients;
setPage(location.hash.slice(1)||'dashboard');
refresh().catch(error=>$('#global-status').textContent=error.message);
