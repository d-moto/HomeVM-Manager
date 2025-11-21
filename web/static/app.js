const API_BASE = '/api';

// State
let vms = [];
let pendingAction = null;

// DOM Elements
const vmGrid = document.getElementById('vm-grid');
const addModal = document.getElementById('add-modal');
const pwModal = document.getElementById('password-modal');
const addForm = document.getElementById('add-form');

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchVMs();
    setInterval(fetchVMs, 5000); // Poll every 5s
    updateClock();
    setInterval(updateClock, 1000);
});

function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString();
}

// Fetch Data
async function fetchVMs() {
    try {
        const res = await fetch(`${API_BASE}/vms`);
        vms = await res.json();
        render();
    } catch (e) {
        console.error("Failed to fetch VMs", e);
    }
}

// Render
function render() {
    vmGrid.innerHTML = '';
    let running = 0;
    let stopped = 0;

    vms.forEach(vm => {
        const isRunning = vm.status === '稼働中';
        if (isRunning) running++; else stopped++;

        const card = document.createElement('div');
        card.className = 'vm-card glass';
        card.innerHTML = `
            <div class="vm-header">
                <div class="vm-name">${vm.vm_name}</div>
                <div class="vm-status-dot ${isRunning ? 'running' : 'stopped'}"></div>
            </div>
            <div class="vm-details">
                <p><span>IP:</span> <span>${vm.host_ip || '-'}</span></p>
                <p><span>MAC:</span> <span>${vm.mac}</span></p>
                <p><span>User:</span> <span>${vm.user}</span></p>
                <p><span>Method:</span> <span>${vm.method}</span></p>
                <p><span>Status:</span> <span>${vm.status}</span></p>
            </div>
            <div class="vm-actions">
                <button class="btn btn-connect" onclick="connectVM('${vm.method}', '${vm.user}', '${vm.host_ip}')"><i class="fa-solid fa-plug"></i> Connect</button>
                ${vm.type === 'physical' ?
                `<button class="btn btn-power" onclick="confirmPower('${vm.mac}', 'wol')"><i class="fa-solid fa-bolt"></i> WOL</button>` : ''
            }
                <button class="btn btn-power" onclick="confirmPower('${vm.mac}', 'off')"><i class="fa-solid fa-power-off"></i> OFF</button>
                <button class="btn btn-reboot" onclick="confirmPower('${vm.mac}', 'reboot')"><i class="fa-solid fa-rotate-right"></i> Reboot</button>
                <button class="btn btn-delete" onclick="deleteVM('${vm.mac}')"><i class="fa-solid fa-trash"></i></button>
            </div>
        `;
        vmGrid.appendChild(card);
    });

    document.getElementById('total-vms').innerText = vms.length;
    document.getElementById('running-vms').innerText = running;
    document.getElementById('stopped-vms').innerText = stopped;
}

function connectVM(method, user, ip) {
    if (!ip || ip === 'null' || ip === '-') {
        alert('IP address not available');
        return;
    }
    if (method === 'SSH') {
        window.open(`ssh://${user}@${ip}`);
    } else if (method === 'WinRM' || method === 'API') {
        window.location.href = `/api/rdp/${ip}`;
    } else {
        alert('Connection method not supported for this VM');
    }
}

// Actions
function openAddModal() {
    addModal.classList.add('open');
}

function closeAddModal() {
    addModal.classList.remove('open');
    addForm.reset();
}

addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(addForm);
    const data = Object.fromEntries(formData.entries());

    try {
        const res = await fetch(`${API_BASE}/vms`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (res.ok) {
            closeAddModal();
            fetchVMs();
        } else {
            alert('Failed to add VM');
        }
    } catch (e) {
        console.error(e);
    }
});

async function deleteVM(mac) {
    if (!confirm('Are you sure you want to delete this VM?')) return;
    try {
        await fetch(`${API_BASE}/vms/${mac}`, { method: 'DELETE' });
        fetchVMs();
    } catch (e) {
        console.error(e);
    }
}

// Power Actions
function confirmPower(mac, action) {
    pendingAction = { mac, action };
    // If WOL, no password needed usually, but for simplicity we try direct execution first
    executePower(null);
}

async function executePower(password) {
    if (!pendingAction) return;

    const payload = { ...pendingAction, password };

    try {
        const res = await fetch(`${API_BASE}/power`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.status === 401) {
            // Need password
            const vm = vms.find(v => v.mac === pendingAction.mac);
            document.getElementById('pw-target-name').innerText = `Enter password for ${vm.vm_name} (${vm.host_ip})`;
            pwModal.classList.add('open');
            document.getElementById('pw-input').focus();
            return;
        }

        const data = await res.json();
        if (res.ok) {
            alert(`Success: ${data.message}`);
            closePwModal();
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (e) {
        alert(`Network Error: ${e}`);
    }
}

function closePwModal() {
    pwModal.classList.remove('open');
    document.getElementById('pw-input').value = '';
    pendingAction = null;
}

function submitPassword() {
    const pw = document.getElementById('pw-input').value;
    executePower(pw);
}
