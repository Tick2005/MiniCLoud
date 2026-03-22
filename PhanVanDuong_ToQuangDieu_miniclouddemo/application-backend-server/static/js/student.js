const bodyEl = document.getElementById("student-body");
const searchEl = document.getElementById("student-search");
const refreshBtn = document.getElementById("student-refresh");

let sourceRows = [];

function render(rows) {
  bodyEl.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td>${row.name}</td>
        <td>${row.major}</td>
        <td>${row.gpa}</td>
      </tr>
    `
    )
    .join("");
}

async function loadStudents() {
  const res = await fetch("/api/student?format=json");
  sourceRows = await res.json();
  render(sourceRows);
}

function filterRows() {
  const q = searchEl.value.trim().toLowerCase();
  if (!q) {
    render(sourceRows);
    return;
  }
  const filtered = sourceRows.filter((row) => {
    return (
      String(row.name).toLowerCase().includes(q) ||
      String(row.major).toLowerCase().includes(q) ||
      String(row.id).includes(q)
    );
  });
  render(filtered);
}

refreshBtn.addEventListener("click", loadStudents);
searchEl.addEventListener("input", filterRows);

loadStudents().catch(() => {
  bodyEl.innerHTML = '<tr><td colspan="4">Failed to load student data.</td></tr>';
});
