# TaskBoard — Design Document

A Kanban-style todo application. Three columns — **To Do**, **In Progress**, **Completed** — with task cards dragged between them.

| Layer     | Choice                          |
| --------- | ------------------------------- |
| Frontend  | React                           |
| Backend   | Python Flask                    |
| Database  | PostgreSQL                      |
| Status    | Design — not yet built          |

---

## 1. Overview

TaskBoard is a personal task manager built around a Kanban board. Instead of a flat checklist, tasks live in one of three columns and move left to right as work progresses. A task is created in **To Do**, dragged to **In Progress** when it's picked up, and dragged to **Completed** when it's finished.

**Who it's for:** one person managing their own work. Every task belongs to exactly one user and is only ever visible to that user. There is no sharing, no team, no assignment to other people.

**The goal:** a user can see everything they have to do, and its state, in a single glance — and change that state with one drag.

**What makes it more than a todo list:** the board is the status. There is no separate "done" checkbox to keep in sync with a column; the column a card sits in is the single source of truth for whether that task is not started, underway, or finished.

---

## 2. Tech Stack

| Layer          | Choice                                    | Why                                                                                                                                                             |
| -------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend       | React (Vite, JavaScript or TypeScript)    | The board is highly stateful — cards moving, a modal opening, filters narrowing a list. Vite over CRA for a fast dev server and a modern build.                 |
| Drag & drop    | @dnd-kit/core + @dnd-kit/sortable         | Actively maintained, accessible (keyboard drag works out of the box), and small. react-beautiful-dnd is no longer maintained.                                    |
| Routing        | React Router                              | Three routes and a redirect guard — nothing heavier is needed.                                                                                                  |
| Server state   | TanStack Query (React Query)              | Caching, refetch on focus, and — crucially for the board — first-class optimistic updates with automatic rollback. Plain useEffect + fetch is a valid substitute. |
| Backend        | Flask + Flask-SQLAlchemy                  | Small enough to read in one sitting; SQLAlchemy gives models, relationships, and safe parameterised queries.                                                     |
| Migrations     | Alembic (via Flask-Migrate)               | The schema grows over five build phases — migrations, not hand-edited SQL, keep environments in step.                                                            |
| Validation     | Marshmallow (or Pydantic)                 | Request bodies come from a browser; validate at the edge, not in the route body.                                                                                 |
| Auth           | PyJWT + Werkzeug password hashing         |                                                                                                                                                                 |
| Database       | PostgreSQL 16                             | Native ENUM types for status and priority, a real many-to-many join table for tags, and ILIKE for the search filter.                                            |
| CORS           | Flask-CORS                                | The React dev server and Flask run on different ports.                                                                                                          |

---

## 3. Core Features

### MVP — the board works.

1.  Create a task with a title and an optional description
2.  See all tasks laid out in three columns by status
3.  Drag a card from one column to another to change its status
4.  Reorder cards within a column
5.  Open a card to edit it
6.  Delete a task
7.  Everything persists — a refresh shows the board exactly as it was left

### Extensions — built in order after the MVP.

- **Login** — register, log in, log out; every task is scoped to its owner
- **Due dates & priority** — a date and a Low/Medium/High level per task, surfaced on the card
- **Tags** — user-defined coloured labels, many per task
- **Search & filter** — narrow the board by text, tag, or due date

### Explicitly not in scope

Naming these now stops them creeping in later:

- Multiple boards or projects — there is exactly one board per user
- Custom or reorderable columns — the three statuses are fixed
- Sharing, collaboration, assigning tasks to other people
- Notifications or email reminders
- File attachments, comments, subtasks, checklists
- Recurring tasks
- Offline support
- Mobile-native apps (the web app should not break on a phone, but no dedicated mobile design)

---

## 4. Frontend Design

### 4.1 The Kanban board — `/board`

**Layout.** A fixed top bar holds the app name on the left and, on the right, the search input, the tag filter, the due-date filter, a **+ New Task** button, and the user avatar menu (which contains **Log out**). Below it, three equal-width columns fill the remaining height. Each column has a header showing its name and a live count of the cards in it, and each column scrolls independently when it overflows.

**Card anatomy.** Each card shows, top to bottom:

