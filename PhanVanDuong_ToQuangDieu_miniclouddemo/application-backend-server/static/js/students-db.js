const bodyEl = document.getElementById("db-body");
const statusEl = document.getElementById("status");
const searchInput = document.getElementById("search-q");
const refreshBtn = document.getElementById("refresh-btn");
const editSelectedBtn = document.getElementById("edit-selected-btn");
const deleteSelectedBtn = document.getElementById("delete-selected-btn");
const deleteAllBtn = document.getElementById("delete-all-btn");
const checkAll = document.getElementById("check-all");

const form = document.getElementById("student-form");
const rowIdInput = document.getElementById("row-id");
const studentIdInput = document.getElementById("student-id");
const fullnameInput = document.getElementById("fullname");
const dobInput = document.getElementById("dob");
const majorInput = document.getElementById("major");
const resetBtn = document.getElementById("reset-btn");
const confirmModal = document.getElementById("confirm-modal");
const confirmMessage = document.getElementById("confirm-message");
const confirmOkBtn = document.getElementById("confirm-ok");
const confirmCancelBtn = document.getElementById("confirm-cancel");

let currentRows = [];
let editingSnapshot = null;
let searchDebounceTimer = null;

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.background = isError ? "#ffe8e8" : "#f4f8ff";
  statusEl.style.color = isError ? "#9f1d1d" : "#244f8a";
}

function rowTemplate(row) {
  return `
    <tr>
      <td><input class="row-check" type="checkbox" value="${row.id}" /></td>
      <td>${row.id}</td>
      <td>${row.student_id}</td>
      <td>${row.fullname}</td>
      <td>${String(row.dob).slice(0, 16)}</td>
      <td>${row.major}</td>
    </tr>
  `;
}

function showConfirm(message) {
  return new Promise((resolve) => {
    confirmMessage.textContent = message;
    confirmModal.classList.remove("hidden");

    const onConfirm = () => {
      cleanup();
      resolve(true);
    };

    const onCancel = () => {
      cleanup();
      resolve(false);
    };

    function cleanup() {
      confirmModal.classList.add("hidden");
      confirmOkBtn.removeEventListener("click", onConfirm);
      confirmCancelBtn.removeEventListener("click", onCancel);
    }

    confirmOkBtn.addEventListener("click", onConfirm);
    confirmCancelBtn.addEventListener("click", onCancel);
  });
}

async function fetchRows(query = "") {
  const url = query
    ? `/api/students-db?format=json&q=${encodeURIComponent(query)}`
    : "/api/students-db?format=json";
  const res = await fetch(url);
  if (!res.ok) throw new Error("Load failed");
  const rows = await res.json();
  currentRows = rows;
  bodyEl.innerHTML = rows.map(rowTemplate).join("");
  checkAll.checked = false;
  setStatus(`Loaded ${rows.length} record(s).`);
}

async function fetchRowsWithRetry(query = "", retries = 4) {
  let lastErr = null;
  for (let i = 0; i < retries; i += 1) {
    try {
      await fetchRows(query);
      return;
    } catch (err) {
      lastErr = err;
      await new Promise((resolve) => setTimeout(resolve, 350 * (i + 1)));
    }
  }
  throw lastErr;
}

function selectedIds() {
  return [...document.querySelectorAll(".row-check:checked")].map((el) => el.value);
}

function selectedNumericIds() {
  return selectedIds().map((v) => Number(v));
}

function getSelectedSingleIdOrWarn() {
  const ids = selectedNumericIds();
  if (!ids.length) {
    setStatus("Please select exactly one row to edit.", true);
    return null;
  }
  if (ids.length > 1) {
    setStatus("Only one row can be selected for editing.", true);
    return null;
  }
  return ids[0];
}

