const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("vaultrag-token") || "";
let me = null;
let view = "chat";
function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", "Bearer " + token);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  return fetch(path, { ...options, headers, cache: "no-store" }).then(async (r) => {
    const data = r.status === 204 ? null : await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed (" + r.status + ")");
    return data;
  });
}
function msg(id, text, type = "") { $(id).textContent = text || ""; $(id).className = "msg " + type; }
function authView(on) { $("login").classList.toggle("hidden", on); $("workspace").classList.toggle("hidden", !on); $("logout").classList.toggle("hidden", !on); $("user").textContent = on && me ? me.username + " · " + me.role : "Not signed in"; }
function setView(name) {
  view = name;
  document.querySelectorAll(".nav").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  ["chat", "documents", "admin"].forEach((v) => $(v + "-view").classList.toggle("hidden", v !== name));
  $("title").textContent = ({chat:"Ask your documents",documents:"Document library",admin:"Administration"})[name];
  if (token && name === "documents") loadDocuments();
  if (token && name === "admin" && me?.role === "admin") loadAdmin();
}
async function metrics() { const d=await api("/api/metrics");$("docs").textContent=d.indexed_documents;$("chunks").textContent=d.indexed_chunks;$("role").textContent=d.role; }
async function loadDocuments() {
  const rows=await api("/api/documents");const body=$("document-list");body.replaceChildren();
  rows.forEach((d)=>{const tr=document.createElement("tr");[d.filename,d.state,d.visibility,String(d.chunk_count)].forEach((v)=>{const td=document.createElement("td");td.textContent=v;tr.appendChild(td);});const td=document.createElement("td");if(d.can_delete){const b=document.createElement("button");b.className="delete";b.textContent="Delete";b.addEventListener("click",async()=>{if(!confirm("Delete this document and its indexed chunks?"))return;try{await api("/api/documents/"+encodeURIComponent(d.id),{method:"DELETE"});await loadDocuments();await metrics();}catch(e){msg("upload-msg",e.message,"error");}});td.appendChild(b);}tr.appendChild(td);body.appendChild(tr);});
  if(!rows.length){const tr=document.createElement("tr");const td=document.createElement("td");td.colSpan=5;td.textContent="No visible documents.";tr.appendChild(td);body.appendChild(tr);}
}
function renderCitations(rows){const root=$("citations");root.replaceChildren();rows.forEach((r)=>{const card=document.createElement("article");card.className="citation";const title=document.createElement("strong");title.textContent=r.filename;const id=document.createElement("small");id.textContent="["+r.source_id+"] · "+(r.section||"Document");const p=document.createElement("p");p.textContent=r.excerpt;card.append(title,id,p);root.appendChild(card);});}
async function restore(){if(!token){authView(false);return;}try{me=await api("/api/auth/me");authView(true);await metrics();document.querySelector('[data-view="admin"]').classList.toggle("hidden",me.role!=="admin");setView(view);}catch(_){token="";sessionStorage.removeItem("vaultrag-token");authView(false);}}
$("login-form").addEventListener("submit",async(e)=>{e.preventDefault();msg("login-msg","Signing in…");try{const r=await api("/api/auth/login",{method:"POST",body:JSON.stringify({username:$("username").value,password:$("password").value})});token=r.access_token;sessionStorage.setItem("vaultrag-token",token);$("password").value="";await restore();}catch(err){msg("login-msg",err.message,"error");}});
$("logout").addEventListener("click",()=>{token="";me=null;sessionStorage.removeItem("vaultrag-token");authView(false);});
document.querySelectorAll(".nav").forEach((b)=>b.addEventListener("click",()=>setView(b.dataset.view)));
$("chat-form").addEventListener("submit",async(e)=>{e.preventDefault();const b=e.submitter;b.disabled=true;msg("chat-msg","Retrieving evidence and querying the local model…");$("answer").classList.add("hidden");$("citations").replaceChildren();try{const r=await api("/api/chat",{method:"POST",body:JSON.stringify({question:$("question").value})});$("answer").textContent=r.answer;$("answer").classList.remove("hidden");renderCitations(r.citations||[]);msg("chat-msg","Retrieved "+r.retrieved_count+" chunk(s) · "+r.latency_ms+" ms","success");}catch(err){msg("chat-msg",err.message,"error");}finally{b.disabled=false;}});
$("visibility").addEventListener("change",()=>$("group-label").classList.toggle("hidden",$("visibility").value!=="groups"));
$("upload-form").addEventListener("submit",async(e)=>{e.preventDefault();const f=$("file").files[0];if(!f)return;const data=new FormData();data.append("file",f);data.append("visibility",$("visibility").value);data.append("groups_csv",$("groups").value);msg("upload-msg","Parsing and indexing locally…");try{const r=await api("/api/documents",{method:"POST",body:data});msg("upload-msg","Indexed "+r.filename+" ("+r.chunk_count+" chunks).","success");$("file").value="";await loadDocuments();await metrics();}catch(err){msg("upload-msg",err.message,"error");}});
$("user-form").addEventListener("submit",async(e)=>{e.preventDefault();const data={username:$("new-username").value,password:$("new-password").value,role:$("new-role").value,groups:$("new-groups").value.split(",").map((x)=>x.trim()).filter(Boolean)};try{const u=await api("/api/admin/users",{method:"POST",body:JSON.stringify(data)});msg("user-msg","Created "+u.username+".","success");$("user-form").reset();await loadAdmin();}catch(err){msg("user-msg",err.message,"error");}});
async function loadAdmin(){if(me?.role!=="admin")return;const [users,events]=await Promise.all([api("/api/admin/users"),api("/api/audit?limit=80")]);const ul=$("users");ul.replaceChildren();users.forEach((u)=>{const d=document.createElement("div");d.textContent=u.username+" · "+u.role;const s=document.createElement("small");s.textContent="Groups: "+(u.groups||[]).join(", ");d.appendChild(s);ul.appendChild(d);});const al=$("audit");al.replaceChildren();events.forEach((e)=>{const d=document.createElement("div");d.textContent=e.action+" · "+e.outcome;const s=document.createElement("small");s.textContent=e.created_at+" · "+e.entity_type;d.appendChild(s);al.appendChild(d);});}
fetch("/api/health",{cache:"no-store"}).then((r)=>r.json()).then((h)=>{$("health").textContent="Database "+h.database+" · local model "+h.local_model;}).catch(()=>$("health").textContent="Health status unavailable");
authView(false);restore();