| Element          | Notes                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| Title            | Bold, one line, truncated with an ellipsis past the width of the card                              |
| Description snippet | One line, grey, truncated; omitted entirely if there's no description                            |
| Priority badge   | Green `LOW` / amber `MEDIUM` / red `HIGH`                                                         |
| Due-date chip    | `Due 12 Sep`; renders red when the date is in the past and the task isn't done. Omitted if no due date. |
| Tag pills        | One per tag, in the tag's own colour                                                              |

Cards in **Completed** are rendered muted — grey text, desaturated badges — so the eye skips over them.

At the bottom of every column sits a dashed **+ Add task** target that opens the modal in create mode with that column's status pre-selected.

**Drag and drop.** This is the core interaction, so it gets the most detail:

- Grabbing a card lifts it — a shadow and a slight scale — and it follows the cursor
- The column under the cursor shows a dashed drop zone at the insertion point
- Dropping calls `PATCH /api/tasks/:id/move` with the new status and position
- The move is optimistic: local state updates the instant the card is dropped, before the request resolves. If the request fails, the card animates back to where it came from and a toast explains why
- Dragging within a column reorders it — same endpoint, same status, new position
- Keyboard equivalent: tab to a card, Space to pick up, arrow keys to move, Space to drop. @dnd-kit provides this; do not disable it

---

### 4.2 Card detail modal

Cards are too small to hold every field, so all editing happens in one modal used in two modes.

|                        | Edit mode                        | Create mode                                   |
| ---------------------- | -------------------------------- | --------------------------------------------- |
| Opened by              | Clicking a card                  | **+ New Task** or a column's **+ Add task**   |
| Header                 | "Edit task"                      | "New task"                                    |
| Fields                 | Populated                        | Empty; status defaults to the originating column, priority to Medium |
| Delete button          | Shown                            | Hidden                                        |
| Saves with             | `PATCH /api/tasks/:id`           | `POST /api/tasks`                             |

**Fields:** Title (text, required), Description (textarea), Status (select — the three columns), Priority (select — Low/Medium/High), Due date (date picker with a clear link), Tags (pill multi-select with a **+ tag** affordance). Edit mode also shows a small created/updated line above the footer.

**Validation.**

| Field       | Rule                         | Message                       |
| ----------- | ---------------------------- | ----------------------------- |
| Title       | Required, 1–200 chars        | "Give the task a title"       |
| Description | Optional, max 2000 chars     | "Description is too long"     |
| Due date    | Optional, valid date         | "That date isn't valid"       |

Save is disabled until the title is non-empty and something has actually changed.

**Behaviour.** Esc, the X, Cancel, and a backdrop click all close without saving. Delete asks for confirmation first, then closes the modal and removes the card. Changing Status in the modal does exactly what dragging the card to that column does — the card jumps to its new column when the modal closes. Tag changes are sent separately via `PUT /api/tasks/:id/tags`.

---

### 4.3 Login and Sign Up

Two centred single-column forms, each on a plain background, each with a link to the other.

- `/login` — email, password, Log in, and a link to sign up
- `/signup` — display name, email, password (min 8 chars), confirm password, Create account, and a link back to log in

Both have an inline error slot beneath the fields. Server errors land there: `401` → "Incorrect email or password", `409` → "That email is already registered". Client-side, "Passwords don't match" appears before anything is sent.

On success both store the returned token and redirect to `/board`.

**Auth flow:** Visit `/board` → token in localStorage? → yes: render the board; no: redirect to `/login` → submit → `POST /api/auth/login` → `{ token, user }` → store token in localStorage → render the board.

---

### 4.4 Routes and Component Tree

| Route    | Component     | Guard                                   |
| -------- | ------------- | --------------------------------------- |
| `/login` | LoginPage     | Redirects to `/board` if already logged in |
| `/signup`| SignupPage    | Redirects to `/board` if already logged in |
| `/board` | BoardPage     | Redirects to `/login` if there's no token |
| `/`      | —             | Redirects to `/board`                   |

