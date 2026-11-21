// SMT Supervisor Dashboard - Administrative Engine

let allInquiries = [];
let smtToken = sessionStorage.getItem('smt_token');
let currentCabIdForDocs = null;
let staffSession = { role: 'staff', can_od: false, email: null };

function applyStaffSession(me) {
    staffSession = {
        email: me.email || null,
        role: me.role || 'staff',
        can_od: !!me.can_od,
    };
    smtToken = smtToken || 'session';
    sessionStorage.setItem('smt_token', smtToken);
    const nav = document.getElementById('od-workspace-nav');
    if (nav) nav.style.display = staffSession.can_od ? '' : 'none';
    const odCard = document.getElementById('od-workspace-card');
    if (odCard) odCard.style.display = staffSession.can_od ? '' : 'none';
    const label = document.getElementById('staff-session-label');
    if (label) {
        label.textContent = staffSession.email || '';
    }
    const settingsLabel = document.getElementById('settings-session-label');
    if (settingsLabel) {
        settingsLabel.textContent = staffSession.email || 'Staff session';
    }
    const avatar = document.querySelector('.portal-avatar');
    if (avatar) {
        const ch = (staffSession.email || 'A').trim().charAt(0).toUpperCase();
        avatar.textContent = ch || 'A';
    }
    const hint = document.getElementById('google-login-hint');
    if (hint) hint.style.display = me.google_login ? 'none' : 'block';
}

function showLoginOverlay(me) {
    document.getElementById('admin-login-overlay').classList.remove('hidden');
    document.getElementById('admin-workspace').style.display = 'none';
    const hint = document.getElementById('google-login-hint');
    const localForm = document.getElementById('local-login-form');
    const googleBtn = document.getElementById('google-login-btn');
    const emails = (me && me.local_staff) || [];
    if (localForm && emails.length) {
        const select = document.getElementById('local-staff-email');
        select.replaceChildren();
        emails.forEach((email) => {
            const option = document.createElement('option');
            option.value = email;
            option.textContent = email;
            if (email.indexOf('abhishek') === 0) option.selected = true;
            select.appendChild(option);
        });
        localForm.style.display = 'block';
        if (googleBtn) googleBtn.style.display = 'none';
        if (hint) hint.style.display = 'none';
    } else if (hint) {
        hint.style.display = me && me.google_login ? 'none' : 'block';
    }
    const params = new URLSearchParams(window.location.search);
    const errorEl = document.getElementById('login-error');
    if (params.get('login_error') === 'not_allowed') {
        errorEl.style.display = 'block';
        errorEl.textContent = 'This Gmail is not on the SMT staff list.';
    } else if (params.get('login_error') === 'google') {
        errorEl.style.display = 'block';
        errorEl.textContent = 'Google Sign-In failed. Use an approved SMT Gmail.';
    }
}

function revealWorkspace(me) {
    applyStaffSession(me || {});
    document.getElementById('admin-login-overlay').classList.add('hidden');
    document.getElementById('admin-workspace').style.display = 'flex';
    const hash = (window.location.hash || '').replace('#', '');
    const allowed = ['home', 'datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'pg-duties', 'pg-finance', 'reports', 'companies', 'ev', 'tracking', 'settings', 'help'];
    switchTab(allowed.includes(hash) ? hash : 'home');
}

window.onload = async function() {
    try {
        const response = await fetch('/api/admin/me', { credentials: 'same-origin' });
        const me = await response.json();
        if (response.ok && me.authenticated) {
            revealWorkspace(me);
            return;
        }
        showLoginOverlay(me);
    } catch (err) {
        showLoginOverlay({ google_login: false });
    }
};

function adminLogout() {
    sessionStorage.removeItem('smt_token');
    smtToken = null;
    staffSession = { role: 'staff', can_od: false, email: null };
    fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' }).finally(() => {
        window.location.href = '/admin';
    });
}

function toggleAdminNav() {
    const workspace = document.getElementById('admin-workspace');
    if (workspace) workspace.classList.toggle('nav-open');
}

function closeAdminNav() {
    const workspace = document.getElementById('admin-workspace');
    if (workspace) workspace.classList.remove('nav-open');
}

