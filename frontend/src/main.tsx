import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BarChart3, CheckCircle2, ChevronRight, CircleUserRound, FolderKanban, LayoutDashboard, ListTodo, LogOut, Menu, Plus, Search, Settings, Users, X } from "lucide-react";
import "./styles.css";

type User = { id: number; name: string; email: string; role?: string };
type Project = { id: number; name: string; description: string; status: string; start_date: string | null; end_date: string | null; progress: number; task_count: number; completed_count: number; members: User[] };
type Task = { id: number; project_id: number; project_name: string; title: string; description: string; status: string; priority: string; start_date: string | null; due_date: string | null; assignees: User[] };
type Dashboard = { stats: { projects: number; tasks: number; completed: number; overdue: number; members: number }; projects: Project[]; my_tasks: Task[] };
type MembersData = { members: User[]; invitations: { id: number; email: string; role: string; token: string }[] };

const API = "/api";
const tokenKey = "taskautomation_token";

function api(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem(tokenKey);
  return fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...(options.headers || {}),
    },
  }).then(async (response) => {
    const body = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`);
    return body;
  });
}

function Login({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const result = await api("/auth/login/", { method: "POST", body: JSON.stringify({ email, password }) });
      localStorage.setItem(tokenKey, result.token);
      onLogin();
    } catch (err: any) { setError(err.message); }
    finally { setLoading(false); }
  }

  return <div className="auth-page">
    <div className="auth-card">
      <div className="brand large"><span className="brand-mark">T</span><span>Taskautomation</span></div>
      <h1>Welcome back</h1>
      <p>Sign in with the administrator email and password you entered during installation.</p>
      <form onSubmit={submit} className="form-stack">
        <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus /></label>
        <label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        {error && <div className="error-box">{error}</div>}
        <button className="primary-btn full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  </div>;
}

function AcceptInvite({ invite, onAccepted }: { invite: string; onAccepted: () => void }) {
  const [info, setInfo] = useState<any>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api(`/invitations/${invite}/`).then(setInfo).catch((e) => setError(e.message)); }, [invite]);
  async function submit(e: FormEvent) {
    e.preventDefault(); setError("");
    try {
      const result = await api(`/invitations/${invite}/`, { method: "POST", body: JSON.stringify({ name, password }) });
      localStorage.setItem(tokenKey, result.token); window.history.replaceState({}, "", "/"); onAccepted();
    } catch (e: any) { setError(e.message); }
  }
  return <div className="auth-page"><div className="auth-card">
    <div className="brand large"><span className="brand-mark">T</span><span>Taskautomation</span></div>
    <h1>Join workspace</h1>
    {info && <p>You were invited as <strong>{info.email}</strong> to <strong>{info.workspace}</strong>.</p>}
    <form className="form-stack" onSubmit={submit}>
      <label>Your name<input value={name} onChange={e => setName(e.target.value)} required /></label>
      <label>Create password<input type="password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} required /></label>
      {error && <div className="error-box">{error}</div>}
      <button className="primary-btn full">Accept invitation</button>
    </form>
  </div></div>;
}

function Modal({ title, children, onClose }: any) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={e => e.stopPropagation()}>
    <div className="modal-head"><h2>{title}</h2><button className="icon-btn" onClick={onClose}><X size={18}/></button></div>{children}
  </div></div>;
}

function App() {
  const [authenticated, setAuthenticated] = useState(!!localStorage.getItem(tokenKey));
  const [me, setMe] = useState<any>(null);
  const [page, setPage] = useState("dashboard");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [membersData, setMembersData] = useState<MembersData>({ members: [], invitations: [] });
  const [activeProjectId, setActiveProjectId] = useState<number | null>(null);
  const [projectModal, setProjectModal] = useState(false);
  const [taskModal, setTaskModal] = useState(false);
  const [inviteModal, setInviteModal] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [error, setError] = useState("");

  const inviteToken = new URLSearchParams(location.search).get("invite");
  if (inviteToken && !authenticated) return <AcceptInvite invite={inviteToken} onAccepted={() => setAuthenticated(true)} />;

  const loadAll = async () => {
    if (!localStorage.getItem(tokenKey)) return;
    try {
      const [meData, dash, projectData, taskData, memberData] = await Promise.all([
        api("/auth/me/"), api("/dashboard/"), api("/projects/"), api("/tasks/"), api("/members/")
      ]);
      setMe(meData); setDashboard(dash); setProjects(projectData); setTasks(taskData); setMembersData(memberData);
      if (!activeProjectId && projectData.length) setActiveProjectId(projectData[0].id);
      setAuthenticated(true); setError("");
    } catch (e: any) {
      if (/Invalid token|credentials|Authentication/i.test(e.message)) { localStorage.removeItem(tokenKey); setAuthenticated(false); }
      else setError(e.message);
    }
  };

  useEffect(() => { if (authenticated) loadAll(); }, [authenticated]);

  const activeProject = projects.find(p => p.id === activeProjectId) || null;
  const projectTasks = tasks.filter(t => t.project_id === activeProjectId);
  const statuses = [
    ["todo", "To do"], ["in_progress", "In progress"], ["review", "Review"], ["done", "Done"]
  ];

  function logout() { localStorage.removeItem(tokenKey); setAuthenticated(false); setMe(null); }
  if (!authenticated) return <Login onLogin={() => setAuthenticated(true)} />;

  async function createProject(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const fd = new FormData(e.currentTarget);
    try {
      const project = await api("/projects/", { method: "POST", body: JSON.stringify({
        name: fd.get("name"), description: fd.get("description"), start_date: fd.get("start_date") || null, end_date: fd.get("end_date") || null,
        member_ids: fd.getAll("members").map(Number)
      }) });
      setProjectModal(false); setActiveProjectId(project.id); setPage("board"); await loadAll();
    } catch (e: any) { setError(e.message); }
  }

  async function createTask(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const fd = new FormData(e.currentTarget);
    const projectId = Number(fd.get("project_id") || activeProjectId);
    try {
      await api("/tasks/", { method: "POST", body: JSON.stringify({
        project_id: projectId, title: fd.get("title"), description: fd.get("description"), priority: fd.get("priority"), due_date: fd.get("due_date") || null,
        assignee_ids: fd.getAll("assignees").map(Number)
      }) });
      setTaskModal(false); await loadAll();
    } catch (e: any) { setError(e.message); }
  }

  async function inviteMember(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const fd = new FormData(e.currentTarget);
    try {
      const result = await api("/members/", { method: "POST", body: JSON.stringify({ email: fd.get("email"), role: fd.get("role") }) });
      setInviteModal(false); await loadAll();
      if (result.invite_url) navigator.clipboard?.writeText(result.invite_url).catch(() => {});
    } catch (e: any) { setError(e.message); }
  }

  async function setTaskStatus(task: Task, status: string) {
    try { await api(`/tasks/${task.id}/`, { method: "PATCH", body: JSON.stringify({ status }) }); await loadAll(); }
    catch (e: any) { setError(e.message); }
  }

  const nav = [
    ["dashboard", "Dashboard", LayoutDashboard], ["projects", "Projects", FolderKanban], ["tasks", "My Tasks", ListTodo], ["board", "Board", CheckCircle2], ["team", "Team", Users], ["reports", "Reports", BarChart3]
  ] as const;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
      <div className="brand"><span className="brand-mark">T</span><span>Taskautomation</span><button className="mobile-close" onClick={() => setMobileNav(false)}><X/></button></div>
      <div className="workspace-card"><div><span className="workspace-label">WORKSPACE</span><strong>{me?.workspace?.name || "Workspace"}</strong></div><ChevronRight size={16}/></div>
      <nav>{nav.map(([id, label, Icon]) => <button key={id} className={page === id ? "active" : ""} onClick={() => { setPage(id); setMobileNav(false); }}><Icon size={18}/><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><button onClick={() => setPage("settings")}><Settings size={18}/>Settings</button><button onClick={logout}><LogOut size={18}/>Sign out</button></div>
    </aside>

    <main className="main-area">
      <header className="topbar">
        <button className="menu-btn" onClick={() => setMobileNav(true)}><Menu/></button>
        <div className="search"><Search size={17}/><input placeholder="Search projects and tasks" /></div>
        <button className="profile"><CircleUserRound size={24}/><span>{me?.user?.name || me?.user?.email}</span></button>
      </header>
      <section className="content">
        {error && <div className="error-box global">{error}<button onClick={() => setError("")}><X size={14}/></button></div>}

        {page === "dashboard" && <>
          <div className="page-head"><div><p className="eyebrow">OVERVIEW</p><h1>Dashboard</h1><p>Real-time progress from your workspace data.</p></div><div className="head-actions"><button className="secondary-btn" onClick={() => setProjectModal(true)}><Plus size={17}/>New project</button><button className="primary-btn" onClick={() => setTaskModal(true)} disabled={!projects.length}><Plus size={17}/>New task</button></div></div>
          <div className="stats-grid">
            {[['Projects', dashboard?.stats.projects || 0], ['Open tasks', (dashboard?.stats.tasks || 0) - (dashboard?.stats.completed || 0)], ['Completed', dashboard?.stats.completed || 0], ['Overdue', dashboard?.stats.overdue || 0], ['Members', dashboard?.stats.members || 0]].map(([label, value]) => <div className="stat-card" key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}
          </div>
          <div className="section-head"><h2>Projects</h2><button className="link-btn" onClick={() => setPage("projects")}>View all</button></div>
          {!projects.length ? <Empty title="No projects yet" text="Create your first project to start organizing work." action="Create project" onAction={() => setProjectModal(true)} /> : <div className="project-grid">{projects.slice(0,6).map(p => <ProjectCard key={p.id} project={p} onOpen={() => { setActiveProjectId(p.id); setPage("board"); }}/>)}</div>}
          <div className="section-head"><h2>My tasks</h2></div>
          <TaskTable tasks={dashboard?.my_tasks || []} onStatus={setTaskStatus}/>
        </>}

        {page === "projects" && <>
          <div className="page-head"><div><p className="eyebrow">WORKSPACE</p><h1>Projects</h1><p>Create projects and track progress from completed tasks.</p></div><button className="primary-btn" onClick={() => setProjectModal(true)}><Plus size={17}/>New project</button></div>
          {!projects.length ? <Empty title="No projects yet" text="Your workspace starts empty—no demo data is added." action="Create your first project" onAction={() => setProjectModal(true)}/> : <div className="project-grid">{projects.map(p => <ProjectCard key={p.id} project={p} onOpen={() => { setActiveProjectId(p.id); setPage("board"); }}/>)}</div>}
        </>}

        {page === "tasks" && <>
          <div className="page-head"><div><p className="eyebrow">YOUR WORK</p><h1>Tasks</h1><p>Tasks assigned to you or created by you.</p></div><button className="primary-btn" onClick={() => setTaskModal(true)} disabled={!projects.length}><Plus size={17}/>New task</button></div>
          <TaskTable tasks={tasks.filter(t => t.assignees.some(a => a.id === me?.user?.id) || !t.assignees.length)} onStatus={setTaskStatus}/>
        </>}

        {page === "board" && <>
          <div className="page-head"><div><p className="eyebrow">KANBAN</p><h1>{activeProject?.name || "Project board"}</h1><p>{activeProject ? `${activeProject.progress}% complete · ${activeProject.task_count} tasks` : "Create a project to start using the board."}</p></div><div className="head-actions"><select className="project-select" value={activeProjectId || ""} onChange={e => setActiveProjectId(Number(e.target.value))}><option value="">Select project</option>{projects.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select><button className="primary-btn" onClick={() => setTaskModal(true)} disabled={!activeProject}><Plus size={17}/>Add task</button></div></div>
          {!activeProject ? <Empty title="No project selected" text="Create or select a project to manage its tasks." action="Create project" onAction={() => setProjectModal(true)}/> : <div className="board">{statuses.map(([key,label]) => <div className="board-column" key={key}><div className="column-head"><strong>{label}</strong><span>{projectTasks.filter(t => t.status === key).length}</span></div>{projectTasks.filter(t => t.status === key).map(task => <div className="task-card" key={task.id}><span className={`priority ${task.priority}`}>{task.priority}</span><h3>{task.title}</h3>{task.due_date && <p>Due {task.due_date}</p>}<div className="assignee-row"><span>{task.assignees.map(a => a.name).join(", ") || "Unassigned"}</span><select value={task.status} onChange={e => setTaskStatus(task, e.target.value)}>{statuses.map(([s,l]) => <option value={s} key={s}>{l}</option>)}</select></div></div>)}</div>)}</div>}
        </>}

        {page === "team" && <>
          <div className="page-head"><div><p className="eyebrow">PEOPLE</p><h1>Team</h1><p>Invite people and manage workspace access.</p></div><button className="primary-btn" onClick={() => setInviteModal(true)}><Plus size={17}/>Invite member</button></div>
          <div className="panel"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead><tbody>{membersData.members.map(m => <tr key={m.id}><td>{m.name}</td><td>{m.email}</td><td><span className="badge">{m.role}</span></td></tr>)}</tbody></table></div>
          {!!membersData.invitations.length && <><div className="section-head"><h2>Pending invitations</h2></div><div className="panel"><table><thead><tr><th>Email</th><th>Role</th><th>Status</th></tr></thead><tbody>{membersData.invitations.map(i => <tr key={i.id}><td>{i.email}</td><td>{i.role}</td><td><span className="badge muted">Pending</span></td></tr>)}</tbody></table></div></>}
        </>}

        {page === "reports" && <>
          <div className="page-head"><div><p className="eyebrow">ANALYTICS</p><h1>Reports</h1><p>Live project completion based on your task data.</p></div></div>
          {!projects.length ? <Empty title="No report data" text="Reports appear as you create projects and tasks."/> : <div className="panel report-list">{projects.map(p => <div className="report-row" key={p.id}><div><strong>{p.name}</strong><span>{p.completed_count} of {p.task_count} tasks complete</span></div><div className="progress-wrap"><div className="progress"><span style={{width:`${p.progress}%`}}/></div><b>{p.progress}%</b></div></div>)}</div>}
        </>}

        {page === "settings" && <><div className="page-head"><div><p className="eyebrow">WORKSPACE</p><h1>Settings</h1><p>Workspace and account information.</p></div></div><div className="panel settings-grid"><div><span>Workspace</span><strong>{me?.workspace?.name}</strong></div><div><span>Your role</span><strong>{me?.workspace?.role}</strong></div><div><span>Account</span><strong>{me?.user?.email}</strong></div><div><span>Backend admin</span><a href="/admin/" target="_blank">Open Django admin</a></div></div></>}
      </section>
    </main>

    {projectModal && <Modal title="Create project" onClose={() => setProjectModal(false)}><form className="form-stack" onSubmit={createProject}><label>Project name<input name="name" required autoFocus/></label><label>Description<textarea name="description" rows={3}/></label><div className="form-grid"><label>Start date<input type="date" name="start_date"/></label><label>End date<input type="date" name="end_date"/></label></div>{membersData.members.length > 1 && <fieldset><legend>Project members</legend>{membersData.members.map(m => <label className="check" key={m.id}><input type="checkbox" name="members" value={m.id}/>{m.name} <small>{m.email}</small></label>)}</fieldset>}<button className="primary-btn full">Create project</button></form></Modal>}

    {taskModal && <Modal title="Create task" onClose={() => setTaskModal(false)}><form className="form-stack" onSubmit={createTask}><label>Project<select name="project_id" defaultValue={activeProjectId || projects[0]?.id}>{projects.map(p => <option value={p.id} key={p.id}>{p.name}</option>)}</select></label><label>Task title<input name="title" required autoFocus/></label><label>Description<textarea name="description" rows={3}/></label><div className="form-grid"><label>Priority<select name="priority" defaultValue="medium"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label>Due date<input type="date" name="due_date"/></label></div><fieldset><legend>Assignees</legend>{membersData.members.map(m => <label className="check" key={m.id}><input type="checkbox" name="assignees" value={m.id}/>{m.name} <small>{m.email}</small></label>)}</fieldset><button className="primary-btn full">Create task</button></form></Modal>}

    {inviteModal && <Modal title="Invite team member" onClose={() => setInviteModal(false)}><form className="form-stack" onSubmit={inviteMember}><label>Email<input type="email" name="email" required autoFocus/></label><label>Role<select name="role"><option value="member">Member</option><option value="admin">Admin</option></select></label><p className="form-help">If SMTP is configured, an invitation email is sent automatically. The invitation also appears under Pending invitations.</p><button className="primary-btn full">Send invitation</button></form></Modal>}
  </div>;
}

function Empty({ title, text, action, onAction }: any) { return <div className="empty"><div className="empty-icon"><FolderKanban/></div><h3>{title}</h3><p>{text}</p>{action && <button className="primary-btn" onClick={onAction}><Plus size={16}/>{action}</button>}</div>; }
function ProjectCard({ project, onOpen }: { project: Project; onOpen: () => void }) { return <button className="project-card" onClick={onOpen}><div className="project-top"><span className="project-icon">{project.name.slice(0,1).toUpperCase()}</span><span className="badge">{project.status.replace('_',' ')}</span></div><h3>{project.name}</h3><p>{project.description || "No description"}</p><div className="progress"><span style={{width:`${project.progress}%`}}/></div><div className="project-meta"><span>{project.progress}% complete</span><span>{project.completed_count}/{project.task_count} tasks</span></div></button>; }
function TaskTable({ tasks, onStatus }: { tasks: Task[]; onStatus: (task: Task, status: string) => void }) { const statuses = [["todo","To do"],["in_progress","In progress"],["review","Review"],["done","Done"]]; return !tasks.length ? <Empty title="No tasks yet" text="Tasks will appear here after you create them."/> : <div className="panel table-wrap"><table><thead><tr><th>Task</th><th>Project</th><th>Assignee</th><th>Priority</th><th>Due</th><th>Status</th></tr></thead><tbody>{tasks.map(task => <tr key={task.id}><td><strong>{task.title}</strong></td><td>{task.project_name}</td><td>{task.assignees.map(a => a.name).join(', ') || 'Unassigned'}</td><td><span className={`priority ${task.priority}`}>{task.priority}</span></td><td>{task.due_date || '—'}</td><td><select value={task.status} onChange={e => onStatus(task,e.target.value)}>{statuses.map(([s,l]) => <option value={s} key={s}>{l}</option>)}</select></td></tr>)}</tbody></table></div>; }

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