```text
<App>
  └─ <AuthProvider>          // token, user, login(), logout()
      └─ <Routes>
          ├─ <LoginPage />
          ├─ <SignupPage />
          └─ <ProtectedRoute>
              └─ <BoardPage>
                  ├─ <TopBar>
                  │   ├─ <FilterBar />     // search, tag filter, due filter
                  │   └─ <UserMenu />      // display name, log out
                  ├─ <DndContext>
                  │   └─ <Column /> x 3
                  │       └─ <TaskCard /> x n
                  └─ <TaskModal />          // create or edit, mounted once
```

---

### 4.5 State Management

- **Server state** — `useTasks()` and `useTags()` hooks wrapping TanStack Query. `useTasks()` takes the current filters and calls `GET /api/tasks`; the board derives its three columns by grouping the returned list by status and sorting each group by position.
- **Optimistic moves** — `useMoveTask()` is a mutation with `onMutate` writing the new status/position into the cache, `onError` restoring the snapshot, and `onSettled` invalidating so the server stays the source of truth.
- **Auth state** — `AuthContext` holds the token and the current user. It reads the token from localStorage on mount and calls `GET /api/auth/me` to hydrate the user.
- **UI state** — modal open/closed and which task it's editing live in `BoardPage` local state. Not in a global store; nothing else needs them.
- **The fetch wrapper** — a single `api.js` attaches `Authorization: Bearer <token>` to every request and, on any 401, clears the token and redirects to `/login`.

---

## 5. Database Design

Four tables: `users`, `tasks`, `tags`, and the `task_tags` join table.

### ENUM Types

```text
task_status    todo | in_progress | done
task_priority  low | medium | high
```

### users

| Column        | Type          | Constraints                  |
| ------------- | ------------- | ---------------------------- |
| id            | SERIAL        | PK                           |
| email         | VARCHAR(255)  | UNIQUE, NOT NULL             |
| password_hash | VARCHAR(255)  | NOT NULL                     |
| display_name  | VARCHAR(100)  | NOT NULL                     |
| created_at    | TIMESTAMPZ    | NOT NULL, default now()      |

The plaintext password is never stored or logged.

### tasks

| Column         | Type          | Constraints                                        |
| -------------- | ------------- | -------------------------------------------------- |
| id             | SERIAL        | PK                                                 |
| user_id        | INT           | FK → users(id), ON DELETE CASCADE, NOT NULL        |
| title          | VARCHAR(200)  | NOT NULL                                           |
| description    | TEXT          | nullable                                           |
| status         | task_status   | NOT NULL, default 'todo'                           |
| priority       | task_priority | NOT NULL, default 'medium'                         |
| due_date       | DATE          | nullable                                           |
| position       | INT           | NOT NULL                                           |
| created_at     | TIMESTAMPZ    | NOT NULL, default now()                            |
| updated_at     | TIMESTAMPZ    | NOT NULL, default now()                            |
| completed_at   | TIMESTAMPZ    | nullable                                           |

### tags

| Column   | Type          | Constraints                                  |
| -------- | ------------- | -------------------------------------------- |
| id       | SERIAL        | PK                                           |
| user_id  | INT           | FK → users(id), ON DELETE CASCADE, NOT NULL  |
| name     | VARCHAR(50)   | NOT NULL                                     |
| colour   | CHAR(7)       | NOT NULL — hex, e.g. `#6c8ebf`               |

`UNIQUE (user_id, name)` — one user can't have two tags called "Work", but two different users can each have one.

### task_tags

| Column  | Type | Constraints                                  |
| ------- | ---- | -------------------------------------------- |
| task_id | INT  | FK → tasks(id), ON DELETE CASCADE            |
| tag_id  | INT  | FK → tags(id), ON DELETE CASCADE             |

Composite primary key `(task_id, tag_id)` — which also prevents the same tag being attached to a task twice.

### Design decisions worth stating

- **Columns are an enum, not a table.** The three columns are part of the product, not something a user configures, so `status` is a Postgres enum on `tasks` rather than a `columns` table with a foreign key. This removes a join from the hottest query in the app. Revisit only if custom columns or multiple boards are ever added — at which point columns becomes a real table belonging to a `boards` table.
- **`position` handles ordering.** It orders cards within a column. A drag writes both `status` and `position` in one request. The simplest correct implementation renumbers the affected column(s) 0, 1, 2, ... inside a transaction; a fractional or gapped scheme is a later optimisation and not worth it at this size.
- **`completed_at` is set by the backend, not the client** — when status transitions to `done`, and cleared if it transitions back out. It exists so "what did I finish this week" is answerable later without an audit log.
- **Every query is scoped by `user_id`.** Not just the list endpoint — fetching, updating, and deleting a single task all filter on the owner too, so guessing an id gets a 404, not someone else's task.