const DATASOURCE_TABS = ['datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'pg-duties', 'pg-finance', 'companies', 'ev'];

// --- TAB SWITCHER ---
function switchTab(tabId) {
    if (!smtToken) return;

    document.querySelectorAll('.admin-tab-content').forEach(el => {
        el.classList.remove('active');
        el.style.display = 'none';
    });
    document.querySelectorAll('.portal-side-link, .admin-nav-menu button, .admin-nav-menu a').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelectorAll('.admin-nav-drop').forEach(el => {
        el.classList.remove('is-current');
    });

    const targetTab = document.getElementById(`tab-${tabId}`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }

    const targetBtn = document.getElementById(`btn-tab-${tabId}`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }

    if (tabId === 'tracking') {
        const ets = document.querySelector('[data-group="ets"]');
        if (ets) ets.classList.add('is-current');
    }
    if (DATASOURCE_TABS.includes(tabId)) {
        const ds = document.querySelector('[data-group="datasource"]');
        if (ds) ds.classList.add('is-current');
        const dsBtn = document.getElementById('btn-tab-datasource');
        if (dsBtn) dsBtn.classList.add('active');
    }

    closeAdminNav();
    if (history.replaceState) {
        history.replaceState(null, '', tabId === 'home' ? '/admin' : `/admin#${tabId}`);
    }

    if (tabId === 'home') {
        fetchOpsHomeBoard();
    } else if (tabId === 'inquiries') {
        fetchDashboardData();
    } else if (tabId === 'cabs') {
        fetchCabs();
    } else if (tabId === 'drivers') {
        fetchDrivers();
    } else if (tabId === 'pg-drivers') {
        fetchPgDrivers();
    } else if (tabId === 'pg-vehicles') {
        fetchPgVehicles();
    } else if (tabId === 'pg-duties') {
        fetchPgDuties();
    } else if (tabId === 'pg-finance') {
        fetchPgFinance();
    } else if (tabId === 'reports') {
        fetchStaffNotifications();
    } else if (tabId === 'companies') {
        fetchCompanies();
    } else if (tabId === 'ev') {
        fetchEvCabs();
    } else if (tabId === 'tracking') {
        fetchLiveTrips();
    }
}

window.addEventListener('hashchange', () => {
    if (!smtToken) return;
    const hash = (window.location.hash || '').replace('#', '');
    const allowed = ['home', 'datasource', 'inquiries', 'cabs', 'drivers', 'pg-drivers', 'pg-vehicles', 'pg-duties', 'pg-finance', 'reports', 'companies', 'ev', 'tracking', 'settings', 'help'];
    if (!allowed.includes(hash)) return;
    const current = document.querySelector('.admin-tab-content.active');
    if (current && current.id === `tab-${hash}`) return;
    switchTab(hash);
});

// --- DATA FETCHING (INQUIRIES) ---
async function fetchDashboardData() {
    if (!smtToken) return;

    try {
        // Fetch Stats
        const statsRes = await fetch('/api/stats', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        
        // Fetch Inquiries
        const inquiriesRes = await fetch('/api/inquiries', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });

        if (statsRes.status === 401 || inquiriesRes.status === 401) {
            adminLogout();
            alert("Session expired. Please log in again.");
            return;
        }

        const stats = await statsRes.json();
        allInquiries = await inquiriesRes.json();

        // Update stats widgets
        document.getElementById('stat-total').textContent = stats.total;
        document.getElementById('stat-pending').textContent = stats.pending;
        document.getElementById('stat-in-progress').textContent = stats.in_progress;
        document.getElementById('stat-completed').textContent = stats.completed;
        const zohoEl = document.getElementById('zoho-status');
        if (zohoEl) {
            zohoEl.textContent = stats.zoho_connected ? 'Zoho Sheet: connected' : 'Zoho Sheet: not connected (inquiries stay on this server)';
            zohoEl.style.color = stats.zoho_connected ? '#059669' : '#b45309';
        }

        filterInquiries();
    } catch (err) {
        console.error("Fetch dashboard error:", err);
    }
}

function renderInquiries(list) {
    const tableBody = document.getElementById('inquiries-table-body');
    tableBody.innerHTML = '';

    if (list.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No inquiries found matching criteria.</td></tr>`;
        return;
    }

    list.forEach(item => {
        const tr = document.createElement('tr');
        
        let badgeClass = 'pending';
        if (item.status === 'In Progress') badgeClass = 'in-progress';
        if (item.status === 'Completed') badgeClass = 'completed';

        tr.innerHTML = `
            <td>
                <strong style="color: var(--text-primary); font-size: 0.95rem;">${item.name}</strong>
                ${item.company ? `<div style="font-size: 0.75rem; color: var(--accent);">${item.company}</div>` : ''}
            </td>
            <td>
                <div style="font-size: 0.85rem;">📞 ${item.phone}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">✉️ ${item.email}</div>
            </td>
            <td>
                <span style="font-weight: 500;">${item.service_type}</span>
            </td>
            <td style="text-align: center;">
                <span style="font-family: var(--font-heading); font-weight: 600;">${item.employee_count > 0 ? item.employee_count : '-'}</span>
            </td>
            <td>
                <div style="max-width: 320px; font-size: 0.8rem; line-height: 1.4; color: var(--text-secondary); white-space: pre-wrap;">${item.details || 'N/A'}</div>
            </td>
            <td style="font-size: 0.8rem; color: var(--text-muted);">
                ${item.created_at}
            </td>
            <td>
                <select class="status-select" onchange="updateInquiryStatus(${item.id}, this.value)">
                    <option value="Pending" ${item.status === 'Pending' ? 'selected' : ''}>Pending</option>
                    <option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>In Progress</option>
                    <option value="Completed" ${item.status === 'Completed' ? 'selected' : ''}>Completed</option>
                </select>
                <div style="margin-top: 0.4rem;">
                    <span class="status-badge ${badgeClass}">${item.status}</span>
                </div>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

async function updateInquiryStatus(id, newStatus) {
    if (!smtToken) return;

    try {
        const response = await fetch(`/api/inquiries/${id}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (response.ok) {
            fetchDashboardData();
        } else {
            const errResult = await response.json();
            alert(`Failed to update status: ${errResult.error}`);
        }
    } catch (err) {
        console.error("Status update error:", err);
    }
}

function filterInquiries() {
    const searchQuery = document.getElementById('admin-search-input').value.toLowerCase().trim();
    const filterStatus = document.getElementById('admin-filter-select').value;

    const filtered = allInquiries.filter(item => {
        const matchStatus = (filterStatus === 'all' || item.status === filterStatus);
        const matchSearch = (
            item.name.toLowerCase().includes(searchQuery) ||
            item.email.toLowerCase().includes(searchQuery) ||
            item.phone.toLowerCase().includes(searchQuery) ||
            item.company.toLowerCase().includes(searchQuery) ||
            item.service_type.toLowerCase().includes(searchQuery) ||
            (item.details && item.details.toLowerCase().includes(searchQuery))
        );
        return matchStatus && matchSearch;
    });

    renderInquiries(filtered);
}

// --- MODAL UTILITIES ---
function showAdminModal(title, htmlContent) {
    document.getElementById('admin-modal-title').textContent = title;
    document.getElementById('admin-modal-body').innerHTML = htmlContent;
    document.getElementById('admin-modal-overlay').style.display = 'flex';
}

function closeAdminModal() {
    document.getElementById('admin-modal-overlay').style.display = 'none';
    document.getElementById('admin-modal-body').innerHTML = '';
    document.querySelectorAll('body > .modal-overlay').forEach((node) => node.remove());
}

// Aliases used by PostgreSQL duties/finance helpers.
function openModal(title, htmlContent) {
    showAdminModal(title, htmlContent);
}

function closeModal() {
    closeAdminModal();
}

// --- CABS MANAGEMENT ---
async function fetchCabs() {
    if (!smtToken) return;
    const tbody = document.getElementById('cabs-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Syncing fleet records...</td></tr>`;

    try {
        const res = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (!res.ok) throw new Error("Failed to fetch cabs");
        const cabs = await res.json();
        
        tbody.innerHTML = '';
        if (cabs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No vehicles registered. Click 'Add New Cab' to start.</td></tr>`;
            return;
        }

        for (const cab of cabs) {
            const tr = document.createElement('tr');
            
            // Asynchronously query doc warning status badge
            const docStatus = await getCabDocumentsStatus(cab.id);
            const evBadge = cab.is_ev ? `<span class="badge-ev" style="margin-left: 0.5rem;">EV</span>` : '';
            
            tr.innerHTML = `
                <td>
                    <strong style="color: var(--text-primary); font-size: 0.95rem;">${cab.reg_number}</strong>
                    ${evBadge}
                </td>
                <td>${cab.model}</td>
                <td>${cab.capacity} Seater</td>
                <td>${cab.fuel_type}</td>
                <td>
                    <span class="status-badge ${cab.status === 'Active' ? 'completed' : cab.status === 'Maintenance' ? 'pending' : 'expired'}">${cab.status}</span>
                </td>
                <td>
                    <span class="doc-badge ${docStatus.class}">${docStatus.text}</span>
                </td>
                <td>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick="manageCabDocuments(${cab.id}, '${cab.reg_number}')">📄 Docs</button>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick="showEditCabModal(${JSON.stringify(cab).replace(/"/g, '&quot;')})">Edit</button>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteCab(${cab.id})">Del</button>
                </td>
            `;
            tbody.appendChild(tr);
        }
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error syncing fleet database records.</td></tr>`;
    }
}

async function getCabDocumentsStatus(cabId) {
    try {
        const res = await fetch(`/api/admin/cabs/${cabId}/documents`, {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (!res.ok) return { text: 'No Docs', class: 'warning' };
        const docs = await res.json();
        if (docs.length === 0) return { text: 'No Docs', class: 'warning' };
        
        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);
        
        let status = { text: 'Valid', class: 'completed' };
        
        for (const doc of docs) {
            const expDate = new Date(doc.expiry_date);
            if (expDate < now) {
                return { text: 'Expired', class: 'expired' };
            } else if (expDate <= thirtyDaysLater) {
                status = { text: 'Expiring Soon', class: 'warning' };
            }
        }
        return status;
    } catch (err) {
        return { text: 'Error', class: 'expired' };
    }
}

function showAddCabModal() {
    const html = `
        <form id="cab-form" onsubmit="saveCab(event)">
            <input type="hidden" id="form-cab-id" value="">
            <div class="form-group-custom">
                <label>Registration Number*</label>
                <input type="text" id="cab-reg" class="form-control-custom" placeholder="e.g. KA-05-MB-1234" required>
            </div>
            <div class="form-group-custom">
                <label>Vehicle Model*</label>
                <input type="text" id="cab-model" class="form-control-custom" placeholder="e.g. Toyota Innova" required>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Seating Capacity*</label>
                    <input type="number" id="cab-capacity" class="form-control-custom" min="1" value="4" required>
                </div>
                <div class="form-group-custom">
                    <label>Fuel Type*</label>
                    <select id="cab-fuel" class="form-control-custom" onchange="toggleEvFields(this.value)" required>
                        <option value="Diesel">Diesel</option>
                        <option value="Petrol">Petrol</option>
                        <option value="CNG">CNG</option>
                        <option value="EV">EV (Electric)</option>
                    </select>
                </div>
            </div>
            <div class="form-group-custom">
                <label>Status</label>
                <select id="cab-status" class="form-control-custom">
                    <option value="Active">Active</option>
                    <option value="Maintenance">Maintenance</option>
                    <option value="Inactive">Inactive</option>
                </select>
            </div>
            <div id="ev-fields" style="display: none; border-top: 1px dashed var(--border-color); padding-top: 1rem; margin-top: 1rem;">
                <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">EV Fleet Parameters</h4>
                <div class="form-group-custom">
                    <label>Battery Capacity (e.g. 26 kWh)</label>
                    <input type="text" id="cab-battery" class="form-control-custom" placeholder="e.g. 26 kWh">
                </div>
                <div class="form-grid-2">
                    <div class="form-group-custom">
                        <label>Charge Status (SOC %)</label>
                        <input type="number" id="cab-charge" class="form-control-custom" min="0" max="100" placeholder="e.g. 80">
                    </div>
                    <div class="form-group-custom">
                        <label>Remaining Est. Range (KM)</label>
                        <input type="number" id="cab-range" class="form-control-custom" min="0" placeholder="e.g. 150">
                    </div>
                </div>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Save Vehicle</button>
        </form>
    `;
    showAdminModal("Add Vehicle Registry", html);
}

function showEditCabModal(cab) {
    showAddCabModal();
    document.getElementById('admin-modal-title').textContent = "Modify Vehicle Details";
    document.getElementById('form-cab-id').value = cab.id;
    document.getElementById('cab-reg').value = cab.reg_number;
    document.getElementById('cab-model').value = cab.model;
    document.getElementById('cab-capacity').value = cab.capacity;
    document.getElementById('cab-fuel').value = cab.fuel_type;
    document.getElementById('cab-status').value = cab.status;
    
    if (cab.fuel_type === 'EV') {
        toggleEvFields('EV');
        document.getElementById('cab-battery').value = cab.battery_capacity || '';
        document.getElementById('cab-charge').value = cab.charge_status !== null ? cab.charge_status : '';
        document.getElementById('cab-range').value = cab.range_km !== null ? cab.range_km : '';
    }
}

function toggleEvFields(value) {
    const evFields = document.getElementById('ev-fields');
    if (evFields) {
        if (value === 'EV') {
            evFields.style.display = 'block';
        } else {
            evFields.style.display = 'none';
        }
    }
}

async function saveCab(event) {
    event.preventDefault();
    if (!smtToken) return;

    const cabId = document.getElementById('form-cab-id').value;
    const payload = {
        reg_number: document.getElementById('cab-reg').value.trim(),
        model: document.getElementById('cab-model').value.trim(),
        capacity: document.getElementById('cab-capacity').value,
        fuel_type: document.getElementById('cab-fuel').value,
        status: document.getElementById('cab-status').value,
        is_ev: document.getElementById('cab-fuel').value === 'EV' ? 1 : 0,
        battery_capacity: document.getElementById('cab-battery') ? document.getElementById('cab-battery').value.trim() : null,
        charge_status: document.getElementById('cab-charge') ? document.getElementById('cab-charge').value : null,
        range_km: document.getElementById('cab-range') ? document.getElementById('cab-range').value : null
    };

    const url = cabId ? `/api/admin/cabs/${cabId}` : '/api/admin/cabs';
    const method = cabId ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            closeAdminModal();
            fetchCabs();
        } else {
            alert(result.error || "Failed to save cab.");
        }
    } catch (err) {
        console.error("Save Cab Error:", err);
    }
}

async function deleteCab(cabId) {
    if (!confirm("Are you sure you want to remove this vehicle? All related assignments and documents will be deleted.")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/cabs/${cabId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchCabs();
        } else {
            alert("Failed to delete vehicle.");
        }
    } catch (err) {
        console.error("Delete Cab Error:", err);
    }
}

// --- DOCUMENT SUB-MANAGEMENT ---
async function manageCabDocuments(cabId, regNum) {
    currentCabIdForDocs = cabId;
    const html = `
        <div style="margin-bottom: 2rem;">
            <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">Legal Documents - ${regNum}</h4>
            <div id="docs-list-container">
                <p style="color: var(--text-muted); font-size: 0.85rem;">Retrieving documents...</p>
            </div>
        </div>
        
        <form id="doc-form" onsubmit="saveDocument(event)" style="border-top: 1px solid var(--border-color); padding-top: 1.5rem;">
            <h4 style="font-size: 0.95rem; margin-bottom: 1rem; color: var(--primary);">Add Legal Document</h4>
            <div class="form-group-custom">
                <label>Document Category*</label>
                <select id="doc-type" class="form-control-custom" required>
                    <option value="Insurance">Insurance Policy</option>
                    <option value="Permit">National Permit</option>
                    <option value="Fitness">Fitness Certificate</option>
                    <option value="Road Tax">Road Tax Certificate</option>
                </select>
            </div>
            <div class="form-group-custom">
                <label>Certificate / Document Number*</label>
                <input type="text" id="doc-number" class="form-control-custom" placeholder="e.g. INS-998822" required>
            </div>
            <div class="form-group-custom">
                <label>Expiration Date*</label>
                <input type="date" id="doc-expiry" class="form-control-custom" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1rem;">Upload Document</button>
        </form>
    `;
    showAdminModal("Manage Cabs Documents", html);
    loadCabDocuments(cabId);
}

async function loadCabDocuments(cabId) {
    if (!smtToken) return;
    const container = document.getElementById('docs-list-container');
    
    try {
        const res = await fetch(`/api/admin/cabs/${cabId}/documents`, {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const docs = await res.json();
        
        container.innerHTML = '';
        if (docs.length === 0) {
            container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 1rem 0;">No documents associated with this vehicle.</p>`;
            return;
        }

        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);

        docs.forEach(doc => {
            const expDate = new Date(doc.expiry_date);
            let badgeClass = 'valid';
            let badgeText = 'Valid';

            if (expDate < now) {
                badgeClass = 'expired';
                badgeText = 'Expired';
            } else if (expDate <= thirtyDaysLater) {
                badgeClass = 'warning';
                badgeText = 'Expiring Soon';
            }

            const div = document.createElement('div');
            div.className = 'doc-item-row';
            div.innerHTML = `
                <div class="doc-details">
                    <span class="doc-name">${doc.doc_type}</span>
                    <span class="doc-number">No: ${doc.doc_number}</span>
                    <span class="doc-expiry">Expires: ${doc.expiry_date}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span class="doc-badge ${badgeClass}">${badgeText}</span>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteDocument(${doc.id})">Delete</button>
                </div>
            `;
            container.appendChild(div);
        });
    } catch (err) {
        console.error("Load Documents error:", err);
    }
}

async function saveDocument(event) {
    event.preventDefault();
    if (!smtToken || !currentCabIdForDocs) return;

    const payload = {
        doc_type: document.getElementById('doc-type').value,
        doc_number: document.getElementById('doc-number').value.trim(),
        expiry_date: document.getElementById('doc-expiry').value
    };

    try {
        const res = await fetch(`/api/admin/cabs/${currentCabIdForDocs}/documents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            document.getElementById('doc-number').value = '';
            document.getElementById('doc-expiry').value = '';
            loadCabDocuments(currentCabIdForDocs);
            fetchCabs(); // Refresh parent table list
        } else {
            alert("Failed to save document.");
        }
    } catch (err) {
        console.error("Save Document Error:", err);
    }
}

async function deleteDocument(docId) {
    if (!confirm("Remove this document record?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/documents/${docId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            loadCabDocuments(currentCabIdForDocs);
            fetchCabs(); // Refresh parent table list
        } else {
            alert("Failed to delete document.");
        }
    } catch (err) {
        console.error("Delete Document Error:", err);
    }
}

// --- DRIVER MANAGEMENT ---
async function fetchDrivers() {
    if (!smtToken) return;
    const tbody = document.getElementById('drivers-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Syncing staff database...</td></tr>`;

    try {
        const res = await fetch('/api/admin/drivers', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const drivers = await res.json();
        
        tbody.innerHTML = '';
        if (drivers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No drivers registered. Click 'Add New Driver' to start.</td></tr>`;
            return;
        }

        const now = new Date();
        const thirtyDaysLater = new Date();
        thirtyDaysLater.setDate(now.getDate() + 30);

        drivers.forEach(driver => {
            const tr = document.createElement('tr');
            
            const expDate = new Date(driver.license_expiry);
            let licenseAlert = '';
            if (expDate < now) {
                licenseAlert = ` <span class="doc-badge expired">Expired</span>`;
            } else if (expDate <= thirtyDaysLater) {
                licenseAlert = ` <span class="doc-badge warning">Expiring</span>`;
            }

            tr.innerHTML = `
                <td><strong style="color: var(--text-primary); font-size: 0.95rem;">${driver.name}</strong></td>
                <td>${driver.phone}</td>
                <td><code>${driver.license_number}</code></td>
                <td>${driver.license_expiry}${licenseAlert}</td>
                <td>
                    ${driver.assigned_cab_id ? `<strong>${driver.cab_reg}</strong> <span style="font-size:0.75rem; color: var(--text-secondary);">(${driver.cab_model})</span>` : '<span style="color: var(--text-muted); font-size:0.8rem;">Unassigned</span>'}
                </td>
                <td>
                    <span class="status-badge ${driver.status === 'Active' ? 'completed' : 'expired'}">${driver.status}</span>
                </td>
                <td>
                    <button class="status-select" style="margin-right: 0.25rem;" onclick='showEditDriverModal(${JSON.stringify(driver).replace(/'/g, "\\'")})'>Edit</button>
                    <button class="status-select" style="color: #ef4444;" onclick="deleteDriver(${driver.id})">Del</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error syncing driver database.</td></tr>`;
    }
}

async function showAddDriverModal() {
    if (!smtToken) return;

    try {
        const cabsRes = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await cabsRes.json();
        
        let cabOptions = '<option value="None">None (Unassigned)</option>';
        cabs.forEach(cab => {
            cabOptions += `<option value="${cab.id}">${cab.reg_number} - ${cab.model}</option>`;
        });

        const html = `
            <form id="driver-form" onsubmit="saveDriver(event)">
                <input type="hidden" id="form-driver-id" value="">
                <div class="form-group-custom">
                    <label>Driver Full Name*</label>
                    <input type="text" id="driver-name" class="form-control-custom" placeholder="e.g. Ramesh Kumar" required>
                </div>
                <div class="form-group-custom">
                    <label>Mobile Number*</label>
                    <input type="text" id="driver-phone" class="form-control-custom" placeholder="e.g. +91 9845012345" required>
                </div>
                <div class="form-group-custom">
                    <label>Driving License Number*</label>
                    <input type="text" id="driver-license" class="form-control-custom" placeholder="e.g. DL-KA05202..." required>
                </div>
                <div class="form-group-custom">
                    <label>License Expiration Date*</label>
                    <input type="date" id="driver-license-expiry" class="form-control-custom" required>
                </div>
                <div class="form-grid-2">
                    <div class="form-group-custom">
                        <label>Associate Vehicle</label>
                        <select id="driver-cab" class="form-control-custom">
                            ${cabOptions}
                        </select>
                    </div>
                    <div class="form-group-custom">
                        <label>Status</label>
                        <select id="driver-status" class="form-control-custom">
                            <option value="Active">Active</option>
                            <option value="On Leave">On Leave</option>
                            <option value="Inactive">Inactive</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Save Driver</button>
            </form>
        `;
        showAdminModal("Add Driver Record", html);
    } catch (err) {
        console.error(err);
    }
}

async function showEditDriverModal(driver) {
    await showAddDriverModal();
    document.getElementById('admin-modal-title').textContent = "Modify Driver Details";
    document.getElementById('form-driver-id').value = driver.id;
    document.getElementById('driver-name').value = driver.name;
    document.getElementById('driver-phone').value = driver.phone;
    document.getElementById('driver-license').value = driver.license_number;
    document.getElementById('driver-license-expiry').value = driver.license_expiry;
    document.getElementById('driver-cab').value = driver.assigned_cab_id ? driver.assigned_cab_id : 'None';
    document.getElementById('driver-status').value = driver.status;
}

async function saveDriver(event) {
    event.preventDefault();
    if (!smtToken) return;

    const driverId = document.getElementById('form-driver-id').value;
    const payload = {
        name: document.getElementById('driver-name').value.trim(),
        phone: document.getElementById('driver-phone').value.trim(),
        license_number: document.getElementById('driver-license').value.trim(),
        license_expiry: document.getElementById('driver-license-expiry').value,
        status: document.getElementById('driver-status').value,
        assigned_cab_id: document.getElementById('driver-cab').value
    };

    const url = driverId ? `/api/admin/drivers/${driverId}` : '/api/admin/drivers';
    const method = driverId ? 'PUT' : 'POST';

    try {
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (res.ok) {
            closeAdminModal();
            fetchDrivers();
        } else {
            alert(result.error || "Failed to save driver.");
        }
    } catch (err) {
        console.error("Save Driver Error:", err);
    }
}

async function deleteDriver(driverId) {
    if (!confirm("Are you sure you want to remove this driver from registry?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/drivers/${driverId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchDrivers();
        } else {
            alert("Failed to delete driver.");
        }
    } catch (err) {
        console.error("Delete Driver Error:", err);
    }
}

// --- COMPANIES MANAGEMENT ---
const companyDirectory = new Map();

function setCompanyStatus(message, isError) {
    const status = document.getElementById('companies-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function renderCompanies(companies) {
    const tbody = document.getElementById('companies-table-body');
    companyDirectory.clear();
    tbody.replaceChildren();
    if (!companies.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 5;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No companies yet. Add a company and choose Bengaluru or Hyderabad.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    companies.forEach((company) => {
        companyDirectory.set(company.id, company);
        const row = document.createElement('tr');
        const name = document.createElement('td');
        const strong = document.createElement('strong');
        strong.textContent = company.name;
        name.appendChild(strong);
        const contact = document.createElement('td');
        [company.contact_person, company.contact_email, company.contact_phone].forEach((part) => {
            if (!part) return;
            const line = document.createElement('div');
            line.textContent = part;
            contact.appendChild(line);
        });
        const address = document.createElement('td');
        address.textContent = company.address || '';
        const cities = document.createElement('td');
        cities.textContent = (company.branches || []).map((branch) => branch.city || branch.code).join(', ');
        const actions = document.createElement('td');
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'status-select';
        details.style.marginRight = '0.25rem';
        details.textContent = 'Details';
        details.addEventListener('click', () => showCompanyDetails(company.id));
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => showEditCompanyModal(company));
        actions.append(details, edit);
        row.append(name, contact, address, cities, actions);
        tbody.appendChild(row);
    });
}

async function fetchCompanies() {
    if (!smtToken) return;
    const tbody = document.getElementById('companies-table-body');
    const addButton = document.getElementById('companies-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setCompanyStatus('Loading companies...');
    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading companies...</td></tr>';
    try {
        const res = await fetch('/api/companies', { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setCompanyStatus(body.message || 'Only an owner can manage companies.', true);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Company management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setCompanyStatus(body.message || 'Companies could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #ef4444;">Companies could not be loaded.</td></tr>';
            return;
        }
        setCompanyStatus('');
        renderCompanies(body.data || []);
    } catch (err) {
        console.error(err);
        setCompanyStatus('Companies could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #ef4444;">Companies could not be loaded.</td></tr>';
    }
}

function cityChoices(selected) {
    const chosen = new Set(selected || []);
    return ['BLR', 'HYD'].map((code) => {
        const label = code === 'BLR' ? 'Bengaluru' : 'Hyderabad';
        const checked = chosen.has(code) ? 'checked' : '';
        return `<label class="check"><input type="checkbox" class="company-city" value="${code}" ${checked}> ${label}</label>`;
    }).join('');
}

function selectedCities() {
    return Array.from(document.querySelectorAll('.company-city:checked')).map((box) => box.value);
}

function showAddCompanyModal() {
    const html = `
        <form id="company-form" onsubmit="saveCompany(event)">
            <input type="hidden" id="form-company-id" value="">
            <div class="form-group-custom">
                <label>Company name*</label>
                <input type="text" id="company-name" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Contact person</label>
                <input type="text" id="company-contact" class="form-control-custom">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Contact email</label>
                    <input type="email" id="company-email" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Contact phone</label>
                    <input type="text" id="company-phone" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Address</label>
                <textarea id="company-address" class="form-control-custom"></textarea>
            </div>
            <div class="form-group-custom company-cities">
                <label>Cities*</label>
                <div style="display: flex; gap: 1rem;">${cityChoices([])}</div>
            </div>
            <p id="company-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save company</button>
        </form>
    `;
    showAdminModal('Add company', html);
}

function showEditCompanyModal(company) {
    showAddCompanyModal();
    document.getElementById('admin-modal-title').textContent = 'Edit company';
    document.getElementById('form-company-id').value = company.id;
    document.getElementById('company-name').value = company.name || '';
    document.getElementById('company-contact').value = company.contact_person || '';
    document.getElementById('company-email').value = company.contact_email || '';
    document.getElementById('company-phone').value = company.contact_phone || '';
    document.getElementById('company-address').value = company.address || '';
    const cities = document.querySelector('.company-cities');
    if (cities) cities.remove();
}

function companyPayload() {
    return {
        name: document.getElementById('company-name').value.trim(),
        contact_person: document.getElementById('company-contact').value.trim(),
        contact_email: document.getElementById('company-email').value.trim(),
        contact_phone: document.getElementById('company-phone').value.trim(),
        address: document.getElementById('company-address').value.trim()
    };
}

async function saveCompany(event) {
    event.preventDefault();
    const error = document.getElementById('company-form-error');
    const companyId = document.getElementById('form-company-id').value;
    const payload = companyPayload();
    if (!payload.name) {
        error.textContent = 'Company name is required.';
        return;
    }
    if (!companyId) {
        payload.branch_codes = selectedCities();
        if (!payload.branch_codes.length) {
            error.textContent = 'Select Bengaluru or Hyderabad.';
            return;
        }
    }
    error.textContent = 'Saving...';
    try {
        const res = await fetch(companyId ? `/api/companies/${companyId}` : '/api/companies', {
            method: companyId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The company could not be saved.';
            return;
        }
        closeAdminModal();
        fetchCompanies();
    } catch (err) {
        console.error(err);
        error.textContent = 'The company could not be saved.';
    }
}

async function showCompanyDetails(companyId) {
    const holder = document.createElement('div');
    holder.innerHTML = '<p>Loading company...</p>';
    showAdminModal('Company details', '');
    document.getElementById('admin-modal-body').replaceChildren(holder);
    try {
        const res = await fetch(`/api/companies/${companyId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            holder.textContent = body.message || 'Company details could not be loaded.';
            return;
        }
        const company = body.data;
        companyDirectory.set(company.id, company);
        holder.replaceChildren();
        const title = document.createElement('h3');
        title.textContent = company.name;
        const contact = document.createElement('p');
        contact.textContent = [company.contact_person, company.contact_email, company.contact_phone, company.address]
            .filter(Boolean)
            .join(' · ') || 'No contact details yet.';
        const note = document.createElement('p');
        note.id = 'company-detail-error';
        note.style.color = '#ef4444';
        const cities = document.createElement('div');
        cities.style.display = 'flex';
        cities.style.gap = '1rem';
        ['BLR', 'HYD'].forEach((code) => {
            const label = document.createElement('label');
            label.className = 'check';
            const box = document.createElement('input');
            box.type = 'checkbox';
            box.checked = (company.branches || []).some((branch) => branch.code === code);
            box.addEventListener('change', () => setCompanyCity(company.id, code, box));
            label.append(box, document.createTextNode(code === 'BLR' ? ' Bengaluru' : ' Hyderabad'));
            cities.appendChild(label);
        });
        holder.append(title, contact, cities, note, clientSection(company.id), driverSection(company.id), vehicleSection(company.id));
        loadCompanyClients(company.id);
        loadCompanyDrivers(company.id);
        loadCompanyVehicles(company.id);
    } catch (err) {
        console.error(err);
        holder.textContent = 'Company details could not be loaded.';
    }
}

async function setCompanyCity(companyId, code, box) {
    const note = document.getElementById('company-detail-error');
    if (note) note.textContent = 'Saving city...';
    try {
        const res = await fetch(`/api/companies/${companyId}/branches/${code}`, {
            method: box.checked ? 'POST' : 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            box.checked = !box.checked;
            if (note) note.textContent = body.message || 'The city could not be updated.';
            return;
        }
        if (note) note.textContent = '';
        companyDirectory.set(body.data.id, body.data);
        fetchCompanies();
        if (document.getElementById('company-driver-list')) loadCompanyDrivers(body.data.id);
        if (document.getElementById('company-vehicle-list')) loadCompanyVehicles(body.data.id);
    } catch (err) {
        box.checked = !box.checked;
        if (note) note.textContent = 'The city could not be updated.';
    }
}

function clientSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Clients';
    const list = document.createElement('div');
    list.id = 'company-client-list';
    list.textContent = 'Loading clients...';
    const create = document.createElement('form');
    create.addEventListener('submit', (event) => createCompanyClient(event, companyId));
    create.innerHTML = `
        <div class="form-group-custom"><label>Full name*</label><input id="client-name" class="form-control-custom" required></div>
        <div class="form-group-custom"><label>Email*</label><input id="client-email" type="email" class="form-control-custom" required></div>
        <div class="form-group-custom"><label>Phone</label><input id="client-phone" class="form-control-custom"></div>
        <button type="submit" class="btn btn-primary">Create client</button>
    `;
    const link = document.createElement('form');
    link.addEventListener('submit', (event) => linkExistingClient(event, companyId));
    link.innerHTML = `
        <div class="form-group-custom"><label>Existing client email</label><input id="client-link-email" type="email" class="form-control-custom" required></div>
        <button type="submit" class="btn btn-primary">Link client</button>
    `;
    const error = document.createElement('p');
    error.id = 'company-client-error';
    error.style.color = '#ef4444';
    section.append(heading, list, create, link, error);
    return section;
}

function renderCompanyClients(companyId, clients) {
    const list = document.getElementById('company-client-list');
    if (!list) return;
    list.replaceChildren();
    if (!clients.length) {
        list.textContent = 'No clients linked yet.';
        return;
    }
    const isOwner = staffSession.role === 'od';
    clients.forEach((client) => {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.gap = '0.75rem';
        row.style.marginBottom = '0.4rem';
        row.style.flexWrap = 'wrap';
        const label = document.createElement('span');
        label.textContent = [client.full_name, client.email, client.phone].filter(Boolean).join(' · ');
        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.gap = '0.35rem';
        if (isOwner) {
            const provision = document.createElement('button');
            provision.type = 'button';
            provision.className = 'status-select';
            provision.textContent = 'Provision login';
            provision.addEventListener('click', () => provisionClientLogin(client.id, client.full_name || client.email));
            actions.appendChild(provision);
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'status-select';
        button.textContent = 'Remove link';
        button.addEventListener('click', () => removeCompanyClient(companyId, client.id));
        actions.appendChild(button);
        row.append(label, actions);
        list.appendChild(row);
    });
}

async function provisionClientLogin(clientId, label) {
    if (staffSession.role !== 'od') {
        setClientError('Only an owner can provision client portal logins.');
        return;
    }
    const password = window.prompt(
        `Set a portal password for ${label || 'this client'} (min 8 characters).`
    );
    if (password === null) return;
    if (!password || password.length < 8) {
        setClientError('Password must be at least 8 characters.');
        return;
    }
    setClientError('Provisioning client login...');
    try {
        const res = await fetch(`/api/clients/${clientId}/login-account`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setClientError(body.message || 'Client login could not be provisioned.');
            return;
        }
        setClientError(body.data && body.data.created === false
            ? 'Client login password updated.'
            : 'Client portal login provisioned.');
    } catch (err) {
        console.error(err);
        setClientError('Client login could not be provisioned.');
    }
}

async function loadCompanyClients(companyId) {
    const list = document.getElementById('company-client-list');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            if (list) list.textContent = body.message || 'Clients could not be loaded.';
            return;
        }
        renderCompanyClients(companyId, body.data || []);
    } catch (err) {
        console.error(err);
        if (list) list.textContent = 'Clients could not be loaded.';
    }
}

function setClientError(message) {
    const error = document.getElementById('company-client-error');
    if (error) error.textContent = message || '';
}

async function createCompanyClient(event, companyId) {
    event.preventDefault();
    setClientError('Saving client...');
    try {
        const created = await fetch('/api/clients', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                full_name: document.getElementById('client-name').value.trim(),
                email: document.getElementById('client-email').value.trim(),
                phone: document.getElementById('client-phone').value.trim()
            })
        });
        const createdBody = await created.json();
        if (!created.ok || !createdBody.success) {
            setClientError(createdBody.message || 'The client could not be created.');
            return;
        }
        const linked = await fetch(`/api/companies/${companyId}/clients`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: createdBody.data.id })
        });
        const linkedBody = await linked.json();
        if (!linked.ok || !linkedBody.success) {
            setClientError(linkedBody.message || 'The client was created but could not be linked.');
            return;
        }
        event.target.reset();
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The client could not be created.');
    }
}