async function loadRowIntoForm(id) {
  const res = await fetch(`/api/students-db/${id}`);
  if (!res.ok) {
    setStatus("Cannot load row for editing.", true);
    return;
  }
  const row = await res.json();
  editingSnapshot = {
    student_id: row.student_id,
    fullname: row.fullname,
    dob: String(row.dob || "").slice(0, 10),
    major: row.major,
  };
  rowIdInput.value = row.id;
  studentIdInput.value = row.student_id;
  fullnameInput.value = row.fullname;
  dobInput.value = editingSnapshot.dob;
  majorInput.value = row.major;
  setStatus(`Editing row ${id}.`);
}

editSelectedBtn.addEventListener("click", async () => {
  const id = getSelectedSingleIdOrWarn();
  if (!id) return;
  await loadRowIntoForm(id);
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    student_id: studentIdInput.value.trim(),
    fullname: fullnameInput.value.trim(),
    dob: dobInput.value,
    major: majorInput.value.trim(),
  };

  let res;
  const isUpdate = rowIdInput.value ? true : false;
  
  if (isUpdate) {
    const changed = {};
    if (!editingSnapshot || payload.student_id !== editingSnapshot.student_id) changed.student_id = payload.student_id;
    if (!editingSnapshot || payload.fullname !== editingSnapshot.fullname) changed.fullname = payload.fullname;
    if (!editingSnapshot || payload.dob !== editingSnapshot.dob) changed.dob = payload.dob;
    if (!editingSnapshot || payload.major !== editingSnapshot.major) changed.major = payload.major;

    if (Object.keys(changed).length === 0) {
      setStatus("No changes detected.");
      return;
    }

    res = await fetch(`/api/students-db/${rowIdInput.value}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changed),
    });
  } else {
    res = await fetch("/api/students-db", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    setStatus(err.error || "Save failed.", true);
    return;
  }

  const successMsg = isUpdate ? "✓ Record updated successfully!" : "✓ Record created successfully!";
  setStatus(successMsg);
  
  // Auto-clear form and reset UI after short delay
  setTimeout(() => {
    form.reset();
    rowIdInput.value = "";
    editingSnapshot = null;
    document.querySelectorAll(".row-check").forEach((el) => {
      el.checked = false;
    });
    checkAll.checked = false;
    fetchRows(searchInput.value.trim());
  }, 300);
});

resetBtn.addEventListener("click", () => {
  form.reset();
  rowIdInput.value = "";
  editingSnapshot = null;
  setStatus("Form reset.");
});

searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => fetchRows(searchInput.value.trim()), 250);
});

refreshBtn.addEventListener("click", () => {
  searchInput.value = "";
  fetchRows();
});

checkAll.addEventListener("change", () => {
  const checked = checkAll.checked;
  document.querySelectorAll(".row-check").forEach((el) => {
    el.checked = checked;
  });
});

deleteSelectedBtn.addEventListener("click", async () => {
  const ids = selectedIds();
  if (!ids.length) {
    setStatus("Please select at least one row.", true);
    return;
  }
  const accepted = await showConfirm(`Delete ${ids.length} selected row(s)?`);
  if (!accepted) return;

  const res = await fetch(`/api/students-db?ids=${ids.join(",")}`, { method: "DELETE" });
  if (!res.ok) {
    setStatus("Delete selected failed.", true);
    return;
  }
  setStatus(`Deleted ${ids.length} selected row(s).`);
  fetchRows(searchInput.value.trim());
});

deleteAllBtn.addEventListener("click", async () => {
  const accepted = await showConfirm("Delete ALL rows in students table?");
  if (!accepted) return;

  const res = await fetch("/api/students-db?all=true", { method: "DELETE" });
  if (!res.ok) {
    setStatus("Delete all failed.", true);
    return;
  }
  setStatus("Deleted all rows.");
  fetchRows(searchInput.value.trim());
});

fetchRowsWithRetry().catch(() => {
  bodyEl.innerHTML = '<tr><td colspan="6">Failed to load DB data.</td></tr>';
  setStatus("Initial load failed.", true);
});