---

### DDL

```sql
CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done');
CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPZ NOT NULL DEFAULT now()
);

CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status task_status NOT NULL DEFAULT 'todo',
    priority task_priority NOT NULL DEFAULT 'medium',
    due_date DATE,
    position INT NOT NULL,
    created_at TIMESTAMPZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPZ
);

CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    colour CHAR(7) NOT NULL,
    CONSTRAINT tags_user_name_unique UNIQUE (user_id, name)
);

CREATE TABLE task_tags (
    task_id INT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag_id)
);

CREATE INDEX idx_tasks_board ON tasks (user_id, status, position);
CREATE INDEX idx_tags_user ON tags (user_id);
CREATE INDEX idx_task_tags_tag ON task_tags (tag_id);
```

---

## 6. API Contract

### Conventions

- Base path `/api`. JSON in, JSON out. Keys are `snake_case`.
- Every endpoint except register and login requires `Authorization: Bearer <token>`.
- Dates are ISO-8601: `due_date` is `YYYY-MM-DD`, timestamps are `YYYY-MM-DDTHH:MM:SSZ`.
- Errors always use the same envelope: `{"error": {"code": "VALIDATION_ERROR", "message": "Title is required"}}`
- Shared error codes: `400 VALIDATION_ERROR`, `401 UNAUTHORISED` (missing, malformed, or expired token), `404 NOT_FOUND` (including tasks owned by someone else), `409 CONFLICT`, `500 INTERNAL_ERROR`.

### Auth

| Endpoint           | Request body                       | Success               |
| ------------------ | ---------------------------------- | --------------------- |
| `POST /api/auth/register` | `display_name`, `email`, `password` | `201 { token, user }` |
| `POST /api/auth/login`    | `email`, `password`                | `200 { token, user }` |
| `GET /api/auth/me`        | —                                  | `200 { user }`        |

There is no logout endpoint — the client discards the token.

### Tasks

| Endpoint                | Request body                              | Success          |
| ----------------------- | ----------------------------------------- | ---------------- |
| `GET /api/tasks`        | — (query params below)                    | `200 { tasks: [...] }` |
| `POST /api/tasks`       | `title`, `description?`, `status?`, `priority?`, `due_date?` | `201 { task }`   |
| `GET /api/tasks/:id`    | —                                         | `200 { task }`   |
| `PATCH /api/tasks/:id`  | any subset of the editable fields         | `200 { task }`   |
| `PATCH /api/tasks/:id/move` | `status`, `position`                  | `200 { task }`   |
| `DELETE /api/tasks/:id` | —                                         | `204` no body    |

**GET /api/tasks query parameters** — all optional, all combined with AND:

| Param       | Type                        | Effect                                                       |
| ----------- | --------------------------- | ------------------------------------------------------------ |
| `status`    | `todo` \| `in_progress` \| `done` | Only that column                                       |
| `q`         | string                      | Case-insensitive substring match on title or description (`ILIKE '%q%'`) |
| `tag_id`    | int (repeatable)            | Tasks carrying any of the given tags                         |
| `due_before`| `YYYY-MM-DD`                | Tasks due on or before that date; excludes tasks with no due date |

Results are ordered by `status`, then `position` ascending. The board fetches with no `status` param and groups client-side — one request per board load, not three.

### Task object

```json
{
  "id": 42,
  "title": "Write the Q3 report",
  "description": "Pull the numbers from the finance sheet...",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2026-09-12",
  "position": 0,
  "created_at": "2026-09-02T09:14:00Z",
  "updated_at": "2026-09-10T16:02:00Z",
  "completed_at": null,
  "tags": [
    { "id": 3, "name": "Work", "colour": "#6c8ebf" },
    { "id": 7, "name": "Urgent", "colour": "#b85450" }
  ]
}
```

### Tags