async function linkExistingClient(event, companyId) {
    event.preventDefault();
    setClientError('Linking client...');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: document.getElementById('client-link-email').value.trim() })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setClientError(body.message || 'The client could not be linked.');
            return;
        }
        event.target.reset();
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The client could not be linked.');
    }
}

async function removeCompanyClient(companyId, clientId) {
    setClientError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/clients/${clientId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setClientError(body.message || 'The link could not be removed.');
            return;
        }
        setClientError('');
        loadCompanyClients(companyId);
    } catch (err) {
        console.error(err);
        setClientError('The link could not be removed.');
    }
}

function driverSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Drivers';
    const list = document.createElement('div');
    list.id = 'company-driver-list';
    list.textContent = 'Loading drivers...';
    const form = document.createElement('form');
    form.addEventListener('submit', (event) => linkCompanyDriver(event, companyId));
    const field = document.createElement('div');
    field.className = 'form-group-custom';
    const label = document.createElement('label');
    label.textContent = 'Link an existing driver';
    const choice = document.createElement('select');
    choice.id = 'company-driver-choice';
    choice.className = 'form-control-custom';
    const error = document.createElement('p');
    error.id = 'company-driver-error';
    error.style.color = '#ef4444';
    const button = document.createElement('button');
    button.type = 'submit';
    button.className = 'btn btn-primary';
    button.textContent = 'Link driver';
    field.append(label, choice);
    form.append(field, error, button);
    section.append(heading, list, form);
    return section;
}

function setCompanyDriverError(message) {
    const error = document.getElementById('company-driver-error');
    if (error) error.textContent = message || '';
}

function companySharesDriverCity(company, driver) {
    const cities = new Set((company.branches || []).map((branch) => branch.code));
    return (driver.branches || []).some((branch) => cities.has(branch.code));
}

async function loadCompanyDrivers(companyId) {
    const list = document.getElementById('company-driver-list');
    const choice = document.getElementById('company-driver-choice');
    const company = companyDirectory.get(companyId);
    if (!list || !choice || !company) return;
    list.textContent = 'Loading drivers...';
    try {
        const [linkedRes, directoryRes] = await Promise.all([
            fetch(`/api/companies/${companyId}/drivers`, { credentials: 'same-origin' }),
            fetch('/api/drivers?active=true', { credentials: 'same-origin' })
        ]);
        const linkedBody = await linkedRes.json();
        const directoryBody = await directoryRes.json();
        if (!linkedRes.ok || !linkedBody.success) {
            list.textContent = linkedBody.message || 'Drivers could not be loaded.';
            return;
        }
        renderCompanyDrivers(companyId, linkedBody.data || []);
        choice.replaceChildren();
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Choose a driver';
        choice.appendChild(placeholder);
        const linkedIds = new Set((linkedBody.data || []).map((driver) => driver.id));
        const eligible = (directoryBody.data || []).filter((driver) => (
            driver.active && !linkedIds.has(driver.id) && companySharesDriverCity(company, driver)
        ));
        eligible.forEach((driver) => {
            const option = document.createElement('option');
            option.value = driver.id;
            const city = driver.primary_branch ? (driver.primary_branch.city || driver.primary_branch.code) : '';
            option.textContent = city ? `${driver.display_name} · ${city}` : driver.display_name;
            choice.appendChild(option);
        });
        if (!eligible.length) {
            const empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No active drivers share a city with this company';
            choice.appendChild(empty);
        }
    } catch (err) {
        console.error(err);
        list.textContent = 'Drivers could not be loaded.';
    }
}

function renderCompanyDrivers(companyId, drivers) {
    const list = document.getElementById('company-driver-list');
    list.replaceChildren();
    if (!drivers.length) {
        list.textContent = 'No drivers linked to this company.';
        return;
    }
    drivers.forEach((driver) => {
        const row = document.createElement('p');
        const city = driver.primary_branch ? (driver.primary_branch.city || driver.primary_branch.code) : '';
        row.textContent = [
            driver.display_name,
            driver.phone,
            city,
            driver.active ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.5rem';
        remove.textContent = 'Remove link';
        remove.addEventListener('click', () => unlinkCompanyDriver(companyId, driver.id, driver.display_name));
        row.appendChild(remove);
        list.appendChild(row);
    });
}

async function linkCompanyDriver(event, companyId) {
    event.preventDefault();
    const choice = document.getElementById('company-driver-choice');
    if (!choice.value) {
        setCompanyDriverError('Choose a driver from the directory.');
        return;
    }
    setCompanyDriverError('Linking driver...');
    try {
        const res = await fetch(`/api/companies/${companyId}/drivers`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ driver_id: choice.value })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyDriverError(body.message || 'The driver could not be linked.');
            return;
        }
        setCompanyDriverError('');
        loadCompanyDrivers(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyDriverError('The driver could not be linked.');
    }
}

async function unlinkCompanyDriver(companyId, driverId, driverName) {
    const label = driverName || 'this driver';
    if (!window.confirm(`Remove ${label} from this company? The driver and the company both stay in their directories.`)) return;
    setCompanyDriverError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/drivers/${driverId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyDriverError(body.message || 'The link could not be removed.');
            return;
        }
        setCompanyDriverError('');
        loadCompanyDrivers(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyDriverError('The link could not be removed.');
    }
}

function vehicleSection(companyId) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = 'Vehicles';
    const list = document.createElement('div');
    list.id = 'company-vehicle-list';
    list.textContent = 'Loading vehicles...';
    const form = document.createElement('form');
    form.addEventListener('submit', (event) => linkCompanyVehicle(event, companyId));
    const field = document.createElement('div');
    field.className = 'form-group-custom';
    const label = document.createElement('label');
    label.textContent = 'Link an existing vehicle';
    const choice = document.createElement('select');
    choice.id = 'company-vehicle-choice';
    choice.className = 'form-control-custom';
    const error = document.createElement('p');
    error.id = 'company-vehicle-error';
    error.style.color = '#ef4444';
    const button = document.createElement('button');
    button.type = 'submit';
    button.className = 'btn btn-primary';
    button.textContent = 'Link vehicle';
    field.append(label, choice);
    form.append(field, error, button);
    section.append(heading, list, form);
    return section;
}

function setCompanyVehicleError(message) {
    const error = document.getElementById('company-vehicle-error');
    if (error) error.textContent = message || '';
}

async function loadCompanyVehicles(companyId) {
    const list = document.getElementById('company-vehicle-list');
    const choice = document.getElementById('company-vehicle-choice');
    const company = companyDirectory.get(companyId);
    if (!list || !choice || !company) return;
    list.textContent = 'Loading vehicles...';
    try {
        const [linkedRes, directoryRes] = await Promise.all([
            fetch(`/api/companies/${companyId}/vehicles`, { credentials: 'same-origin' }),
            fetch('/api/vehicles?status=active', { credentials: 'same-origin' })
        ]);
        const linkedBody = await linkedRes.json();
        const directoryBody = await directoryRes.json();
        if (!linkedRes.ok || !linkedBody.success) {
            list.textContent = linkedBody.message || 'Vehicles could not be loaded.';
            return;
        }
        renderCompanyVehicles(companyId, linkedBody.data || []);
        choice.replaceChildren();
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Choose a vehicle';
        choice.appendChild(placeholder);
        const cities = new Set((company.branches || []).map((branch) => branch.code));
        const linkedIds = new Set((linkedBody.data || []).map((vehicle) => vehicle.id));
        const eligible = (directoryBody.data || []).filter((vehicle) => (
            vehicle.status === 'active'
            && vehicle.branch
            && cities.has(vehicle.branch.code)
            && !linkedIds.has(vehicle.id)
        ));
        eligible.forEach((vehicle) => {
            const option = document.createElement('option');
            option.value = vehicle.id;
            const city = vehicle.branch ? (vehicle.branch.city || vehicle.branch.code) : '';
            option.textContent = city ? `${vehicle.registration_number} · ${city}` : vehicle.registration_number;
            choice.appendChild(option);
        });
        if (!eligible.length) {
            const empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No active vehicles are garaged in this company\'s cities';
            choice.appendChild(empty);
        }
    } catch (err) {
        console.error(err);
        list.textContent = 'Vehicles could not be loaded.';
    }
}

function renderCompanyVehicles(companyId, vehicles) {
    const list = document.getElementById('company-vehicle-list');
    list.replaceChildren();
    if (!vehicles.length) {
        list.textContent = 'No vehicles linked to this company.';
        return;
    }
    vehicles.forEach((vehicle) => {
        const row = document.createElement('p');
        const city = vehicle.branch ? (vehicle.branch.city || vehicle.branch.code) : '';
        row.textContent = [
            vehicle.registration_number,
            vehicle.model,
            city,
            vehicle.status === 'active' ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ');
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.5rem';
        remove.textContent = 'Remove link';
        remove.addEventListener('click', () => unlinkCompanyVehicle(companyId, vehicle.id, vehicle.registration_number));
        row.appendChild(remove);
        list.appendChild(row);
    });
}

async function linkCompanyVehicle(event, companyId) {
    event.preventDefault();
    const choice = document.getElementById('company-vehicle-choice');
    if (!choice.value) {
        setCompanyVehicleError('Choose a vehicle from the directory.');
        return;
    }
    setCompanyVehicleError('Linking vehicle...');
    try {
        const res = await fetch(`/api/companies/${companyId}/vehicles`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_id: choice.value })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyVehicleError(body.message || 'The vehicle could not be linked.');
            return;
        }
        setCompanyVehicleError('');
        loadCompanyVehicles(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyVehicleError('The vehicle could not be linked.');
    }
}

