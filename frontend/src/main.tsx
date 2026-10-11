import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bell, CalendarDays, CheckCircle2, ChevronDown, CircleDot, Clock3,
  FolderKanban, Gauge, LayoutDashboard, ListChecks, Menu, MoreHorizontal,
  Plus, Search, Settings, Sparkles, Users, X, Zap
} from "lucide-react";
import "./styles.css";

type Status = "Backlog" | "In progress" | "Review" | "Done";
type Priority = "High" | "Medium" | "Low";
type Task = { id:number; title:string; project:string; status:Status; priority:Priority; due:string; assignee:string; initials:string };

type View = "Dashboard" | "My Tasks" | "Projects" | "Calendar" | "Team" | "Reports" | "Settings";

const initialTasks: Task[] = [
  { id:1, title:"Polish onboarding experience", project:"Website Redesign", status:"In progress", priority:"High", due:"Oct 12", assignee:"Aarav", initials:"AS" },
  { id:2, title:"Finalize API error states", project:"Mobile App", status:"Review", priority:"Medium", due:"Oct 13", assignee:"Meera", initials:"MK" },
  { id:3, title:"Prepare release notes", project:"Website Redesign", status:"Backlog", priority:"Low", due:"Oct 15", assignee:"Rohan", initials:"RS" },
  { id:4, title:"QA payment workflow", project:"Mobile App", status:"Done", priority:"High", due:"Oct 10", assignee:"Pushpender", initials:"PC" },
  { id:5, title:"Build usage dashboard", project:"Analytics", status:"In progress", priority:"Medium", due:"Oct 17", assignee:"Nisha", initials:"NG" },
  { id:6, title:"Audit permissions", project:"Workspace", status:"Backlog", priority:"High", due:"Oct 18", assignee:"Kabir", initials:"KV" }
];

const projects = [
  {name:"Website Redesign", color:"violet", progress:72, tasks:18, members:5},
  {name:"Mobile App", color:"blue", progress:46, tasks:24, members:7},
  {name:"Analytics", color:"cyan", progress:61, tasks:12, members:4},
  {name:"Workspace", color:"amber", progress:33, tasks:9, members:3},
];