| Endpoint                  | Request body       | Success                                   |
| ------------------------- | ------------------ | ----------------------------------------- |
| `GET /api/tags`           | —                  | `200 { tags: [...] }`                     |
| `POST /api/tags`          | `name`, `colour`   | `201 { tag }`                             |
| `DELETE /api/tags/:id`    | —                  | `204` — also detaches it from every task  |
| `PUT /api/tasks/:id/tags` | `{ "tag_ids": [3, 7] }` | `200 { task }`                        |

`PUT /api/tasks/:id/tags` replaces the whole set rather than adding to it — the modal always knows the full list, so send it whole and let the backend diff.

### Worked examples

**Create a task**

```text
POST /api/tasks
Authorization: Bearer eyJhbGciOiJIUzI1Nils...
Content-Type: application/json

{
  "title": "Write the Q3 report",
  "description": "Pull the numbers from the finance sheet",
  "status": "todo",
  "priority": "high",
  "due_date": "2026-09-12"
}
```

`201 Created` — the backend sets `user_id` from the token and `position` to the end of the target column. It is never taken from the request body.

**Move a card between columns**

```text
PATCH /api/tasks/42/move
Authorization: Bearer eyJhbGciOiJIUzI1Nils...
Content-Type: application/json

{"status": "done", "position": 0}
```

In one transaction the backend: verifies the task belongs to the caller; renumbers the source column to close the gap; renumbers the destination column to open a slot at `position`; writes the new `status` and `position`; sets `completed_at` (because the new status is `done`) and bumps `updated_at`. It returns the updated task so the client can reconcile its optimistic state.

---

## 7. Authentication

**Decision: JWT stored in localStorage.** Chosen for simplicity — the token is visible and easy to reason about in DevTools, there is no cookie/CORS/SameSite configuration to get right, and the flow maps one-to-one onto what the code does.

**Registration.** `POST /api/auth/register` validates the email is well-formed and unused and the password is at least 8 characters, hashes it with `werkzeug.security.generate_password_hash` (pbkdf2-sha256), inserts the user, and returns a token immediately — a new user lands straight on their board without a second log in.

**Login.** `POST /api/auth/login` looks up the user by email and checks the password with `check_password_hash`. A wrong email and a wrong password produce the same 401 and the same message, so the response can't be used to enumerate registered addresses.

**The token.**

```python
payload = {
    "sub": user.id,
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(hours=24),
}

token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
```

Signed HS256 with `SECRET_KEY` from the environment — never committed, and different in production. 24-hour expiry.

**Using it.** React stores the token under a single key and the `api.js` wrapper attaches `Authorization: Bearer <token>` to every request. On the Flask side a `@login_required` decorator pulls the header, decodes and verifies the token, loads the user, and puts it on `g.current_user`. A missing, malformed, or expired token is a 401 — never a 500.

**Scoping.** Every task and tag query filters on `g.current_user.id`. Requesting a task belonging to someone else returns 404, not 403 — no information about what exists is leaked.

**Logout.** Purely client-side: clear localStorage and redirect to `/login`. There is no server-side session and no token blacklist, so a stolen token stays valid until it expires.

**Security note — read this before shipping**

localStorage is readable by any JavaScript running on the page. If an attacker ever gets a script onto the page — an XSS hole, a compromised npm dependency — they can read the token and use it until it expires. An `httpOnly` cookie would be unreadable from JavaScript and is the standard production choice.

This design accepts that trade for simplicity. The consequences and the upgrade path:

- Keep the expiry short (24h, not 30 days) so a leaked token has a limited life
- Never render user-supplied strings as HTML anywhere — React escapes by default; do not reach for `dangerouslySetInnerHTML`
- Serve over HTTPS in any deployed environment
- Upgrade path: move the token into an `httpOnly; Secure; SameSite=Lax` cookie set by Flask. The backend change is small; the frontend simply stops touching localStorage and sends `credentials: 'include'`. Do this before the app ever holds data that matters.

---

## 8. Build Phases

Build them in order. Each phase should end with the app working and demonstrable, not half-migrated.

### Phase 1 — MVP board

The board works end to end, for a single hardcoded user. No auth yet.