async function unlinkCompanyVehicle(companyId, vehicleId, registration) {
    const label = registration || 'this vehicle';
    if (!window.confirm(`Remove ${label} from this company? The vehicle and the company both stay in their directories.`)) return;
    setCompanyVehicleError('Removing link...');
    try {
        const res = await fetch(`/api/companies/${companyId}/vehicles/${vehicleId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setCompanyVehicleError(body.message || 'The link could not be removed.');
            return;
        }
        setCompanyVehicleError('');
        loadCompanyVehicles(companyId);
        fetchCompanies();
    } catch (err) {
        console.error(err);
        setCompanyVehicleError('The link could not be removed.');
    }
}


// --- POSTGRESQL DRIVER DIRECTORY ---
function setPgDriverStatus(message, isError) {
    const status = document.getElementById('pg-drivers-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function pgDriverBranchLabel(driver) {
    const branch = driver.primary_branch;
    if (!branch) return '';
    return branch.city || branch.name || branch.code || '';
}

function pgVerificationLabel(status) {
    if (status === 'verified') return 'Verified';
    if (status === 'rejected') return 'Rejected';
    return 'Unverified';
}

function pgVerificationBadge(status) {
    const badge = document.createElement('span');
    const tone = status === 'verified' ? 'valid' : status === 'rejected' ? 'expired' : 'warning';
    badge.className = 'doc-badge ' + tone;
    badge.textContent = pgVerificationLabel(status);
    return badge;
}

function pgDuplicateSummary(driver) {
    const warnings = driver.duplicate_warnings || [];
    if (!warnings.length) return 'None';
    const labels = [];
    warnings.forEach((warning) => {
        const label = warning.match_kind === 'phone' ? 'Phone' : 'Licence';
        if (labels.indexOf(label) === -1) labels.push(label);
    });
    return labels.join(', ');
}

function pgActorLabel(record) {
    return (record && (record.actor_name || record.actor_email)) || 'Owner';
}

function pgHistoryWhen(value) {
    if (!value) return '';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString();
}

function renderPgDuplicateWarnings(warnings, container) {
    container.replaceChildren();
    if (!warnings || !warnings.length) {
        const empty = document.createElement('p');
        empty.textContent = 'No duplicate phone or licence warning.';
        container.appendChild(empty);
        return;
    }
    const note = document.createElement('p');
    note.style.color = '#b45309';
    note.textContent = 'Duplicate warning only. Matching drivers are not merged, deleted, or rejected.';
    container.appendChild(note);
    warnings.forEach((warning) => {
        const other = warning.other_driver || {};
        const line = document.createElement('p');
        const kind = warning.match_kind === 'phone' ? 'Same phone' : 'Same licence';
        line.textContent = [
            kind,
            other.display_name,
            other.phone,
            other.license_number,
            other.verification_status ? pgVerificationLabel(other.verification_status) : '',
            other.active === false ? 'Inactive' : other.active === true ? 'Active' : ''
        ].filter(Boolean).join(' · ');
        container.appendChild(line);
    });
}

function pgDriverActionButton(label, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'status-select';
    button.style.marginRight = '0.25rem';
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
}

function renderPgDrivers(drivers) {
    const tbody = document.getElementById('pg-drivers-table-body');
    tbody.replaceChildren();
    if (!drivers.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 8;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No drivers in this directory yet.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    drivers.forEach((driver) => {
        const row = document.createElement('tr');
        const name = document.createElement('td');
        name.textContent = driver.display_name || '';
        const phone = document.createElement('td');
        phone.textContent = driver.phone || '';
        const licence = document.createElement('td');
        licence.textContent = driver.license_number || '';
        const branch = document.createElement('td');
        branch.textContent = pgDriverBranchLabel(driver);
        const verification = document.createElement('td');
        verification.appendChild(pgVerificationBadge(driver.verification_status));
        const warnings = document.createElement('td');
        warnings.textContent = pgDuplicateSummary(driver);
        const active = document.createElement('td');
        active.textContent = driver.active ? 'Active' : 'Inactive';
        const actions = document.createElement('td');
        actions.append(
            pgDriverActionButton('Details', () => showPgDriverDetails(driver.id)),
            pgDriverActionButton('Edit', () => showEditPgDriverModal(driver))
        );
        if (driver.verification_status === 'unverified') {
            actions.append(
                pgDriverActionButton('Approve', () => reviewPgDriver(driver, 'verified')),
                pgDriverActionButton('Reject', () => reviewPgDriver(driver, 'rejected'))
            );
        } else if (driver.verification_status === 'rejected') {
            actions.append(pgDriverActionButton('Resubmit', () => resubmitPgDriver(driver)));
        } else if (driver.verification_status === 'verified') {
            actions.append(pgDriverActionButton(
                driver.active ? 'Suspend' : 'Restore',
                () => changePgDriverActive(driver, !driver.active)
            ));
        }
        row.append(name, phone, licence, branch, verification, warnings, active, actions);
        tbody.appendChild(row);
    });
}

async function fetchPgDrivers(doneMessage) {
    if (!smtToken) return;
    const tbody = document.getElementById('pg-drivers-table-body');
    const addButton = document.getElementById('pg-drivers-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setPgDriverStatus('Loading drivers...');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Loading drivers...</td></tr>';
    const params = new URLSearchParams();
    const name = document.getElementById('pg-driver-search').value.trim();
    const branch = document.getElementById('pg-driver-branch').value;
    const active = document.getElementById('pg-driver-active').value;
    const verificationField = document.getElementById('pg-driver-verification');
    const verification = verificationField ? verificationField.value : '';
    if (name) params.set('name', name);
    if (branch) params.set('branch', branch);
    if (active) params.set('active', active);
    if (verification) params.set('verification_status', verification);
    const query = params.toString();
    try {
        const res = await fetch(`/api/drivers${query ? `?${query}` : ''}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setPgDriverStatus(body.message || 'Only an owner can manage drivers.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Driver management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setPgDriverStatus(body.message || 'Drivers could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Drivers could not be loaded.</td></tr>';
            return;
        }
        setPgDriverStatus(typeof doneMessage === 'string' ? doneMessage : '');
        renderPgDrivers(body.data || []);
    } catch (err) {
        console.error(err);
        setPgDriverStatus('Drivers could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Drivers could not be loaded.</td></tr>';
    }
}

function showAddPgDriverModal() {
    const html = `
        <form id="pg-driver-form" onsubmit="savePgDriver(event)">
            <input type="hidden" id="pg-driver-id" value="">
            <div class="form-group-custom">
                <label>Driver name*</label>
                <input type="text" id="pg-driver-name" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Phone number</label>
                <input type="text" id="pg-driver-phone" class="form-control-custom">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Licence number</label>
                    <input type="text" id="pg-driver-licence" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Licence expiry</label>
                    <input type="date" id="pg-driver-expiry" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom" id="pg-driver-branch-field">
                <label>Primary branch*</label>
                <select id="pg-driver-city" class="form-control-custom" required>
                    <option value="">Choose a city</option>
                    <option value="BLR">Bengaluru</option>
                    <option value="HYD">Hyderabad</option>
                </select>
            </div>
            <p id="pg-driver-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <div id="pg-driver-form-warnings"></div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save driver</button>
        </form>
    `;
    showAdminModal('Add PostgreSQL driver', html);
}

function showEditPgDriverModal(driver) {
    showAddPgDriverModal();
    document.getElementById('admin-modal-title').textContent = 'Edit PostgreSQL driver';
    document.getElementById('pg-driver-id').value = driver.id;
    document.getElementById('pg-driver-name').value = driver.display_name || '';
    document.getElementById('pg-driver-phone').value = driver.phone || '';
    document.getElementById('pg-driver-licence').value = driver.license_number || '';
    document.getElementById('pg-driver-expiry').value = driver.license_expiry || '';
    const branchField = document.getElementById('pg-driver-branch-field');
    branchField.replaceChildren();
    const note = document.createElement('p');
    note.style.color = 'var(--text-secondary)';
    note.textContent = `Primary branch stays ${pgDriverBranchLabel(driver) || 'as assigned'}. Branch changes are not available here.`;
    branchField.appendChild(note);
}

async function savePgDriver(event) {
    event.preventDefault();
    const error = document.getElementById('pg-driver-form-error');
    const driverId = document.getElementById('pg-driver-id').value;
    const payload = {
        display_name: document.getElementById('pg-driver-name').value.trim(),
        phone: document.getElementById('pg-driver-phone').value.trim(),
        license_number: document.getElementById('pg-driver-licence').value.trim(),
        license_expiry: document.getElementById('pg-driver-expiry').value
    };
    if (!driverId) {
        payload.primary_branch_code = document.getElementById('pg-driver-city').value;
    }
    error.style.color = '#ef4444';
    error.textContent = 'Saving driver...';
    try {
        const res = await fetch(driverId ? `/api/drivers/${driverId}` : '/api/drivers', {
            method: driverId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The driver could not be saved.';
            return;
        }
        const warnings = (body.data && body.data.duplicate_warnings) || [];
        fetchPgDrivers(warnings.length ? 'Driver saved. Review the duplicate warning.' : 'Driver saved.');
        if (warnings.length) {
            error.style.color = '#b45309';
            error.textContent = 'Driver saved. Review the duplicate warning below. Nothing was merged or changed.';
            renderPgDuplicateWarnings(warnings, document.getElementById('pg-driver-form-warnings'));
            return;
        }
        closeAdminModal();
    } catch (err) {
        console.error(err);
        error.textContent = 'The driver could not be saved.';
    }
}

function renderPgDriverDetails(driver) {
    const holder = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = driver.display_name || '';
    const lines = document.createElement('p');
    const status = document.createElement('span');
    status.appendChild(pgVerificationBadge(driver.verification_status));
    lines.append(
        document.createTextNode([
            driver.phone,
            driver.license_number,
            driver.license_expiry ? `Licence expires ${driver.license_expiry}` : '',
            driver.active ? 'Active' : 'Inactive'
        ].filter(Boolean).join(' · ') + ' · '),
        status
    );
    const primary = document.createElement('p');
    primary.textContent = `Primary branch: ${pgDriverBranchLabel(driver) || 'Not recorded'}`;
    const extra = document.createElement('p');
    const others = (driver.branches || []).filter((branch) => !branch.primary);
    extra.textContent = others.length
        ? `Additional branches: ${others.map((branch) => branch.city || branch.code).join(', ')}`
        : 'Additional branches: none';

    const warningTitle = document.createElement('h4');
    warningTitle.textContent = 'Duplicate warnings';
    const warningList = document.createElement('div');
    renderPgDuplicateWarnings(driver.duplicate_warnings, warningList);

    const reviews = document.createElement('div');
    const reviewTitle = document.createElement('h4');
    reviewTitle.textContent = 'Verification history';
    reviews.appendChild(reviewTitle);
    const reviewItems = driver.verification_events || [];
    if (!reviewItems.length) {
        const empty = document.createElement('p');
        empty.textContent = 'No verification history yet.';
        reviews.appendChild(empty);
    } else {
        reviewItems.forEach((event) => {
            const item = document.createElement('p');
            item.textContent = [
                event.event_name,
                `${event.from_status} to ${event.to_status}`,
                event.reason,
                pgActorLabel(event),
                pgHistoryWhen(event.created_at)
            ].filter(Boolean).join(' · ');
            reviews.appendChild(item);
        });
    }
    const changes = document.createElement('div');
    const changeTitle = document.createElement('h4');
    changeTitle.textContent = 'Suspension history';
    changes.appendChild(changeTitle);
    const changeItems = driver.active_changes || [];
    if (!changeItems.length) {
        const empty = document.createElement('p');
        empty.textContent = 'No suspension or restoration yet.';
        changes.appendChild(empty);
    } else {
        changeItems.forEach((change) => {
            const item = document.createElement('p');
            const before = change.active_before ? 'active' : 'inactive';
            const after = change.active_after ? 'active' : 'inactive';
            item.textContent = [
                `${before} to ${after}`,
                change.reason,
                pgActorLabel(change),
                pgHistoryWhen(change.created_at)
            ].filter(Boolean).join(' · ');
            changes.appendChild(item);
        });
    }

    const documentTitle = document.createElement('h4');
    documentTitle.textContent = 'Driver documents';
    const documentNote = document.createElement('p');
    documentNote.style.color = 'var(--text-secondary)';
    documentNote.textContent = 'These records store a type, number, and expiry for this PostgreSQL driver. No file is uploaded.';
    const documentList = document.createElement('div');
    (driver.documents || []).forEach((documentRow) => {
        const item = document.createElement('p');
        item.textContent = [
            documentRow.doc_type,
            documentRow.doc_number,
            documentRow.expiry_date ? `expires ${documentRow.expiry_date}` : 'no expiry'
        ].join(' · ');
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.style.marginLeft = '0.5rem';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => {
            document.getElementById('pg-driver-document-id').value = documentRow.id;
            document.getElementById('pg-driver-document-type').value = documentRow.doc_type || '';
            document.getElementById('pg-driver-document-number').value = documentRow.doc_number || '';
            document.getElementById('pg-driver-document-expiry').value = documentRow.expiry_date || '';
            const error = document.getElementById('pg-driver-document-error');
            error.style.color = 'var(--text-secondary)';
            error.textContent = 'Editing this document. Save to keep the change.';
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.25rem';
        remove.textContent = 'Remove';
        remove.addEventListener('click', () => deletePgDriverDocument(driver.id, documentRow.id));
        item.append(edit, remove);
        documentList.appendChild(item);
    });
    if (!(driver.documents || []).length) {
        const empty = document.createElement('p');
        empty.textContent = 'No driver documents recorded.';
        documentList.appendChild(empty);
    }
    const form = document.createElement('form');
    form.addEventListener('submit', (event) => savePgDriverDocument(event, driver.id));
    form.innerHTML = `
        <input type="hidden" id="pg-driver-document-id" value="">
        <div class="form-grid-2">
            <div class="form-group-custom">
                <label>Document type*</label>
                <input type="text" id="pg-driver-document-type" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Document number*</label>
                <input type="text" id="pg-driver-document-number" class="form-control-custom" required>
            </div>
        </div>
        <div class="form-group-custom">
            <label>Expiry</label>
            <input type="date" id="pg-driver-document-expiry" class="form-control-custom">
        </div>
        <p id="pg-driver-document-error" style="color: #ef4444; min-height: 1.2rem;"></p>
        <button type="submit" class="btn btn-primary">Save document</button>
    `;
    const loginActions = document.createElement('div');
    loginActions.style.margin = '0.75rem 0';
    if (staffSession.role === 'od') {
        const provision = document.createElement('button');
        provision.type = 'button';
        provision.className = 'btn btn-secondary';
        provision.textContent = 'Provision driver app login';
        provision.addEventListener('click', () => provisionDriverLogin(driver.id, driver.display_name || driver.phone));
        loginActions.appendChild(provision);
        const note = document.createElement('p');
        note.style.color = 'var(--text-secondary)';
        note.style.marginTop = '0.35rem';
        note.textContent = 'App login is separate from operational active status and verification.';
        loginActions.appendChild(note);
    }

    holder.append(
        title, lines, primary, extra, loginActions,
        warningTitle, warningList,
        reviews, changes,
        documentTitle, documentNote, documentList, form
    );
    document.getElementById('admin-modal-title').textContent = 'PostgreSQL driver';
    document.getElementById('admin-modal-body').replaceChildren(holder);
}

async function provisionDriverLogin(driverId, label) {
    if (staffSession.role !== 'od') {
        setPgDriverStatus('Only an owner can provision driver logins.', true);
        return;
    }
    const password = window.prompt(
        `Set a driver app password for ${label || 'this driver'} (min 8 characters).`
    );
    if (password === null) return;
    if (!password || password.length < 8) {
        setPgDriverStatus('Password must be at least 8 characters.', true);
        return;
    }
    setPgDriverStatus('Provisioning driver login...');
    try {
        const res = await fetch(`/api/drivers/${driverId}/login-account`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgDriverStatus(body.message || 'Driver login could not be provisioned.', true);
            return;
        }
        setPgDriverStatus(body.data && body.data.created === false
            ? 'Driver app password updated.'
            : 'Driver app login provisioned.');
    } catch (err) {
        console.error(err);
        setPgDriverStatus('Driver login could not be provisioned.', true);
    }
}

async function showPgDriverDetails(driverId) {
    showAdminModal('PostgreSQL driver', '<p>Loading driver...</p>');
    try {
        const res = await fetch(`/api/drivers/${driverId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            const holder = document.createElement('p');
            holder.textContent = body.message || 'The driver could not be loaded.';
            document.getElementById('admin-modal-body').replaceChildren(holder);
            return;
        }
        renderPgDriverDetails(body.data);
    } catch (err) {
        console.error(err);
        const holder = document.createElement('p');
        holder.textContent = 'The driver could not be loaded.';
        document.getElementById('admin-modal-body').replaceChildren(holder);
    }
}

async function savePgDriverDocument(event, driverId) {
    event.preventDefault();
    const error = document.getElementById('pg-driver-document-error');
    const documentId = document.getElementById('pg-driver-document-id').value;
    const docType = document.getElementById('pg-driver-document-type').value.trim();
    const docNumber = document.getElementById('pg-driver-document-number').value.trim();
    error.style.color = '#ef4444';
    if (!docType) {
        error.textContent = 'Document type is required.';
        return;
    }
    if (!docNumber) {
        error.textContent = 'Document number is required.';
        return;
    }
    const payload = {
        doc_type: docType,
        doc_number: docNumber,
        expiry_date: document.getElementById('pg-driver-document-expiry').value
    };
    error.style.color = 'var(--text-secondary)';
    error.textContent = 'Saving document...';
    try {
        const res = await fetch(
            documentId
                ? `/api/drivers/${driverId}/documents/${documentId}`
                : `/api/drivers/${driverId}/documents`,
            {
                method: documentId ? 'PATCH' : 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }
        );
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.style.color = '#ef4444';
            error.textContent = body.message || 'The document could not be saved.';
            return;
        }
        setPgDriverStatus(documentId ? 'Driver document updated.' : 'Driver document saved.');
        renderPgDriverDetails(body.data);
    } catch (err) {
        console.error(err);
        error.style.color = '#ef4444';
        error.textContent = 'The document could not be saved.';
    }
}

async function deletePgDriverDocument(driverId, documentId) {
    if (!window.confirm('Remove this driver document record? The driver stays in the directory. No file is stored.')) return;
    const error = document.getElementById('pg-driver-document-error');
    if (error) {
        error.style.color = 'var(--text-secondary)';
        error.textContent = 'Removing document...';
    }
    try {
        const res = await fetch(`/api/drivers/${driverId}/documents/${documentId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            if (error) {
                error.style.color = '#ef4444';
                error.textContent = body.message || 'The document could not be removed.';
            }
            return;
        }
        setPgDriverStatus('Driver document removed.');
        renderPgDriverDetails(body.data);
    } catch (err) {
        console.error(err);
        if (error) {
            error.style.color = '#ef4444';
            error.textContent = 'The document could not be removed.';
        }
    }
}

async function postPgDriverAction(path, payload, pending, successMessage) {
    setPgDriverStatus(pending);
    try {
        const res = await fetch(path, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgDriverStatus(body.message || 'The driver could not be updated.', true);
            return;
        }
        fetchPgDrivers(successMessage);
    } catch (err) {
        console.error(err);
        setPgDriverStatus('The driver could not be updated.', true);
    }
}

async function reviewPgDriver(driver, decision) {
    const verb = decision === 'verified' ? 'Approve' : 'Reject';
    const reason = window.prompt(`${verb} ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A review reason is required.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/reviews`,
        { decision, reason: reason.trim() },
        `${verb} driver...`,
        decision === 'verified' ? 'Driver approved.' : 'Driver rejected.'
    );
}

async function resubmitPgDriver(driver) {
    const reason = window.prompt(`Resubmit ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A resubmission reason is required.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/resubmissions`,
        { reason: reason.trim() },
        'Resubmit driver...',
        'Driver resubmitted. A new approval is still required.'
    );
}

async function changePgDriverActive(driver, next) {
    const verb = next ? 'Restore' : 'Suspend';
    const reason = window.prompt(`${verb} ${driver.display_name || 'this driver'}. Enter the reason.`);
    if (reason === null) return;
    if (!reason.trim()) {
        setPgDriverStatus('A reason is required to suspend or restore a driver.', true);
        return;
    }
    await postPgDriverAction(
        `/api/drivers/${driver.id}/active`,
        { active: next, reason: reason.trim() },
        `${verb} driver...`,
        next ? 'Driver restored.' : 'Driver suspended.'
    );
}

// --- POSTGRESQL VEHICLE DIRECTORY ---
function setPgVehicleStatus(message, isError) {
    const status = document.getElementById('pg-vehicles-status');
    if (!status) return;
    status.textContent = message || '';
    status.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function pgVehicleBranchLabel(vehicle) {
    const branch = vehicle.branch;
    if (!branch) return '';
    return branch.city || branch.name || branch.code || '';
}

function pgVehicleFuelLabel(vehicle) {
    const fuel = vehicle.fuel_type || '';
    if (vehicle.is_ev && fuel.toLowerCase().indexOf('electric') === -1) {
        return fuel ? fuel + ' · Electric' : 'Electric';
    }
    return fuel;
}

function renderPgVehicles(vehicles) {
    const tbody = document.getElementById('pg-vehicles-table-body');
    tbody.replaceChildren();
    if (!vehicles.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 8;
        cell.style.textAlign = 'center';
        cell.style.color = 'var(--text-muted)';
        cell.textContent = 'No vehicles in this directory yet.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }
    vehicles.forEach((vehicle) => {
        const row = document.createElement('tr');
        const registration = document.createElement('td');
        registration.textContent = vehicle.registration_number || '';
        const model = document.createElement('td');
        model.textContent = vehicle.model || '';
        const fuel = document.createElement('td');
        fuel.textContent = pgVehicleFuelLabel(vehicle);
        const branch = document.createElement('td');
        branch.textContent = pgVehicleBranchLabel(vehicle);
        const driver = document.createElement('td');
        driver.textContent = vehicle.usual_driver ? vehicle.usual_driver.display_name : '';
        const status = document.createElement('td');
        status.textContent = vehicle.status === 'active' ? 'Active' : 'Inactive';
        const documents = document.createElement('td');
        documents.textContent = String(vehicle.document_count || 0);
        const actions = document.createElement('td');
        const details = document.createElement('button');
        details.type = 'button';
        details.className = 'status-select';
        details.style.marginRight = '0.25rem';
        details.textContent = 'Details';
        details.addEventListener('click', () => showPgVehicleDetails(vehicle.id));
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.style.marginRight = '0.25rem';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => showEditPgVehicleModal(vehicle));
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'status-select';
        toggle.textContent = vehicle.status === 'active' ? 'Deactivate' : 'Activate';
        toggle.addEventListener('click', () => togglePgVehicle(vehicle));
        actions.append(details, edit, toggle);
        row.append(registration, model, fuel, branch, driver, status, documents, actions);
        tbody.appendChild(row);
    });
}

async function fetchPgVehicles() {
    if (!smtToken) return;
    const tbody = document.getElementById('pg-vehicles-table-body');
    const addButton = document.getElementById('pg-vehicles-add-button');
    const isOwner = staffSession.role === 'od';
    if (addButton) addButton.style.display = isOwner ? '' : 'none';
    setPgVehicleStatus('Loading vehicles...');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Loading vehicles...</td></tr>';
    const params = new URLSearchParams();
    const registration = document.getElementById('pg-vehicle-search').value.trim();
    const branch = document.getElementById('pg-vehicle-branch').value;
    const status = document.getElementById('pg-vehicle-status').value;
    if (registration) params.set('registration', registration);
    if (branch) params.set('branch', branch);
    if (status) params.set('status', status);
    const query = params.toString();
    try {
        const res = await fetch(`/api/vehicles${query ? `?${query}` : ''}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 403) {
            setPgVehicleStatus(body.message || 'Only an owner can manage vehicles.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Vehicle management is limited to owners.</td></tr>';
            return;
        }
        if (!res.ok || !body.success) {
            setPgVehicleStatus(body.message || 'Vehicles could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Vehicles could not be loaded.</td></tr>';
            return;
        }
        setPgVehicleStatus('');
        renderPgVehicles(body.data || []);
    } catch (err) {
        console.error(err);
        setPgVehicleStatus('Vehicles could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #ef4444;">Vehicles could not be loaded.</td></tr>';
    }
}

function pgVehicleFormHtml() {
    return `
        <form id="pg-vehicle-form" onsubmit="savePgVehicle(event)">
            <input type="hidden" id="pg-vehicle-id" value="">
            <div class="form-group-custom">
                <label>Registration number*</label>
                <input type="text" id="pg-vehicle-registration" class="form-control-custom" required>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Make / model</label>
                    <input type="text" id="pg-vehicle-model" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Capacity</label>
                    <input type="number" id="pg-vehicle-capacity" class="form-control-custom" min="1" max="80">
                </div>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Fuel</label>
                    <input type="text" id="pg-vehicle-fuel" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label>Electric</label>
                    <input type="checkbox" id="pg-vehicle-ev">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Branch*</label>
                <select id="pg-vehicle-city" class="form-control-custom" required>
                    <option value="">Choose a city</option>
                    <option value="BLR">Bengaluru</option>
                    <option value="HYD">Hyderabad</option>
                </select>
            </div>
            <div class="form-group-custom">
                <label>Usual driver</label>
                <select id="pg-vehicle-driver" class="form-control-custom">
                    <option value="">No usual driver</option>
                </select>
            </div>
            <p id="pg-vehicle-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Save vehicle</button>
        </form>
    `;
}

async function fillPgVehicleDrivers(selectedId, selectedName) {
    const select = document.getElementById('pg-vehicle-driver');
    if (!select) return;
    try {
        const res = await fetch('/api/drivers', { credentials: 'same-origin' });
        const body = await res.json();
        select.replaceChildren();
        const none = document.createElement('option');
        none.value = '';
        none.textContent = 'No usual driver';
        select.appendChild(none);
        (body.data || []).forEach((driver) => {
            const option = document.createElement('option');
            option.value = driver.id;
            option.textContent = driver.display_name + (driver.active ? '' : ' (inactive)');
            select.appendChild(option);
        });
        if (selectedId && !select.querySelector(`option[value="${selectedId}"]`)) {
            const current = document.createElement('option');
            current.value = selectedId;
            current.textContent = selectedName || 'Current driver';
            select.appendChild(current);
        }
        select.value = selectedId || '';
    } catch (err) {
        console.error(err);
    }
}

function showAddPgVehicleModal() {
    showAdminModal('Add PostgreSQL vehicle', pgVehicleFormHtml());
    fillPgVehicleDrivers('', '');
}

function showEditPgVehicleModal(vehicle) {
    showAdminModal('Edit PostgreSQL vehicle', pgVehicleFormHtml());
    document.getElementById('pg-vehicle-id').value = vehicle.id;
    document.getElementById('pg-vehicle-registration').value = vehicle.registration_number || '';
    document.getElementById('pg-vehicle-model').value = vehicle.model || '';
    document.getElementById('pg-vehicle-capacity').value = vehicle.capacity == null ? '' : vehicle.capacity;
    document.getElementById('pg-vehicle-fuel').value = vehicle.fuel_type || '';
    document.getElementById('pg-vehicle-ev').checked = !!vehicle.is_ev;
    document.getElementById('pg-vehicle-city').value = vehicle.branch ? vehicle.branch.code : '';
    const usual = vehicle.usual_driver;
    fillPgVehicleDrivers(usual ? usual.id : '', usual ? usual.display_name : '');
}

async function savePgVehicle(event) {
    event.preventDefault();
    const error = document.getElementById('pg-vehicle-form-error');
    const vehicleId = document.getElementById('pg-vehicle-id').value;
    const capacityText = document.getElementById('pg-vehicle-capacity').value.trim();
    let capacity = null;
    if (capacityText) {
        capacity = Number(capacityText);
        if (!Number.isInteger(capacity)) {
            error.textContent = 'Capacity must be a whole number from 1 to 80.';
            return;
        }
    }
    const payload = {
        registration_number: document.getElementById('pg-vehicle-registration').value.trim(),
        model: document.getElementById('pg-vehicle-model').value.trim(),
        capacity: capacity,
        fuel_type: document.getElementById('pg-vehicle-fuel').value.trim(),
        is_ev: document.getElementById('pg-vehicle-ev').checked,
        branch_code: document.getElementById('pg-vehicle-city').value,
        usual_driver_id: document.getElementById('pg-vehicle-driver').value || null
    };
    error.textContent = 'Saving vehicle...';
    try {
        const res = await fetch(vehicleId ? `/api/vehicles/${vehicleId}` : '/api/vehicles', {
            method: vehicleId ? 'PATCH' : 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The vehicle could not be saved.';
            return;
        }
        closeAdminModal();
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        error.textContent = 'The vehicle could not be saved.';
    }
}

async function togglePgVehicle(vehicle) {
    const next = vehicle.status === 'active' ? 'inactive' : 'active';
    const question = next === 'inactive'
        ? 'Deactivate this vehicle? The record stays in the PostgreSQL directory and is not deleted.'
        : 'Activate this vehicle? The record stays in the PostgreSQL directory.';
    if (!window.confirm(question)) return;
    setPgVehicleStatus(next === 'inactive' ? 'Deactivating vehicle...' : 'Activating vehicle...');
    try {
        const res = await fetch(`/api/vehicles/${vehicle.id}`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: next })
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgVehicleStatus(body.message || 'The vehicle status could not be changed.', true);
            return;
        }
        setPgVehicleStatus('');
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        setPgVehicleStatus('The vehicle status could not be changed.', true);
    }
}

function renderPgVehicleDetails(vehicle) {
    const holder = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = vehicle.registration_number || '';
    const lines = document.createElement('p');
    lines.textContent = [
        vehicle.model,
        vehicle.capacity ? `${vehicle.capacity} seats` : '',
        pgVehicleFuelLabel(vehicle),
        vehicle.status === 'active' ? 'Active' : 'Inactive'
    ].filter(Boolean).join(' · ');
    const branch = document.createElement('p');
    branch.textContent = `Branch: ${pgVehicleBranchLabel(vehicle) || 'Not recorded'}`;
    const driver = document.createElement('p');
    driver.textContent = `Usual driver: ${vehicle.usual_driver ? vehicle.usual_driver.display_name : 'None'}`;
    const note = document.createElement('p');
    note.style.color = 'var(--text-secondary)';
    note.textContent = 'Document records store a type, number, and expiry. This directory does not upload files.';
    const list = document.createElement('div');
    (vehicle.documents || []).forEach((documentRow) => {
        const item = document.createElement('p');
        item.textContent = [
            documentRow.doc_type,
            documentRow.doc_number,
            documentRow.expiry_date ? `expires ${documentRow.expiry_date}` : 'no expiry'
        ].join(' · ');
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.className = 'status-select';
        edit.style.marginLeft = '0.5rem';
        edit.textContent = 'Edit';
        edit.addEventListener('click', () => {
            document.getElementById('pg-document-id').value = documentRow.id;
            document.getElementById('pg-document-type').value = documentRow.doc_type || '';
            document.getElementById('pg-document-number').value = documentRow.doc_number || '';
            document.getElementById('pg-document-expiry').value = documentRow.expiry_date || '';
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'status-select';
        remove.style.marginLeft = '0.25rem';
        remove.textContent = 'Remove';
        remove.addEventListener('click', () => deletePgVehicleDocument(vehicle.id, documentRow.id));
        item.append(edit, remove);
        list.appendChild(item);
    });
    if (!(vehicle.documents || []).length) {
        const empty = document.createElement('p');
        empty.textContent = 'No documents recorded.';
        list.appendChild(empty);
    }
    const form = document.createElement('form');
    form.id = 'pg-document-form';
    form.addEventListener('submit', (event) => savePgVehicleDocument(event, vehicle.id));
    form.innerHTML = `
        <input type="hidden" id="pg-document-id" value="">
        <div class="form-grid-2">
            <div class="form-group-custom">
                <label>Document type*</label>
                <input type="text" id="pg-document-type" class="form-control-custom" required>
            </div>
            <div class="form-group-custom">
                <label>Document number*</label>
                <input type="text" id="pg-document-number" class="form-control-custom" required>
            </div>
        </div>
        <div class="form-group-custom">
            <label>Expiry</label>
            <input type="date" id="pg-document-expiry" class="form-control-custom">
        </div>
        <p id="pg-document-error" style="color: #ef4444; min-height: 1.2rem;"></p>
        <button type="submit" class="btn btn-primary">Save document</button>
    `;
    holder.append(title, lines, branch, driver, note, list, form);
    document.getElementById('admin-modal-body').replaceChildren(holder);
}

async function showPgVehicleDetails(vehicleId) {
    showAdminModal('PostgreSQL vehicle', '<p>Loading vehicle...</p>');
    try {
        const res = await fetch(`/api/vehicles/${vehicleId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            const holder = document.createElement('p');
            holder.textContent = body.message || 'The vehicle could not be loaded.';
            document.getElementById('admin-modal-body').replaceChildren(holder);
            return;
        }
        renderPgVehicleDetails(body.data);
    } catch (err) {
        console.error(err);
        const holder = document.createElement('p');
        holder.textContent = 'The vehicle could not be loaded.';
        document.getElementById('admin-modal-body').replaceChildren(holder);
    }
}

async function savePgVehicleDocument(event, vehicleId) {
    event.preventDefault();
    const error = document.getElementById('pg-document-error');
    const documentId = document.getElementById('pg-document-id').value;
    const payload = {
        doc_type: document.getElementById('pg-document-type').value.trim(),
        doc_number: document.getElementById('pg-document-number').value.trim(),
        expiry_date: document.getElementById('pg-document-expiry').value
    };
    error.textContent = 'Saving document...';
    try {
        const res = await fetch(
            documentId ? `/api/vehicles/${vehicleId}/documents/${documentId}` : `/api/vehicles/${vehicleId}/documents`,
            {
                method: documentId ? 'PATCH' : 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }
        );
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'The document could not be saved.';
            return;
        }
        renderPgVehicleDetails(body.data);
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
        error.textContent = 'The document could not be saved.';
    }
}

async function deletePgVehicleDocument(vehicleId, documentId) {
    if (!window.confirm('Remove this document record? The vehicle stays in the directory.')) return;
    try {
        const res = await fetch(`/api/vehicles/${vehicleId}/documents/${documentId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            const error = document.getElementById('pg-document-error');
            if (error) error.textContent = body.message || 'The document could not be removed.';
            return;
        }
        renderPgVehicleDetails(body.data);
        fetchPgVehicles();
    } catch (err) {
        console.error(err);
    }
}

// --- TRANSIT ROSTER ASSIGNMENT ---
async function assignCabToCompany(companyId, companyName) {
    if (!smtToken) return;

    try {
        // Fetch all cabs
        const cabsRes = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await cabsRes.json();

        // Fetch all drivers
        const driversRes = await fetch('/api/admin/drivers', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const drivers = await driversRes.json();

        let cabOptions = '';
        cabs.forEach(cab => {
            cabOptions += `<option value="${cab.id}">${cab.reg_number} - ${cab.model} (${cab.fuel_type})</option>`;
        });

        let driverOptions = '';
        drivers.forEach(driver => {
            if (driver.status === 'Active') {
                driverOptions += `<option value="${driver.id}">${driver.name} (License Expires: ${driver.license_expiry})</option>`;
            }
        });

        if (cabs.length === 0 || drivers.length === 0) {
            alert("You need at least one vehicle and one active driver registered to create an assignment.");
            return;
        }

        const html = `
            <form id="assignment-form" onsubmit="saveAssignment(event, ${companyId})">
                <p style="margin-bottom: 1.5rem; font-size: 0.85rem; color: var(--text-secondary);">Select the vehicle and driver to assign to contract for <strong>${companyName}</strong>.</p>
                <div class="form-group-custom">
                    <label>Select Fleet Vehicle*</label>
                    <select id="assign-cab-id" class="form-control-custom" required>
                        ${cabOptions}
                    </select>
                </div>
                <div class="form-group-custom">
                    <label>Select Responsible Driver*</label>
                    <select id="assign-driver-id" class="form-control-custom" required>
                        ${driverOptions}
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Link to Contract</button>
            </form>
        `;
        showAdminModal("Create Fleet Assignment", html);
    } catch (err) {
        console.error("Assign Cab error:", err);
    }
}

async function saveAssignment(event, companyId) {
    event.preventDefault();
    if (!smtToken) return;

    const payload = {
        cab_id: document.getElementById('assign-cab-id').value,
        driver_id: document.getElementById('assign-driver-id').value
    };

    try {
        const res = await fetch(`/api/admin/companies/${companyId}/assignments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeAdminModal();
            fetchCompanies();
        } else {
            const result = await res.json();
            alert(result.error || "Failed to link cab and driver.");
        }
    } catch (err) {
        console.error("Save Assignment Error:", err);
    }
}

async function deleteAssignment(assignmentId, companyId) {
    if (!confirm("Dissolve this vehicle assignment contract?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/assignments/${assignmentId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            loadCompanyAssignments(companyId);
        } else {
            alert("Failed to dissolve assignment.");
        }
    } catch (err) {
        console.error("Delete Assignment Error:", err);
    }
}

// --- EV VEHICLES MANAGEMENT & MONITORING ---
async function fetchEvCabs() {
    if (!smtToken) return;
    const tbody = document.getElementById('ev-table-body');
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Connecting telemetry...</td></tr>`;

    try {
        const res = await fetch('/api/admin/cabs', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const cabs = await res.json();
        
        tbody.innerHTML = '';
        const evs = cabs.filter(c => c.is_ev === 1);

        if (evs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No electric vehicles (EV) currently in the registry.</td></tr>`;
            return;
        }

        evs.forEach(cab => {
            const tr = document.createElement('tr');
            const soc = cab.charge_status !== null ? cab.charge_status : 0;
            const estRange = cab.range_km !== null ? `${cab.range_km} KM` : 'N/A';
            const batCap = cab.battery_capacity ? cab.battery_capacity : 'N/A';
            
            // Bar coloring
            let socClass = 'soc-high';
            if (soc < 20) socClass = 'soc-low';
            else if (soc < 70) socClass = 'soc-mid';

            tr.innerHTML = `
                <td><strong style="color: var(--text-primary); font-size: 0.95rem;">${cab.reg_number}</strong></td>
                <td>${cab.model}</td>
                <td>${batCap}</td>
                <td>
                    <div class="soc-container">
                        <div class="soc-info">
                            <span>🔋 Charge Level</span>
                            <span>${soc}%</span>
                        </div>
                        <div class="soc-bar-bg">
                            <div class="soc-bar-fill ${socClass}" style="width: ${soc}%;"></div>
                        </div>
                    </div>
                </td>
                <td><strong style="font-family: var(--font-heading); color: var(--primary-light);">${estRange}</strong></td>
                <td>
                    <span class="status-badge ${cab.status === 'Active' ? 'completed' : cab.status === 'Maintenance' ? 'pending' : 'expired'}">${cab.status}</span>
                </td>
                <td>
                    <button class="status-select" onclick='showTelemetryUpdateModal(${JSON.stringify(cab).replace(/'/g, "\\'")})'>⚡ Update SOC</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #ef4444;">Error fetching EV telemetry.</td></tr>`;
    }
}

function showTelemetryUpdateModal(cab) {
    const html = `
        <form id="telemetry-form" onsubmit="saveTelemetry(event, ${cab.id})">
            <p style="margin-bottom: 1.5rem; font-size: 0.85rem; color: var(--text-secondary);">Update real-time battery status and est range for <strong>${cab.reg_number} (${cab.model})</strong>.</p>
            <input type="hidden" id="tel-reg" value="${cab.reg_number}">
            <input type="hidden" id="tel-model" value="${cab.model}">
            <input type="hidden" id="tel-capacity" value="${cab.capacity}">
            <input type="hidden" id="tel-fuel" value="${cab.fuel_type}">
            <input type="hidden" id="tel-status" value="${cab.status}">
            <input type="hidden" id="tel-battery" value="${cab.battery_capacity || ''}">
            
            <div class="form-group-custom">
                <label>Current Battery Charge (SOC %)*</label>
                <input type="number" id="tel-charge" class="form-control-custom" min="0" max="100" value="${cab.charge_status !== null ? cab.charge_status : 100}" required>
            </div>
            <div class="form-group-custom">
                <label>Estimated Remaining Range (KM)*</label>
                <input type="number" id="tel-range" class="form-control-custom" min="0" value="${cab.range_km !== null ? cab.range_km : 200}" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 1.5rem;">Update Telemetry</button>
        </form>
    `;
    showAdminModal("Update EV Telemetry", html);
}

async function saveTelemetry(event, cabId) {
    event.preventDefault();
    if (!smtToken) return;

    const payload = {
        reg_number: document.getElementById('tel-reg').value,
        model: document.getElementById('tel-model').value,
        capacity: document.getElementById('tel-capacity').value,
        fuel_type: document.getElementById('tel-fuel').value,
        status: document.getElementById('tel-status').value,
        is_ev: 1,
        battery_capacity: document.getElementById('tel-battery').value,
        charge_status: document.getElementById('tel-charge').value,
        range_km: document.getElementById('tel-range').value
    };

    try {
        const res = await fetch(`/api/admin/cabs/${cabId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${smtToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            closeAdminModal();
            fetchEvCabs();
        } else {
            alert("Failed to update telemetry.");
        }
    } catch (err) {
        console.error("Save Telemetry Error:", err);
    }
}

// --- LIVE OPERATIONS TRACKING & OPTIMIZATION SYSTEM ---

async function fetchLiveTrips() {
    if (!smtToken) return;

    try {
        // Fetch active trips
        const tripsRes = await fetch('/api/admin/trips', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const trips = await tripsRes.json();

        // Fetch active safety alerts
        const alertsRes = await fetch('/api/admin/safety-alerts', {
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const alerts = await alertsRes.json();

        // Update Overview Metrics Counters
        let activeVehicles = 0;
        let onboardEmployees = 0;
        let activeAlerts = 0;
        let evTrips = 0;
        let evTotalActive = 0;

        trips.forEach(t => {
            if (t.status === 'En Route' || t.status === 'SOS Alert') {
                activeVehicles++;
            }
            if (t.cab_is_ev === 1) {
                evTotalActive++;
            }
            t.passengers.forEach(p => {
                if (p.status === 'Onboard') {
                    onboardEmployees++;
                }
            });
        });

        alerts.forEach(a => {
            if (a.status === 'Active') {
                activeAlerts++;
            }
        });

        // Compute EV fleet utilization ratio
        const evUtilization = evTotalActive > 0 ? Math.round((evTotalActive / activeVehicles) * 100) || 0 : 0;

        document.getElementById('track-stat-active').textContent = activeVehicles;
        document.getElementById('track-stat-onboard').textContent = onboardEmployees;
        document.getElementById('track-stat-alerts').textContent = activeAlerts;
        document.getElementById('track-stat-ev').textContent = evUtilization + '%';

        // Render live dispatch cards
        renderLiveTripCards(trips);

        // Render Safety alerts table
        renderSafetyAlertsTable(alerts);

        // Render active vehicle points on the Bangalore map
        drawLiveVehicles(trips);

    } catch (err) {
        console.error("Error fetching live operations data:", err);
    }
}

function renderLiveTripCards(trips) {
    const container = document.getElementById('live-trips-list');
    container.innerHTML = '';

    if (trips.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 3rem 0; color: var(--text-muted);">
                <span style="font-size: 2rem;">📭</span>
                <p style="margin-top: 0.5rem; font-size: 0.85rem;">No active dispatches. Click "Run Route Optimizer" to cluster quote requests and deploy fleet.</p>
            </div>
        `;
        return;
    }

    trips.forEach(trip => {
        const div = document.createElement('div');
        div.className = `live-trip-card ${trip.status === 'SOS Alert' ? 'sos-active' : ''}`;
        
        let statusBadgeClass = 'pending';
        if (trip.status === 'En Route') statusBadgeClass = 'in-progress';
        if (trip.status === 'Completed') statusBadgeClass = 'completed';
        if (trip.status === 'SOS Alert') statusBadgeClass = 'expired';

        let progressFillClass = '';
        if (trip.status === 'Completed') progressFillClass = 'completed-fill';
        if (trip.status === 'SOS Alert') progressFillClass = 'sos-fill';

        // Construct passenger status pills
        let passengerPills = '';
        trip.passengers.forEach(p => {
            let pillClass = '';
            if (p.status === 'Onboard') pillClass = 'onboard';
            if (p.status === 'Dropped') pillClass = 'dropped';
            passengerPills += `<span class="passenger-pill ${pillClass}">👤 ${p.name} (${p.status})</span>`;
        });

        // SOS or Resolve button
        let actionBtn = '';
        if (trip.status === 'SOS Alert') {
            actionBtn = `<button class="status-select" style="background:#10b981; color:white; border-color:#10b981; padding:0.25rem 0.6rem;" onclick="resolveTripSOS(${trip.id})">Resolve SOS</button>`;
        } else if (trip.status !== 'Completed') {
            actionBtn = `<button class="status-select" style="background:#ef4444; color:white; border-color:#ef4444; padding:0.25rem 0.6rem;" onclick="triggerTripSOS(${trip.id})">Trigger SOS 🚨</button>`;
        }

        div.innerHTML = `
            <div class="live-trip-header">
                <div>
                    <span style="font-size:0.75rem; text-transform:uppercase; font-weight:600; color:var(--text-muted);">Trip ID: #${trip.id}</span>
                    <h4 style="font-size:1.05rem; margin-top:0.15rem; color:var(--primary);">${trip.route_name}</h4>
                </div>
                <span class="status-badge ${statusBadgeClass}">${trip.status}</span>
            </div>
            
            <div class="live-trip-body">
                <div>
                    <strong>🚖 ${trip.cab_reg}</strong> (${trip.cab_model})<br>
                    <span style="font-size:0.75rem;">Driver: ${trip.driver_name}</span>
                </div>
                <div style="text-align:right;">
                    <strong>Speed: ${trip.speed} km/h</strong><br>
                    <span style="font-size:0.75rem;">ETA: ${trip.eta}</span>
                </div>
            </div>

            <div class="live-trip-progress-container">
                <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-secondary); margin-bottom:0.2rem;">
                    <span>Commute progress</span>
                    <span>${Math.round(trip.progress)}%</span>
                </div>
                <div class="live-trip-progress-bar">
                    <div class="live-trip-progress-fill ${progressFillClass}" style="width: ${trip.progress}%;"></div>
                </div>
            </div>

            <div style="border-top:1px solid var(--border-color); padding-top:0.75rem;">
                <div style="font-size:0.75rem; font-weight:600; margin-bottom:0.3rem;">Passengers Roster:</div>
                <div class="passenger-pills-container">
                    ${passengerPills}
                </div>
            </div>

            <div style="display:flex; justify-content:flex-end; margin-top:0.25rem;">
                ${actionBtn}
            </div>
        `;
        container.appendChild(div);
    });
}

function renderSafetyAlertsTable(alerts) {
    const tbody = document.getElementById('safety-alerts-table-body');
    tbody.innerHTML = '';

    const activeAlerts = alerts.filter(a => a.status === 'Active');

    if (activeAlerts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No active safety logs. Fleet operating within parameters.</td>
            </tr>
        `;
        return;
    }

    activeAlerts.forEach(a => {
        const tr = document.createElement('tr');
        tr.className = 'alert-row-active';
        tr.innerHTML = `
            <td style="padding:0.75rem 1rem; font-size:0.8rem; font-weight:600; color:var(--text-primary);">${a.created_at}</td>
            <td style="padding:0.75rem 1rem; font-size:0.8rem;">
                <strong>Trip #${a.trip_id}</strong><br>
                <span style="font-size:0.72rem; color:var(--text-secondary);">${a.route_name}</span>
            </td>
            <td style="padding:0.75rem 1rem;">
                <span class="doc-badge expired">${a.alert_type}</span>
            </td>
            <td style="padding:0.75rem 1rem; font-size:0.8rem; color:#ef4444; font-weight:500;">${a.details}</td>
            <td style="padding:0.75rem 1rem;">
                <button class="btn btn-secondary" style="padding:0.3rem 0.75rem; font-size:0.75rem;" onclick="resolveTripSOS(${a.trip_id})">Resolve & Clear</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function drawLiveVehicles(trips) {
    const group = document.getElementById('map-active-vehicles-group');
    if (!group) return;
    group.innerHTML = '';

    trips.forEach(trip => {
        if (trip.status === 'Completed' || trip.progress >= 100) return;

        // Find path element
        let pathId = '';
        if (trip.route_name.includes('Amazon')) pathId = 'path-route-amazon';
        else if (trip.route_name.includes('TCS')) pathId = 'path-route-tcs';
        else if (trip.route_name.includes('Optum')) pathId = 'path-route-optum';
        else if (trip.route_name.includes('Electronic City') || trip.route_name.includes('Rental') || trip.route_name.includes('Airport')) pathId = 'path-route-ecity';
        else pathId = 'path-route-optum'; // fallback

        const pathEl = document.getElementById(pathId);
        if (!pathEl) return;

        try {
            const pathLength = pathEl.getTotalLength();
            const percent = trip.progress / 100;
            const point = pathEl.getPointAtLength(percent * pathLength);

            // Determine classes
            let dotClass = 'map-vehicle-dot';
            let dotColor = '#f59e0b'; // default ICE amber
            if (trip.cab_is_ev === 1) {
                dotClass += ' ev-vehicle';
                dotColor = '#10b981'; // Green
            }
            if (trip.status === 'SOS Alert') {
                dotClass += ' sos-vehicle';
                dotColor = '#ef4444'; // Red
            }

            const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            g.setAttribute('class', dotClass);
            g.setAttribute('transform', `translate(${point.x}, ${point.y})`);
            g.setAttribute('onclick', `switchTab('tracking');`);

            // Inner circle
            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('cx', '0');
            circle.setAttribute('cy', '0');
            circle.setAttribute('r', '8');
            circle.setAttribute('fill', dotColor);
            g.appendChild(circle);

            // Glowing pulse ring
            const pulse = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            pulse.setAttribute('cx', '0');
            pulse.setAttribute('cy', '0');
            pulse.setAttribute('r', '14');
            pulse.setAttribute('fill', 'none');
            pulse.setAttribute('stroke', dotColor);
            pulse.setAttribute('stroke-width', '1.5');
            pulse.setAttribute('opacity', '0.6');
            g.appendChild(pulse);

            // Text Label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', '10');
            text.setAttribute('y', '4');
            text.setAttribute('fill', '#ffffff');
            text.setAttribute('font-size', '8');
            text.setAttribute('font-weight', '700');
            text.setAttribute('font-family', 'sans-serif');
            text.textContent = `${trip.cab_reg} (${trip.speed} km/h)`;
            g.appendChild(text);

            group.appendChild(g);

        } catch (e) {
            console.error("Error drawing vehicle path position:", e);
        }
    });
}

async function optimizeAndDispatch() {
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/optimize', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const result = await res.json();
        
        if (res.ok) {
            alert(result.message);
            fetchLiveTrips();
        } else {
            alert(result.error || "Route optimization failed.");
        }
    } catch (err) {
        console.error("Route Optimization Dispatch error:", err);
    }
}

async function simulateTripTick() {
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/simulate-tick', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        const result = await res.json();
        
        if (res.ok) {
            fetchLiveTrips();
            if (result.alerts_generated > 0) {
                console.log(`[ALERT WARNING] Simulation generated ${result.alerts_generated} new alerts!`);
            }
        }
    } catch (err) {
        console.error("Simulate Progress Tick error:", err);
    }
}

async function triggerTripSOS(tripId) {
    if (!confirm("Are you sure you want to broadcast a simulated passenger SOS emergency alert for this vehicle?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/trips/${tripId}/sos`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Trigger SOS Error:", err);
    }
}

async function resolveTripSOS(tripId) {
    if (!smtToken) return;

    try {
        const res = await fetch(`/api/admin/trips/${tripId}/resolve-sos`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Resolve SOS Error:", err);
    }
}

async function clearSimulationTrips() {
    if (!confirm("This will dissolve all active tracking paths and release associated vehicles. Continue?")) return;
    if (!smtToken) return;

    try {
        const res = await fetch('/api/admin/trips/clear', {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${smtToken}` }
        });
        if (res.ok) {
            fetchLiveTrips();
        }
    } catch (err) {
        console.error("Reset simulation error:", err);
    }
}

// --- Supervisor home operations board ---
function opsHomeMoney(value) {
    const n = Number(value || 0);
    return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function opsHomeTile(label, value, tabId, filters) {
    const safeLabel = escapeHtmlDuty(label);
    const safeValue = escapeHtmlDuty(String(value == null ? '—' : value));
    const attrs = tabId
        ? ` type="button" class="ops-kpi" onclick="openOpsHomeLink('${tabId}', ${JSON.stringify(filters || {})})"`
        : ' class="ops-kpi is-static"';
    const tag = tabId ? 'button' : 'div';
    return `<${tag}${attrs}><span class="ops-kpi-label">${safeLabel}</span><strong class="ops-kpi-value">${safeValue}</strong></${tag}>`;
}

function openOpsHomeLink(tabId, filters) {
    if (tabId === 'pg-duties') {
        const origin = document.getElementById('pg-duty-origin');
        const status = document.getElementById('pg-duty-status');
        const dateEl = document.getElementById('pg-duty-date');
        if (origin) origin.value = (filters && filters.origin) || '';
        if (status) status.value = (filters && filters.status) || '';
        if (dateEl) {
            dateEl.value = (filters && filters.trip_date === 'today')
                ? new Date().toISOString().slice(0, 10)
                : ((filters && filters.trip_date) || '');
        }
    } else if (tabId === 'pg-drivers') {
        const verification = document.getElementById('pg-driver-verification');
        const active = document.getElementById('pg-driver-active');
        if (verification && filters && filters.verification_status) {
            verification.value = filters.verification_status;
        }
        if (active && filters && filters.active != null) {
            active.value = String(filters.active);
        }
    } else if (tabId === 'pg-finance') {
        // Finance tab loads its own dashboard.
    }
    switchTab(tabId);
}

async function fetchOpsHomeBoard() {
    const status = document.getElementById('ops-home-status');
    const grid = document.getElementById('ops-home-kpis');
    if (!grid) return;
    if (status) status.textContent = 'Loading operational counts…';
    grid.innerHTML = '<div class="ops-kpi is-static"><span class="ops-kpi-label">Status</span><strong class="ops-kpi-value">Loading…</strong></div>';
    const branch = (document.getElementById('ops-home-branch') || {}).value || '';
    const opsQuery = branch ? `?branch=${encodeURIComponent(branch)}` : '';
    const financeQuery = branch ? `?branch=${encodeURIComponent(branch)}` : '';
    try {
        const [opsRes, financeRes] = await Promise.all([
            fetch(`/api/operations/dashboard${opsQuery}`, { credentials: 'same-origin' }),
            fetch(`/api/finance/dashboard${financeQuery}`, { credentials: 'same-origin' }),
        ]);
        const opsBody = await opsRes.json();
        const financeBody = await financeRes.json();
        if (!opsRes.ok || !opsBody.success) {
            if (status) status.textContent = opsBody.message || 'Operations board is not available.';
            grid.innerHTML = `<div class="ops-kpi is-static"><span class="ops-kpi-label">Error</span><strong class="ops-kpi-value">${escapeHtmlDuty(opsBody.message || 'Unavailable')}</strong></div>`;
            return;
        }
        const ops = opsBody.data || {};
        const finance = (financeRes.ok && financeBody.success && financeBody.data) || {};
        const today = new Date().toISOString().slice(0, 10);
        grid.innerHTML = [
            opsHomeTile("Today's bookings", ops.bookings_today, 'pg-duties', { trip_date: 'today' }),
            opsHomeTile('Upcoming', ops.upcoming_bookings, 'pg-duties', {}),
            opsHomeTile('Unassigned', ops.unassigned_bookings, 'pg-duties', { status: 'unassigned' }),
            opsHomeTile('Assigned', ops.assigned_duties, 'pg-duties', { status: 'assigned' }),
            opsHomeTile('Accepted', ops.accepted_duties, 'pg-duties', { status: 'accepted' }),
            opsHomeTile('In progress', ops.trips_in_progress, 'pg-duties', { status: 'started' }),
            opsHomeTile('Completed today', ops.completed_today, 'pg-duties', { status: 'completed', trip_date: today }),
            opsHomeTile('Cancelled today', ops.cancelled_today, 'pg-duties', { status: 'cancelled', trip_date: today }),
            opsHomeTile('Client requests', ops.client_requests_open, 'pg-duties', { origin: 'client_request', status: 'unassigned' }),
            opsHomeTile('Active drivers', ops.active_drivers, 'pg-drivers', { active: true }),
            opsHomeTile('Pending verification', ops.pending_driver_verification, 'pg-drivers', { verification_status: 'unverified' }),
            opsHomeTile('Active vehicles', ops.active_vehicles, 'pg-vehicles', {}),
            opsHomeTile('Outstanding invoices', `₹ ${opsHomeMoney(finance.outstanding_receivables)}`, 'pg-finance', {}),
            opsHomeTile('Overdue invoices', finance.overdue_invoice_count || 0, 'pg-finance', {}),
            opsHomeTile('Pending payouts', `₹ ${opsHomeMoney(finance.pending_driver_payouts)}`, 'pg-finance', {}),
            opsHomeTile('Expenses', `₹ ${opsHomeMoney(finance.expenses)}`, 'pg-finance', {}),
        ].join('');
        if (status) {
            status.textContent = financeRes.ok && financeBody.success
                ? 'Counts respect your branch access. Click a tile to open the matching register.'
                : 'Duty counts loaded. Finance summary is not available for this session.';
        }
    } catch (err) {
        console.error(err);
        if (status) status.textContent = 'Operations board could not be loaded.';
        grid.innerHTML = '<div class="ops-kpi is-static"><span class="ops-kpi-label">Error</span><strong class="ops-kpi-value">Unavailable</strong></div>';
    }
}

// --- PostgreSQL Duties ---
let pgDutyBranchMap = null;
let pgDutySelectedId = null;
let pgDutyAssignBusy = false;

function setPgDutyStatus(message, isError) {
    const el = document.getElementById('pg-duties-status');
    if (!el) return;
    el.textContent = message || '';
    el.style.color = isError ? '#ef4444' : 'var(--text-secondary)';
}

function filterPgDutiesClientRequests() {
    const origin = document.getElementById('pg-duty-origin');
    const status = document.getElementById('pg-duty-status');
    if (origin) origin.value = 'client_request';
    if (status && !status.value) status.value = 'unassigned';
    fetchPgDuties('Showing client booking requests.');
}

function originBadge(origin) {
    const value = String(origin || '').toLowerCase();
    if (value === 'client_request') return '<span class="origin-badge origin-client">Client request</span>';
    if (value === 'rac') return '<span class="origin-badge origin-rac">RAC</span>';
    if (value === 'retail') return '<span class="origin-badge origin-retail">Retail</span>';
    return escapeHtmlDuty(origin || '—');
}

async function loadPgDutyBranches() {
    if (pgDutyBranchMap) return pgDutyBranchMap;
    const res = await fetch('/api/branches', { credentials: 'same-origin' });
    const body = await res.json();
    pgDutyBranchMap = {};
    (body.data || []).forEach((row) => {
        pgDutyBranchMap[row.id] = row.code || row.city || row.id;
    });
    return pgDutyBranchMap;
}

function escapeHtmlDuty(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function fetchPgDuties(doneMessage) {
    if (!smtToken) return;
    const tbody = document.getElementById('pg-duties-table-body');
    if (!tbody) return;
    setPgDutyStatus('Loading duties...');
    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">Loading duties...</td></tr>';
    try {
        await loadPgDutyBranches();
        const params = new URLSearchParams();
        const search = document.getElementById('pg-duty-search').value.trim();
        const branch = document.getElementById('pg-duty-branch').value;
        const status = document.getElementById('pg-duty-status').value;
        const origin = (document.getElementById('pg-duty-origin') || {}).value || '';
        const tripDate = document.getElementById('pg-duty-date').value;
        if (search) params.set('search', search);
        if (branch) params.set('branch', branch);
        if (status) params.set('status', status);
        if (origin) params.set('origin', origin);
        if (tripDate) params.set('trip_date', tripDate);
        const query = params.toString();
        const res = await fetch(`/api/operations/bookings${query ? `?${query}` : ''}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (res.status === 401) {
            setPgDutyStatus('Sign in required.', true);
            return;
        }
        if (!res.ok || !body.success) {
            setPgDutyStatus(body.message || 'Duties could not be loaded.', true);
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ef4444;">Duties could not be loaded.</td></tr>';
            return;
        }
        const rows = body.data || [];
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">No bookings match these filters.</td></tr>';
            setPgDutyStatus(typeof doneMessage === 'string' ? doneMessage : 'No bookings found.');
            return;
        }
        tbody.innerHTML = '';
        rows.forEach((row) => {
            const tr = document.createElement('tr');
            const branchLabel = pgDutyBranchMap[row.branch_id] || row.branch_id || '';
            tr.innerHTML = `
                <td>${escapeHtmlDuty(row.trip_date || '')}</td>
                <td>${escapeHtmlDuty(row.source_booking_id || '—')}</td>
                <td>${escapeHtmlDuty(row.employee_name || '')}</td>
                <td>${escapeHtmlDuty(branchLabel)}</td>
                <td>${originBadge(row.origin)}</td>
                <td>${escapeHtmlDuty(row.status || '')}</td>
                <td>${escapeHtmlDuty(row.duty_type || '')}</td>
                <td>${escapeHtmlDuty(row.pickup_time || row.planned_start || '')}</td>
                <td><button type="button" class="btn btn-secondary" onclick="openPgDutyDetail('${row.id}')">Open</button></td>
            `;
            tbody.appendChild(tr);
        });
        setPgDutyStatus(typeof doneMessage === 'string' ? doneMessage : `${rows.length} booking${rows.length === 1 ? '' : 's'}.`);
    } catch (err) {
        console.error(err);
        setPgDutyStatus('Duties could not be loaded.', true);
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ef4444;">Duties could not be loaded.</td></tr>';
    }
}

async function showCreatePgDutyModal() {
    let companyOptions = '<option value="">No company (retail / internal)</option>';
    try {
        const companiesRes = await fetch('/api/companies', { credentials: 'same-origin' });
        const companiesBody = await companiesRes.json();
        if (companiesRes.ok && companiesBody.success) {
            companyOptions += (companiesBody.data || []).map((c) =>
                `<option value="${escapeHtmlDuty(c.id)}">${escapeHtmlDuty(c.name)}</option>`
            ).join('');
        }
    } catch (err) {
        console.error(err);
    }
    const html = `
        <form id="pg-duty-form" onsubmit="savePgDuty(event)">
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label for="pg-duty-form-branch">Branch*</label>
                    <select id="pg-duty-form-branch" class="form-control-custom" required>
                        <option value="">Choose a city</option>
                        <option value="BLR">Bengaluru</option>
                        <option value="HYD">Hyderabad</option>
                    </select>
                </div>
                <div class="form-group-custom">
                    <label for="pg-duty-form-date">Trip date*</label>
                    <input type="date" id="pg-duty-form-date" class="form-control-custom" required>
                </div>
            </div>
            <div class="form-group-custom">
                <label for="pg-duty-form-company">Company</label>
                <select id="pg-duty-form-company" class="form-control-custom">${companyOptions}</select>
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label for="pg-duty-form-source">Source booking ID</label>
                    <input type="text" id="pg-duty-form-source" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label for="pg-duty-form-pickup">Pickup time</label>
                    <input type="time" id="pg-duty-form-pickup" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom">
                <label for="pg-duty-form-employee">Passenger / employee</label>
                <input type="text" id="pg-duty-form-employee" class="form-control-custom">
            </div>
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label for="pg-duty-form-duty">Duty type</label>
                    <input type="text" id="pg-duty-form-duty" class="form-control-custom">
                </div>
                <div class="form-group-custom">
                    <label for="pg-duty-form-cab">Cab type</label>
                    <input type="text" id="pg-duty-form-cab" class="form-control-custom">
                </div>
            </div>
            <div class="form-group-custom">
                <label for="pg-duty-form-route">Pickup / route</label>
                <input type="text" id="pg-duty-form-route" class="form-control-custom">
            </div>
            <div class="form-group-custom">
                <label for="pg-duty-form-remarks">Remarks</label>
                <textarea id="pg-duty-form-remarks" class="form-control-custom" rows="2"></textarea>
            </div>
            <p id="pg-duty-form-error" style="color: #ef4444; min-height: 1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width: 100%; justify-content: center;">Create booking</button>
        </form>
    `;
    openModal('Create PostgreSQL booking', html);
}

async function resolvePgDutyBranchId(code) {
    const res = await fetch('/api/branches', { credentials: 'same-origin' });
    const body = await res.json();
    const found = (body.data || []).find((row) => row.code === code);
    return found ? found.id : null;
}

async function savePgDuty(event) {
    event.preventDefault();
    const error = document.getElementById('pg-duty-form-error');
    error.textContent = '';
    const code = document.getElementById('pg-duty-form-branch').value;
    const branchId = await resolvePgDutyBranchId(code);
    if (!branchId) {
        error.textContent = 'Branch is not valid.';
        return;
    }
    const companyId = (document.getElementById('pg-duty-form-company') || {}).value || '';
    const payload = {
        branch_id: branchId,
        trip_date: document.getElementById('pg-duty-form-date').value,
        company_id: companyId || null,
        source_booking_id: document.getElementById('pg-duty-form-source').value.trim() || null,
        pickup_time: document.getElementById('pg-duty-form-pickup').value || null,
        employee_name: document.getElementById('pg-duty-form-employee').value.trim() || null,
        duty_type: document.getElementById('pg-duty-form-duty').value.trim() || null,
        cab_type: document.getElementById('pg-duty-form-cab').value.trim() || null,
        planned_start: document.getElementById('pg-duty-form-route').value.trim() || null,
        remarks: document.getElementById('pg-duty-form-remarks').value.trim() || null,
    };
    Object.keys(payload).forEach((key) => {
        if (payload[key] === null || payload[key] === '') delete payload[key];
    });
    try {
        const res = await fetch('/api/operations/bookings', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'Booking could not be created.';
            return;
        }
        closeModal();
        fetchPgDuties('Booking created.');
        if (body.data && body.data.id) openPgDutyDetail(body.data.id);
    } catch (err) {
        console.error(err);
        error.textContent = 'Booking could not be created.';
    }
}

async function openPgDutyDetail(bookingId) {
    pgDutySelectedId = bookingId;
    const panel = document.getElementById('pg-duty-detail');
    panel.style.display = 'block';
    panel.innerHTML = '<p style="color: var(--text-secondary);">Loading booking...</p>';
    try {
        const tripRes = await fetch(`/api/operations/bookings/${bookingId}/trip`, { credentials: 'same-origin' });
        const tripBody = await tripRes.json();
        if (!tripRes.ok || !tripBody.success) {
            panel.innerHTML = `<p style="color:#ef4444;">${escapeHtmlDuty(tripBody.message || 'Booking could not be loaded.')}</p>`;
            return;
        }
        const data = tripBody.data || {};
        const booking = data.booking || data;
        const assignment = data.assignment;
        const session = data.session;
        const events = data.events || [];
        await loadPgDutyBranches();
        const branchLabel = pgDutyBranchMap[booking.branch_id] || booking.branch_id || '';
        let actions = '';
        if (booking.status === 'unassigned') {
            actions += `<button class="btn btn-primary" type="button" onclick="promptAssignPgDuty('${booking.id}')">Assign driver</button>`;
            actions += `<button class="btn btn-secondary" type="button" onclick="promptEditPgDuty('${booking.id}')">Edit / reschedule</button>`;
            actions += `<button class="btn btn-secondary" type="button" onclick="confirmPgDutyCancel('${booking.id}')">Cancel</button>`;
        }
        if (booking.status === 'assigned' || booking.status === 'accepted') {
            actions += `<button class="btn btn-primary" type="button" onclick="promptAssignPgDuty('${booking.id}', true)">Reassign</button>`;
            actions += `<button class="btn btn-secondary" type="button" onclick="runPgDutyAction('/api/operations/bookings/${booking.id}/unassign', {})">Unassign</button>`;
            if (assignment) {
                actions += `<button class="btn btn-secondary" type="button" onclick="promptChangePgDutyVehicle('${assignment.id}', '${booking.id}')">Change vehicle</button>`;
            }
            if (assignment && booking.status === 'assigned') {
                actions += `<button class="btn btn-secondary" type="button" onclick="runPgDutyAction('/api/operations/assignments/${assignment.id}/accept', {})">Mark accepted</button>`;
                actions += `<button class="btn btn-secondary" type="button" onclick="promptRejectPgDuty('${assignment.id}')">Reject</button>`;
                actions += `<button class="btn btn-secondary" type="button" onclick="runPgDutyAction('/api/operations/assignments/${assignment.id}/resend-message', {})">Resend WhatsApp</button>`;
            }
            if (booking.status === 'accepted') {
                actions += `<button class="btn btn-primary" type="button" onclick="runPgDutyAction('/api/operations/bookings/${booking.id}/start', {})">Start trip</button>`;
            }
            actions += `<button class="btn btn-secondary" type="button" onclick="confirmPgDutyCancel('${booking.id}')">Cancel</button>`;
        }
        if (booking.status === 'started') {
            actions += `<button class="btn btn-primary" type="button" onclick="runPgDutyAction('/api/operations/bookings/${booking.id}/complete', {})">Complete trip</button>`;
            actions += `<button class="btn btn-secondary" type="button" onclick="confirmPgDutyCancel('${booking.id}')">Cancel</button>`;
        }
        let assignmentHistory = '';
        try {
            const histRes = await fetch(`/api/operations/bookings/${bookingId}/assignments`, { credentials: 'same-origin' });
            const histBody = await histRes.json();
            if (histRes.ok && histBody.success) {
                const payload = histBody.data || {};
                const rows = payload.assignments || (Array.isArray(payload) ? payload : []);
                assignmentHistory = rows.length
                    ? rows.map((row) => escapeHtmlDuty(
                        `${row.status || ''} · ${row.driver_name || row.driver_id || ''} · ${row.vehicle_registration || row.vehicle_id || 'no vehicle'}`
                    )).join('<br>')
                    : '—';
            }
        } catch (err) {
            assignmentHistory = '—';
        }
        panel.innerHTML = `
            <div class="dashboard-table-container">
                <div class="dashboard-table-header" style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap;">
                    <h3 style="font-size: 1.25rem;">Booking detail</h3>
                    <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">${actions}</div>
                </div>
                <div style="padding: 1rem; display:grid; gap:0.5rem;">
                    <div><strong>Status:</strong> ${escapeHtmlDuty(booking.status)}</div>
                    <div><strong>Origin:</strong> ${originBadge(booking.origin)}</div>
                    <div><strong>Source ID:</strong> ${escapeHtmlDuty(booking.source_booking_id || '—')}</div>
                    <div><strong>Date / time:</strong> ${escapeHtmlDuty(booking.trip_date || '')} ${escapeHtmlDuty(booking.pickup_time || '')}</div>
                    <div><strong>Branch:</strong> ${escapeHtmlDuty(branchLabel)}</div>
                    <div><strong>Passenger:</strong> ${escapeHtmlDuty(booking.employee_name || '')}</div>
                    <div><strong>Duty / cab:</strong> ${escapeHtmlDuty(booking.duty_type || '')} / ${escapeHtmlDuty(booking.cab_type || '')}</div>
                    <div><strong>Pickup:</strong> ${escapeHtmlDuty(booking.planned_start || booking.route_text || '')}</div>
                    <div><strong>Remarks:</strong> ${escapeHtmlDuty(booking.remarks || '')}</div>
                    <div><strong>Driver:</strong> ${escapeHtmlDuty(assignment ? (assignment.driver_name || assignment.driver_id) : '—')}</div>
                    <div><strong>Assignment status:</strong> ${escapeHtmlDuty(assignment ? assignment.status : '—')}</div>
                    <div><strong>Vehicle:</strong> ${escapeHtmlDuty(assignment && assignment.vehicle_registration ? assignment.vehicle_registration : '—')}</div>
                    <div><strong>WhatsApp:</strong> ${escapeHtmlDuty(assignment && assignment.whatsapp_status ? assignment.whatsapp_status : '—')}</div>
                    <div><strong>Session:</strong> ${escapeHtmlDuty(session ? session.status : '—')}</div>
                    <div><strong>Session times:</strong> ${escapeHtmlDuty(session ? `${session.started_at || '—'} → ${session.ended_at || '—'}` : '—')}</div>
                    <div><strong>Booking events:</strong> ${(events || []).map((ev) => escapeHtmlDuty(`${ev.old_status || '∅'} → ${ev.new_status}`)).join(' · ') || '—'}</div>
                    <div><strong>Assignment history:</strong><div>${assignmentHistory || '—'}</div></div>
                </div>
            </div>
        `;
    } catch (err) {
        console.error(err);
        panel.innerHTML = '<p style="color:#ef4444;">Booking could not be loaded.</p>';
    }
}

function confirmPgDutyCancel(bookingId) {
    if (!window.confirm('Cancel this booking? Open assignments will be closed by the backend rules.')) return;
    runPgDutyAction(`/api/operations/bookings/${bookingId}/cancel`, {});
}

async function runPgDutyAction(url, payload) {
    try {
        const res = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {}),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            setPgDutyStatus(body.message || 'Action failed.', true);
            return;
        }
        let message = 'Duty updated.';
        if (body.whatsapp) {
            const wa = Array.isArray(body.whatsapp) ? body.whatsapp[0] : body.whatsapp;
            if (wa && wa.send_status) message += ` WhatsApp: ${wa.send_status}.`;
        }
        fetchPgDuties(message);
        if (pgDutySelectedId) openPgDutyDetail(pgDutySelectedId);
    } catch (err) {
        console.error(err);
        setPgDutyStatus('Action failed.', true);
    }
}

async function promptAssignPgDuty(bookingId, reassign) {
    const [driversRes, vehiclesRes] = await Promise.all([
        fetch('/api/drivers?active=true&verification_status=verified', { credentials: 'same-origin' }),
        fetch('/api/vehicles?status=active', { credentials: 'same-origin' }),
    ]);
    const driversBody = await driversRes.json();
    const vehiclesBody = await vehiclesRes.json();
    const drivers = driversBody.data || [];
    const vehicles = vehiclesBody.data || [];
    if (!drivers.length) {
        setPgDutyStatus('No verified active drivers are available.', true);
        return;
    }
    const options = drivers.map((d) => `<option value="${d.id}">${escapeHtmlDuty(d.display_name)} (${escapeHtmlDuty(d.phone || 'no phone')})</option>`).join('');
    const vehicleOptions = ['<option value="">No vehicle</option>'].concat(
        vehicles.map((v) => `<option value="${v.id}">${escapeHtmlDuty(v.registration_number || v.id)} · ${escapeHtmlDuty(v.model || '')}</option>`)
    ).join('');
    const html = `
        <form onsubmit="submitAssignPgDuty(event, '${bookingId}', ${reassign ? 'true' : 'false'})">
            <div class="form-group-custom">
                <label for="pg-duty-assign-driver">Driver*</label>
                <select id="pg-duty-assign-driver" class="form-control-custom" required>${options}</select>
            </div>
            <div class="form-group-custom">
                <label for="pg-duty-assign-vehicle">Vehicle (optional)</label>
                <select id="pg-duty-assign-vehicle" class="form-control-custom">${vehicleOptions}</select>
            </div>
            <label style="display:flex; gap:0.5rem; align-items:center; margin-bottom:1rem;">
                <input type="checkbox" id="pg-duty-assign-wa" checked>
                Send WhatsApp after save
            </label>
            <p id="pg-duty-assign-error" style="color:#ef4444; min-height:1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width:100%; justify-content:center;">${reassign ? 'Reassign' : 'Assign'}</button>
        </form>
    `;
    openModal(reassign ? 'Reassign driver' : 'Assign driver', html);
}

async function submitAssignPgDuty(event, bookingId, reassign) {
    event.preventDefault();
    if (pgDutyAssignBusy) return;
    const error = document.getElementById('pg-duty-assign-error');
    error.textContent = '';
    const payload = {
        driver_id: document.getElementById('pg-duty-assign-driver').value,
        send_message: document.getElementById('pg-duty-assign-wa').checked,
    };
    const vehicle = document.getElementById('pg-duty-assign-vehicle').value.trim();
    if (vehicle) payload.vehicle_id = vehicle;
    const url = reassign
        ? `/api/operations/bookings/${bookingId}/reassign`
        : `/api/operations/bookings/${bookingId}/assign`;
    pgDutyAssignBusy = true;
    try {
        const res = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'Assignment failed.';
            return;
        }
        closeModal();
        let message = reassign ? 'Driver reassigned.' : 'Driver assigned.';
        if (body.whatsapp) {
            const wa = Array.isArray(body.whatsapp) ? body.whatsapp[0] : body.whatsapp;
            if (wa && wa.send_status) message += ` WhatsApp: ${wa.send_status}.`;
        }
        fetchPgDuties(message);
        openPgDutyDetail(bookingId);
    } catch (err) {
        console.error(err);
        error.textContent = 'Assignment failed.';
    } finally {
        pgDutyAssignBusy = false;
    }
}

async function promptChangePgDutyVehicle(assignmentId, bookingId) {
    const vehiclesRes = await fetch('/api/vehicles?status=active', { credentials: 'same-origin' });
    const vehiclesBody = await vehiclesRes.json();
    const vehicles = vehiclesBody.data || [];
    if (!vehicles.length) {
        setPgDutyStatus('No active vehicles are available.', true);
        return;
    }
    const options = vehicles.map((v) =>
        `<option value="${v.id}">${escapeHtmlDuty(v.registration_number || v.id)} · ${escapeHtmlDuty(v.model || '')}</option>`
    ).join('');
    const html = `
        <form onsubmit="submitChangePgDutyVehicle(event, '${assignmentId}', '${bookingId}')">
            <div class="form-group-custom">
                <label for="pg-duty-change-vehicle">Vehicle*</label>
                <select id="pg-duty-change-vehicle" class="form-control-custom" required>${options}</select>
            </div>
            <p id="pg-duty-change-vehicle-error" style="color:#ef4444; min-height:1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width:100%; justify-content:center;">Save vehicle</button>
        </form>
    `;
    openModal('Change vehicle', html);
}

async function submitChangePgDutyVehicle(event, assignmentId, bookingId) {
    event.preventDefault();
    const error = document.getElementById('pg-duty-change-vehicle-error');
    error.textContent = '';
    try {
        const res = await fetch(`/api/operations/assignments/${assignmentId}/vehicle`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vehicle_id: document.getElementById('pg-duty-change-vehicle').value }),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'Vehicle could not be changed.';
            return;
        }
        closeModal();
        fetchPgDuties('Vehicle updated.');
        openPgDutyDetail(bookingId);
    } catch (err) {
        console.error(err);
        error.textContent = 'Vehicle could not be changed.';
    }
}

function promptRejectPgDuty(assignmentId) {
    const reason = prompt('Rejection reason');
    if (!reason || !reason.trim()) return;
    runPgDutyAction(`/api/operations/assignments/${assignmentId}/reject`, { reason: reason.trim() });
}

async function promptEditPgDuty(bookingId) {
    const tripRes = await fetch(`/api/operations/bookings/${bookingId}/trip`, { credentials: 'same-origin' });
    const tripBody = await tripRes.json();
    if (!tripRes.ok || !tripBody.success) {
        setPgDutyStatus(tripBody.message || 'Booking could not be loaded.', true);
        return;
    }
    const booking = (tripBody.data && tripBody.data.booking) || tripBody.data;
    const html = `
        <form onsubmit="submitEditPgDuty(event, '${bookingId}')">
            <div class="form-grid-2">
                <div class="form-group-custom">
                    <label>Trip date</label>
                    <input type="date" id="pg-duty-edit-date" class="form-control-custom" value="${escapeHtmlDuty(booking.trip_date || '')}">
                </div>
                <div class="form-group-custom">
                    <label>Pickup time</label>
                    <input type="time" id="pg-duty-edit-pickup" class="form-control-custom" value="${escapeHtmlDuty((booking.pickup_time || '').slice(0,5))}">
                </div>
            </div>
            <div class="form-group-custom">
                <label>Passenger</label>
                <input type="text" id="pg-duty-edit-employee" class="form-control-custom" value="${escapeHtmlDuty(booking.employee_name || '')}">
            </div>
            <div class="form-group-custom">
                <label>Remarks</label>
                <textarea id="pg-duty-edit-remarks" class="form-control-custom" rows="2">${escapeHtmlDuty(booking.remarks || '')}</textarea>
            </div>
            <p id="pg-duty-edit-error" style="color:#ef4444; min-height:1.2rem;"></p>
            <button type="submit" class="btn btn-primary" style="width:100%; justify-content:center;">Save changes</button>
        </form>
    `;
    openModal('Edit / reschedule booking', html);
}

async function submitEditPgDuty(event, bookingId) {
    event.preventDefault();
    const error = document.getElementById('pg-duty-edit-error');
    error.textContent = '';
    const payload = {
        trip_date: document.getElementById('pg-duty-edit-date').value || undefined,
        pickup_time: document.getElementById('pg-duty-edit-pickup').value || null,
        employee_name: document.getElementById('pg-duty-edit-employee').value.trim() || null,
        remarks: document.getElementById('pg-duty-edit-remarks').value.trim() || null,
    };
    try {
        const res = await fetch(`/api/operations/bookings/${bookingId}`, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const body = await res.json();
        if (!res.ok || !body.success) {
            error.textContent = body.message || 'Booking could not be updated.';
            return;
        }
        closeModal();
        fetchPgDuties('Booking updated.');
        openPgDutyDetail(bookingId);
    } catch (err) {
        console.error(err);
        error.textContent = 'Booking could not be updated.';
    }
}

// --- PostgreSQL Finance ---
function pgFinanceBranch() {
    return (document.getElementById('pg-finance-branch') || {}).value || '';
}

function pgFinanceMoney(value) {
    const n = Number(value || 0);
    return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

async function fetchPgFinance(message) {
    const status = document.getElementById('pg-finance-status');
    if (status) status.textContent = message || 'Loading finance...';
    const branch = pgFinanceBranch();
    const search = (document.getElementById('pg-finance-search') || {}).value || '';
    const q = new URLSearchParams();
    if (branch) q.set('branch', branch);
    if (search) q.set('search', search);
    try {
        const [dashRes, invRes, payRes, expRes] = await Promise.all([
            fetch(`/api/finance/dashboard${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`, { credentials: 'same-origin' }),
            fetch(`/api/finance/invoices?${q.toString()}`, { credentials: 'same-origin' }),
            fetch(`/api/finance/payouts${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`, { credentials: 'same-origin' }),
            fetch(`/api/finance/expenses${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`, { credentials: 'same-origin' }),
        ]);
        const dash = await dashRes.json();
        const invoices = await invRes.json();
        const payouts = await payRes.json();
        const expenses = await expRes.json();
        if (!dashRes.ok || !dash.success) {
            if (status) status.textContent = dash.message || 'Finance is not available.';
            return;
        }
        renderPgFinanceDashboard(dash.data || {});
        renderPgFinanceInvoices((invoices.success && invoices.data) || []);
        renderPgFinancePayouts((payouts.success && payouts.data) || []);
        renderPgFinanceExpenses((expenses.success && expenses.data) || []);
        const settlementSelect = document.getElementById('pg-finance-settlement-company');
        if (settlementSelect && !(dash.data && (dash.data.by_company || []).length)) {
            try {
                const companiesRes = await fetch('/api/companies', { credentials: 'same-origin' });
                const companiesBody = await companiesRes.json();
                if (companiesRes.ok && companiesBody.success) {
                    populatePgFinanceSettlementCompanies(
                        (companiesBody.data || []).map((row) => ({
                            company_id: row.id,
                            company_name: row.name,
                        }))
                    );
                }
            } catch (err) {
                console.error(err);
            }
        }
        if (status) status.textContent = message || `Loaded ${((invoices.data) || []).length || 0} invoices.`;
    } catch (err) {
        console.error(err);
        if (status) status.textContent = 'Finance could not be loaded.';
    }
}

function renderPgFinanceDashboard(data) {
    const el = document.getElementById('pg-finance-dashboard-body');
    if (!el) return;
    const byBranch = (data.by_branch || []).map((row) =>
        `<li>${escapeHtmlDuty(row.branch_code || row.branch_id)} · invoiced ₹ ${pgFinanceMoney(row.invoiced)} · outstanding ₹ ${pgFinanceMoney(row.outstanding)}</li>`
    ).join('') || '<li>No branch totals.</li>';
    const byCompany = (data.by_company || []).slice(0, 8).map((row) =>
        `<li>${escapeHtmlDuty(row.company_name || row.company_id)} · outstanding ₹ ${pgFinanceMoney(row.outstanding)}</li>`
    ).join('') || '<li>No company totals.</li>';
    el.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(10rem,1fr)); gap:0.75rem;">
            <div><strong>Invoiced</strong><div>₹ ${pgFinanceMoney(data.total_invoiced)}</div></div>
            <div><strong>Collected</strong><div>₹ ${pgFinanceMoney(data.total_collected)}</div></div>
            <div><strong>Outstanding</strong><div>₹ ${pgFinanceMoney(data.outstanding_receivables)}</div></div>
            <div><strong>Overdue invoices</strong><div>${data.overdue_invoice_count || 0}</div></div>
            <div><strong>Pending payouts</strong><div>₹ ${pgFinanceMoney(data.pending_driver_payouts)}</div></div>
            <div><strong>Paid payouts</strong><div>₹ ${pgFinanceMoney(data.paid_driver_payouts)}</div></div>
            <div><strong>Expenses</strong><div>₹ ${pgFinanceMoney(data.expenses)}</div></div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(14rem,1fr)); gap:1rem; margin-top:1rem;">
            <div><strong>By branch</strong><ul style="margin:0.35rem 0 0; padding-left:1.1rem;">${byBranch}</ul></div>
            <div><strong>By company</strong><ul style="margin:0.35rem 0 0; padding-left:1.1rem;">${byCompany}</ul></div>
        </div>`;
    populatePgFinanceSettlementCompanies(data.by_company || []);
}

function populatePgFinanceSettlementCompanies(rows) {
    const select = document.getElementById('pg-finance-settlement-company');
    if (!select) return;
    const current = select.value;
    const options = ['<option value="">Choose company</option>'].concat(
        rows.map((row) => `<option value="${escapeHtmlDuty(row.company_id)}">${escapeHtmlDuty(row.company_name || row.company_id)}</option>`)
    );
    select.innerHTML = options.join('');
    if (current) select.value = current;
}

function renderPgFinanceInvoices(rows) {
    const body = document.getElementById('pg-finance-invoices-body');
    if (!body) return;
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-muted);">No invoices yet.</td></tr>';
        return;
    }
    body.innerHTML = rows.map((row) => `
        <tr>
            <td>${escapeHtmlDuty(row.invoice_number || '')}</td>
            <td>${escapeHtmlDuty(row.company_name || '')}</td>
            <td>${escapeHtmlDuty(row.status || '')}</td>
            <td>₹ ${pgFinanceMoney(row.total_amount)}</td>
            <td>₹ ${pgFinanceMoney(row.paid_amount)}</td>
            <td>₹ ${pgFinanceMoney(row.outstanding_amount)}</td>
            <td style="white-space:nowrap;">
                <button class="btn btn-secondary" type="button" onclick="openPgInvoiceDetail('${row.id}')">Open</button>
                <a class="btn btn-secondary" href="/admin/invoices/?invoice_id=${encodeURIComponent(row.id)}">Print</a>
            </td>
        </tr>`).join('');
}

function renderPgFinancePayouts(rows) {
    const body = document.getElementById('pg-finance-payouts-body');
    if (!body) return;
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No payouts yet.</td></tr>';
        return;
    }
    body.innerHTML = rows.map((row) => {
        let actions = '—';
        if (row.status === 'pending') {
            actions = `
                <button class="btn btn-secondary" type="button" onclick="markPgPayoutPaid('${row.id}')">Mark paid</button>
                <button class="btn btn-secondary" type="button" onclick="cancelPgPayout('${row.id}')">Cancel</button>`;
        }
        return `
        <tr>
            <td>${escapeHtmlDuty(row.driver_name || '')}</td>
            <td>${escapeHtmlDuty(row.source_booking_id || row.booking_id || '')}</td>
            <td>${escapeHtmlDuty(row.status || '')}</td>
            <td>₹ ${pgFinanceMoney(row.amount)}</td>
            <td>${escapeHtmlDuty(row.reference || '')}</td>
            <td style="white-space:nowrap;">${actions}</td>
        </tr>`;
    }).join('');
}

function renderPgFinanceExpenses(rows) {
    const body = document.getElementById('pg-finance-expenses-body');
    if (!body) return;
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No expenses yet.</td></tr>';
        return;
    }
    body.innerHTML = rows.map((row) => {
        const actions = row.status === 'cancelled'
            ? '—'
            : `<button class="btn btn-secondary" type="button" onclick="cancelPgExpense('${row.id}')">Cancel</button>`;
        return `
        <tr>
            <td>${escapeHtmlDuty(row.expense_date || '')}</td>
            <td>${escapeHtmlDuty(row.category || '')}</td>
            <td>${escapeHtmlDuty(row.description || '')}</td>
            <td>₹ ${pgFinanceMoney(row.amount)}</td>
            <td>${escapeHtmlDuty(row.status || '')}</td>
            <td>${actions}</td>
        </tr>`;
    }).join('');
}

async function openPgInvoiceDetail(invoiceId) {
    const detail = document.getElementById('pg-finance-detail');
    if (!detail) return;
    detail.style.display = 'block';
    detail.innerHTML = '<p style="color: var(--text-secondary);">Loading invoice...</p>';
    try {
        const res = await fetch(`/api/finance/invoices/${invoiceId}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            detail.innerHTML = `<p style="color: var(--danger);">${body.message || 'Invoice was not found.'}</p>`;
            return;
        }
        const invoice = body.data.invoice || {};
        const lines = body.data.lines || [];
        const payments = body.data.payments || [];
        detail.innerHTML = `
            <div class="dashboard-table-container">
                <div class="dashboard-table-header" style="display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap;">
                    <h3 style="font-size:1.25rem;">${invoice.invoice_number || 'Invoice'} · ${invoice.status || ''}</h3>
                    <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                        ${invoice.status === 'draft' ? `<button class="btn btn-primary" type="button" onclick="issuePgInvoice('${invoice.id}')">Issue</button>` : ''}
                        ${invoice.status !== 'void' && invoice.status !== 'draft' ? `<button class="btn btn-secondary" type="button" onclick="recordPgPayment('${invoice.id}')">Record payment</button>` : ''}
                        ${invoice.status !== 'void' ? `<button class="btn btn-secondary" type="button" onclick="voidPgInvoice('${invoice.id}')">Void</button>` : ''}
                        <a class="btn btn-secondary" href="/admin/invoices/?invoice_id=${encodeURIComponent(invoice.id)}">Print layout</a>
                    </div>
                </div>
                <div style="padding:1rem;">
                    <p>Company: ${invoice.company_name || ''} · Outstanding ₹ ${pgFinanceMoney(invoice.outstanding_amount)}</p>
                    <h4>Lines</h4>
                    <ul>${lines.map((line) => `<li>${line.description} · ₹ ${pgFinanceMoney(line.amount)}</li>`).join('') || '<li>None</li>'}</ul>
                    <h4>Payments</h4>
                    <ul>${payments.map((p) => {
                        const reverseBtn = p.active
                            ? ` <button class="btn btn-secondary" type="button" onclick="reversePgPayment('${p.id}', '${invoice.id}')">Reverse</button>`
                            : '';
                        return `<li>${escapeHtmlDuty(p.paid_on)} · ₹ ${pgFinanceMoney(p.amount)} · ${escapeHtmlDuty(p.method || '')} ${p.active ? '' : '(reversed)'}${reverseBtn}</li>`;
                    }).join('') || '<li>None</li>'}</ul>
                </div>
            </div>`;
    } catch (err) {
        console.error(err);
        detail.innerHTML = '<p style="color: var(--danger);">Invoice could not be loaded.</p>';
    }
}

async function reversePgPayment(paymentId, invoiceId) {
    if (!window.confirm('Reverse this payment? This uses the finance reverse API.')) return;
    const reason = prompt('Reversal reason') || 'Reversed from supervisor portal';
    const res = await fetch(`/api/finance/payments/${paymentId}/reverse`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Payment could not be reversed.');
        return;
    }
    fetchPgFinance('Payment reversed.');
    openPgInvoiceDetail(invoiceId);
}

async function issuePgInvoice(invoiceId) {
    const res = await fetch(`/api/finance/invoices/${invoiceId}/issue`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Invoice could not be issued.');
        return;
    }
    fetchPgFinance('Invoice issued.');
    openPgInvoiceDetail(invoiceId);
}

async function voidPgInvoice(invoiceId) {
    const reason = prompt('Void reason');
    if (!reason) return;
    const res = await fetch(`/api/finance/invoices/${invoiceId}/void`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Invoice could not be voided.');
        return;
    }
    fetchPgFinance('Invoice voided.');
    openPgInvoiceDetail(invoiceId);
}

async function recordPgPayment(invoiceId) {
    const amount = prompt('Payment amount (INR)');
    if (!amount) return;
    const paidOn = prompt('Paid on (YYYY-MM-DD)', new Date().toISOString().slice(0, 10));
    if (!paidOn) return;
    const method = prompt('Method (cash/neft/rtgs/upi/cheque/card/other)', 'neft') || 'neft';
    const reference = prompt('Reference (optional)') || null;
    const res = await fetch(`/api/finance/invoices/${invoiceId}/payments`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount, paid_on: paidOn, method, reference }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Payment could not be recorded.');
        return;
    }
    fetchPgFinance('Payment recorded.');
    openPgInvoiceDetail(invoiceId);
}

async function showCreatePgInvoiceModal() {
    const companiesRes = await fetch('/api/companies', { credentials: 'same-origin' });
    const companiesBody = await companiesRes.json();
    const companies = (companiesBody.success && companiesBody.data) || [];
    const companyOptions = companies.map((c) => `<option value="${c.id}">${escapeHtmlDuty(c.name)}</option>`).join('');
    const html = `
        <p id="pg-finance-invoice-error" style="color:var(--danger);"></p>
        <label for="pg-fin-inv-branch">Branch</label>
        <select id="pg-fin-inv-branch" class="form-control-custom">
            <option value="BLR">Bengaluru</option>
            <option value="HYD">Hyderabad</option>
        </select>
        <label for="pg-fin-inv-company">Company</label>
        <select id="pg-fin-inv-company" class="form-control-custom">${companyOptions}</select>
        <label for="pg-fin-inv-desc">Line description</label>
        <input id="pg-fin-inv-desc" class="form-control-custom" value="Cab hire charges">
        <label for="pg-fin-inv-amount">Line amount (INR)</label>
        <input id="pg-fin-inv-amount" class="form-control-custom" type="number" min="0" step="0.01">
        <label for="pg-fin-inv-due">Due date</label>
        <input id="pg-fin-inv-due" class="form-control-custom" type="date">
        <div style="display:flex; gap:0.5rem; margin-top:1rem;">
            <button class="btn btn-primary" type="button" onclick="submitPgInvoice()">Save draft</button>
            <button class="btn btn-secondary" type="button" onclick="closeModal()">Cancel</button>
        </div>`;
    openModal('Create invoice', html);
}

async function submitPgInvoice() {
    const error = document.getElementById('pg-finance-invoice-error');
    error.textContent = '';
    const branchCode = document.getElementById('pg-fin-inv-branch').value;
    const branchesRes = await fetch('/api/branches', { credentials: 'same-origin' });
    const branchesBody = await branchesRes.json();
    const branch = ((branchesBody.data) || []).find((b) => b.code === branchCode);
    if (!branch) {
        error.textContent = 'Branch is not available.';
        return;
    }
    const payload = {
        branch_id: branch.id,
        company_id: document.getElementById('pg-fin-inv-company').value,
        due_date: document.getElementById('pg-fin-inv-due').value || null,
        lines: [{
            description: document.getElementById('pg-fin-inv-desc').value.trim(),
            amount: document.getElementById('pg-fin-inv-amount').value,
        }],
    };
    const res = await fetch('/api/finance/invoices', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        error.textContent = body.message || 'Invoice could not be created.';
        return;
    }
    closeModal();
    fetchPgFinance('Invoice draft created.');
    const invoice = (body.data && body.data.invoice) || body.data;
    if (invoice && invoice.id) openPgInvoiceDetail(invoice.id);
}

async function showCreatePgExpenseModal() {
    const html = `
        <p id="pg-finance-expense-error" style="color:var(--danger);"></p>
        <label for="pg-fin-exp-branch">Branch</label>
        <select id="pg-fin-exp-branch" class="form-control-custom">
            <option value="BLR">Bengaluru</option>
            <option value="HYD">Hyderabad</option>
        </select>
        <label for="pg-fin-exp-category">Category</label>
        <input id="pg-fin-exp-category" class="form-control-custom" value="Fuel">
        <label for="pg-fin-exp-desc">Description</label>
        <input id="pg-fin-exp-desc" class="form-control-custom">
        <label for="pg-fin-exp-amount">Amount</label>
        <input id="pg-fin-exp-amount" class="form-control-custom" type="number" min="0" step="0.01">
        <label for="pg-fin-exp-date">Date</label>
        <input id="pg-fin-exp-date" class="form-control-custom" type="date" value="${new Date().toISOString().slice(0,10)}">
        <div style="display:flex; gap:0.5rem; margin-top:1rem;">
            <button class="btn btn-primary" type="button" onclick="submitPgExpense()">Save</button>
            <button class="btn btn-secondary" type="button" onclick="closeModal()">Cancel</button>
        </div>`;
    openModal('Add expense', html);
}

async function submitPgExpense() {
    const error = document.getElementById('pg-finance-expense-error');
    error.textContent = '';
    const branchCode = document.getElementById('pg-fin-exp-branch').value;
    const branchesRes = await fetch('/api/branches', { credentials: 'same-origin' });
    const branchesBody = await branchesRes.json();
    const branch = ((branchesBody.data) || []).find((b) => b.code === branchCode);
    if (!branch) {
        error.textContent = 'Branch is not available.';
        return;
    }
    const payload = {
        branch_id: branch.id,
        category: document.getElementById('pg-fin-exp-category').value.trim(),
        description: document.getElementById('pg-fin-exp-desc').value.trim(),
        amount: document.getElementById('pg-fin-exp-amount').value,
        expense_date: document.getElementById('pg-fin-exp-date').value,
    };
    const res = await fetch('/api/finance/expenses', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        error.textContent = body.message || 'Expense could not be saved.';
        return;
    }
    closeModal();
    fetchPgFinance('Expense recorded.');
}

async function showCreatePgPayoutModal() {
    const [driversRes, bookingsRes] = await Promise.all([
        fetch('/api/drivers?active=true', { credentials: 'same-origin' }),
        fetch('/api/operations/bookings?status=completed', { credentials: 'same-origin' }),
    ]);
    const driversBody = await driversRes.json();
    const bookingsBody = await bookingsRes.json();
    const drivers = (driversBody.success && driversBody.data) || [];
    const bookings = (bookingsBody.success && bookingsBody.data) || [];
    const driverOptions = drivers.map((d) =>
        `<option value="${d.id}">${escapeHtmlDuty(d.display_name)} (${escapeHtmlDuty(d.phone || '')})</option>`
    ).join('');
    const bookingOptions = bookings.slice(0, 100).map((b) =>
        `<option value="${b.id}">${escapeHtmlDuty(b.source_booking_id || b.id)} · ${escapeHtmlDuty(b.trip_date || '')}</option>`
    ).join('');
    const html = `
        <p id="pg-finance-payout-error" style="color:var(--danger);"></p>
        <label for="pg-fin-pay-driver">Driver</label>
        <select id="pg-fin-pay-driver" class="form-control-custom">${driverOptions}</select>
        <label for="pg-fin-pay-booking">Completed booking</label>
        <select id="pg-fin-pay-booking" class="form-control-custom">${bookingOptions}</select>
        <label for="pg-fin-pay-amount">Amount (INR)</label>
        <input id="pg-fin-pay-amount" class="form-control-custom" type="number" min="0" step="0.01">
        <label for="pg-fin-pay-ref">Reference</label>
        <input id="pg-fin-pay-ref" class="form-control-custom">
        <div style="display:flex; gap:0.5rem; margin-top:1rem;">
            <button class="btn btn-primary" type="button" onclick="submitPgPayout()">Save pending payout</button>
            <button class="btn btn-secondary" type="button" onclick="closeModal()">Cancel</button>
        </div>`;
    openModal('Create driver payout', html);
}

async function submitPgPayout() {
    const error = document.getElementById('pg-finance-payout-error');
    error.textContent = '';
    const payload = {
        driver_id: document.getElementById('pg-fin-pay-driver').value,
        booking_id: document.getElementById('pg-fin-pay-booking').value,
        amount: document.getElementById('pg-fin-pay-amount').value,
        reference: document.getElementById('pg-fin-pay-ref').value.trim() || null,
    };
    const res = await fetch('/api/finance/payouts', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        error.textContent = body.message || 'Payout could not be created.';
        return;
    }
    closeModal();
    fetchPgFinance('Payout created.');
}

async function markPgPayoutPaid(payoutId) {
    const reference = prompt('Payment reference (optional)') || null;
    const res = await fetch(`/api/finance/payouts/${payoutId}`, {
        method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'paid', reference }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Payout could not be marked paid.');
        return;
    }
    fetchPgFinance('Payout marked paid.');
}

async function cancelPgPayout(payoutId) {
    if (!window.confirm('Cancel this pending payout?')) return;
    const res = await fetch(`/api/finance/payouts/${payoutId}`, {
        method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'cancelled' }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Payout could not be cancelled.');
        return;
    }
    fetchPgFinance('Payout cancelled.');
}

async function cancelPgExpense(expenseId) {
    if (!window.confirm('Cancel this expense?')) return;
    const res = await fetch(`/api/finance/expenses/${expenseId}`, {
        method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'cancelled' }),
    });
    const body = await res.json();
    if (!res.ok || !body.success) {
        alert(body.message || 'Expense could not be cancelled.');
        return;
    }
    fetchPgFinance('Expense cancelled.');
}