function App(){
  const [view,setView]=useState<View>("Dashboard");
  const [tasks,setTasks]=useState<Task[]>(initialTasks);
  const [query,setQuery]=useState("");
  const [apiStatus,setApiStatus]=useState("checking");
  const [modal,setModal]=useState(false);
  const [mobile,setMobile]=useState(false);

  useEffect(()=>{ fetch("/api/health/").then(r=>r.json()).then(d=>setApiStatus(d.status||"unknown")).catch(()=>setApiStatus("offline")); },[]);

  const visibleTasks=useMemo(()=>tasks.filter(t=>`${t.title} ${t.project}`.toLowerCase().includes(query.toLowerCase())),[tasks,query]);

  function addTask(title:string, project:string, priority:Priority){
    if(!title.trim()) return;
    setTasks(v=>[{id:Date.now(), title, project, status:"Backlog", priority, due:"Oct 20", assignee:"You", initials:"YO"},...v]);
    setModal(false);
  }

  const nav:[View,React.ReactNode][]=[
    ["Dashboard",<LayoutDashboard size={18}/>],["My Tasks",<ListChecks size={18}/>],["Projects",<FolderKanban size={18}/>],
    ["Calendar",<CalendarDays size={18}/>],["Team",<Users size={18}/>],["Reports",<Gauge size={18}/>],["Settings",<Settings size={18}/>]
  ];

  return <div className="app-shell">
    <aside className={`sidebar ${mobile?"open":""}`}>
      <div className="brand"><div className="brand-mark"><Zap size={18}/></div><span>Taskautomation</span><button className="icon-btn mobile-close" onClick={()=>setMobile(false)}><X size={20}/></button></div>
      <div className="workspace"><div className="workspace-avatar">TS</div><div><strong>Tech Spectra</strong><small>Product workspace</small></div><ChevronDown size={16}/></div>
      <nav>{nav.map(([name,icon])=><button key={name} className={view===name?"active":""} onClick={()=>{setView(name);setMobile(false)}}>{icon}<span>{name}</span>{name==="My Tasks"&&<b>6</b>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="upgrade"><Sparkles size={17}/><strong>Built for your server</strong><span>Self-hosted, private and under your control.</span></div>
        <a href="/admin/" className="admin-link">Internal admin</a>
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <button className="icon-btn menu-btn" onClick={()=>setMobile(true)}><Menu size={20}/></button>
        <div className="search"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search tasks, projects, people..."/><kbd>⌘ K</kbd></div>
        <div className="top-actions"><div className={`api-pill ${apiStatus}`}>{apiStatus==="ok"?"System online":apiStatus}</div><button className="icon-btn"><Bell size={19}/><i/></button><div className="profile">PC</div></div>
      </header>

      <section className="content">
        <div className="page-heading"><div><span className="eyebrow">WORKSPACE</span><h1>{view}</h1><p>{view==="Dashboard"?"A clear view of what is moving, blocked and due next.":`Manage your ${view.toLowerCase()} from one place.`}</p></div><button className="primary-btn" onClick={()=>setModal(true)}><Plus size={18}/> New task</button></div>
        {view==="Dashboard" && <Dashboard tasks={visibleTasks} setView={setView}/>} 
        {view==="My Tasks" && <TaskTable tasks={visibleTasks}/>} 
        {view==="Projects" && <Projects tasks={visibleTasks}/>} 
        {view==="Calendar" && <Placeholder icon={<CalendarDays size={34}/>} title="Calendar" text="Timeline and due-date planning will live here."/>}
        {view==="Team" && <Team/>}
        {view==="Reports" && <Reports tasks={tasks}/>} 
        {view==="Settings" && <SettingsView apiStatus={apiStatus}/>} 
      </section>
    </main>
    {modal && <NewTaskModal close={()=>setModal(false)} add={addTask}/>} 
  </div>
}

function Dashboard({tasks,setView}:{tasks:Task[],setView:(v:View)=>void}){
  const done=tasks.filter(t=>t.status==="Done").length;
  const active=tasks.filter(t=>t.status==="In progress").length;
  return <>
    <div className="stats-grid">
      <Stat label="Open tasks" value={tasks.length-done} trend="+4 this week" icon={<ListChecks/>}/>
      <Stat label="In progress" value={active} trend="Across 3 projects" icon={<CircleDot/>}/>
      <Stat label="Completed" value={done+24} trend="87% on time" icon={<CheckCircle2/>}/>
      <Stat label="Due soon" value={3} trend="Next 48 hours" icon={<Clock3/>}/>
    </div>
    <div className="dashboard-grid">
      <section className="panel projects-panel"><div className="panel-head"><div><h2>Project progress</h2><p>Current delivery health</p></div><button onClick={()=>setView("Projects")}>View all</button></div>
        <div className="project-list">{projects.map(p=><div className="project-row" key={p.name}><div className={`project-icon ${p.color}`}>{p.name[0]}</div><div className="project-info"><div><strong>{p.name}</strong><span>{p.progress}%</span></div><div className="progress"><i style={{width:`${p.progress}%`}}/></div><small>{p.tasks} tasks · {p.members} members</small></div></div>)}</div>
      </section>
      <section className="panel focus-panel"><div className="panel-head"><div><h2>Today</h2><p>Your focus list</p></div><MoreHorizontal size={19}/></div>{tasks.slice(0,4).map(t=><TaskMini key={t.id} task={t}/>)}</section>
    </div>
    <section className="panel board-preview"><div className="panel-head"><div><h2>Team board</h2><p>Latest work across projects</p></div><button onClick={()=>setView("Projects")}>Open board</button></div><Kanban tasks={tasks}/></section>
  </>
}

function Stat({label,value,trend,icon}:{label:string,value:number,trend:string,icon:React.ReactNode}){return <div className="stat-card"><div className="stat-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{trend}</small></div></div>}
function TaskMini({task}:{task:Task}){return <div className="task-mini"><span className={`priority ${task.priority.toLowerCase()}`}/><div><strong>{task.title}</strong><small>{task.project} · {task.due}</small></div><div className="avatar">{task.initials}</div></div>}

function Projects({tasks}:{tasks:Task[]}){return <><div className="project-cards">{projects.map(p=><div className="project-card" key={p.name}><div className={`project-icon ${p.color}`}>{p.name[0]}</div><div className="project-title"><strong>{p.name}</strong><MoreHorizontal size={18}/></div><p>{p.tasks} tasks · {p.members} members</p><div className="progress"><i style={{width:`${p.progress}%`}}/></div><span>{p.progress}% complete</span></div>)}</div><section className="panel board-full"><div className="panel-head"><div><h2>Project board</h2><p>Drag-and-drop workflow foundation</p></div></div><Kanban tasks={tasks}/></section></>}

function Kanban({tasks}:{tasks:Task[]}){const statuses:Status[]=["Backlog","In progress","Review","Done"]; return <div className="kanban">{statuses.map(s=><div className="column" key={s}><div className="column-head"><span><i className={`status-dot ${s.replace(" ","-").toLowerCase()}`}/>{s}</span><b>{tasks.filter(t=>t.status===s).length}</b></div>{tasks.filter(t=>t.status===s).map(t=><div className="task-card" key={t.id}><div className="task-meta"><span className={`tag ${t.priority.toLowerCase()}`}>{t.priority}</span><MoreHorizontal size={16}/></div><strong>{t.title}</strong><p>{t.project}</p><div className="task-foot"><span><CalendarDays size={14}/>{t.due}</span><div className="avatar">{t.initials}</div></div></div>)}</div>)}</div>}

function TaskTable({tasks}:{tasks:Task[]}){return <section className="panel table-panel"><div className="table-row table-head"><span>Task</span><span>Project</span><span>Status</span><span>Priority</span><span>Due</span><span>Owner</span></div>{tasks.map(t=><div className="table-row" key={t.id}><span><strong>{t.title}</strong></span><span>{t.project}</span><span><em className={`status-badge ${t.status.replace(" ","-").toLowerCase()}`}>{t.status}</em></span><span><em className={`tag ${t.priority.toLowerCase()}`}>{t.priority}</em></span><span>{t.due}</span><span className="owner"><div className="avatar">{t.initials}</div>{t.assignee}</span></div>)}</section>}

function Team(){const people=["Pushpender Chaudhary","Aarav Sharma","Meera Kapoor","Rohan Singh","Nisha Gupta","Kabir Verma"];return <div className="team-grid">{people.map((p,i)=><div className="person-card" key={p}><div className="person-avatar">{p.split(" ").map(x=>x[0]).slice(0,2).join("")}</div><strong>{p}</strong><span>{i===0?"Workspace owner":"Team member"}</span><div className="person-stats"><b>{12-i}</b><small>Open tasks</small></div></div>)}</div>}
function Reports({tasks}:{tasks:Task[]}){return <div className="reports-grid"><section className="panel report-main"><h2>Delivery overview</h2><div className="bars">{projects.map(p=><div key={p.name}><span>{p.name}</span><div><i style={{width:`${p.progress}%`}}/></div><b>{p.progress}%</b></div>)}</div></section><section className="panel report-side"><h2>Task health</h2><div className="big-number">{Math.round(tasks.filter(t=>t.status==="Done").length/Math.max(tasks.length,1)*100)}%</div><p>Current visible completion rate</p></section></div>}
function SettingsView({apiStatus}:{apiStatus:string}){return <div className="settings-grid"><section className="panel settings-card"><h2>Workspace</h2><label>Workspace name<input defaultValue="Tech Spectra"/></label><label>Default timezone<input defaultValue="Asia/Kolkata"/></label><button className="primary-btn">Save changes</button></section><section className="panel settings-card"><h2>System</h2><div className="setting-line"><span>Backend API</span><b className={apiStatus==="ok"?"success":"danger"}>{apiStatus}</b></div><div className="setting-line"><span>Deployment</span><b>Self-hosted</b></div><div className="setting-line"><span>Database</span><b>PostgreSQL</b></div></section></div>}
function Placeholder({icon,title,text}:{icon:React.ReactNode,title:string,text:string}){return <div className="placeholder">{icon}<h2>{title}</h2><p>{text}</p></div>}

function NewTaskModal({close,add}:{close:()=>void,add:(t:string,p:string,pr:Priority)=>void}){const [title,setTitle]=useState("");const [project,setProject]=useState(projects[0].name);const [priority,setPriority]=useState<Priority>("Medium");return <div className="modal-backdrop" onMouseDown={close}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><div><span className="eyebrow">QUICK CREATE</span><h2>New task</h2></div><button className="icon-btn" onClick={close}><X size={20}/></button></div><label>Task name<input autoFocus value={title} onChange={e=>setTitle(e.target.value)} placeholder="What needs to be done?"/></label><label>Project<select value={project} onChange={e=>setProject(e.target.value)}>{projects.map(p=><option key={p.name}>{p.name}</option>)}</select></label><label>Priority<select value={priority} onChange={e=>setPriority(e.target.value as Priority)}><option>Low</option><option>Medium</option><option>High</option></select></label><div className="modal-actions"><button className="secondary-btn" onClick={close}>Cancel</button><button className="primary-btn" onClick={()=>add(title,project,priority)}><Plus size={17}/>Create task</button></div></div></div>}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
