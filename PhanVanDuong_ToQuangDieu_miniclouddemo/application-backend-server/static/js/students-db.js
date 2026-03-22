const bodyEl = document.getElementById("db-body");
const statusEl = document.getElementById("status");
const searchInput = document.getElementById("search-q");
const searchBtn = document.getElementById("search-btn");
const refreshBtn = document.getElementById("refresh-btn");
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
      <td>
        <button type="button" class="ghost" onclick="editRow(${row.id})">Edit</button>
        <button type="button" class="danger" onclick="deleteOne(${row.id})">Delete</button>
      </td>
    </tr>
  `;
}

async function fetchRows(query = "") {
  const url = query
    ? `/api/students-db?format=json&q=${encodeURIComponent(query)}`
    : "/api/students-db?format=json";
  const res = await fetch(url);
  if (!res.ok) throw new Error("Load failed");
  const rows = await res.json();
  bodyEl.innerHTML = rows.map(rowTemplate).join("");
  checkAll.checked = false;
  setStatus(`Loaded ${rows.length} record(s).`);
}

function selectedIds() {
  return [...document.querySelectorAll(".row-check:checked")].map((el) => el.value);
}

async function deleteOne(id) {
  if (!confirm(`Delete row ${id}?`)) return;
  const res = await fetch(`/api/students-db/${id}`, { method: "DELETE" });
  if (!res.ok) {
    setStatus("Delete failed.", true);
    return;
  }
  setStatus(`Deleted row ${id}.`);
  fetchRows(searchInput.value.trim());
}

window.deleteOne = deleteOne;

async function editRow(id) {
  const res = await fetch(`/api/students-db/${id}`);
  if (!res.ok) {
    setStatus("Cannot load row for editing.", true);
    return;
  }
  const row = await res.json();
  rowIdInput.value = row.id;
  studentIdInput.value = row.student_id;
  fullnameInput.value = row.fullname;
  dobInput.value = String(row.dob || "").slice(0, 10);
  majorInput.value = row.major;
  setStatus(`Editing row ${id}.`);
}

window.editRow = editRow;

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    student_id: studentIdInput.value.trim(),
    fullname: fullnameInput.value.trim(),
    dob: dobInput.value,
    major: majorInput.value.trim(),
  };

  let res;
  if (rowIdInput.value) {
    res = await fetch(`/api/students-db/${rowIdInput.value}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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

  setStatus(rowIdInput.value ? "Record updated." : "Record created.");
  form.reset();
  rowIdInput.value = "";
  fetchRows(searchInput.value.trim());
});

resetBtn.addEventListener("click", () => {
  form.reset();
  rowIdInput.value = "";
  setStatus("Form reset.");
});

searchBtn.addEventListener("click", () => fetchRows(searchInput.value.trim()));
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
  if (!confirm(`Delete ${ids.length} selected row(s)?`)) return;

  const res = await fetch(`/api/students-db?ids=${ids.join(",")}`, { method: "DELETE" });
  if (!res.ok) {
    setStatus("Delete selected failed.", true);
    return;
  }
  setStatus(`Deleted ${ids.length} selected row(s).`);
  fetchRows(searchInput.value.trim());
});

deleteAllBtn.addEventListener("click", async () => {
  if (!confirm("Delete ALL rows in students table?")) return;
  const res = await fetch("/api/students-db?all=true", { method: "DELETE" });
  if (!res.ok) {
    setStatus("Delete all failed.", true);
    return;
  }
  setStatus("Deleted all rows.");
  fetchRows(searchInput.value.trim());
});

fetchRows().catch(() => {
  bodyEl.innerHTML = '<tr><td colspan="7">Failed to load DB data.</td></tr>';
  setStatus("Initial load failed.", true);
});