async function loadPgCompanySettlement() {
    const companyId = (document.getElementById('pg-finance-settlement-company') || {}).value || '';
    const bodyEl = document.getElementById('pg-finance-settlement-body');
    if (!bodyEl) return;
    if (!companyId) {
        bodyEl.textContent = 'Choose a company to view settlement and billable bookings.';
        return;
    }
    bodyEl.textContent = 'Loading settlement…';
    try {
        const branch = pgFinanceBranch();
        const q = branch ? `?branch=${encodeURIComponent(branch)}` : '';
        const [settlementRes, billableRes] = await Promise.all([
            fetch(`/api/finance/companies/${companyId}/settlement${q}`, { credentials: 'same-origin' }),
            fetch(`/api/finance/companies/${companyId}/billable-bookings${q}`, { credentials: 'same-origin' }),
        ]);
        const settlementBody = await settlementRes.json();
        const billableBody = await billableRes.json();
        if (!settlementRes.ok || !settlementBody.success) {
            bodyEl.textContent = settlementBody.message || 'Settlement could not be loaded.';
            return;
        }
        const s = settlementBody.data || {};
        const billable = (billableRes.ok && billableBody.success && (billableBody.data || [])) || [];
        bodyEl.innerHTML = `
            <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(10rem,1fr)); gap:0.75rem; margin-bottom:1rem;">
                <div><strong>Completed duty value</strong><div>₹ ${pgFinanceMoney(s.completed_duty_value)}</div></div>
                <div><strong>Invoiced</strong><div>₹ ${pgFinanceMoney(s.invoiced_amount)}</div></div>
                <div><strong>Payments received</strong><div>₹ ${pgFinanceMoney(s.payments_received)}</div></div>
                <div><strong>Outstanding</strong><div>₹ ${pgFinanceMoney(s.outstanding_balance)}</div></div>
                <div><strong>Pending driver payouts</strong><div>₹ ${pgFinanceMoney(s.pending_driver_payouts)}</div></div>
            </div>
            <strong>Billable bookings</strong>
            <ul style="margin:0.35rem 0 0; padding-left:1.1rem;">
                ${billable.length
                    ? billable.slice(0, 25).map((row) =>
                        `<li>${escapeHtmlDuty(row.source_booking_id || row.booking_id || row.id)} · ${escapeHtmlDuty(row.trip_date || '')} · ₹ ${pgFinanceMoney(row.amount || row.customer_amount || 0)}</li>`
                    ).join('')
                    : '<li>No billable bookings.</li>'}
            </ul>`;
    } catch (err) {
        console.error(err);
        bodyEl.textContent = 'Settlement could not be loaded.';
    }
}