- [ ] Postgres running; `tasks` table and both enums created via an Alembic migration
- [ ] A dev user is seeded and its id is used everywhere `user_id` is needed
- [ ] `GET`, `POST`, `PATCH`, `DELETE /api/tasks` and `PATCH /api/tasks/:id/move` all work against the database
- [ ] The board renders three columns and puts every task in the right one
- [ ] **+ New Task** opens the modal, saving creates a task, and it appears in the right column without a refresh
- [ ] Clicking a card opens it in edit mode; saving updates the card in place
- [ ] Deleting a task removes it from the board after a confirmation
- [ ] Dragging a card to another column moves it, and it is still there after a page refresh
- [ ] Dragging a card within a column reorders it, and that order survives a refresh
- [ ] A failed move rolls the card back to its original column and shows an error

### Phase 2 — Login

- [x] `users` table migrated in; `tasks.user_id` becomes a real FK to it
- [x] `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` all work
- [x] Passwords are stored hashed — confirmed by looking directly at the table
- [x] `@login_required` protects every task route; an unauthenticated request gets 401
- [x] `/login` and `/signup` render and show server errors inline
- [x] Visiting `/board` without a token redirects to `/login`
- [x] After logging in, the user lands on `/board` and sees their own tasks
- [x] Two different accounts each see only their own tasks — verified by signing up twice
- [x] Requesting another user's task id by hand returns 404
- [x] Log out clears the token and returns to `/login`; the back button doesn't restore the board

### Phase 3 — Due dates and priority

- [ ] `due_date` and `priority` columns migrated in with sensible defaults for existing rows
- [ ] Both are settable in the modal and accepted by `POST` and `PATCH`
- [ ] The priority badge renders on the card in the right colour
- [ ] The due-date chip renders on the card, and is omitted when there's no date
- [ ] An overdue, not-done task shows its chip in red
- [ ] Clearing a due date works and persists as `null`
- [ ] Moving a task to Completed sets `completed_at`; moving it back out clears it

### Phase 4 — Tags

- [ ] `tags` and `task_tags` tables migrated in, with the `(user_id, name)` unique constraint
- [ ] `GET`/`POST`/`DELETE /api/tags` and `PUT /api/tasks/:id/tags` all work
- [ ] The modal lists the user's tags, and tags can be added to and removed from a task
- [ ] A new tag can be created from inside the modal, with a colour chosen
- [ ] Tag pills render on cards in the tag's colour
- [ ] Creating a duplicate tag name shows a clear error rather than a 500
- [ ] Deleting a tag removes it from every task that had it, without deleting those tasks

### Phase 5 — Search and filter

- [ ] `GET /api/tasks` honours `q`, `tag_id`, and `due_before`, and combines them
- [ ] The search input filters the board as you type (debounced ~300ms), matching title and description, case-insensitively
- [ ] The tag filter narrows the board to tasks carrying the selected tag
- [ ] The due filter offers **Overdue / Today / This week / Any**
- [ ] Filters combine — search plus tag plus due date narrows correctly
- [ ] Column counts reflect what's visible, not the unfiltered totals
- [ ] Clearing all filters restores the full board
- [ ] Filtering never triggers a full page reload

---

## 9. Open Questions

Deliberately unresolved — decide these when the phase that needs them arrives.

1.  **Delete: hard or soft?** Currently a hard `DELETE`, with confirmation as the only safety net. A `deleted_at` column plus an "Undo" toast is friendlier and costs one nullable column and a filter on every query.
2.  **Should Completed auto-archive?** The third column grows forever. Options: hide anything completed more than 30 days ago behind a "show older" link, add an explicit Archive action, or leave it alone. Not a problem until it is.
3.  **Are tags per-user or global?** Per-user, as designed. If sharing is ever added, a shared board with two users' private tags on the same card gets awkward — that's the point at which tags would need to move under a board rather than under a user.
4.  **Position renumbering at scale.** Renumbering a whole column per drag is fine for hundreds of tasks and wrong for tens of thousands. If it ever matters, switch to fractional or gapped positions.
5.  **Does the board need to work on a phone?** No mobile layout is designed. Three columns on a 375px screen means horizontal scrolling, and touch drag-and-drop needs testing. If mobile matters, that's a design pass of its own.
6.  **What happens when the token expires mid-session?** Currently: the next request 401s and the user is bounced to `/login`, losing whatever they were typing. A refresh-token flow, or at minimum a warning before expiry, would be kinder.
