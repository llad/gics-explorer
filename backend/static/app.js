async function fetchVersions() {
  const res = await fetch('/api/versions');
  return res.json();
}

async function fetchTree(id) {
  const res = await fetch(`/api/tree/${id}`);
  return res.json();
}

async function populateVersions(select) {
  select.innerHTML = '';
  const versions = await fetchVersions();
  versions.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v.id;
    opt.textContent = `${v.label}`;
    select.appendChild(opt);
  });
}

function renderTree(node, container) {
  const ul = document.createElement('ul');
  for (const item of node) {
    const li = document.createElement('li');
    li.textContent = `${item.code} - ${item.name}`;
    if (item.groups) {
      renderTree(item.groups, li);
    } else if (item.industries) {
      renderTree(item.industries, li);
    } else if (item.subs) {
      renderTree(item.subs, li);
    }
    ul.appendChild(li);
  }
  container.appendChild(ul);
}

async function init() {
  const versionSelect = document.getElementById('version');
  await populateVersions(versionSelect);
  async function loadTree() {
    const tree = document.getElementById('tree');
    tree.innerHTML = '';
    const data = await fetchTree(versionSelect.value);
    renderTree(data, tree);
  }
  versionSelect.addEventListener('change', loadTree);
  await loadTree();
  document.querySelectorAll('button[data-level]').forEach(btn => {
    btn.addEventListener('click', () => {
      const level = btn.dataset.level;
      const id = versionSelect.value;
      window.location = `/api/export/${id}/${level}`;
    });
  });
  document.getElementById('ingest-btn').addEventListener('click', async () => {
    const url = document.getElementById('gics-url').value;
    const label = document.getElementById('gics-label').value;
    const eff = document.getElementById('gics-eff').value;
    await fetch('/api/ingest-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url, label: label, effective_date: eff })
    });
    await populateVersions(versionSelect);
    await loadTree();
  });
}

init();