// --- Reports + supervisor notifications (Master Prompt 7) ---
function reportQueryParams() {
    const params = new URLSearchParams();
    const from = (document.getElementById('report-from') || {}).value || '';
    const to = (document.getElementById('report-to') || {}).value || '';
    const branch = (document.getElementById('report-branch') || {}).value || '';
    const companyId = (document.getElementById('report-company-id') || {}).value || '';
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (branch) params.set('branch', branch);
    if (companyId.trim()) params.set('company_id', companyId.trim());
    return params;
}

async function fetchStaffNotifications() {
    const list = document.getElementById('staff-notif-list');
    const unread = document.getElementById('staff-notif-unread');
    if (!list) return;
    list.textContent = 'Loading alerts�';
    try {
        const res = await fetch('/api/operations/notifications', { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            list.textContent = body.message || 'Alerts need migration 016 or are unavailable.';
            if (unread) unread.textContent = '�';
            return;
        }
        const rows = (body.data && body.data.notifications) || [];
        const count = (body.data && body.data.unread_count) || 0;
        if (unread) unread.textContent = count + ' unread';
        if (!rows.length) {
            list.textContent = 'No supervisor alerts yet.';
            return;
        }
        list.innerHTML = rows.slice(0, 20).map((n) => `
            <div style="display:flex; justify-content:space-between; gap:0.75rem; padding:0.4rem 0; border-bottom:1px solid #eef2f7;">
                <div>
                    <strong>${escapeHtmlDuty(n.title)}</strong>
                    <div style="color:var(--text-secondary); font-size:0.85rem;">${escapeHtmlDuty(n.body)}</div>
                    <div style="color:var(--text-muted); font-size:0.75rem;">${escapeHtmlDuty(n.created_at || '')} � ${escapeHtmlDuty(n.kind || '')}</div>
                </div>
                ${n.read_at ? '' : `<button type="button" class="btn btn-secondary" onclick="markStaffNotificationRead('${n.id}')">Mark read</button>`}
            </div>`).join('');
    } catch (err) {
        console.error(err);
        list.textContent = 'Alerts could not be loaded.';
    }
}

async function markStaffNotificationRead(id) {
    await fetch(`/api/operations/notifications/${id}/read`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: '{}',
    });
    fetchStaffNotifications();
}

function renderReportSummary(summary) {
    const el = document.getElementById('report-summary');
    if (!el) return;
    if (!summary || typeof summary !== 'object') {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = Object.keys(summary).map((key) => `
        <div class="ops-kpi is-static">
            <span class="ops-kpi-label">${escapeHtmlDuty(key.replace(/_/g, ' '))}</span>
            <strong class="ops-kpi-value">${escapeHtmlDuty(summary[key])}</strong>
        </div>`).join('');
}

function renderReportTable(reportName, data) {
    const head = document.getElementById('report-table-head');
    const body = document.getElementById('report-table-body');
    if (!head || !body) return;
    let rows = data.rows || [];
    let columns = [];
    if (reportName === 'branch-company') {
        rows = []
            .concat((data.by_branch || []).map((r) => ({ section: 'branch', name: r.branch_code, bookings: r.bookings, completed: r.completed, cancelled: r.cancelled })))
            .concat((data.by_company || []).map((r) => ({ section: 'company', name: r.company_name, bookings: r.bookings, completed: r.completed, cancelled: '' })));
    }
    if (reportName === 'financial-summary') {
        rows = Object.keys(data.summary || {}).map((k) => ({ metric: k, value: data.summary[k] }));
    }
    if (!rows.length) {
        head.innerHTML = '<tr><th>Result</th></tr>';
        body.innerHTML = '<tr><td style="text-align:center; color: var(--text-muted);">No rows for these filters.</td></tr>';
        return;
    }
    columns = Object.keys(rows[0]);
    head.innerHTML = '<tr>' + columns.map((c) => `<th>${escapeHtmlDuty(c)}</th>`).join('') + '</tr>';
    body.innerHTML = rows.slice(0, 200).map((row) =>
        '<tr>' + columns.map((c) => `<td>${escapeHtmlDuty(row[c])}</td>`).join('') + '</tr>'
    ).join('');
}

async function runSupervisorReport() {
    const status = document.getElementById('report-status');
    const name = (document.getElementById('report-name') || {}).value || 'bookings';
    if (status) status.textContent = 'Loading report�';
    try {
        const params = reportQueryParams();
        const res = await fetch(`/api/reports/${encodeURIComponent(name)}?${params.toString()}`, { credentials: 'same-origin' });
        const body = await res.json();
        if (!res.ok || !body.success) {
            if (status) status.textContent = body.message || 'Report could not be loaded.';
            return;
        }
        const data = body.data || {};
        renderReportSummary(data.summary || {});
        renderReportTable(name, data);
        if (status) status.textContent = `Loaded ${name} report.`;
    } catch (err) {
        console.error(err);
        if (status) status.textContent = 'Report could not be loaded.';
    }
}

function exportSupervisorReportCsv() {
    const name = (document.getElementById('report-name') || {}).value || 'bookings';
    const params = reportQueryParams();
    params.set('export', 'csv');
    window.location.href = `/api/reports/${encodeURIComponent(name)}?${params.toString()}`;
}
